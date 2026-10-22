"""Run the active boot launcher with fake downloaders; never access the network."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from test_autostart import SHELL, shell_path


BASH = shutil.which("bash")
if BASH is None and SHELL:
    candidate = Path(SHELL).with_name("bash.exe" if os.name == "nt" else "bash")
    if candidate.is_file():
        BASH = str(candidate)


@unittest.skipUnless(BASH, "Bash is required for active launcher integration tests")
class RunledTests(unittest.TestCase):
    def run_launcher(self, mode, tool="curl", installed=True, program_exit=0):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            root = Path(folder)
            commands = root / "bin"
            commands.mkdir()
            workdir = root / "controller"
            workdir.mkdir()
            program = workdir / "magfest_led.py"
            original = 'import sys\nprint("installed controller ran", sys.argv[1:], flush=True)\nsys.exit(7)\n'
            if installed:
                program.write_text(original)
            # Isolate PATH so each downloader branch and the missing-tool case
            # can run without falling back to an actual network client.
            scripts = {name: f'#!/bin/sh\nexec /usr/bin/{name} "$@"\n'
                       for name in ("mkdir", "chmod", "mktemp", "cp", "mv", "rm")}
            if tool:
                scripts[tool] = '''#!/bin/sh
while test "$#" -gt 0; do
    case "$1" in
        -o|-qO) destination=$2; shift 2 ;;
        *) shift ;;
    esac
done
case "$MAGFEST_TEST_DOWNLOAD" in
    valid) printf '%s\\n' 'import sys' 'print("downloaded controller ran", sys.argv[1:], flush=True)' "sys.exit($MAGFEST_TEST_EXIT)" > "$destination" ;;
    invalid) printf '%s\\n' 'def broken(:' > "$destination" ;;
    empty) : > "$destination" ;;
    failed) printf '%s\\n' '# partial download' > "$destination"; exit 1 ;;
esac
'''
            for name, source in scripts.items():
                path = commands / name
                path.write_text(source, newline="\n")
                path.chmod(0o755)
            env = dict(os.environ, PATH=shell_path(commands),
                       MAGFEST_PYTHON=Path(sys.executable).as_posix(),
                       MAGFEST_WORKDIR=workdir.as_posix(),
                       MAGFEST_DOWNLOAD_URL="https://unused.invalid/controller.py",
                       MAGFEST_TEST_DOWNLOAD=mode, MAGFEST_TEST_EXIT=str(program_exit))
            script = Path(__file__).resolve().parents[1] / "Pi/runled.sh"
            result = subprocess.run([BASH, "--noprofile", "--norc", shell_path(script), "--switch", "192.0.2.10"],
                                    env=env, capture_output=True, text=True, timeout=10)
            if mode == "valid":
                self.assertEqual(result.returncode, program_exit, result.stderr)
                self.assertIn("downloaded controller ran ['--switch', '192.0.2.10']", result.stdout)
                if installed:
                    self.assertEqual(Path(str(program) + ".previous").read_text(), original)
            elif installed:
                self.assertEqual(result.returncode, 7, result.stderr)
                self.assertIn("installed controller ran ['--switch', '192.0.2.10']", result.stdout)
                self.assertEqual(program.read_text(), original)
            else:
                self.assertEqual(result.returncode, 1)
                self.assertIn("No installed controller", result.stderr)
            self.assertEqual(list(workdir.glob("*.download.*")), [])

    def test_curl_update_and_argument_forwarding(self):
        self.run_launcher("valid")

    def test_wget_update(self):
        self.run_launcher("valid", tool="wget")

    def test_failed_download_preserves_installed_program(self):
        self.run_launcher("failed")

    def test_invalid_download_preserves_installed_program(self):
        self.run_launcher("invalid")

    def test_empty_download_preserves_installed_program(self):
        self.run_launcher("empty")

    def test_no_download_tool_still_runs_installed_program(self):
        self.run_launcher("failed", tool=None)

    def test_missing_program_and_failed_download_exits(self):
        self.run_launcher("failed", installed=False)

    def test_initial_install(self):
        self.run_launcher("valid", installed=False)

    def test_controller_failure_reaches_supervisor(self):
        self.run_launcher("valid", program_exit=9)


if __name__ == "__main__":
    unittest.main()
