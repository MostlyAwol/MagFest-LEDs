#!/usr/bin/env python3
# This is the server file
# Edit/Created by Jay Clark
# Last Update Nov. 28, 2025

import time
import argparse
import socket
import threading
import sys
import os
import subprocess
import signal
import json
import logging
import queue
import re
import errno
from collections import deque
from pathlib import Path

log = logging.getLogger("magfest")
Session = None  # Hardware dependencies are loaded in main(), not on import.

##############################################################################################################
# Global Variables (I know I shouldn't)
##############################################################################################################
# Commands use UDP, including LAN broadcasts.
PORT = 42424
HOST = ''
version = "3.2026.10.21"
MAX_LENGTH = 4096
last_percent = -1
last_scale = 0
color_split = 45 # Rings needed to reach maximum channel brightness.
hostname = socket.gethostname()

switch_ip = None
#switch_mib = "1.3.6.1.2.1.2.2.1.10.2" #Quanta Switches wrong one though...
switch_mib = "1.3.6.1.2.1.2.2.1.10.49" #SHould be the real port to monitor!!!
#switch_mib = "1.3.6.1.2.1.2.2.1.10.6" #UDR7 Port 4

#LED Defaults?
max_speed = 250
default_speed = 60

#Thread End Variables
exit_event = threading.Event()
stop_threads = False
##############################################################################################################
running = True
commands = queue.Queue(maxsize=64)
worker_errors = queue.Queue()
health = {"state": "starting", "mode": "BANDWIDTH", "snmp_failures": 0,
          "last_snmp_success": None, "last_error": None, "bits_per_second": 0,
          "invalid_commands": 0, "dropped_commands": 0}
started_at = time.monotonic()
last_led_progress = started_at


def pause(seconds):
    """Allow every animation delay to be interrupted by a mode change."""
    exit_event.wait(seconds)


def status():
    return dict(health, hostname=hostname, version=version, switch_ip=switch_ip,
                oid=switch_mib, pid=os.getpid(),
                uptime_seconds=round(time.monotonic() - started_at, 1),
                timestamp=time.time())


def notify(message):
    address = os.environ.get("NOTIFY_SOCKET")
    if not address:
        return
    if address.startswith("@"):
        address = "\0" + address[1:]
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
            sock.settimeout(0.2)
            sock.connect(address)
            sock.sendall(message.encode())
    except OSError:
        log.warning("Could not notify systemd", exc_info=True)


def show_strip(strip):
    global last_led_progress
    strip.show()
    last_led_progress = time.monotonic()


def check_workers():
    if not worker_errors.empty():
        raise RuntimeError("Background worker failed") from worker_errors.get_nowait()
    if LED_thread is not None and LED_thread.is_alive():
        if time.monotonic() - last_led_progress > 15:
            raise RuntimeError("LED worker has made no progress for 15 seconds")


def start_led(target, *arguments):
    global LED_thread, last_led_progress
    last_led_progress = time.monotonic()
    def guarded():
        try:
            target(*arguments)
            if not stop_threads:
                raise RuntimeError("LED worker returned unexpectedly")
        except Exception as error:
            log.exception("LED worker failed")
            worker_errors.put(error)
    LED_thread = threading.Thread(target=guarded, name="led", daemon=True)
    LED_thread.start()


def shutdown(signum, frame):
    global running, stop_threads
    running = False
    stop_threads = True
    exit_event.set()

# Define functions which animate LEDs in various ways.
def colorWipe(strip, color, wait_ms=50):
	"""Wipe color across display a pixel at a time."""
	while not stop_threads:
		colorFill(strip, (0,0,0,))
		for i in range(60):
			if stop_threads:
				return
			strip[i*5+0] = color
			strip[i*5+1] = color
			strip[i*5+2] = color
			strip[i*5+3] = color
			strip[i*5+4] = color
			show_strip(strip)
			pause(wait_ms/1000.0)
		if stop_threads:
			return

def theaterChase(strip, color, wait_ms=50, iterations=10):
	"""Movie theater light style chaser animation."""
	while True:
		for q in range(15):
			for i in range(0, 60, 15):
				for a in range(min(15, len(strip) - (i+q)*5)):
					strip[(i+q)*5+a] = color
			show_strip(strip)
			pause(wait_ms/1000.0)
			for i in range(0, 60, 15):
				for a in range(min(15, len(strip) - (i+q)*5)):
					strip[(i+q)*5+a] = (0,0,0)
			if stop_threads:
				return

