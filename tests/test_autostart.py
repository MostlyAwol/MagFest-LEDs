"""Exercise the real shell script using local fake wget/logger commands."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SHELL = shutil.which("sh")
if SHELL is None and os.name == "nt":
    candidate = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/usr/bin/sh.exe"
    if candidate.is_file():
        SHELL = str(candidate)


def shell_path(path):
    path = Path(path).resolve().as_posix()
    if os.name == "nt":
        return "/" + path[0].lower() + path[2:]
    return path


@unittest.skipUnless(SHELL, "A POSIX shell is needed for launcher integration tests")
class AutostartTests(unittest.TestCase):
    def run_launcher(self, mode, installed=True):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            commands = root / "bin"
            commands.mkdir()
            program = root / "magfest_led.py"
            original = 'print("installed controller ran", flush=True)\n'
            if installed:
                program.write_text(original)
            scripts = {
                "id": '#!/bin/sh\nprintf "0\\n"\n',
                "logger": '''#!/bin/sh
if test "$2" = magfest-led; then
    cat >> "$MAGFEST_TEST_LOG"
else
    printf '%s\\n' "$*" >> "$MAGFEST_TEST_LOG"
fi
''',
                "wget": '''#!/bin/sh
case "$MAGFEST_TEST_DOWNLOAD" in
    valid) printf '%s\\n' 'print("downloaded controller ran", flush=True)' > "$4" ;;
    invalid) printf '%s\\n' 'def broken(:' > "$4" ;;
    empty) : > "$4" ;;
    failed) exit 1 ;;
esac
''',
            }
            for name, source in scripts.items():
                path = commands / name
                path.write_text(source, newline="\n")
                path.chmod(0o755)
            output = root / "output.log"
            env = dict(os.environ, MAGFEST_PYTHON=Path(sys.executable).as_posix(),
                       MAGFEST_PROGRAM=shell_path(program),
                       MAGFEST_DOWNLOAD_URL="http://unused.invalid/controller.py",
                       MAGFEST_TEST_DOWNLOAD=mode, MAGFEST_TEST_LOG=shell_path(output),
                       MAGFEST_TEST_BIN=shell_path(commands))
            script = Path(__file__).resolve().parents[1] / "Pi/autostart.sh"
            result = subprocess.run(
                [SHELL, "-c", 'PATH="$MAGFEST_TEST_BIN:/usr/bin:/bin"; export PATH; exec /bin/sh "$1"',
                 "launcher-test", shell_path(script)],
                env=env, capture_output=True, text=True, timeout=10)
            logs = output.read_text() if output.exists() else ""
            if installed or mode == "valid":
                self.assertEqual(result.returncode, 0, result.stderr)
                if mode == "valid":
                    self.assertIn("downloaded controller ran", logs)
                    if installed:
                        self.assertEqual(Path(str(program) + ".previous").read_text(), original)
                else:
                    self.assertIn("installed controller ran", logs)
                    self.assertEqual(program.read_text(), original)
            else:
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("No installed controller", logs)
            self.assertEqual(list(root.glob("*.download.*")), [])

    def test_valid_download_preserves_previous_and_runs_update(self):
        self.run_launcher("valid")

    def test_failed_download_runs_installed_copy(self):
        self.run_launcher("failed")

    def test_invalid_python_runs_installed_copy(self):
        self.run_launcher("invalid")

    def test_empty_download_runs_installed_copy(self):
        self.run_launcher("empty")

    def test_missing_copy_and_failed_download_reports_failure(self):
        self.run_launcher("failed", installed=False)


if __name__ == "__main__":
    unittest.main()
