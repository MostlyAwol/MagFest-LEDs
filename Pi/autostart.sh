#!/bin/sh

# Keep the installed copy usable even if the LAN update server is unavailable.
# Set MAGFEST_PYTHON to a virtualenv's Python if that is where the Pi libraries live.
PYTHON=${MAGFEST_PYTHON:-/usr/bin/python3}
FILE=${MAGFEST_PROGRAM:-/home/pi/rpi_ws281x/python/magfest_led.py}
URL=${MAGFEST_DOWNLOAD_URL:-http://wall.lan.magfest.net/magfest_led.py}

report() {
    printf '%s\n' "$*" >&2
    if command -v logger >/dev/null 2>&1; then
        logger -t magfest-autostart -- "$*"
    fi
}

if ! "$PYTHON" -c 'import sys; sys.exit(sys.version_info[0] != 3)'; then
    report "Cannot run Python 3 at $PYTHON; controller not started"
    exit 1
fi

if ! cd "$(dirname "$FILE")"; then
    report "Controller directory is missing: $(dirname "$FILE")"
    exit 1
fi

# Download into the destination directory so the final rename is atomic.
if CANDIDATE=$(mktemp "$FILE.download.XXXXXX"); then
    trap 'rm -f "$CANDIDATE"' 0
    trap 'exit 1' 1 2 15
    if wget --timeout=10 --tries=2 -O "$CANDIDATE" "$URL" &&
       test -s "$CANDIDATE" &&
       "$PYTHON" -c 'import pathlib, sys; compile(pathlib.Path(sys.argv[1]).read_bytes(), sys.argv[1], "exec")' "$CANDIDATE"; then
        if test ! -f "$FILE" || cp -p "$FILE" "$FILE.previous"; then
            if mv -f "$CANDIDATE" "$FILE"; then
                report "Controller update installed from $URL"
            else
                report "Could not install update; using existing controller"
            fi
        else
            report "Could not preserve previous controller; skipping update"
        fi
    else
        report "Download failed or was empty/invalid Python; using existing controller"
    fi
else
    report "Could not create download file; using existing controller"
fi

if test ! -s "$FILE"; then
    report "No installed controller available at $FILE"
    exit 1
fi

run_controller() {
    if test "$(id -u)" -eq 0; then
        exec "$PYTHON" -u "$FILE"
    else
        # A boot task must never wait at an invisible sudo password prompt.
        exec sudo -n "$PYTHON" -u "$FILE"
    fi
}

report "Starting controller: $PYTHON -u $FILE"
if command -v logger >/dev/null 2>&1; then
    run_controller 2>&1 | logger -t magfest-led &
else
    report "logger unavailable; controller output will use the boot task's output"
    run_controller &
fi

exit 0