def wheel(pos):
	"""Generate rainbow colors across 0-255 positions."""
	if pos < 85:
		return (pos * 3, 255 - pos * 3, 0)
	elif pos < 170:
		pos -= 85
		return (255 - pos * 3, 0, pos * 3)
	else:
		pos -= 170
		return (0, pos * 3, 255 - pos * 3)

def rainbow(strip, wait_ms=20, iterations=1):
	"""Draw rainbow that fades across all pixels at once."""
	for j in range(256*iterations):
		for i in range(len(strip)):
			strip[i] = wheel((i+j) & 255)
		show_strip(strip)
		pause(wait_ms/1000.0)

def rainbowCycle(strip, wait_ms=20, iterations=5):
	"""Draw rainbow that uniformly distributes itself across all pixels."""
	while True:
		for j in range(256):
			for i in range(len(strip)):
				strip[i] = wheel((int(i * 256 / len(strip)) + j) & 255)
			show_strip(strip)
			if stop_threads:
				return
			pause(wait_ms/1000.0)

def theaterChaseRainbow(strip, wait_ms=50):
	"""Rainbow movie theater light style chaser animation."""
	for j in range(256):
		for q in range(3):
			for i in range(0, len(strip), 3):
				strip[i+q] = wheel((i+j) % 255)
			show_strip(strip)
			pause(wait_ms/1000.0)
			for i in range(0, len(strip), 3):
				strip[i+q] = (0,0,0)

def colorFill(strip, color, amount=60):
	for i in range(amount):
		strip[i*5+0] = color
		strip[i*5+1] = color
		strip[i*5+2] = color
		strip[i*5+3] = color
		strip[i*5+4] = color
	show_strip(strip)

def DebugLED(strip, color):
	#Debug LED are the last Ring or 5 LED (Top of the pole)
	#Remember to clear this when no longer needed.
	strip[60*5-1] = color
	strip[60*5-2] = color
	strip[60*5-3] = color
	strip[60*5-4] = color
	strip[60*5-5] = color
	strip[59*5-1] = color
	strip[59*5-2] = color
	strip[59*5-3] = color
	strip[59*5-4] = color
	strip[59*5-5] = color
	strip[58*5-1] = color
	strip[58*5-2] = color
	strip[58*5-3] = color
	strip[58*5-4] = color
	strip[58*5-5] = color
	show_strip(strip);

def FlipFlop(strip, color):
	while True:
		for i in range(int(len(strip) / 2)):
			strip[i] = color
		for i in range(int(len(strip) / 2),len(strip)):
			strip[i]= (0,0,0)
		show_strip(strip)
		pause(0.5)
		for i in range(int(len(strip) / 2)):
			strip[i] =(0,0,0)
		for i in range(int(len(strip) / 2),len(strip)):
			strip[i] = color
		show_strip(strip)
		pause(0.5)
		if stop_threads:
			break

def Beat(strip, color, speed=20):
	position = 1
	direction = 0 #0 = Up / 1 = Down
	while True:
		if position <= 60 and direction == 0:
			led_color = color
		else:
			led_color = (0,0,0)
		strip[position*5+0] = led_color
		strip[position*5+1] = led_color
		strip[position*5+2] = led_color
		strip[position*5+3] = led_color
		strip[position*5+4] = led_color
		if direction == 0:
			position = position + 1
			if position >= 60:
				direction = 1
				position = 60 - 1
		else:
			position = position - 1
			if position <= 0:
				direction = 0
				position = 0
		show_strip(strip)
		pause(speed / 1000.0)
		if stop_threads:
			break

def RBeat(strip, color, speed=20):
	position = 59
	direction = 1 #0 = Up / 1 = Down
	while True:
		if position >= 0 and direction == 1:
			led_color = color
		else:
			led_color = (0,0,0)
		strip[position*5+0] = led_color
		strip[position*5+1] = led_color
		strip[position*5+2] = led_color
		strip[position*5+3] = led_color
		strip[position*5+4] = led_color
		if direction == 0:
			position = position + 1
			if position >= 60:
				direction = 1
				position = 60 - 1
		else:
			position = position - 1
			if position <= 0:
				direction = 0
				position = 0
		show_strip(strip)
		pause(speed / 1000.0)
		if stop_threads:
			break

