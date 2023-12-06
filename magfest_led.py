#!/usr/bin/env python3
# This is the server file
# Edit/Created by Jay Clark
# Last Update Dec. 5nd 2023
# NeoPixel library strandtest example
# Author: Tony DiCola (tony@tonydicola.com)
#
# Direct port of the Arduino NeoPixel library strandtest example.  Showcases
# various animations on a strip of NeoPixels.

import time
from neopixel import *
import argparse
import random
import socket
import threading
import sys
from easysnmp import Session
from array import *
import urllib2
import json
import os
##############################################################################################################
# Global Variables (I know I shouldn't)
##############################################################################################################
#Change to TCP or UDP depending on the need. UDP will allow broadcast IPs to work.
protocol_mode = "UDP"
PORT = 42424
HOST = ''
version = "2.2023.12.4"
MAX_LENGTH = 4096
last_percent = -1
miss_count = 0
color_split = 45
doing_what = ""
arg_1 = ""
arg_2 = ""
last_command = ''
hostname = socket.gethostname()
light_id = hostname[3:]
url = "http://wall.lan.magfest.net/ledconfig.pl?action=GETINFO&lightid=" + str(light_id) + "&version=" + version
#url = "http://magwall.lan.magfest.net/ledconfig.pl?action=GETINFO&lightid=" + str(light_id) + "&version=" + version
config = True #Change this to real version!

switch_ip = "192.168.1.235"
switch_mib = "1.3.6.1.2.1.2.2.1.10.2"
bandwidth_rate = 1000000000

wd_running = False

#LED Defaults?
max_speed = 250
default_speed = 60

#Thread End Variables
exit_event = threading.Event()

stop_threads = False

wd_run = True
socket_run = True
##############################################################################################################


# Define functions which animate LEDs in various ways.
def colorWipe(strip, color, wait_ms=50):
	"""Wipe color across display a pixel at a time."""
	while True:
		colorFill(strip, Color(0,0,0,))
		for i in range(60):
			strip.setPixelColor(i*5+0, color)
			strip.setPixelColor(i*5+1, color)
			strip.setPixelColor(i*5+2, color)
			strip.setPixelColor(i*5+3, color)
			strip.setPixelColor(i*5+4, color)
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
					strip.setPixelColor((i+q)*5+a, color)
			strip.show()
			time.sleep(wait_ms/1000.0)
			for i in range(0, 60, 15):
				for a in range(0,15):
					strip.setPixelColor((i+q)*5+a, 0)
			global stop_threads
			if stop_threads:
				return

def wheel(pos):
	"""Generate rainbow colors across 0-255 positions."""
	if pos < 85:
		return Color(pos * 3, 255 - pos * 3, 0)
	elif pos < 170:
		pos -= 85
		return Color(255 - pos * 3, 0, pos * 3)
	else:
		pos -= 170
		return Color(0, pos * 3, 255 - pos * 3)

def rainbow(strip, wait_ms=20, iterations=1):
	"""Draw rainbow that fades across all pixels at once."""
	for j in range(256*iterations):
		for i in range(strip.numPixels()):
			strip.setPixelColor(i, wheel((i+j) & 255))
		strip.show()
		time.sleep(wait_ms/1000.0)

def rainbowCycle(strip, wait_ms=20, iterations=5):
	"""Draw rainbow that uniformly distributes itself across all pixels."""
	while True:
		for j in range(256):
			for i in range(strip.numPixels()):
				strip.setPixelColor(i, wheel((int(i * 256 / strip.numPixels()) + j) & 255))
			strip.show()
			global stop_threads
			if stop_threads:
				return
			time.sleep(wait_ms/1000.0)

def theaterChaseRainbow(strip, wait_ms=50):
	"""Rainbow movie theater light style chaser animation."""
	for j in range(256):
		for q in range(3):
			for i in range(0, strip.numPixels(), 3):
				strip.setPixelColor(i+q, wheel((i+j) % 255))
			strip.show()
			time.sleep(wait_ms/1000.0)
			for i in range(0, strip.numPixels(), 3):
				strip.setPixelColor(i+q, 0)

def colorFill(strip, color, amount=60):
	for i in range(amount):
		strip.setPixelColor(i*5+0, color)
		strip.setPixelColor(i*5+1, color)
		strip.setPixelColor(i*5+2, color)
		strip.setPixelColor(i*5+3, color)
		strip.setPixelColor(i*5+4, color)
	strip.show()

