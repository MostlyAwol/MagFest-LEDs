# MagFest LED sticks: Raspberry Pi OS setup and operations guide

**Last reviewed: October 21, 2026. Controller: `3.2026.10.21`.**

This is the main guide for building, testing, and operating the 30 headless LED
sticks. It starts with a blank microSD card and consolidates the program,
network, startup, update, and troubleshooting information in this repository.
The commands are instructions to run later; writing this guide has not changed
any Pi or installed any services.

The recovered image works on the existing hardware. The revised Python and
launcher have automated tests, but **the complete fresh Trixie installation and
revised systemd watchdog configuration still need a physical Pi Zero trial**.
Keep the working image as a recovery copy. Build and qualify one spare card
before rebuilding any working stick.

## Contents

1. [System overview and known configuration](#1-system-overview-and-known-configuration)
2. [Prepare hardware and recovery information](#2-prepare-hardware-and-recovery-information)
3. [Install Raspberry Pi OS](#3-install-raspberry-pi-os)
4. [First login and operating system packages](#4-first-login-and-operating-system-packages)
5. [Copy the project onto the Pi](#5-copy-the-project-onto-the-pi)
6. [Install the Python environment](#6-install-the-python-environment)
7. [Configure and check LED hardware access](#7-configure-and-check-led-hardware-access)
8. [Check Ethernet, LLDP, and switch SNMP](#8-check-ethernet-lldp-and-switch-snmp)
9. [Install the controller and existing hostname setup](#9-install-the-controller-and-existing-hostname-setup)
10. [Test Python before enabling automatic startup](#10-test-python-before-enabling-automatic-startup)
11. [Configure and enable the LED service](#11-configure-and-enable-the-led-service)
12. [Optional GitHub updates at service startup](#12-optional-github-updates-at-service-startup)
13. [Everyday control and remote status](#13-everyday-control-and-remote-status)
14. [Logging, power information, and diagnostic collection](#14-logging-power-information-and-diagnostic-collection)
15. [Failure symptoms and investigation](#15-failure-symptoms-and-investigation)
16. [Qualify one stick before updating the fleet](#16-qualify-one-stick-before-updating-the-fleet)
17. [Build and maintain the 30-stick fleet](#17-build-and-maintain-the-30-stick-fleet)
18. [Recovery and rollback](#18-recovery-and-rollback)
19. [Remaining facts to record](#19-remaining-facts-to-record)

## 1. System overview and known configuration

Each stick contains a Pi Zero and 300 addressable RGB LEDs. The Pi connects to a
switch, discovers its management IPv4 address through LLDP, reads an SNMP
traffic counter, and displays a moving bandwidth bar. UDP commands can select
other animations or query status. It measures one configured interface's incoming
traffic; it does not automatically find the uplink, sum the switch ports, or
measure the Pi's own Ethernet traffic.

| Item | Current configuration |
| --- | --- |
| Board | Pi Zero family; record the exact model during installation |
| LED data | BCM GPIO 18, physical header pin 12 |
| LEDs | 300 GRB pixels, treated as 60 groups of five |
| Brightness | `0.2`, fixed in `magfest_led.py` |
| Network discovery | `lldpctl -f keyvalue`, default interface `eth0` |
| Switch counter | Incoming octets on interface index 49 by default |
| Default OID | `1.3.6.1.2.1.2.2.1.10.49` (32-bit `ifInOctets`) |
| SNMP | v2c; community defaults to `public` |
| Control/status | IPv4 UDP port `42424`, bound on all local interfaces |
| Installed controller | `/home/magfest/magfest_led.py` |
| Installed launcher | `/home/magfest/runled.sh` |
| LED systemd unit | `/etc/systemd/system/runled.service` |
| Hostname unit | `/etc/systemd/system/set-hostname-from-mac.service` |
| Hostname script | `/usr/local/sbin/set-hostname-from-mac.sh` |
| Hostname completion marker | `/var/lib/hostname-from-mac.done` |
| Runtime status | `/run/magfest-led/status.json` |

The active source files are `magfest_led.py`, `Pi/runled.sh`,
`Pi/runled.service`, `Pi/set-hostname-from-mac.sh`, and
`Pi/set-hostname-from-mac.service`. The old `Pi/autostart.sh`, root-level
`magfest-led.service`, and `How To Setup From Fresh.txt` are historical or
alternative material, not the installation path in this guide. Do not enable
two LED services against the same hardware.

## 2. Prepare hardware and recovery information

Have a spare microSD card, card reader, Pi power supply, the stick's LED power
supply, Ethernet adapter/cabling, and a computer with SSH/SCP available. Label
the test stick and record its Ethernet MAC and eventual hostname.

Keep the known working image unchanged. If possible, collect these from a
working Pi before migrating:

```bash
cat /etc/os-release
python3 --version
tr -d '\0' < /proc/device-tree/model
uname -a
sudo systemctl cat runled.service
sudo systemctl cat set-hostname-from-mac.service
sudo systemctl show runled.service -p ExecStart -p Environment -p User
ip -brief address
```

The repository establishes the data pin and software brightness, but not the
actual LED model, supply sizing, fuse arrangement, level shifter, or wiring
diagram. Verify the real assembly. The LED supply must be sized for the actual
strip; the Pi's supply rating is not a rating for 300 LEDs. Keep Pi and LED
signal grounds common, use the strip's data-input end, and check whether the
existing circuit shifts the Pi's 3.3 V signal to the LED logic voltage. Do not
feed 5 V into a Pi GPIO. The upstream driver documents the signal-level issue
and pin numbering: [rpi_ws281x hardware notes](https://github.com/rpi-ws281x/rpi-ws281x-python/blob/master/library/README.rst).

## 3. Install Raspberry Pi OS

Raspbian is now named **Raspberry Pi OS**. As checked for this guide, the current
release is Debian 13 Trixie; the download page lists October 6, 2026 images.
For an original Zero or Zero W, choose **Raspberry Pi OS Lite (32-bit)**.
The 32-bit image also provides a common starting point if the fleet includes
Zero 2 W boards. The original Zero cannot run a 64-bit OS. Sources:
[current images](https://www.raspberrypi.com/software/operating-systems/),
[OS editions and architecture](https://www.raspberrypi.com/documentation/computers/os.html).

On the Windows computer:

1. Install/open [Raspberry Pi Imager](https://www.raspberrypi.com/software/).
2. Select the actual Pi model, then the current **Lite, 32-bit** image.
3. Select the spare microSD card. Writing the image erases that selected card.
4. In customisation, create user **`magfest`**, set its password or SSH key,
   enable SSH, and set the timezone/keyboard locale. Use a temporary unique
   hostname such as `led-build-01`; the existing hostname service will later
   replace it with a name derived from the MAC address.
5. Configure Wi-Fi only if that board has Wi-Fi and you need it for setup.
   The controller's intended switch discovery is over wired Ethernet.
6. Write and verify the card, insert it in the Pi, attach Ethernet, then power on.

These are the headless customisation options described in the
[official Imager setup guide](https://www.raspberrypi.com/documentation/computers/getting-started.html).

Find its address in the DHCP server/router or connect to its temporary hostname
if your network resolves it. Use its IP if `.local` name resolution is unavailable:

```text
ssh magfest@THE_PI_IP_ADDRESS
```

This guide uses `magfest` and `/home/magfest` intentionally to match the recovered
launcher/service. Using another account requires adjusting paths consistently.

## 4. First login and operating system packages

Unless marked **Windows PowerShell**, commands below run in the Pi's SSH shell.
First verify the board, OS, and clock:

```bash
cat /etc/os-release
uname -m
dpkg --print-architecture
python3 --version
timedatectl status
ip -brief address
```

Update this fresh installation, then install the tools used by this project:

```bash
sudo apt update
sudo apt full-upgrade -y
sudo apt install -y python3 python3-venv python3-pip python3-dev build-essential \
  git curl wget ca-certificates file lldpd snmp libsnmp-dev python3-easysnmp \
  libgpiod-dev python3-libgpiod avahi-daemon
sudo systemctl enable --now lldpd
sudo systemctl enable --now ssh
sudo reboot
```

The GPIO support packages follow the
[Blinka Linux setup prerequisites](https://learn.adafruit.com/circuitpython-on-raspberrypi-linux?view=all).
GPIO 18 NeoPixel output does not require enabling SPI or I2C for this application.

Reconnect after reboot. `avahi-daemon` is for convenient local hostname
discovery; DHCP/DNS or IP addresses can be used instead. It is not required by
the bandwidth calculation. Numeric SNMP OIDs in this guide do not require a
downloaded vendor MIB database.

**Dependency checkpoint:** if `python3-easysnmp` has no installation candidate,
record `apt-cache policy python3-easysnmp`, the OS release, and architecture
before proceeding. Debian Trixie publishes a Python 3.13 EasySNMP package, but
the Pi's configured repositories must supply an appropriate build. Do not add
ordinary Debian ARM repositories to an original Pi Zero just to force a package.
See the [Debian package details](https://packages.debian.org/trixie/python3-easysnmp).

The upstream EasySNMP repository is archived and has reported modern Python
installation issues. For this fresh build, prefer the OS package over blindly
running `pip install easysnmp` from PyPI. If this dependency cannot import on
Trixie, the new build has not passed commissioning. Preserve the working image
and evaluate a separate Raspberry Pi OS Legacy Lite 32-bit / Bookworm card;
do not mix Bookworm packages into Trixie or downgrade the working fleet in place.
Sources: [upstream status/issues](https://github.com/easysnmp/easysnmp/issues),
[available OS images](https://www.raspberrypi.com/software/operating-systems/).

## 5. Copy the project onto the Pi

Use the revised files from the checkout being tested. Some recovered service
files may not yet be committed/published, so copying that checkout avoids
assuming GitHub already contains them.

**Windows PowerShell, from `D:\projects\MagFest-LEDs`:** replace the example
address with the real test Pi's address.

```powershell
$StickAddress = '192.0.2.50'
$StickLogin = "magfest@$StickAddress"
ssh $StickLogin 'mkdir -p /home/magfest/MagFest-LEDs/Pi /home/magfest/MagFest-LEDs/tools /home/magfest/MagFest-LEDs/tests'
scp magfest_led.py PI_SETUP_GUIDE.md "$($StickLogin):/home/magfest/MagFest-LEDs/"
scp Pi/runled.sh Pi/runled.service Pi/set-hostname-from-mac.sh Pi/set-hostname-from-mac.service "$($StickLogin):/home/magfest/MagFest-LEDs/Pi/"
scp tools/stick_status.py tools/pi_diagnostics.py "$($StickLogin):/home/magfest/MagFest-LEDs/tools/"
scp tests/test_controller.py tests/test_autostart.py tests/test_runled.py "$($StickLogin):/home/magfest/MagFest-LEDs/tests/"
scp Pi/autostart.sh "$($StickLogin):/home/magfest/MagFest-LEDs/Pi/"
```

The final copy is only to let the retained historical-launcher tests run; it
does not enable that launcher. Alternatively, clone the repository once the
intended release has been published and select its tested commit. The remaining
steps assume the staging directory is `/home/magfest/MagFest-LEDs`.

Do not let Windows CRLF line endings turn into a `/bin/bash^M` boot failure.
The repository specifies LF for shell files; verify the staged files on the Pi:

```bash
cd /home/magfest/MagFest-LEDs
file Pi/*.sh
bash -n Pi/runled.sh
bash -n Pi/set-hostname-from-mac.sh
python3 -m py_compile magfest_led.py tools/stick_status.py tools/pi_diagnostics.py
```

If `file` reports CRLF, convert the staged shell files to LF before installing
them. Do not edit the working image's original files as a substitute for making
an independently tested installation.

## 6. Install the Python environment

Use a virtual environment and keep the system interpreter managed by `apt`.
`--system-site-packages` makes the OS-provided EasySNMP extension visible inside
the environment. It does not mean packages should be installed with global
`sudo pip`. This follows Adafruit's venv approach, with an absolute interpreter
path so root and systemd use the same environment:
[Adafruit Python installation](https://learn.adafruit.com/neopixels-on-raspberry-pi/python-usage).

```bash
python3 -m venv --system-site-packages /home/magfest/venv
/home/magfest/venv/bin/python -m pip install --upgrade pip setuptools wheel
/home/magfest/venv/bin/python -m pip install adafruit-blinka adafruit-circuitpython-neopixel rpi_ws281x
/home/magfest/venv/bin/python -m pip check
sudo /home/magfest/venv/bin/python -c 'import sys, board, neopixel, rpi_ws281x, easysnmp; print(sys.executable); print("GPIO:", board.D18); print("EasySNMP:", easysnmp.__file__)'
```

The last command must succeed **as root with that exact interpreter**. A package
importing in an interactive shell is not enough if the service uses another
Python. Installing native dependencies on a Zero can take time; an import test
does not yet prove the driver can initialise the LEDs.

After a successful build, save the actual resolved environment:

```bash
mkdir -p /home/magfest/build-record
/home/magfest/venv/bin/python -m pip freeze > /home/magfest/build-record/pip-freeze.txt
dpkg-query -W > /home/magfest/build-record/os-packages.txt
cat /etc/os-release > /home/magfest/build-record/os-release.txt
uname -a > /home/magfest/build-record/kernel.txt
```

This is a record of the environment, not yet proof that it is fleet-ready.
Keep the installed package versions consistent after qualification.

## 7. Configure and check LED hardware access

The current program uses GPIO 18's PWM-backed NeoPixel output and runs as root.
The upstream driver documents a conflict between PWM LED output and onboard
Broadcom audio. For this dedicated LED build, disable onboard audio before the
first hardware test:

```bash
sudo cp -a /boot/firmware/config.txt /boot/firmware/config.txt.before-magfest
sudo nano /boot/firmware/config.txt
```

Find an active `dtparam=audio=on` line and change it to `dtparam=audio=off`.
Avoid leaving conflicting active audio settings later in the file. Also prevent
the conflicting audio module from being loaded:

```bash
printf '%s\n' 'blacklist snd_bcm2835' | sudo tee /etc/modprobe.d/magfest-led-audio.conf
sudo reboot
```

The current OS stores this config under `/boot/firmware/`; older instructions
using `/boot/config.txt` are not the path assumed here. Sources:
[Pi boot configuration](https://www.raspberrypi.com/documentation/computers/config_txt.html),
[driver PWM limitations](https://github.com/rpi-ws281x/rpi-ws281x-python/blob/master/library/README.rst).

After reboot:

```bash
lsmod | grep snd_bcm2835
vcgencmd get_throttled
vcgencmd measure_temp
```

No `snd_bcm2835` match is expected. If it still loads, inspect the active boot
configuration and module-loading files rather than repeatedly reinstalling
Python packages. Do not change DMA channels or GPIO pins during baseline setup.

With no controller service running, use this low-brightness, one-pixel test:

```bash
sudo /home/magfest/venv/bin/python - <<'PY'
import time
import board
import neopixel

pixels = neopixel.NeoPixel(board.D18, 300, brightness=0.02,
                          auto_write=False, pixel_order=neopixel.GRB)
try:
    pixels.fill((0, 0, 0))
    pixels[0] = (0, 255, 0)
    pixels.show()
    time.sleep(3)
finally:
    pixels.fill((0, 0, 0))
    pixels.show()
    pixels.deinit()
PY
```

The first pixel should show green briefly, then clear. If this fails, diagnose
GPIO initialisation, audio conflicts, power, grounding, data direction, and
signal levels before investigating SNMP. Do not run this test while another
process is driving the same strip.

## 8. Check Ethernet, LLDP, and switch SNMP

### Ethernet and discovery

```bash
ip -brief link
ip -brief address
ip route
sudo systemctl status lldpd --no-pager
sudo lldpctl -f keyvalue
```

The default program expects an IPv4 neighbor management address under:

```text
lldp.eth0.chassis.mgmt-ip=192.168.1.10
```

Your address will differ. LLDP must be transmitted by the connected switch port
and include a management IPv4 address. The switch can advertise an address that
is not reachable from the Pi's VLAN; LLDP discovery alone does not prove SNMP
connectivity. For LLDP behavior and diagnostics see the
[lldpd project documentation](https://github.com/lldpd/lldpd/blob/master/README.md).

If the USB Ethernet adapter is named something other than `eth0`, use the
program's `--interface ACTUAL_INTERFACE` argument. If the switch does not
advertise a suitable address, use `--switch ACTUAL_SWITCH_IP` or the
`MAGFEST_SWITCH` environment variable. This skips discovery; it does not bypass
SNMP routing, access controls, or credentials. Do not disable predictable network
names globally just to make this one application work.

### Switch and counter selection

The switch needs SNMP v2c read access from the Pi. Confirm its management address,
community, access-control rules, and which interface should drive the stick.
Do not assume physical port 49 is SNMP interface index 49.

Use your actual values in this Pi-shell example:

```bash
SWITCH_IP='192.168.1.10'
COMMUNITY='public'
snmpget -v2c -c "$COMMUNITY" -t 2 -r 0 "$SWITCH_IP" .1.3.6.1.2.1.1.3.0
snmpwalk -v2c -c "$COMMUNITY" -t 2 -r 0 -On "$SWITCH_IP" .1.3.6.1.2.1.31.1.1.1.1
snmpwalk -v2c -c "$COMMUNITY" -t 2 -r 0 -On "$SWITCH_IP" .1.3.6.1.2.1.2.2.1.2
snmpget -v2c -c "$COMMUNITY" -t 2 -r 0 "$SWITCH_IP" .1.3.6.1.2.1.31.1.1.1.6.49
```

The walks report interface names/descriptions with their indexes. Replace the
final `.49` after identifying the real interface. The last query should return
a `Counter64` if that interface supports `ifHCInOctets`. Query it again while
traffic is flowing; its value should increase. Source:
[Net-SNMP query manual](https://www.net-snmp.org/docs/man/snmpget.html).

Prefer `ifHCInOctets` (`1.3.6.1.2.1.31.1.1.1.6.INDEX`) over the current default
32-bit `ifInOctets` (`1.3.6.1.2.1.2.2.1.10.INDEX`) when supported. The controller
detects the counter width from the response. The 32-bit wrap calculation is
heuristic: multiple wraps and counter resets cannot always be distinguished.
This program is an activity display, not an accounting meter. The high-capacity
counters are described in [RFC 2863](https://www.rfc-editor.org/rfc/rfc2863.html).

SNMP v2c and the UDP control protocol should stay on the intended LAN/control
network. Permit Pi-to-switch SNMP UDP 161, intended-controller-to-Pi UDP 42424,
and your SSH administration path. Internet/DNS/time access is needed during
installation and for optional remote updates, not for cached LAN monitoring.
Do not apply an untested firewall ruleset remotely and lose SSH access.

## 9. Install the controller and existing hostname setup

On a **fresh test Pi**, install the staged files:

```bash
cd /home/magfest/MagFest-LEDs
sudo install -m 0700 magfest_led.py /home/magfest/magfest_led.py
sudo install -m 0700 Pi/runled.sh /home/magfest/runled.sh
sudo install -m 0755 Pi/set-hostname-from-mac.sh /usr/local/sbin/set-hostname-from-mac.sh
sudo install -m 0644 Pi/set-hostname-from-mac.service /etc/systemd/system/set-hostname-from-mac.service
sudo install -m 0644 Pi/runled.service /etc/systemd/system/runled.service
sudo systemctl daemon-reload
sudo systemctl enable set-hostname-from-mac.service
```

These steps install the existing hostname files unchanged. On a working image
where they are already installed and working, leave them alone rather than
re-running installation or resetting the marker.

### Exactly what MAC-based naming does

The recovered script chooses `eth0`, otherwise `wlan0`, otherwise the first
available non-loopback interface. MAC `aa:bb:cc:12:34:56` becomes hostname
`led-12-34-56`. It tries `hostnamectl`, has a file/kernel-hostname fallback, and
updates the `127.0.1.1` entry in `/etc/hosts` when it changes the name.

The unit runs before `network.target` and skips execution when
`/var/lib/hostname-from-mac.done` exists. The script checks the same marker and
writes it after handling the name. **It also writes the marker when it finds no
interface or an invalid MAC.** Therefore a marker alone is not proof of a
successful rename; verify hostname and logs. An Ethernet adapter that is not yet
enumerated may cause naming from Wi-Fi instead. Replacing the selected adapter
later does not rename a stick whose marker already exists.

For a fresh Pi that has not run this service yet, reboot with its intended
Ethernet hardware attached:

```bash
sudo reboot
```

Reconnect using its DHCP address or new name, then inspect:

```bash
hostnamectl --static
cat /etc/hostname
cat /etc/hosts
ip -brief link
sudo journalctl -u set-hostname-from-mac.service -b --no-pager
ls -l /var/lib/hostname-from-mac.done
```

Do not remove the marker on working sticks just to repeat these checks.
Names derived from only three MAC octets are not guaranteed collision-free;
confirm all 30 actual hostnames are distinct.

## 10. Test Python before enabling automatic startup

From the staged checkout, run the automated tests without starting the service:

```bash
cd /home/magfest/MagFest-LEDs
/home/magfest/venv/bin/python -m unittest discover -s tests -v
```

The Python/launcher tests use simulated GPIO/SNMP and local sockets. Passing
them does not replace the one-pixel hardware test or real switch queries.

Make sure `runled.service` and any historical LED launcher are not already
running. Then run the installed controller in the foreground:

```bash
sudo /home/magfest/venv/bin/python -u /home/magfest/magfest_led.py
```

If discovery needs an override, use this form instead, with your real address,
interface name, and OID:

```bash
sudo /home/magfest/venv/bin/python -u /home/magfest/magfest_led.py \
  --interface eth0 --switch 192.168.1.10 --oid 1.3.6.1.2.1.31.1.1.1.6.49
```

For a different SNMP community, set `MAGFEST_SNMP_COMMUNITY` through `sudo env`
or the service configuration below; exporting it in your ordinary shell alone
does not guarantee `sudo` preserves it. Check the startup version in the log
and query `STATUS` from a second terminal/computer. Stop with Ctrl+C; LEDs
should clear and the process should exit.

## 11. Configure and enable the LED service

### Use the known local controller during commissioning

The recovered launcher downloads from GitHub at **every service start**, not
only boot. Until the revised files are published and a release is selected,
do not let that download overwrite the copied controller with a different
version. This guide initially uses a systemd drop-in to run the local validated
Python copy directly. `runled.sh` remains installed for optional updates later.

```bash
sudo install -d -m 0755 /etc/systemd/system/runled.service.d
sudo tee /etc/systemd/system/runled.service.d/10-site.conf >/dev/null <<'EOF'
[Service]
Environment="MAGFEST_PYTHON=/home/magfest/venv/bin/python"
ExecStart=
ExecStart=/home/magfest/venv/bin/python -u /home/magfest/magfest_led.py
EOF
```

Default discovery/community/OID remain in effect. If needed, edit that same
drop-in and add these lines under `[Service]`, replacing the example values:

```ini
Environment="MAGFEST_SWITCH=192.168.1.10"
Environment="MAGFEST_OID=1.3.6.1.2.1.31.1.1.1.6.49"
Environment="MAGFEST_SNMP_COMMUNITY=public"
```

Omit `MAGFEST_SWITCH` to use LLDP. Protect a file containing a private community
with `sudo chmod 0600 /etc/systemd/system/runled.service.d/10-site.conf`.
If the interface name differs, append `--interface ACTUAL_INTERFACE` to the
drop-in's `ExecStart` command. The controller has no interface environment
variable. Never assume a configuration example knows the actual switch port.

### Service behavior

| Setting in `Pi/runled.service` | Meaning for this application |
| --- | --- |
| `User=root` | Required baseline for the current GPIO/PWM backend |
| `After=` and `Wants=` | Request network-online, LLDP, and the existing hostname service; order the LED start after them |
| `ExecStartPre=/bin/sleep 60` | Preserve the known working delay on every start/restart |
| `Type=notify` | Wait for the updated controller's readiness notification |
| `TimeoutStartSec=120` | Total startup budget, including the 60-second sleep |
| `WatchdogSec=30` | Detect missing main-loop heartbeats after readiness |
| `Restart=on-failure`, `RestartSec=5` | Retry after a fatal exit/watchdog failure; the next start also sleeps 60 seconds |
| `StartLimitIntervalSec=0` | Do not permanently stop retrying after repeated failures |
| `TimeoutStopSec=15` | Bound service shutdown before systemd forces termination |
| `RuntimeDirectory=magfest-led` | Create `/run/magfest-led` for status snapshots |
| Journal output, `LimitCORE=0` | Capture logs and avoid controller core dumps |

`Wants=` does not make a missing/failed LLDP or hostname unit a hard requirement
for the LED program. Inspect their status as well. `network-online.target` does
not guarantee the Internet, GitHub, or switch management is reachable. Keep the
60-second delay until its original cause is established on real hardware.
The revised Python retries LLDP/SNMP failures, but that does not prove those
were the original reason for the delay. See the official
[service notification/watchdog documentation](https://www.freedesktop.org/software/systemd/man/systemd.service.html).

**Do not install this notify/watchdog unit with the old Python controller.**
The old program does not send the required notifications and would repeatedly
time out. Readiness means the controller loop has started, not that SNMP works.
Amber or red fault states can coexist with an active, responsive service.

Validate and start:

```bash
sudo systemctl daemon-reload
sudo systemctl cat runled.service
sudo systemd-analyze verify /etc/systemd/system/runled.service
sudo systemctl enable --now runled.service
sudo systemctl status runled.service --no-pager
sudo journalctl -u runled.service -b -n 100 --no-pager
```

The start command can legitimately wait more than a minute. If verification
reports missing executables/units or unknown settings, resolve those messages
before commissioning. From then on, reboot should start the LEDs automatically.

## 12. Optional GitHub updates at service startup

For event operation, a qualified local copy is often the easiest version to
reproduce. The local-controller mode above runs without Internet. Keep it if
you do not need boot-time updates.

To retain the recovered GitHub-update workflow, choose a **published, tested
Git commit** containing the notification-capable controller. Publish the
intended release first; a local Git commit alone is not downloadable. On the Pi,
enter that full commit SHA and check the exact downloadable file:

```bash
read -r -p 'Full 40-character published release commit SHA: ' MAGFEST_RELEASE
if [[ ! "$MAGFEST_RELEASE" =~ ^[0-9a-fA-F]{40}$ ]]; then
  echo 'Invalid commit SHA; stop here and supply the actual release commit.'
else
  RELEASE_URL="https://raw.githubusercontent.com/MostlyAwol/MagFest-LEDs/${MAGFEST_RELEASE}/magfest_led.py"
  curl -fSL --connect-timeout 5 --max-time 30 "$RELEASE_URL" -o /home/magfest/release-candidate.py
fi
```

If download fails or the SHA was invalid, stop this update procedure. Inspect
the downloaded candidate's version/source and perform the same foreground
hardware test before selecting it. Never enable a notify service for a candidate
that lacks readiness/watchdog support. The following replaces the earlier
`10-site.conf`; carry over your actual switch/community settings and interface
argument if you used them.

```bash
sudo systemctl stop runled.service
sudo cp -a /etc/systemd/system/runled.service.d/10-site.conf /root/runled-site.before-updates.conf
sudo tee /etc/systemd/system/runled.service.d/10-site.conf >/dev/null <<EOF
[Service]
Environment="MAGFEST_PYTHON=/home/magfest/venv/bin/python"
Environment="MAGFEST_DOWNLOAD_URL=$RELEASE_URL"
ExecStart=
ExecStart=/home/magfest/runled.sh
EOF
sudo systemctl daemon-reload
sudo systemctl start runled.service
sudo journalctl -u runled.service -b -n 100 --no-pager
```

Use this block only in the shell where the verified `RELEASE_URL` was set.
Check `systemctl cat runled.service` and `STATUS` afterward. With a non-`eth0`
adapter, append `--interface ACTUAL_INTERFACE` to this launcher's `ExecStart`;
`runled.sh` forwards arguments to Python.

The launcher now downloads beside the installed file, rejects an empty or
syntactically invalid candidate, preserves the last installed file as
`magfest_led.py.previous`, and atomically replaces the controller. Download or
tool failures leave the installed copy available. Curl has a 15-second total
request limit; wget has a ten-second network timeout and two attempts. The
service startup deadline is a further backstop. Logs remain with systemd because
the launcher finishes with foreground `exec` and unbuffered Python.

Syntax validation does not test GPIO, imports, or runtime behavior. `.previous`
is not automatic rollback or proof of a hardware-tested release. An older cached
controller without notifications is not a compatible fallback for this unit.
By default the script's URL points to `main`; without pinning, a service restart
can install different code on different sticks. It updates only the Python
file, not OS packages, Python packages, service files, or the launcher itself.

## 13. Everyday control and remote status

### LED meanings

| Display | Meaning |
| --- | --- |
| Alternating amber halves | Waiting for LLDP switch management IPv4 discovery |
| Top 15 pixels red, remaining pixels off | SNMP failure; retrying |
| Bandwidth bar, minimum two groups | SNMP monitoring active, including idle traffic |
| Rainbow, solid fill, or another animation | That mode was selected remotely |
| Blank | Could be intentional `STOP`, startup delay, stopped process, or a hardware fault; query status/logs |

The bar averages up to ten rate samples using actual elapsed time. Its automatic
full-bar scales are magenta 100 Kbit/s, cyan 1 Mbit/s, blue 10 Mbit/s, green
100 Mbit/s, yellow 1 Gbit/s, and red 10 Gbit/s. It is not a fixed percentage of
the negotiated link speed. The first sample/recovery sample establishes a
baseline. The discovered switch address is retained until process restart.

### Commands

Send one ASCII UDP datagram to the **Pi's** address on port 42424. Names are
case-insensitive; whitespace/newlines are accepted. Colors are six hex digits.

| Command | Effect |
| --- | --- |
| `BANDWIDTH` | Resume SNMP monitoring |
| `RAINBOW` | Continuous rainbow |
| `FF FF0000` | Alternate halves in red, fixed half-second timing |
| `FILL 00FF00 60` | Fill 60 groups green; amount may be 1–60 |
| `WIPE 0000FF 60` | Blue wipe, 60 ms step delay |
| `CHASE FF0000 60` | Red chase, 60 ms delay |
| `BEAT FF0000 60` | Upward fill/downward clear |
| `RBEAT FF0000 60` | Reverse beat |
| `RBBEAT 60` | Beat through a palette |
| `STOP` | Clear the stick |
| `STATUS` | Reply with JSON health information |

Speed arguments accept 1–250 ms and default to 60. `FF` accepts the validated
numeric argument but keeps fixed timing. Invalid commands leave the active mode
alone. Up to 64 commands may queue; excess commands are discarded. Commands
other than `STATUS` have no acknowledgment. Power commands `REBOOT`/`SHUTDOWN`
are disabled unless the controller is launched with `--allow-power-commands`.
The UDP protocol has no authentication.

From any computer with Python, for example:

```python
import socket

with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
    sock.sendto(b"RAINBOW", ("192.168.1.50", 42424))
```

To check one or all 30 sticks from the workstation:

```text
python tools/stick_status.py 192.168.1.50 192.168.1.51
```

Supply your actual addresses/hostnames. JSON output includes target, running
version, hostname, uptime, state/mode, switch/OID, bandwidth, last successful
SNMP timestamp, consecutive failures, last error, and invalid/dropped-command
counts. `unreachable` means no usable reply; it cannot distinguish a firewall
from a dead Pi. This tool works with the revised controller, not the old one.

### Local service commands

```bash
sudo systemctl status runled.service --no-pager
sudo systemctl show runled.service -p MainPID -p NRestarts -p Result
sudo journalctl -u runled.service -b -n 100 --no-pager
sudo journalctl -u runled.service -f
cat /run/magfest-led/status.json
sudo systemctl restart runled.service
```

The JSON file is atomically updated every 30 seconds and on clean exit. Check
its timestamp; a file by itself is not proof that the controller is still alive.
`/run` is volatile across reboots. The service restart again includes the
60-second pre-start delay.

## 14. Logging, power information, and diagnostic collection

Keep enough logs to investigate a reboot without allowing unlimited disk use.
This proposed journal policy limits persistent logs to roughly 64 MB and seven
days, with a 16 MB runtime cap. Apply it first to the test image; it is a policy
choice, not a claim about the recovered image's existing retention settings.

```bash
sudo install -d -m 0755 /etc/systemd/journald.conf.d
sudo tee /etc/systemd/journald.conf.d/60-magfest.conf >/dev/null <<'EOF'
[Journal]
Storage=persistent
SystemMaxUse=64M
RuntimeMaxUse=16M
MaxRetentionSec=7day
EOF
sudo systemctl restart systemd-journald
sudo journalctl --flush
journalctl --disk-usage
```

Journald storage limits are not an exact zero-overshoot disk quota; keep free
space and monitor it. Persistent logs write to the SD card. For a volatile-only
policy, use `Storage=volatile`, accepting that logs disappear at reboot. Source:
[journald configuration](https://www.freedesktop.org/software/systemd/man/latest/journald.conf.html).

Collect a report using the service's Python environment:

```bash
cd /home/magfest/MagFest-LEDs
sudo /home/magfest/venv/bin/python tools/pi_diagnostics.py > /tmp/magfest-diagnostics.txt 2>&1
```

The report includes OS/Python/package versions, network addresses, LLDP, status,
disk usage, temperature/power flags, and recent `runled` service logs. Each
external diagnostic command has a timeout. A copied checkout without `.git`
will report Git errors for its revision queries; the rest of the report remains
useful. Also capture hostname service logs separately when investigating naming.

```bash
vcgencmd get_throttled
vcgencmd measure_temp
df -h /
df -i /
sudo journalctl -k -b --no-pager
sudo journalctl -u runled.service -b -1 -n 100 --no-pager
```

`get_throttled` can include historical as well as current conditions; save the
exact value. Bit 0 indicates current undervoltage; bit 16 indicates undervoltage
has occurred. Bits 2 and 18 indicate current and historical throttling. See
[the official status-bit documentation](https://www.raspberrypi.com/documentation/computers/os.html#vcgencmd).
A previous-boot journal exists only if logs were retained. Compare
a failed stick against a working one using the same supply/cable/adapter to
separate hardware from software differences. The program cannot measure actual
light output: successful `show()` calls do not prove the strip received data.

## 15. Failure symptoms and investigation

| Symptom | Check first | Next action |
| --- | --- | --- |
| No DHCP/SSH/Pi activity | Card, board power, Ethernet adapter, DHCP lease | Try the known working image on that same hardware |
| Service starting for about a minute | `systemctl status runled` | Expected sleep; inspect logs if it exceeds the startup budget |
| Service repeatedly fails | `journalctl -u runled -b` | Match interpreter/import errors, permissions, GPIO errors, or notification timeout to the actual installed version |
| Readiness timeout | Python version/source and effective `ExecStart` | Old Python may run but never send `READY=1`; use matching controller and unit |
| Amber continuously | `lldpctl -f keyvalue`, interface name | Fix switch advertisement/interface or configure explicit switch IP |
| Red top pixels | SNMP error in `STATUS` and direct `snmpget` | Check route/VLAN, community, ACL, counter/index, switch availability |
| No status reply | Pi IP, UDP 42424 access, controller version | SSH and inspect the service; absence is not proof of failed hardware |
| Status healthy, LEDs dark/flickering/wrong color | Current mode, power/data/ground, GRB order, audio conflict | Run the standalone one-pixel test with the service stopped |
| Bandwidth does not match the intended uplink | SNMP interface names/index and incoming/outgoing direction | Select the correct incoming counter; prefer supported 64-bit counter |
| Name stayed `led-build-01` | Marker plus hostname service journal | Script can mark done without a valid interface; investigate before resetting anything |
| Several sticks have the same name | Selected MAC, cloned completion marker | Correct the provisioning process; do not reset markers fleet-wide blindly |
| `/bin/bash^M` or bad interpreter | Shell file line endings | Recopy/install LF files |
| GPIO permission or import failure only in service | `systemctl cat runled`, effective user/interpreter | Use root and the absolute venv Python path |
| Filesystem full or read-only | `df`, kernel journal, journal usage | Preserve diagnostics; investigate SD card/power and recover from the known image |

The revised controller limits SNMP exception stack traces to once per minute
and logs a health summary every 30 seconds. LLDP attempts have a three-second
subprocess timeout and ten-second retry spacing. SNMP has a one-second timeout,
no native retries, and an interruptible wait between attempts. Malformed packets
are discarded. A failed worker or one making no progress for 15 seconds triggers
a fatal exit; a five-second thread join limit prevents unbounded mode-switch
waits. The service watchdog covers a main loop that stops sending heartbeats.

These layers cannot recover every native-driver fault and do not reboot a
frozen OS. Power, SD-card failure, Ethernet enumeration, and signal integrity
remain separate hardware/system concerns.

## 16. Qualify one stick before updating the fleet

Record expected observations as you test; do not treat an unattended boot as
complete validation.

1. **Cold boot with normal network:** hostname is unique, service passes the
   intentional startup delay, `STATUS` shows the intended version/switch/OID,
   and real traffic changes the LEDs.
2. **Cold boot without Internet:** the local-controller configuration starts;
   if using the update launcher, a compatible installed copy starts after its
   failed download. No Internet is required for a reachable LAN switch.
3. **Switch/SNMP unavailable:** amber or red is visible as appropriate, status
   remains queryable, and animation commands still work. Restore access and
   return to `BANDWIDTH`; confirm monitoring resumes.
4. **Commands and shutdown:** exercise fill/rainbow/beat, `STOP`, then
   `BANDWIDTH`. A deliberate `systemctl stop runled` clears the LEDs and stays
   stopped. Start again and verify the delay and version.
5. **Crash recovery:** on the bench only, terminate the actual main process
   abnormally; verify a recorded failure, incremented restart count, the
   five-second restart interval plus the 60-second sleep, and return to control.
6. **Stall recovery:** with console/recovery access, suspend the main process
   to simulate missing heartbeats; verify systemd kills/restarts it after the
   watchdog deadline. This is an intentional fault test, not a routine command
   to run on the live event network.
7. **Soak:** leave it running through an extended traffic/idle cycle and several
   cold boots. Check restart counts, power flags, storage usage, and logs.
8. **Repeatability:** build a second card/second stick from the recorded steps
   and versions before calling the image qualified for all 30.

The repository tests pass on the development machine; this physical validation
record is still to be completed. Do not remove the 60-second delay as part of
qualification unless separately investigating its original purpose.

## 17. Build and maintain the 30-stick fleet

The least ambiguous starting method is imaging/provisioning each card with
its own identity. If using a master image instead, prepare it deliberately as
a provisioning image. A byte-for-byte clone of an already commissioned stick
can copy its hostname marker, hostname, machine identity, SSH host keys,
credentials, and network connection identifiers.

For cloned cards, establish a first-boot procedure that gives each Pi its own
machine identity and SSH host keys, and allows the existing MAC hostname script
to run. Reset the hostname marker only in the offline master/clone preparation
process, not on working deployed sticks. Do not assume hostname changes alone
solve DHCP or SSH identity duplication. Verify which Ethernet MAC is actually
available when the hostname service executes. We have not added an automated
clone-generalisation tool to this repository.

Keep an inventory with: physical stick label, Pi model, Ethernet MAC, hostname,
reserved/DHCP IP, monitored switch/interface, OS image date/hash, kernel,
Python/dependency versions, controller commit/version, installation date, last
qualification date, and hardware repairs. Use DHCP reservations or known DNS
where practical, and keep a list usable by `tools/stick_status.py`.

After qualification, archive the image plus package records, source revision,
service/drop-in files, and hardware notes. If updating from GitHub, pin the same
tested commit on all sticks. Freeze the release before the event, update a
small batch first, and query all sticks for their **running** version. File
contents on disk and a Git checkout hash do not prove which code is loaded by
a process that started earlier.

## 18. Recovery and rollback

If a stick is reachable, capture logs/status before rebooting it. For a bad
Python update, stop the LED service and inspect the saved version before reuse:

```bash
sudo systemctl stop runled.service
sudo /home/magfest/venv/bin/python -m py_compile /home/magfest/magfest_led.py.previous
```

Only restore that file if it is the intended compatible release. An original
pre-notification program will not work with this notify/watchdog service unit.
Use a known qualified source copy if the previous file's identity is uncertain.
After selecting the correct source, install it as `/home/magfest/magfest_led.py`
and either use the local-controller drop-in from section 11 or correct the
pinned download URL **before** restarting. Otherwise the launcher can download
the bad revision again immediately.

If the service configuration is the problem, restore the matching qualified
unit and drop-in, run `sudo systemctl daemon-reload`, then start the service.
If the filesystem or Pi is unreachable, preserve the failed card and boot a
qualified spare card. Keeping the original working image intact remains the
recovery path while the new OS build is being validated.

## 19. Remaining facts to record

The hostname script and both original service definitions are now present.
The following still need to be recorded from the working image/test hardware:

- Exact Pi Zero model(s), Ethernet adapter chip/model, and stable interface names.
- Working OS release, Python executable/version, package versions, and boot config.
- Actual LED type, wiring diagram, level shifter, supply/injection/fusing details.
- Switch models, management VLAN/routing, SNMP community policy, and intended port indexes.
- Why the 60-second delay was required and whether anything else is still starting then.
- Completed Trixie dependency, GPIO, notification/watchdog, offline-boot, and soak results.
- A tested release commit and a repeatable per-device identity process for clones.

Update this guide with those measured results. The objective is one documented,
qualified OS/software/hardware combination, rather than 30 slightly different
installations whose failures are hard to compare.
