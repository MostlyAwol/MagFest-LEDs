#!/usr/bin/env python3
"""Run on a stick: sudo python3 tools/pi_diagnostics.py > /tmp/magfest-diagnostics.txt"""
import glob
import importlib.metadata
from pathlib import Path
import platform
import subprocess
import sys


def command(arguments):
    print("\n$ " + " ".join(arguments), flush=True)
    try:
        result = subprocess.run(arguments, capture_output=True, text=True, timeout=10)
        print(result.stdout.rstrip())
        if result.stderr:
            print(result.stderr.rstrip())
        print("exit:", result.returncode)
    except (OSError, subprocess.SubprocessError) as error:
        print(error)


def main():
    print("Platform:", platform.platform())
    print("Python:", sys.version, sys.executable)
    for filename in ("/etc/os-release", "/proc/device-tree/model",
                     "/sys/class/thermal/thermal_zone0/temp", "/run/magfest-led/status.json"):
        try:
            print("\n" + filename + ":\n" + Path(filename).read_text().replace("\0", ""))
        except OSError as error:
            print(filename, error)
    for name in ("Adafruit-Blinka", "adafruit-circuitpython-neopixel", "rpi-ws281x", "easysnmp"):
        try:
            print(name, importlib.metadata.version(name))
        except importlib.metadata.PackageNotFoundError:
            print(name, "not installed in this Python environment")
    # Report startup file paths containing likely controller references. Do not
    # dump arbitrary scripts or environment files that may contain credentials.
    print("\nPossible startup files (inspect these to find the boot script):")
    patterns = ("/etc/rc.local", "/etc/systemd/system/*.service", "/etc/cron.d/*",
                "/etc/crontab", "/var/spool/cron/crontabs/*", "/home/*/.profile")
    for pattern in patterns:
        for filename in sorted(glob.glob(pattern)):
            try:
                text = Path(filename).read_text(errors="replace").lower()
                if any(token in text for token in ("magfest", "git pull", "git clone", ".sh", "@reboot")):
                    print(filename)
            except OSError as error:
                print(filename, error)
    for arguments in (
        ["ip", "-brief", "address"], ["ip", "route"],
        ["vcgencmd", "get_throttled"], ["vcgencmd", "measure_temp"],
        ["df", "-h", "/"], ["df", "-i", "/"],
        ["systemctl", "--failed", "--no-pager"],
        ["systemctl", "status", "magfest-led", "lldpd", "--no-pager"],
        ["journalctl", "-u", "magfest-led", "-b", "-n", "100", "--no-pager"],
        ["lldpctl", "-f", "keyvalue"],
        ["git", "rev-parse", "HEAD"], ["git", "status", "--short"],
    ):
        command(arguments)


if __name__ == "__main__":
    main()