def DebugLED(strip, color):
	#Debug LED are the last Ring or 5 LED (Top of the pole)
	#Remember to clear this when no longer needed.
	strip.setPixelColor(60*5-0, color)
	strip.setPixelColor(60*5-1, color)
	strip.setPixelColor(60*5-2, color)
	strip.setPixelColor(60*5-3, color)
	strip.setPixelColor(60*5-4, color)
	strip.setPixelColor(59*5-0, color)
	strip.setPixelColor(59*5-1, color)
	strip.setPixelColor(59*5-2, color)
	strip.setPixelColor(59*5-3, color)
	strip.setPixelColor(59*5-4, color)
	strip.setPixelColor(58*5-0, color)
	strip.setPixelColor(58*5-1, color)
	strip.setPixelColor(58*5-2, color)
	strip.setPixelColor(58*5-3, color)
	strip.setPixelColor(58*5-4, color)
	strip.show();

def FlipFlop(strip, color):
	while True:
		for i in range(strip.numPixels() / 2):
			strip.setPixelColor(i, color)
		for i in range(strip.numPixels() / 2,strip.numPixels()):
			strip.setPixelColor(i, Color(0,0,0))
		strip.show()
		time.sleep(0.5)
		for i in range(strip.numPixels() / 2):
			strip.setPixelColor(i, Color(0,0,0))
		for i in range(strip.numPixels() / 2,strip.numPixels()):
			strip.setPixelColor(i, color)
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
			led_color = Color(0,0,0)
		strip.setPixelColor(position*5+0, led_color)
		strip.setPixelColor(position*5+1, led_color)
		strip.setPixelColor(position*5+2, led_color)
		strip.setPixelColor(position*5+3, led_color)
		strip.setPixelColor(position*5+4, led_color)
		if direction == 0:
			position = position + 1
			if position >= 60:
				direction = 1
				position = 60 - 1
		else:
			position = position - 1
			if position <= 0:
				direction = 0
				position = 1
		strip.show()			
		#time.sleep(speed/1000)
		global stop_threads
		if stop_threads:
			break

def RBeat(strip, color, speed=20):
	position = 60
	direction = 1 #0 = Up / 1 = Down
	while True:
		if position >= 0 and direction == 1:
			led_color = color
		else:
			led_color = Color(0,0,0)
		strip.setPixelColor(position*5+0, led_color)
		strip.setPixelColor(position*5+1, led_color)
		strip.setPixelColor(position*5+2, led_color)
		strip.setPixelColor(position*5+3, led_color)
		strip.setPixelColor(position*5+4, led_color)
		if direction == 0:
			position = position + 1
			if position >= 60:
				direction = 1
				position = 60 - 1
		else:
			position = position - 1
			if position <= 0:
				direction = 0
				position = 1
		strip.show()			
		#time.sleep(speed/1000)
		global stop_threads
		if stop_threads:
			break

def RBBeat(strip, speed=20):
	position = 1
	direction = 0 #0 = Up / 1 = Down
	cpalette = [Color(255,0,0), Color(255,255,0), Color(0,255,0), Color(0,255,255), Color(0,0,255), Color(255,0,255)]
	current_color = 0
	while True:
		if position <= 60 and direction == 0:
			led_color = cpalette[current_color]
		else:
			led_color = Color(0,0,0)
		strip.setPixelColor(position*5+0, led_color)
		strip.setPixelColor(position*5+1, led_color)
		strip.setPixelColor(position*5+2, led_color)
		strip.setPixelColor(position*5+3, led_color)
		strip.setPixelColor(position*5+4, led_color)
		if direction == 0:
			position = position + 1
			if position >= 60:
				direction = 1
				position = 60 - 1
		else:
			position = position - 1
			if position <= 0:
				direction = 0
				position = 1
				current_color = current_color + 1
				if current_color >= 6:
					current_color = 0
		strip.show()			
		#time.sleep(speed/1000)
		global stop_threads
		if stop_threads:
			break

