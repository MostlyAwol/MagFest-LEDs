# Controller reliability and troubleshooting

The consolidated installation and operations manual is
[PI_SETUP_GUIDE.md](PI_SETUP_GUIDE.md). Use it for the full fresh-OS setup;
this file retains the reliability change notes and supporting details.

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
lockup, power loss, or failed SD card. The recovered `runled.service` already
restarts fatal process failures. Its revised version also configures a process
watchdog and must be deployed with the notification-capable Python controller.

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

## Boot service and deployment

`Pi/runled.sh` is the active launcher recovered from the working image.
`Pi/autostart.sh` is historical and is not used by the current sticks. Its
old HTTP server and `/home/pi` paths do not describe the current setup.

The active launcher downloads `magfest_led.py` from the `main` branch at
`https://raw.githubusercontent.com/MostlyAwol/MagFest-LEDs/main/magfest_led.py`
and runs `/home/magfest/magfest_led.py` with `python3`. It retrieves a raw file;
it does not clone a Git checkout. Publishing a change to that branch affects
future successful boot downloads. No release/commit is pinned by default.

The original launcher downloaded directly over the installed file and exited
on download failure, so an offline or interrupted update could stop startup.
It now downloads to a temporary file beside the installed program, checks for
nonempty valid Python, backs up the installed copy to `magfest_led.py.previous`,
and renames the candidate into place. An unavailable or invalid update leaves
the installed copy in use. Curl has a five-second connection timeout and a
15-second overall request limit; wget uses a ten-second network timeout and
two attempts. Missing download tools also fall back to the installed copy.
Without an installed copy or valid download, startup exits with an error.

Overrides: `MAGFEST_PYTHON` chooses the interpreter (including a virtualenv),
`MAGFEST_WORKDIR` changes `/home/magfest`, and `MAGFEST_DOWNLOAD_URL` chooses a
different raw-file URL. Arguments are passed through to Python unchanged.
The launcher keeps its foreground `exec` behavior and now uses unbuffered
Python output. It does not add `sudo`, background the program, redirect its
logs, or implement its own restart loop. The parent boot mechanism determines
privileges, log capture, and whether a fatal exit causes a restart.

The recovered `Pi/runled.service` confirms that systemd starts this launcher
as a system service. Its existing configuration already restarted failed
processes after five seconds and captured stdout/stderr in the journal. It
also slept for 60 seconds on every start, including every restart, and had
no watchdog for a running but hung process. No `User=` was specified, so the
system service ran as root.

The revised `Pi/runled.service` explicitly keeps root execution and journal
capture, retains the working image's 60-second pre-start sleep, requests `lldpd`
and the existing hostname service, and creates the runtime status directory.
The LED unit explicitly starts after the hostname service has finished (or
been skipped by its first-boot condition); the hostname unit itself is unchanged.
Its existing `Before=network.target` also expresses that hostname setup should
precede network startup. This ordering does not establish why the delay was
needed; keep the delay until its cause can be investigated on physical hardware.
The new Python retries LLDP/SNMP failures, but that does not prove it covers the
original startup problem.

`Type=notify` waits for the controller's readiness message, with a 120-second
startup deadline covering the 60-second sleep, launcher download, and Python
initialization. Every automatic restart also includes the sleep. Once ready,
a 30-second watchdog checks main-loop progress;
failures restart after five seconds. Automatic start rate limiting is disabled
so repeated failures do not leave a headless stick permanently stopped.
A deliberate `systemctl stop` still stops it. This is a process watchdog,
not a hardware watchdog for a frozen Pi. Configuration semantics are described
in [systemd.service](https://www.freedesktop.org/software/systemd/man/systemd.service.html)
and [systemd.unit](https://www.freedesktop.org/software/systemd/man/systemd.unit.html).

**Deploy this service only with the updated notification-capable Python
controller (`3.2026.10.21` in this checkout).** The old Python program never
sends readiness/watchdog messages and would repeatedly time out under this
unit. Confirm that the launcher's download URL serves the updated controller,
or point it at the tested revision before installing the service. An old cached
copy is not a compatible fallback for the new notification-based unit. These
repository edits have not installed or restarted anything on a Pi.

`Pi/set-hostname-from-mac.service` is the existing working hostname setup and
has been left unchanged. The earlier root-level `magfest-led.service` is a
generic alternative sample; the recovered `Pi/runled.service` is now the
relevant unit. Do not enable both LED services.

On a test stick, inspect the real unit, recent logs, and restart count with:

```sh
sudo systemctl cat runled.service
sudo systemctl status runled.service --no-pager
sudo journalctl -u runled.service -b -n 100 --no-pager
sudo systemctl show runled.service -p MainPID -p NRestarts -p Result
```

Journal retention still depends on the Pi image. Syntax validation in the
launcher does not verify dependencies or hardware compatibility. A valid Python
update that fails at runtime needs manual rollback or a separate release/rollback
mechanism; `.previous` is a backup, not automatic rollback. It represents the
last installed file, not necessarily a hardware-tested version. A restart also
runs the launcher again and retries its update, so a broken revision served
from `main` can cause repeated restarts until the revision or URL is corrected.
Pinning the fleet to a tested commit before the event would avoid that drift.

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
with the switch. Test readiness, watchdog recovery, and restart behavior under the real service
before updating the remaining sticks.
