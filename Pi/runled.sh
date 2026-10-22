#!/bin/bash

set -euo pipefail
PY_URL="${MAGFEST_DOWNLOAD_URL:-https://raw.githubusercontent.com/MostlyAwol/MagFest-LEDs/main/magfest_led.py}"
WORKDIR="${MAGFEST_WORKDIR:-/home/magfest}"
SCRIPT="${WORKDIR}/magfest_led.py"
PYTHON_BIN="${MAGFEST_PYTHON:-python3}"

if ! "$PYTHON_BIN" -c 'import sys; sys.exit(sys.version_info[0] != 3)'; then
  echo "Python 3 is required; check MAGFEST_PYTHON ($PYTHON_BIN)" >&2
  exit 1
fi

mkdir -p "$WORKDIR"
chmod 700 "$WORKDIR"

CANDIDATE=""
cleanup() {
  if [[ -n "$CANDIDATE" ]]; then
    rm -f -- "$CANDIDATE"
  fi
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM

download() {
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL --connect-timeout 5 --max-time 15 "$PY_URL" -o "$CANDIDATE"
  elif command -v wget >/dev/null 2>&1; then
    wget --timeout=10 --tries=2 -qO "$CANDIDATE" "$PY_URL"
  else
    echo "curl or wget unavailable; skipping update" >&2
    return 1
  fi
}

echo "Checking for controller update from $PY_URL..."
# Download beside the installed file: rename then replaces it atomically.
if CANDIDATE=$(mktemp "${SCRIPT}.download.XXXXXX") &&
   download && [[ -s "$CANDIDATE" ]] &&
   "$PYTHON_BIN" -c 'import pathlib, sys; compile(pathlib.Path(sys.argv[1]).read_bytes(), sys.argv[1], "exec")' "$CANDIDATE"; then
  if { [[ ! -f "$SCRIPT" ]] || cp -p -- "$SCRIPT" "${SCRIPT}.previous"; } &&
     chmod 700 "$CANDIDATE" && mv -f -- "$CANDIDATE" "$SCRIPT"; then
    echo "Controller update installed"
  else
    echo "Could not install update; keeping installed controller" >&2
  fi
else
  echo "Update unavailable, empty, or invalid Python; keeping installed controller" >&2
fi

if [[ ! -s "$SCRIPT" ]]; then
  echo "No installed controller available at $SCRIPT" >&2
  exit 1
fi

# A successful exec does not run Bash's EXIT trap.
cleanup
trap - EXIT HUP INT TERM
chmod 700 "$SCRIPT"
echo "Starting controller: $PYTHON_BIN -u $SCRIPT"
exec "$PYTHON_BIN" -u "$SCRIPT" "$@"