def RBBeat(strip, speed=20):
	position = 0
	direction = 0 #0 = Up / 1 = Down
	cpalette = [(255,0,0), (255,255,0), (0,255,0), (0,255,255), (0,0,255), (255,0,255)]
	current_color = 0
	while True:
		if position <= 60 and direction == 0:
			led_color = cpalette[current_color]
		else:
			led_color = (0,0,0)
		strip[position*5+0] = led_color
		strip[position*5+1] = led_color
		strip[position*5+2] = led_color
		strip[position*5+3] = led_color
		strip[position*5+4] = led_color
		if direction == 0:
			position = position + 1
			if position >= 60:
				direction = 1
				position = 60 - 1
		else:
			position = position - 1
			if position <= 0:
				direction = 0
				position = 0
				current_color = current_color + 1
				if current_color >= 6:
					current_color = 0
		show_strip(strip)
		pause(speed / 1000.0)
		if stop_threads:
			break

def LEDBandWidth(strip, percent, color_split, scale):
	global last_percent
	global last_scale
	red = 0
	green = 0

	percent = int(percent)

	if percent < 2:
		percent = 2

	if percent > 60:
		percent = 60

	if last_percent < 0:
		last_percent = 0
		colorFill(strip, (0,0,0))

	if last_scale != scale:
		colorFill(strip, (0,0,0))

	if percent < last_percent:
		for i in range(last_percent, percent,-1):
			strip[i*5-1] = (0,0,0)
			strip[i*5-2] = (0,0,0)
			strip[i*5-3] = (0,0,0)
			strip[i*5-4] = (0,0,0)
			strip[i*5-5] = (0,0,0)
			show_strip(strip)

			#Delay should depend on how many pixels are changing. Faster for more and slower for less?
			if i - percent <= 5:
				pause(25/1000)


	if percent > last_percent: #Color
		for i in range(0, percent):
			if i < 0:
				i = 0

			#Compute Color
			color_value = (int(255 / color_split)) * i + 1
			if color_value > 255:
				color_value = 255

			if scale == 0: #1 000 00 bits PURPLE
				LED_Color = (color_value,0, color_value)
			if scale == 1: #10 000 00 bits BLUE
				LED_Color = (0,color_value, color_value)
			if scale == 2: #100 000 00 bits GREEN
				LED_Color = (0,0, color_value)
			if scale == 3: #1 000 000 00 bits Yellow
				LED_Color = (0,color_value, 0)
			if scale == 4: #10 000 000 00 bits Red
				LED_Color = (color_value, color_value, 0)
			if scale == 5: #10 000 000 000
				LED_Color = (color_value, 0, 0)

			strip[i*5+0] = LED_Color
			strip[i*5+1] = LED_Color
			strip[i*5+2] = LED_Color
			strip[i*5+3] = LED_Color
			strip[i*5+4] = LED_Color
			show_strip(strip)

			if percent - i <= 5:
				pause(25/1000)

	last_percent = percent
	last_scale = scale

def counter_rate(previous, current, elapsed, bits):
    if previous is None or elapsed <= 0:
        return None
    delta = current - previous
    if delta < 0:
        # Only accept a wrap near the boundary; other decreases rebaseline.
        maximum = 1 << bits
        if previous < maximum * 0.9 or current > maximum * 0.1:
            return None
        delta += maximum
    return delta * 8 / elapsed


def MonitorBandwidth(switch_ip, snmp_mib):
    global last_percent, last_scale, last_led_progress
    previous = None
    previous_time = None
    samples = deque(maxlen=10)
    session = None
    next_log = 0
    scale = 0
    rates = [100000 * 10 ** i for i in range(6)]
    while not stop_threads:
        try:
            if session is None:
                session = Session(hostname=switch_ip, community=snmp_community,
                                  version=2, timeout=1, retries=0)
            result = session.get(snmp_mib)
            current = int(result.value)
            bits = 64 if result.snmp_type == "COUNTER64" else 32
            if current < 0 or current >= 1 << bits:
                raise ValueError("SNMP value is outside counter range")
            now = time.monotonic()
            rate = counter_rate(previous, current,
                                now - previous_time if previous_time is not None else 0, bits)
            previous, previous_time = current, now
            recovering = health["state"] != "monitoring"
            health.update(state="monitoring", last_snmp_success=time.time(),
                          last_error=None, snmp_failures=0)
            if recovering:
                log.info("SNMP monitoring active: %s %s", switch_ip, snmp_mib)
                last_percent = -1
            if rate is None:
                samples.clear()
            else:
                samples.append(rate)
            average = sum(samples) / len(samples) if samples else 0
            health["bits_per_second"] = round(average)
            while scale < len(rates) - 1 and average >= rates[scale]:
                scale += 1
            while scale > 0 and average <= rates[scale] * 0.05:
                scale -= 1
            # Repaint on scale changes even if the height is identical or lower.
            if last_scale != scale:
                last_percent = -1
        except Exception as error:
            # A network/library/value failure is recoverable. LED errors below
            # escape to the worker supervisor instead of leaving a frozen display.
            health.update(state="snmp_error", last_error=str(error)[:300],
                          snmp_failures=health["snmp_failures"] + 1)
            previous = previous_time = None
            samples.clear()
            session = None
            if time.monotonic() >= next_log:
                log.exception("SNMP polling failed; retrying")
                next_log = time.monotonic() + 60
            colorFill(strip, (0, 0, 0))
            DebugLED(strip, (255, 0, 0))
        else:
            LEDBandWidth(strip, average / rates[scale] * 60, color_split, scale)
            # A steady bar intentionally skips strip.show(); a completed poll
            # and render still proves the worker is making progress.
            last_led_progress = time.monotonic()
        pause(1)


