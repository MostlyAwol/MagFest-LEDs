#!/usr/bin/env bash
set -euo pipefail

MARKER="/var/lib/hostname-from-mac.done"

# Run only once
[ -f "$MARKER" ] && exit 0

# --- helpers ---
choose_iface() {
  # Prefer eth0, then wlan0, then first non-loopback
  for i in eth0 wlan0; do
    [ -e "/sys/class/net/$i/address" ] && { echo "$i"; return 0; }
  done
  for p in /sys/class/net/*; do
    i="$(basename "$p")"
    [ "$i" = "lo" ] && continue
    [ -e "/sys/class/net/$i/address" ] && { echo "$i"; return 0; }
  done
  return 1
}

set_hostname() {
  local new="$1"

  # Try hostnamectl first (DBus/hostnamed path)
  if command -v hostnamectl >/dev/null 2>&1; then
    if hostnamectl set-hostname "$new" 2>/dev/null; then
      echo "$new" > /etc/hostname  # keep file in sync
      logger -t set-hostname-from-mac "hostnamectl set-hostname $new"
      return 0
    fi
  fi

  # Fallback: write /etc/hostname and kernel hostname directly
  echo "$new" > /etc/hostname
  if command -v hostname >/dev/null 2>&1; then
    hostname "$new"
  fi
  logger -t set-hostname-from-mac "fallback set hostname to $new"
  return 0
}
# --- end helpers ---

IFACE="$(choose_iface || true)"
if [ -z "${IFACE:-}" ]; then
  logger -t set-hostname-from-mac "no interface found; skipping"
  install -D -m 0644 /dev/null "$MARKER"
  exit 0
fi

MAC="$(tr '[:upper:]' '[:lower:]' < "/sys/class/net/$IFACE/address")"
if ! [[ "$MAC" =~ ^([0-9a-f]{2}:){5}[0-9a-f]{2}$ ]]; then
  logger -t set-hostname-from-mac "invalid MAC on $IFACE: $MAC"
  install -D -m 0644 /dev/null "$MARKER"
  exit 0
fi

# last three octets + LED- prefix → led-aa-bb-cc
SUFFIX="$(echo "$MAC" | awk -F: '{printf "%s-%s-%s\n", $4, $5, $6}')"
NEW_HOSTNAME="LED-$SUFFIX"
NEW_HOSTNAME="$(echo "$NEW_HOSTNAME" | tr '[:upper:]' '[:lower:]')"

# sanitize for hostname rules
if ! [[ "$NEW_HOSTNAME" =~ ^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$ ]]; then
  NEW_HOSTNAME="$(echo "$NEW_HOSTNAME" | tr -cd 'a-z0-9-' | sed -E 's/^-+//; s/-+$//')"
  [ -z "$NEW_HOSTNAME" ] && NEW_HOSTNAME="rpi"
fi

CURRENT="$(hostnamectl --static 2>/dev/null || hostname -s || cat /etc/hostname || echo "")"
if [ "$CURRENT" != "$NEW_HOSTNAME" ]; then
  set_hostname "$NEW_HOSTNAME"

  # Update 127.0.1.1 line (Debian/Raspbian convention)
  if grep -qE '^127\.0\.1\.1\s' /etc/hosts; then
    sed -i -E "s/^127\.0\.1\.1\s+.*/127.0.1.1\t$NEW_HOSTNAME/" /etc/hosts
  else
    echo -e "127.0.1.1\t$NEW_HOSTNAME" >> /etc/hosts
  fi
  logger -t set-hostname-from-mac "hostname set to $NEW_HOSTNAME"
else
  logger -t set-hostname-from-mac "hostname already $NEW_HOSTNAME; no change"
fi

# Mark as done only after attempting change
install -D -m 0644 /dev/null "$MARKER"
exit 0
