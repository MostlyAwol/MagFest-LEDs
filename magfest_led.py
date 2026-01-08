#!/usr/bin/env python3
# This is the server file
# Edit/Created by Jay Clark
# Last Update Nov. 28, 2025

import time
import neopixel # type: ignore
import argparse
import socket
import threading
import sys
from easysnmp import Session # type: ignore
from array import *
import os
import subprocess
import board # type: ignore
import signal
from easysnmp.exceptions import EasySNMPTimeoutError # type: ignore

print("=== MAGFEST START ===")
print("EUID:", os.geteuid())
print("EXE :", sys.executable)
print("CWD :", os.getcwd())
sys.stdout.flush()
time.sleep(1)

##############################################################################################################
# Global Variables (I know I shouldn't)
##############################################################################################################
#Change to TCP or UDP depending on the need. UDP will allow broadcast IPs to work.
protocol_mode = "UDP"
PORT = 42424
HOST = ''
version = "2.2026.01.08c"
MAX_LENGTH = 4096
last_percent = -1
last_scale = 0
color_split = 45 #NO IDEA WHAT YOU DO?
doing_what = "RAINBOW"
arg_1 = ""
arg_2 = ""
last_command = ''
hostname = socket.gethostname()

switch_ip = None
#switch_mib = "1.3.6.1.2.1.2.2.1.10.2" #Quanta Switches wrong one though...
switch_mib = "1.3.6.1.2.1.2.2.1.10.49" #SHould be the real port to monitor!!!
#switch_mib = "1.3.6.1.2.1.2.2.1.10.6" #UDR7 Port 4
bandwidth_rate = 1000000

#LED Defaults?
max_speed = 250
default_speed = 60

#Thread End Variables
exit_event = threading.Event()
stop_threads = False
socket_run = True
##############################################################################################################
running = True

def shutdown(signum, frame):
    global running
    print(f"Received signal {signum}, shutting down cleanly...")
    running = False

# Define functions which animate LEDs in various ways.
def colorWipe(strip, color, wait_ms=50):
	"""Wipe color across display a pixel at a time."""
	while True:
		colorFill(strip, (0,0,0,))
		for i in range(60):
			strip[i*5+0] = color
			strip[i*5+1] = color
			strip[i*5+2] = color
			strip[i*5+3] = color
			strip[i*5+4] = color
			strip.show()
			time.sleep(wait_ms/1000.0)
		global stop_threads
		if stop_threads:
			return

def theaterChase(strip, color, wait_ms=50, iterations=10):
	"""Movie theater light style chaser animation."""
	while True:
		for q in range(15):
			for i in range(0, 60, 15):
				for a in range(0,15):
					strip[(i+q)*5+a] = color
			strip.show()
			time.sleep(wait_ms/1000.0)
			for i in range(0, 60, 15):
				for a in range(0,15):
					strip[(i+q)*5+a] = (0,0,0)
			global stop_threads
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
		strip.show()
		time.sleep(wait_ms/1000.0)

def rainbowCycle(strip, wait_ms=20, iterations=5):
	"""Draw rainbow that uniformly distributes itself across all pixels."""
	while True:
		for j in range(256):
			for i in range(len(strip)):
				strip[i] = wheel((int(i * 256 / len(strip)) + j) & 255)
			strip.show()
			global stop_threads
			if stop_threads:
				return
			time.sleep(wait_ms/1000.0)

def theaterChaseRainbow(strip, wait_ms=50):
	"""Rainbow movie theater light style chaser animation."""
	for j in range(256):
		for q in range(3):
			for i in range(0, len(strip), 3):
				strip[i+q] = wheel((i+j) % 255)
			strip.show()
			time.sleep(wait_ms/1000.0)
			for i in range(0, len(strip), 3):
				strip[i+q] = (0,0,0)

def colorFill(strip, color, amount=60):
	for i in range(amount):
		strip[i*5+0] = color
		strip[i*5+1] = color
		strip[i*5+2] = color
		strip[i*5+3] = color
		strip[i*5+4] = color
	strip.show()

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
	strip.show();

