# Controller reliability and troubleshooting

This describes version `3.2026.10.21`. Changes are local source changes; no Pi
has been updated. The LED hardware remains 300 GRB pixels on GPIO 18 at 0.2
brightness. No new Python dependency is required by the controller.

## Problems found in the previous program

| Problem | Likely symptom | Change |
| --- | --- | --- |
| SNMP timeout handler skipped the stop check; unbounded thread joins | Switching modes or exiting hangs indefinitely | Interruptible delays, stop checks on every retry, five-second join limit |
| Only one SNMP exception type handled; worker failures never checked | LEDs freeze while the Python process remains alive | Retry network/value errors; supervise worker exceptions and progress |
| Startup color parsed an empty command argument | Intended discovery/error indicators never appear | Actual amber discovery animation and red SNMP indicator |
| LLDP subprocess had no timeout; retries lost their delay after five failures | Startup hangs or spins without useful LEDs | Three-second subprocess timeout and ten-second retry interval |
| Commands passed through shared strings without validation | Commands lost, stale arguments, numeric arguments fail | Bounded command queue, explicit color/argument validation |
| Invalid ASCII could terminate the receiver | Remote controls silently stop responding | Malformed/oversized packets discarded |
| SIGTERM handler was never registered | Service stops without LED cleanup | Register SIGINT/SIGTERM and clean up in `finally` |
| Beat effects ignored speed and ran without delay | High CPU use and excessive LED writes | Honor validated speed in milliseconds |
| Chase effect indexed beyond pixel 299 late in its cycle | Chase animation crashes after initially working | Clip each chase segment to the strip length |
| Counter deltas treated as bytes per second regardless of elapsed time | Incorrect bandwidth after delays/errors | Use monotonic elapsed time; rebaseline after failed samples |
| Scale changes cleared LEDs without reliably repainting them | Display unexpectedly becomes blank | Force a complete repaint after scale changes/recovery |

## What you see on the stick

- Alternating amber halves: waiting for an IPv4 switch management address via LLDP.
- Last 15 pixels solid red, remaining pixels off: SNMP failure; retrying every second
  after each failed request. An SNMP request has a one-second timeout and no native retries.
- Bandwidth bar, at least two groups of five: successful SNMP monitoring, including idle traffic.
- Other animations or a blank stick: may be an intentional command (`STOP` blanks it).

Discovery and SNMP outages do not disable remote animation commands. Discovery
runs in the main loop and can delay applying a command by up to three seconds;
stopping an in-flight SNMP request normally takes up to its timeout. A worker
that fails or makes no progress for 15 seconds causes a logged, nonzero process
exit. A replacement LED worker is never started while an old worker is stuck.

Python cannot guarantee recovery from a native driver deadlock, segfault, Pi
lockup, power loss, or failed SD card. A process supervisor is required to
restart after a fatal exit. The optional service file provides that later;
your current boot script will not automatically gain restart behavior just by
downloading this Python file.

## Commands and configuration

UDP port `42424` remains the default; command names are now case-insensitive.
Whitespace and trailing newlines are accepted. Commands:

```text
BANDWIDTH
RAINBOW
FF FF0000
FILL 00FF00 60
WIPE 0000FF 60
CHASE FF0000 60
BEAT FF0000 60
RBEAT FF0000 60
RBBEAT 60
STOP
STATUS
```

Colors are six hexadecimal digits. `FILL` accepts an optional amount of 1–60
groups; other numeric arguments are delays of 1–250 milliseconds, default 60.
`FF` accepts a validated delay argument for compatibility but keeps its fixed
half-second timing. Invalid commands leave the current mode running. Pending
commands are limited to 64; excess commands are discarded. Only `STATUS`
replies; other commands retain their fire-and-forget behavior.

`REBOOT` and `SHUTDOWN` require `--allow-power-commands` at launch. They are
disabled by default to prevent accidental shutdowns from network packets.
There is still no command authentication; limit port access to your control network.
The unused TCP branch has been removed.

Existing `sudo python3 magfest_led.py` startup remains supported. Defaults:

| Option/environment variable | Default |
| --- | --- |
| `--switch` / `MAGFEST_SWITCH` | Discover with LLDP |
| `--interface` | `eth0` |
| `--oid` / `MAGFEST_OID` | `1.3.6.1.2.1.2.2.1.10.49` |
| `MAGFEST_SNMP_COMMUNITY` | `public` |
| `--port` | `42424` |
| `--status-file` | `/run/magfest-led/status.json` |

An explicit switch skips LLDP. The first discovered address is retained for the
process lifetime; restart or use an explicit address if the management IP changes.

The display averages up to ten rate samples and automatically selects a scale:
magenta 100 Kbit/s, cyan 1 Mbit/s, blue 10 Mbit/s, green 100 Mbit/s,
yellow 1 Gbit/s, red 10 Gbit/s. These are full-bar rates, not negotiated port
speed percentages. The old full-stick RGB cycling at very low traffic is replaced
by the minimum bandwidth bar so red remains useful as a fault indication.