def parse_command(data):
    words = data.decode("ascii").split()
    if not words:
        raise ValueError("empty command")
    mode = words[0].upper()
    no_args = {"BANDWIDTH", "RAINBOW", "STOP", "STATUS", "REBOOT", "SHUTDOWN"}
    colored = {"FF", "FILL", "WIPE", "CHASE", "BEAT", "RBEAT"}
    if mode in no_args and len(words) == 1:
        return mode, None, None
    if mode == "RBBEAT" and len(words) <= 2:
        speed = int(words[1]) if len(words) == 2 else default_speed
        if not 1 <= speed <= max_speed:
            raise ValueError("speed must be 1..250 milliseconds")
        return mode, None, speed
    if mode not in colored or not 2 <= len(words) <= 3:
        raise ValueError("unknown command or incorrect argument count")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", words[1]):
        raise ValueError("color must be six hexadecimal digits")
    color = tuple(int(words[1][i:i+2], 16) for i in (0, 2, 4))
    value = int(words[2]) if len(words) == 3 else (60 if mode == "FILL" else default_speed)
    if not 1 <= value <= (60 if mode == "FILL" else max_speed):
        raise ValueError("amount/speed out of range")
    return mode, color, value


def SocketThread():
    while running:
        try:
            data, address = serversocket.recvfrom(MAX_LENGTH + 1)
        except socket.timeout:
            continue
        except OSError as error:
            # Windows reports oversized datagrams as WSAEMSGSIZE instead of
            # returning a truncated buffer as Linux does.
            if error.errno == errno.EMSGSIZE or getattr(error, "winerror", None) == 10040:
                health["invalid_commands"] += 1
                continue
            # ICMP errors from a closed status-query client are not a broken
            # listening socket (notably WSAECONNRESET on Windows).
            if error.errno in {errno.ECONNRESET, errno.ECONNREFUSED}:
                continue
            if running:
                worker_errors.put(error)
            return
        try:
            if len(data) > MAX_LENGTH:
                raise ValueError("command too long")
            command = parse_command(data)
            if command[0] == "STATUS":
                # Read-only diagnostic response; other commands keep the old
                # fire-and-forget protocol. Replies may require firewall access.
                serversocket.sendto(json.dumps(status()).encode(), address)
            else:
                commands.put_nowait(command)
        except (ValueError, UnicodeError):
            # Ignore malformed/flooded datagrams without killing the receiver
            # or filling the SD card with per-packet log messages.
            health["invalid_commands"] += 1
        except queue.Full:
            health["dropped_commands"] += 1
        except OSError:
            log.debug("UDP reply failed", exc_info=True)


def StopLED():
    global stop_threads, last_percent, last_scale
    stop_threads = True
    exit_event.set()
    if LED_thread is not None:
        LED_thread.join(timeout=5)
        if LED_thread.is_alive():
            raise RuntimeError("LED worker did not stop within 5 seconds")
    colorFill(strip, (0, 0, 0))
    last_percent, last_scale = -1, 0
    if running:
        stop_threads = False
        exit_event.clear()


def get_switch_ip(interface="eth0"):
    try:
        result = subprocess.run(["lldpctl", "-f", "keyvalue"],
                                capture_output=True, text=True, timeout=3, check=True)
        for line in result.stdout.splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() == f"lldp.{interface}.chassis.mgmt-ip":
                # This controller's command/network setup is IPv4.
                try:
                    socket.inet_pton(socket.AF_INET, value.strip())
                except OSError:
                    continue
                return value.strip()
        raise ValueError("no IPv4 management address advertised")
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        health.update(state="discovery", last_error=str(error)[:300])
        log.warning("Switch discovery failed: %s", error)
        return None