def FlipFlop(strip, color):
	while True:
		for i in range(int(len(strip) / 2)):
			strip[i] = color
		for i in range(int(len(strip) / 2),len(strip)):
			strip[i]= (0,0,0)
		strip.show()
		time.sleep(0.5)
		for i in range(int(len(strip) / 2)):
			strip[i] =(0,0,0)
		for i in range(int(len(strip) / 2),len(strip)):
			strip[i] = color
		strip.show()
		time.sleep(0.5)
		global stop_threads
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
		strip.show()			
		global stop_threads
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
		strip.show()			
		global stop_threads
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
		strip.show()			
		global stop_threads
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
			strip.show()

			#Delay should depend on how many pixels are changing. Faster for more and slower for less?
			if i - percent <= 5:
				time.sleep(25/1000)


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
			strip.show()

			if percent - i <= 5:
				time.sleep(25/1000)

	last_percent = percent
	last_scale = scale

def MonitorBandwidth(switch_ip, snmp_mib):
	old_bytes = 0
	current_bytes = 0
	global bandwidth_rate
	bandwidth = []
	scale = 0
	last_scale = 0
	fillcolor = [(255,0,0),(0,255,0),(0,0,255)]
	current_color = 0

	session = Session(hostname=switch_ip, community='public', version=2,timeout=2, retries=2,)
	while True:
		max_bytes_per_second = bandwidth_rate / 8; #100Mbps Line
		# Create an SNMP session to be used for all our requests
		# You may retrieve an individual OID using an SNMP GET
		try:
			location = session.get(snmp_mib)
			current_bytes = int(location.value)
		except EasySNMPTimeoutError:
			time.sleep(1)
			continue
	
		bandwidth_used = 0

		if current_bytes >= old_bytes:
			if old_bytes != 0:
				bandwidth_used = current_bytes - old_bytes
			else:
				bandwidth_used = 0
		else:
			bandwidth_used = 4294967295 - old_bytes + current_bytes

		oldest_bandwidth = 0
		total = 0
		bandwidth.append(bandwidth_used)

		if len(bandwidth) == 11:
			oldest_bandwidth = bandwidth.pop(0)

		for x in bandwidth:
			total = total + x

		avr_bandwidth = total / len(bandwidth)
		percent = avr_bandwidth / float(max_bytes_per_second) * 100
		percent = int(percent)
		
		#This is the Scale of the LEDs being lit up
		if percent >= 100:
			bandwidth_rate = bandwidth_rate * 10
			scale = scale + 1
			if bandwidth_rate >= 10000000000:
				bandwidth_rate = 10000000000
				scale = 5
			
		if percent <= 5:
			bandwidth_rate = bandwidth_rate / 10
			scale = scale - 1
			if bandwidth_rate <= 10000:
				bandwidth_rate = 10000
				scale = -1
		percent = (int(60 * percent)) / 100;
		global strip
		global color_split
		if scale == -1:
			colorFill(strip,fillcolor[current_color])
			current_color = current_color + 1
			if current_color > 2:
				current_color = 0	
		else:
			LEDBandWidth(strip, percent, color_split, scale)
		old_bytes = current_bytes
		last_scale = scale
		time.sleep(1.0)
		global stop_threads
		if stop_threads:
			break

def SocketThread():
	while True:
		#Sits here to wait for a command a Thread is handling the LEDs at this point. The "at" thread is doing the LEDs
		if protocol_mode == "TCP":
			(clientsocket, address) = serversocket.accept()
			handle(clientsocket)
			
		if protocol_mode == "UDP":
			data, address = serversocket.recvfrom(1024)
			handle(data)

		#print "Packet received from " + str(address)
		time.sleep(1)
		
		if exit_event.is_set():
			print("I was told to stop")
			break

def handle(socket_data):
	global protocol_mode
	global doing_what
	global arg_1
	global arg_2

	if protocol_mode == "TCP":
		buf = socket_data.recv(MAX_LENGTH) #Is this Blocking?

	if protocol_mode == "UDP":
		buf = socket_data #clientsocket.recv(MAX_LENGTH) #Is this Blocking?

	words = buf.split(" ")

	#Fill array with commands
	for i in range(0, len(words)):
		if i == 0:
			doing_what = words[i]
		if i == 1:
			arg_1 = words[i]
		if i == 2:
			arg_2 = words[i]

	return