The existing OID counts incoming octets on interface index 49. Prefer the switch's
64-bit `ifHCInOctets` counter, commonly `1.3.6.1.2.1.31.1.1.1.6.49`, **after
confirming the actual interface index and switch support**. Counter width is read
from the SNMP response. The standard describes why high-capacity counters matter:
[RFC 2863](https://www.rfc-editor.org/rfc/rfc2863.html).

The 32-bit wrap handling is a heuristic: accept a drop near the counter boundary;
otherwise rebaseline. Multiple wraps and resets near that boundary cannot be
distinguished reliably from these samples. Counter discontinuity timestamps are
not currently polled. This is an activity display, not an accounting meter.

## Check sticks from a laptop

The status tool uses only Python's standard library:

```sh
python tools/stick_status.py 192.168.1.50 192.168.1.51
```

Supply all 30 addresses/hostnames to check them concurrently. Each output line
is JSON with target, hostname, running version, uptime, mode/state, switch IP,
OID, last SNMP success time, consecutive SNMP failures, last error, and measured
bits per second. A missing reply is reported as `unreachable`; this alone cannot
distinguish a stopped program from a network, firewall, or hardware failure.
Hostnames are helpful only if they are unique across your cloned images.

Local JSON status is replaced atomically every 30 seconds and on clean exit.
Its timestamp tells you whether the file is stale. `/run` normally resides in
RAM, avoiding repeated SD-card writes for these snapshots. Logs go to stderr
with timestamps and stack traces; SNMP error stack traces are limited to once
per minute, with a health summary every 30 seconds. Your launcher must capture
stderr if you want those logs retained. Avoid an unlimited logfile on the SD card.

## Optional Pi information collection, when an image/stick is available

From this repository on a stick, using the same Python environment as the controller:

```sh
sudo python3 tools/pi_diagnostics.py > /tmp/magfest-diagnostics.txt 2>&1
```

It collects OS/Python/package versions, network addresses, temperature/power
flags, disk usage, LLDP output, service logs if present, and paths of possible
startup files. Every external command has a ten-second timeout; missing tools
are reported. It does not install software or change startup configuration.
It reports the checkout revision, which can differ from an already running
process if your boot script updates files during execution. `STATUS` reports
the version actually loaded by the process.

Useful later: keep a known-good local copy that boots without Git access, give
each stick a unique hostname/physical label, retain bounded logs, and compare
one failed stick against a working one using the same power supply/data wiring.

## Optional supervisor, for later deployment

The existing boot script is now available at `Pi/autostart.sh`. It downloads
from `http://wall.lan.magfest.net/magfest_led.py`, **not Git**. Publishing code
to Git does not change that server's file. The script uses Python 3 explicitly,
limits download retries/timeouts, checks for nonempty valid Python before
replacing the installed copy, preserves the old copy as `magfest_led.py.previous`,
and falls back to the installed copy when an update fails. Syntax validation
does not verify dependencies, hardware compatibility, or download authenticity.
The existing HTTP endpoint assumes a trusted LAN.

Paths default to `/usr/bin/python3` and
`/home/pi/rpi_ws281x/python/magfest_led.py`. Override them with
`MAGFEST_PYTHON` and `MAGFEST_PROGRAM`; `MAGFEST_DOWNLOAD_URL` overrides the
download URL. Confirm the actual Python environment before deploying. The
script's caller needs permission to replace the installed file and a backup.
It starts Python as root, or uses noninteractive `sudo` if called by another
user, so startup cannot hang on a password prompt.

Output is sent to `logger` with tag `magfest-led`; launcher messages use
`magfest-autostart`. On a Pi using journald, inspect it with
`sudo journalctl -b -t magfest-led -t magfest-autostart --no-pager` (the boot
script is not a `magfest-led.service` unit). Retention depends on the image's
logging configuration. If `logger` is unavailable, output stays attached to
the caller. The script still backgrounds the controller and does not restart
it after an exit. It also does not report whether background startup succeeded;
inspect logs or query `STATUS` to confirm. A syntactically valid update that
fails at runtime requires manual rollback or a supervisor/deployment workflow.

`magfest-led.service` is a sample, not installed by these changes. It assumes
the checkout is `/opt/MagFest-LEDs` and dependencies belong to `/usr/bin/python3`;
adjust both paths for the actual image. Disable the old boot launcher before
enabling a service so two processes cannot drive the same GPIO or bind the port.
`/etc/default/magfest-led` may contain `MAGFEST_SWITCH`, `MAGFEST_OID`, and
`MAGFEST_SNMP_COMMUNITY` assignments; protect its permissions if using credentials.

The service restarts on failure after five seconds. Main-loop watchdog messages
allow systemd to kill/restart a stalled process after 30 seconds. This is a
process watchdog, not a hardware watchdog for a frozen OS. See
[systemd.service](https://www.freedesktop.org/software/systemd/man/systemd.service.html).
Service logs can be read with `sudo journalctl -u magfest-led -b --no-pager`;
configure retention when the real image is available.

## Verification and first-stick checks

```sh
python -m unittest discover -s tests -v
python -m py_compile magfest_led.py tools/stick_status.py tools/pi_diagnostics.py
```

Tests use simulated LEDs/SNMP and real local UDP sockets, including a subprocess
running the actual main loop. On Windows, the signal handler is exercised
directly; OS delivery of SIGTERM is checked by the subprocess test on Linux.
GPIO timing, EasySNMP's native library, real LLDP output, systemd watchdogs,
and power/SD-card behavior still need validation on a Pi. No dependency versions
are pinned until the working Pi OS/Python/library combination is known.

Before updating the fleet, try one stick: boot with the switch absent, select
an animation, restore the network/SNMP and return to `BANDWIDTH`, check `STATUS`,
and send SIGTERM to verify cleanup. Compare real traffic and counter selection
with the switch. Test the optional supervisor separately before relying on it.