def LEDBandWidth(strip, percent, color_split):
	global last_percent
	red = 0
	green = 0

	if percent < 2:
		percent = 2

	if percent > 60:
		percent = 60

	if last_percent < 0:
		last_percent = 0
		colorFill(strip, Color(0,0,0))

	if percent < last_percent:
		#print "SHRINK IT!!!"
		for i in range(last_percent+1, percent,-1):
			#print "I="+ str(i)
			strip.setPixelColor(i*5-0, Color(0,0,0))
			strip.setPixelColor(i*5-1, Color(0,0,0))
			strip.setPixelColor(i*5-2, Color(0,0,0))
			strip.setPixelColor(i*5-3, Color(0,0,0))
			strip.setPixelColor(i*5-4, Color(0,0,0))
			strip.show()

			#Delay should depend on how many pixels are changing. Faster for more and slower for less?
			if i - percent <= 5:
				time.sleep(25/1000)
			else:
				time.sleep(1/1000)


	if percent > last_percent:
		for i in range(last_percent, percent):
			if i < 0:
				i = 0

			#Compute Color
			if i < color_split:
				green = 255
				red = (255 / color_split) * i
			else:
				red = 255
				green = 255 - ((255 / color_split) * (i-(60-color_split)))

			#print "I="+ str(i) +"   R="+ str(red) +" G="+ str(green)

			strip.setPixelColor(i*5+0, Color(red,green,0))
			strip.setPixelColor(i*5+1, Color(red,green,0))
			strip.setPixelColor(i*5+2, Color(red,green,0))
			strip.setPixelColor(i*5+3, Color(red,green,0))
			strip.setPixelColor(i*5+4, Color(red,green,0))
			strip.show()

			if percent - i <= 5:
				time.sleep(25/1000)
			else:
				time.sleep(1/1000)

	last_percent = percent

def MonitorBandwidth(switch_ip, snmp_mib):
	old_bytes = 0;
	current_bytes = 0
	global bandwidth_rate
	#max_bytes_per_second = bandwidth_rate / 8; #100Mbps Line
	bandwidth = []
	scale = 0

	while True:
		max_bytes_per_second = bandwidth_rate / 8; #100Mbps Line
		# Create an SNMP session to be used for all our requests
		session = Session(hostname=switch_ip, community='public', version=2)
		# You may retrieve an individual OID using an SNMP GET
		#location = session.get('.1.3.6.1.2.1.2.2.1.10.4')
		location = session.get(snmp_mib)
		#print "Location = " + str(location.value)
		current_bytes = int(location.value)
		bandwidth_used = 0;

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
		#percent = bandwidth_used / float(max_bytes_per_second) * 100
		percent = int(percent)
		
		
		#This is the Scale of the LEDs being lit up
		if percent >= 100:
			bandwidth_rate = bandwidth_rate * 10
			scale = scale + 1
		#	print "Bandwidth Up " + str(bandwidth_rate)
			if bandwidth_rate >= 10000000000:
				bandwidth_rate = 10000000000
			
		if percent <= 5:
			bandwidth_rate = bandwidth_rate / 10
			scale = scale - 1
		#	print "Bandwidth Down " + str(bandwidth_rate)
			if bandwidth_rate <= 1000000:
				bandwidth_rate = 1000000
			
		#print "Old Bytes = " + str(old_bytes)
		#print "Current Bytes = " + str(current_bytes)
		#print "Bandwidth = " + str(bandwidth_used)
		#print "Line Speed = " + str(max_bytes_per_second)
		#print "Average Percentage = " + str(percent)
		percent = (60 * percent) / 100;
		#print "LED Fill = " + str(percent)
		#print bandwidth
		print "============================"
		global strip
		global color_split
		LEDBandWidth(strip, percent, color_split)
		old_bytes = current_bytes
		time.sleep(1.25)
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

		print "Packet received from " + str(address)
		time.sleep(1)
		
		if exit_event.is_set():
			print "I was told to stop"
			break

def handle(socket_data):
	global protocol_mode
	global doing_what
	global arg_1
	global arg_2
	while 1:

		if protocol_mode == "TCP":
			buf = socket_data.recv(MAX_LENGTH) #Is this Blocking?

		if protocol_mode == "UDP":
			buf = socket_data #clientsocket.recv(MAX_LENGTH) #Is this Blocking?

		#Split buffer on space
		print buf
		words = buf.split(" ")
		print "-------------------------"
		print words

		#Fill array with commands
		for i in range(0, len(words)):
			if i == 0:
				doing_what = words[i]
			if i == 1:
				arg_1 = words[i]
			if i == 2:
				arg_2 = words[i]

		return