def StopLED():
	global stop_threads
	#print "Stopping LED Thread"
	stop_threads = True
	LED_thread.join()
	#print "LED Stopped - Clearing..."
	colorFill(strip, (0,0,0))
	strip.show()
	stop_threads = False

def get_switch_ip(interface="eth0") -> str | None:
    cmd = ["lldpctl", "-f", "keyvalue"]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print("lldpctl failed:", result.stderr.strip())
        return None

    mgmt_ip = None
    for line in result.stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key == "lldp.eth0.chassis.mgmt-ip":
            mgmt_ip = value
            break

    return mgmt_ip

##############################################################################################################
# Init of Program

# Process arguments
parser = argparse.ArgumentParser()
parser.add_argument('-c', '--clear', action='store_true', help='clear the display on exit')
args = parser.parse_args()

# LED strip configuration:
LED_COUNT      = 300      # Number of LED pixels.
LED_PIN        = board.D18      # GPIO pin connected to the pixels (18 uses PWM!).
ORDER = neopixel.GRB

# Create NeoPixel object with appropriate configuration.
strip = neopixel.NeoPixel(LED_PIN, LED_COUNT, brightness=0.2, auto_write=False, pixel_order=ORDER)

#Setup Sockets for listening for Commands
if protocol_mode == "TCP":
	serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #SOCK_STREAM (TCP) or SOCK_DGRAM (UDP)
	serversocket.bind((HOST, PORT))
	serversocket.listen(1)

if protocol_mode == "UDP":
	serversocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) #SOCK_STREAM (TCP) or SOCK_DGRAM (UDP)
	serversocket.bind((HOST, PORT))

#Start Thread for the sockets
print("Starting Socket Thread")
socket_run = True
socket_thread = threading.Thread(target=SocketThread)
socket_thread.daemon = True
socket_thread.start()

print('Press Ctrl-C to quit.')

LED_thread = threading.Thread(target=DebugLED, args=(strip, (0,255,0))) #On and Ready
LED_thread.start()
last_command = "start"
print(f"Debug Showing Version: {version}")

#Find the switch IP address we are plugged into with lldp
#switch_ip = None
config_count = 0
while switch_ip is None:
	switch_ip = get_switch_ip()
	StopLED()
	try:
		color = "FFCC00"
		color = tuple(int(arg_1[i:i+2], 16) for i in (0, 2, 4))
		LED_thread = threading.Thread(target=FlipFlop, args=(strip, (int(color[0]),int(color[1]),int(color[2]))))
		LED_thread.start()
	except:
		print("Flip Flop Error")
	if switch_ip is None:
		config_count = config_count + 1
		if config_count < 6:
			time.sleep(5 * 60)
		else:
			StopLED()
			try:
				color = "FF0000"
				color = tuple(int(arg_1[i:i+2], 16) for i in (0, 2, 4))
				LED_thread = threading.Thread(target=FlipFlop, args=(strip, (int(color[0]),int(color[1]),int(color[2]))))
				LED_thread.start()
			except:
				print("Flip Flop Error")
print(f"Switch IP for me: {switch_ip}")
doing_what = "BANDWIDTH"

