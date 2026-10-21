# MagFest-LEDs

> The reliability update is documented in [RELIABILITY.md](RELIABILITY.md),
> including current commands, visible fault states, and remote status queries.
> The existing notes below describe version `2.2026.01.08d` and are retained
> as historical setup context; use the reliability guide for current behavior.

Raspberry Pi Zero lighting controller for a LAN party room. Each light stick uses
300 addressable LEDs, with its Pi connected to a network switch. The main mode
turns switch traffic into a changing light display; remote commands also select
rainbows, solid colors, and other animations.

The controller is implemented in [`magfest_led.py`](magfest_led.py). Its current
version string is `2.2026.01.08d`.

## Hardware and software

- Raspberry Pi Zero with an Ethernet interface named `eth0` and access to the switch.
- A 300-pixel NeoPixel-compatible stick, configured for GRB color order, with data
  on GPIO 18 (`board.D18`). Provide power appropriate for the stick and a common
  ground with the Pi; this repository does not include a wiring diagram.
- A switch advertising its management IP through LLDP and allowing SNMP v2c
  reads from the Pi. The code uses the community string `public`.
- Raspberry Pi OS / Linux with Python 3.10 or newer (the code uses `str | None`).
- Python dependencies: `neopixel` (Adafruit CircuitPython NeoPixel), `board`
  (Adafruit Blinka), and `easysnmp`, plus the Pi hardware backend required by
  NeoPixel. EasySNMP also needs the native Net-SNMP libraries/build dependencies.
- `lldpd`, running with its `lldpctl` command available on `PATH`.

The old [`How To Setup From Fresh.txt`](How%20To%20Setup%20From%20Fresh.txt) contains
legacy Python package commands and is not a complete setup guide for the current
program. There is no dependency lockfile, installer, or service definition in
this repository.

## Configuration and startup

Settings are currently edited directly in `magfest_led.py`:

| Setting | Current value | Purpose |
| --- | --- | --- |
| `LED_COUNT` | `300` | Pixels per controller; many effects also assume 60 groups of five pixels. |
| `LED_PIN` | `board.D18` | LED data GPIO. |
| `ORDER` | `neopixel.GRB` | Pixel color order. |
| `brightness` in `NeoPixel(...)` | `0.2` | Global brightness, on a scale from 0 to 1. |
| `protocol_mode` | `"UDP"` | Network command transport. Use UDP; the TCP branch has a decoding issue. |
| `HOST` / `PORT` | `''` / `42424` | Listen on all IPv4 interfaces, port 42424. |
| `switch_mib` | `1.3.6.1.2.1.2.2.1.10.49` | Incoming octet counter for switch interface index 49. Change for your switch's monitored port. |
| `bandwidth_rate` | `1000000` | Initial display scale in bits per second; adjusts automatically. |

Choose the switch interface whose traffic should drive the room's display, such
as an uplink. The program reads one port's incoming counter; it does not sum all
switch ports or combine incoming and outgoing traffic.

After installing the dependencies and configuring LLDP/SNMP, run on the Pi from
the repository directory with the Python environment that contains them:

```sh
sudo python3 magfest_led.py
```

If using a virtual environment, use its Python executable with `sudo` instead.
The GPIO/PWM backend generally requires root access. There is no automatic boot
setup included.

At startup, the program opens the command socket, briefly lights the last 15
pixels green, and calls `lldpctl -f keyvalue` to find
`lldp.eth0.chassis.mgmt-ip`. It waits for that address before entering the mode
selection loop, then starts `BANDWIDTH` automatically. If discovery fails, the
first five unsuccessful attempts each wait five minutes; later attempts have no
explicit retry delay. Remote animation commands do not bypass this startup wait.

## Bandwidth display

The controller polls SNMP about once per second, subtracts consecutive octet
counter readings, and averages up to 10 samples. The resulting traffic estimate
controls the height of a bar made from groups of five LEDs, with a minimum of two
groups and a maximum of 60.

The display automatically moves between scales as traffic rises or falls. Bar
colors progress through magenta, cyan, blue, green, yellow, and red as the scale
increases. At the lowest scale, the entire stick cycles red, green, and blue
instead of displaying a bar. This is a relative activity display, rather than a
fixed percentage of the switch port's negotiated link speed.

The configured counter is 32-bit. The code attempts wraparound handling, but
multiple wraps between polls, switch counter resets, and variable polling delays
can affect the estimate. SNMP timeouts are retried without a dedicated LED error
indication.

## Remote commands and modes

Send one ASCII command per UDP datagram to the **Pi's IP address**, port `42424`.
Use single spaces between arguments, six hexadecimal color digits without `#`,
and no trailing newline. The receiver does not send an acknowledgment and pauses
one second after each received command.

For example, run this with Python on a computer that can reach the Pi, replacing
the example address:

```python
import socket

with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
    sock.sendto(b"RAINBOW", ("192.168.1.50", 42424))
```

| Command | Effect |
| --- | --- |
| `BANDWIDTH` | Resume monitoring the discovered switch. |
| `RAINBOW` | Continuous rainbow distributed along the stick. |
| `FF FF0000` | Alternate the two halves of the stick in the supplied color every half second. |
| `FILL 00FF00` | Fill the stick with the supplied color. |
| `WIPE 0000FF` | Repeatedly fill the stick in groups of five, then restart. |
| `CHASE FF0000` | Repeating theater-style chase in the supplied color. |
| `BEAT FF0000` | Fill upward and clear downward in the supplied color. |
| `RBEAT FF0000` | Fill downward and clear upward in the supplied color. |
| `RBBEAT` | Repeat the beat effect through a six-color palette. |
| `STOP` | Stop the current effect and clear the stick. |
| `REBOOT` | Clear the stick and request a Pi reboot. |
| `SHUTDOWN` | Clear the stick and request a Pi shutdown. |

Animation command names are case-insensitive. `STOP`, `REBOOT`, and `SHUTDOWN`
must be uppercase. Commands are unauthenticated, including reboot and shutdown,
so restrict access to the command port to the intended control network.

### Current limitations

- Omit optional speed/amount arguments. The command handlers compare received
  strings with integers before converting them, so explicit numeric arguments
  fail. `FILL` always fills all 60 groups; the beat effects do not use their speed
  parameter. `WIPE` and `CHASE` default to a 60 ms delay.
- The startup amber/red flip-flop indicators parse the command color argument
  instead of their hardcoded colors, so they normally log `Flip Flop Error`.
- Switching modes can wait for an animation cycle or an SNMP operation to finish.
  Repeated SNMP timeouts can prevent the bandwidth thread from stopping.
- Ctrl+C in the main loop attempts to stop the effect and clear the LEDs. The
  `-c` / `--clear` option is accepted but unused; clearing is already attempted
  on that exit path. The defined signal handler is not registered, so SIGTERM
  does not use that cleanup path.

## License

See [`LICENSE`](LICENSE) for the GNU General Public License, version 3.