def GetConfig():
	global switch_ip
	global switch_mib
	global bandwidth_rate
	try:
		req = urllib2.Request(url)
		response = urllib2.urlopen(req)
		html = response.read()
		lightinfo = json.loads(html)
		#print lightinfo["switch_ip"]
		switch_ip = lightinfo["switch_ip"]
		switch_mib = lightinfo["snmp"]
		bandwidth_rate = int(lightinfo["bandwidth"])
		#Save the file
		with open('config.json', 'w') as outfile:
			json.dump(lightinfo, outfile)
		return True

	except urllib2.HTTPError as e:
		#print "HTTPError Showing"
		#Check for config.json
		try:
			f = open("config.json")
			#Check date/time on file
			mod_time = int(os.path.getmtime("config.json"))
			epoch_time = int(time.time())

			if (epoch_time - mod_time) < 60*60*24:
				lightinfo = json.load(f)
				#print lightinfo["switch_ip"]
				switch_ip = lightinfo["switch_ip"]
				switch_mib = lightinfo["snmp"]
				bandwidth = int(lightinfo["bandwidth"])
				return True
			else:
				return False

		except IOError:
			#print("File not accessible")
			return False

		return False

	except urllib2.URLError as e:
		#print "URLError Showing"
		#Check for config.json
		try:
			f = open("config.json")
			#Check date/time on file
			mod_time = int(os.path.getmtime("config.json"))
			epoch_time = int(time.time())

			if (epoch_time - mod_time) < 60*60*24:
				lightinfo = json.load(f)
				#print lightinfo["switch_ip"]
				switch_ip = lightinfo["switch_ip"]
				switch_mib = lightinfo["snmp"]
				bandwidth = int(lightinfo["bandwidth"])
				return True
			else:
				return False

		except IOError:
			#print("File not accessible")
			return False

		return False

def WatchDog():
	while True:
		global wd_running
		if wd_running == True:
			seconds = time.time()
			#print "Time: " + str(seconds)
			with open('/home/pi/watchdog.txt', 'w') as WDfile:
				WDfile.write(str(seconds));

			wd_running = False
		else:
			print "Watchdog Timer STOPPED THREAD ENDING"
			break
		if exit_event.is_set():
			break
		time.sleep(5)
		
def StopLED():
	global stop_threads
	print "Stopping LED Thread"
	stop_threads = True
	LED_thread.join()
	print "LED Stopped - Clearing..."
	colorFill(strip, Color(0,0,0))
	strip.show()
	stop_threads = False

##############################################################################################################
# Init of Program

# Process arguments
parser = argparse.ArgumentParser()
parser.add_argument('-c', '--clear', action='store_true', help='clear the display on exit')
args = parser.parse_args()

# LED strip configuration:
LED_COUNT      = 300      # Number of LED pixels.
LED_PIN        = 18      # GPIO pin connected to the pixels (18 uses PWM!).
#LED_PIN        = 10      # GPIO pin connected to the pixels (10 uses SPI /dev/spidev0.0).
LED_FREQ_HZ    = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA        = 10      # DMA channel to use for generating signal (try 10)
LED_BRIGHTNESS = 75     # Set to 0 for darkest and 255 for brightest
LED_INVERT     = False   # True to invert the signal (when using NPN transistor level shift)
LED_CHANNEL    = 0       # set to '1' for GPIOs 13, 19, 41, 45 or 53
LED_TYPE       = ws.WS2812_STRIP

# Create NeoPixel object with appropriate configuration.
strip = Adafruit_NeoPixel(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL, LED_TYPE)
# Intialize the library (must be called once before other functions).
strip.begin()

#Setup Sockets for listening for Commands
if protocol_mode == "TCP":
	serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #SOCK_STREAM (TCP) or SOCK_DGRAM (UDP)
	serversocket.bind((HOST, PORT))
	serversocket.listen(1)

if protocol_mode == "UDP":
	serversocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) #SOCK_STREAM (TCP) or SOCK_DGRAM (UDP)
	serversocket.bind((HOST, PORT))

#Get the Config File
#Get the Config File and Do nothing else until it been seen.
while config == False:
	print "Getting Config"
	config = GetConfig()
	if config == False:
		StopLED()
		LED_thread = threading.Thread(target=FlipFlop, args=(strip , Color(255,128,0))) #GetConfig returned false ie. Error
		LED_thread.start()
		time.sleep(5)
	else:
		#Config has been received continue with program!
		StopLED()

#Start Thread for the sockets
print "Starting Socket Thread"
socket_run = True
socket_thread = threading.Thread(target=SocketThread)
socket_thread.setDaemon(True)
socket_thread.start()