try:
	while running:
		#Check if we are doing something based on the doing_what being filled in by the socket
		if doing_what.upper() != "":
			print("Doing What: " + doing_what)
			print("Arg 1: " + arg_1)
			print("Arg 2: " + arg_2)

		if doing_what.upper() == "BANDWIDTH":
			StopLED()
			LED_thread = threading.Thread(target=MonitorBandwidth, args=(switch_ip, switch_mib))
			LED_thread.start()
		
		if doing_what.upper() == "RAINBOW":
			StopLED()
			LED_thread = threading.Thread(target=rainbowCycle, args=(strip, ))
			LED_thread.start()

		if doing_what.upper() == 'FF': #Flip Flop of Color "FF <HEXCODE>"
			StopLED()
			try:
				color = tuple(int(arg_1[i:i+2], 16) for i in (0, 2, 4))
				LED_thread = threading.Thread(target=FlipFlop, args=(strip, (int(color[0]),int(color[1]),int(color[2]))))
				LED_thread.start()
			except:
				print("Flip Flop Error")

		if doing_what.upper() == "FILL": #FILL <HEXColor>
			StopLED()
			try:
				color = tuple(int(arg_1[i:i+2], 16) for i in (0, 2, 4))
				if arg_2 == "":
					arg_2 = 60
				if arg_2 >= 60:
					arg_2 = 60
				print(str(color))
				colorFill(strip, (int(color[0]),int(color[1]),int(color[2])), 60)
			except:
				print("FILL Error " + str(arg_1) +" "+ str(arg_2))

		if doing_what.upper() == "WIPE": #WIPE <HEXColor> <speed>
			StopLED()
			try:
				color = tuple(int(arg_1[i:i+2], 16) for i in (0, 2, 4))
				if arg_2 == "":
					arg_2 = default_speed
				if arg_2 >= max_speed:
					arg_2 = max_speed
				LED_thread = threading.Thread(target=colorWipe, args=(strip, (int(color[0]),int(color[1]),int(color[2])), int(arg_2)) )
				LED_thread.start()
			except:
				print("Wipe Error")

		if doing_what.upper() == "CHASE":  #Chase <Color> <Speed>
			StopLED()
			try:
				color = tuple(int(arg_1[i:i+2], 16) for i in (0, 2, 4))
				if arg_2 == "":
					arg_2 = default_speed
				if arg_2 >= max_speed:
					arg_2 = max_speed
				LED_thread = threading.Thread(target=theaterChase, args=(strip, (int(color[0]),int(color[1]),int(color[2])), int(arg_2)) )
				LED_thread.start()
			except:
				print("Chase Error")

		if doing_what.upper() == "BEAT":
			StopLED()
			try:
				color = tuple(int(arg_1[i:i+2], 16) for i in (0, 2, 4))
				if arg_2 == "":
					arg_2 = default_speed
				if arg_2 >= max_speed:
					arg_2 = max_speed
				LED_thread = threading.Thread(target=Beat, args=(strip, (int(color[0]),int(color[1]),int(color[2])), arg_2 ))
				LED_thread.start()
			except:
				print("Beat Error")

		if doing_what.upper() == "RBEAT":
			StopLED()
			try:
				color = tuple(int(arg_1[i:i+2], 16) for i in (0, 2, 4))
				if arg_2 == "":
					arg_2 = default_speed
				if arg_2 >= max_speed:
					arg_2 = max_speed
				LED_thread = threading.Thread(target=RBeat, args=(strip, (int(color[0]),int(color[1]),int(color[2])), arg_2 ))
				LED_thread.start()
			except:
				print("Beat Error")

		if doing_what.upper() == "RBBEAT":
			StopLED()
			try:
				if arg_1 == "":
					arg_1 = default_speed
				if arg_1 >= max_speed:
					arg_1 = max_speed
				LED_thread = threading.Thread(target=RBBeat, args=(strip, arg_1 ))
				LED_thread.start()
			except:
				print("Beat Error")

		if doing_what == "REBOOT":
			StopLED()
			os.system('reboot now')

		if doing_what == "SHUTDOWN":
			StopLED()
			os.system('shutdown now')

		if doing_what == 'STOP':
			StopLED()

		#Clear Variable so we know we process them
		doing_what = ""
		arg_1 = ""
		arg_2 = ""
		time.sleep(1)
	
	print("Cleanup complete, exiting.")
	exit_event.set()
	#Blanking LED
	StopLED()
	print("Turning off LEDs")
	colorFill(strip, (0,0,0))
	strip.show()	
	#Exiting
	sys.exit(0)
		
except KeyboardInterrupt:
	print("Keyboard Interrupt Starting to Exit")
	exit_event.set()
	#Blanking LED
	StopLED()
	print("Turning off LEDs")
	colorFill(strip, (0,0,0))
	strip.show()	
	#Exiting
	print("Exiting")
	sys.exit(0)