def write_status(path):
    try:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(json.dumps(status()) + "\n")
        temporary.replace(destination)
    except OSError:
        log.exception("Could not write status file %s", path)


def apply_command(command):
    mode, color, value = command
    if mode in {"REBOOT", "SHUTDOWN"} and not allow_power_commands:
        log.warning("Power command disabled: %s", mode)
        return
    StopLED()
    health.update(mode=mode, state="animation" if mode != "BANDWIDTH" else "discovery")
    log.info("Mode: %s", mode)
    if mode == "BANDWIDTH":
        if switch_ip:
            start_led(MonitorBandwidth, switch_ip, switch_mib)
        else:
            start_led(FlipFlop, strip, (255, 160, 0))
    elif mode == "RAINBOW":
        start_led(rainbowCycle, strip)
    elif mode == "FILL":
        colorFill(strip, color, value)
    elif mode == "STOP":
        health["state"] = "stopped"
    elif mode in {"REBOOT", "SHUTDOWN"}:
        subprocess.run(["systemctl", "reboot" if mode == "REBOOT" else "poweroff"],
                       timeout=5, check=True)
    else:
        effects = {"FF": FlipFlop, "WIPE": colorWipe, "CHASE": theaterChase,
                   "BEAT": Beat, "RBEAT": RBeat, "RBBEAT": RBBeat}
        arguments = (strip, value) if mode == "RBBEAT" else ((strip, color) if mode == "FF" else (strip, color, value))
        start_led(effects[mode], *arguments)


def main():
    global strip, serversocket, LED_thread, running, switch_ip, switch_mib
    global snmp_community, allow_power_commands, Session
    parser = argparse.ArgumentParser(description="Headless LAN bandwidth LED controller")
    parser.add_argument("-c", "--clear", action="store_true", help="compatibility option; LEDs always clear on exit")
    parser.add_argument("--switch", default=os.environ.get("MAGFEST_SWITCH"))
    parser.add_argument("--interface", default="eth0")
    parser.add_argument("--oid", default=os.environ.get("MAGFEST_OID", switch_mib))
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--status-file", default="/run/magfest-led/status.json")
    parser.add_argument("--allow-power-commands", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    log.info("Starting %s on %s; Python %s", version, hostname, sys.executable)
    switch_ip, switch_mib = args.switch, args.oid
    snmp_community = os.environ.get("MAGFEST_SNMP_COMMUNITY", "public")
    allow_power_commands = args.allow_power_commands
    LED_thread = None
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    import board
    import neopixel
    from easysnmp import Session as snmp_session
    Session = snmp_session
    strip = neopixel.NeoPixel(board.D18, 300, brightness=0.2,
                              auto_write=False, pixel_order=neopixel.GRB)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as serversocket:
            serversocket.bind((HOST, args.port))
            serversocket.settimeout(0.5)
            receiver = threading.Thread(target=SocketThread, name="commands", daemon=True)
            receiver.start()
            apply_command(("BANDWIDTH", None, None))
            notify("READY=1")
            next_discovery = next_status = next_watchdog = 0
            watchdog_interval = max(0.1, int(os.environ.get("WATCHDOG_USEC", "30000000")) / 3000000)
            while running:
                now = time.monotonic()
                check_workers()
                if health["mode"] == "BANDWIDTH" and not switch_ip and now >= next_discovery:
                    switch_ip = get_switch_ip(args.interface)
                    next_discovery = time.monotonic() + 10
                    if switch_ip and running:
                        apply_command(("BANDWIDTH", None, None))
                if now >= next_watchdog:
                    notify("WATCHDOG=1")
                    next_watchdog = now + watchdog_interval
                if now >= next_status:
                    write_status(args.status_file)
                    log.info("Health: %s", json.dumps(status()))
                    next_status = now + 30
                try:
                    command = commands.get(timeout=0.1)
                except queue.Empty:
                    continue
                if running:
                    apply_command(command)
    finally:
        running = False
        notify("STOPPING=1")
        StopLED()
        strip.deinit()
        health["state"] = "exited"
        write_status(args.status_file)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log.exception("Controller failed; exiting for supervisor restart")
        sys.exit(1)