#Start Thread for the Watchdog timer
wd_running = True
print "Starting Watchdog Thread"
wd_run = True
WD_thread = threading.Thread(target=WatchDog)
WD_thread.setDaemon(True)
WD_thread.start()

print ('Press Ctrl-C to quit.')


try:

	#print "Debug and Thread creation?"
	LED_thread = threading.Thread(target=DebugLED, args=(strip, Color(0,255,0))) #On and Ready
	LED_thread.start()
	last_command = "start"
	print "Debug Showing Version: " + version		

	while True:

		#print "-= Main Loop =-"

		#Keep the Watchdog Thread Active
		wd_running = True

		#Check if we are doing something based on the doing_what being filled in by the socket
		if doing_what.upper() != "":
			print "Doing What: " + doing_what
			print "Arg 1: " + arg_1
			print "Arg 2: " + arg_2

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
				LED_thread = threading.Thread(target=FlipFlop, args=(strip, Color(int(color[0]),int(color[1]),int(color[2]))))
				LED_thread.start()
			except:
				print "Flip Flop Error"

		if doing_what.upper() == "FILL": #FILL <HEXColor>
			StopLED()
			try:
				color = tuple(int(arg_1[i:i+2], 16) for i in (0, 2, 4))
				if arg_2 == "":
					arg_2 = 60
				if arg_2 >= 60:
					arg_2 = 60
				print str(color)
				colorFill(strip, Color(int(color[0]),int(color[1]),int(color[2])), 60)
			except:
				print "FILL Error " + str(arg_1) +" "+ str(arg_2)

		if doing_what.upper() == "WIPE": #WIPE <HEXColor> <speed>
			StopLED()
			try:
				color = tuple(int(arg_1[i:i+2], 16) for i in (0, 2, 4))
				if arg_2 == "":
					arg_2 = default_speed
				if arg_2 >= max_speed:
					arg_2 = max_speed
				LED_thread = threading.Thread(target=colorWipe, args=(strip, Color(int(color[0]),int(color[1]),int(color[2])), int(arg_2)) )
				LED_thread.start()
			except:
				print "Wipe Error"

		if doing_what.upper() == "CHASE":  #Chase <Color> <Speed>
			StopLED()
			try:
				color = tuple(int(arg_1[i:i+2], 16) for i in (0, 2, 4))
				if arg_2 == "":
					arg_2 = default_speed
				if arg_2 >= max_speed:
					arg_2 = max_speed
				LED_thread = threading.Thread(target=theaterChase, args=(strip, Color(int(color[0]),int(color[1]),int(color[2])), int(arg_2)) )
				LED_thread.start()
			except:
				print "Chase Error"

		if doing_what.upper() == "BEAT":
			StopLED()
			try:
				color = tuple(int(arg_1[i:i+2], 16) for i in (0, 2, 4))
				if arg_2 == "":
					arg_2 = default_speed
				if arg_2 >= max_speed:
					arg_2 = max_speed
				LED_thread = threading.Thread(target=Beat, args=(strip, Color(int(color[0]),int(color[1]),int(color[2])), arg_2 ))
				LED_thread.start()
			except:
				print "Beat Error"

		if doing_what.upper() == "RBEAT":
			StopLED()
			try:
				color = tuple(int(arg_1[i:i+2], 16) for i in (0, 2, 4))
				if arg_2 == "":
					arg_2 = default_speed
				if arg_2 >= max_speed:
					arg_2 = max_speed
				LED_thread = threading.Thread(target=RBeat, args=(strip, Color(int(color[0]),int(color[1]),int(color[2])), arg_2 ))
				LED_thread.start()
			except:
				print "Beat Error"

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
				print "Beat Error"

		if doing_what == "REBOOT":
			StopLED()
			os.system('reboot now')

		if doing_what == "SHUTDOWN":
			StopLED()
			os.system('shutdown now')

		if doing_what == 'STOP':
			StopLED()



		doing_what = ""
		arg_1 = ""
		arg_2 = ""
		time.sleep(1)
		
except KeyboardInterrupt:
	print "Keyboard Interrupt Starting to Exit"
	exit_event.set()
	#Blanking LED
	StopLED()
	print "Turning off LEDs"
	colorFill(strip, Color(0,0,0))
	strip.show()	
	#Exiting
	print "Exiting"
	sys.exit(0)
