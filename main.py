# ---------------------------------------------------------------------
# Program:     GPS-TTN
# Author:      Marco Rainone - Wireless Lab ICTP
# email:       mrainone@ictp.it / mrainone@libero.it
# Ver:         1.0
# Last Update: 2019/02/04
#
# micropython program for acquiring the gps position and send it to TTN using lorawan.
# GPS library used:
# https://github.com/gregcope/L76micropyGPS
# ---------------------------------------------------------------------
import machine
import pycom
import math
import time
import utime
import struct
import socket
import binascii
from network import LoRa
from L76micropyGPS import L76micropyGPS
from micropyGPS import MicropyGPS
from pytrack import Pytrack
import gc
import LEDColors

# ======================================================
# main
# ======================================================
#
#----------------------------------------------
# CONFIGURATION
#
# TTN join configuration parameters - here for pytrack-03-w-lopy
dev_addr = struct.unpack(">l", binascii.unhexlify('260110AB'))[0]
nwk_swkey = binascii.unhexlify('F5DB25C7984F21CBCB672679255381E9')
app_swkey = binascii.unhexlify('61F3D09AA61D0262575BDB38DEDDC3BE')
#
# delay in msec to repeat loop
DelayLoopLogger = 20000                 # wait 20sec for logger loop

#----------------------------------------------
# START GPS LOGGER
#----------------------------------------------
#
gc.enable()                             # enable GC

#----------------------------------------------
py = Pytrack()                          # Start GPS, you need this line

# Start a microGPS object, you need this line
my_gps = MicropyGPS(location_formatting='dd')

# Start the L76micropyGPS object, you need this line
L76micropyGPS = L76micropyGPS(my_gps, py)

# Start the thread, you need this line
gpsThread = L76micropyGPS.startGPSThread()

print("startGPSThread thread id is: {}".format(gpsThread))

#start rtc
rtc = machine.RTC()

#----------------------------------------------
# USE LED TO SIGNAL THE OPERATING PHASES
pycom.heartbeat(False)          # stop the heartbeat
led = LEDColors.pyLED()
led.setLED('red')               # initialize led: led red

#----------------------------------------------
print ("setting up LoRa")
# Initialize LoRaWAN radio
lora = LoRa(mode=LoRa.LORAWAN, region=LoRa.EU868)

# Set network keys
app_eui = binascii.unhexlify('70B3D57ED001825F')
app_key = binascii.unhexlify('0F422B11DCFE3853380083B1F41D4895')

# Join the network
lora.join(activation=LoRa.OTAA, auth=(app_eui, app_key), timeout=0)
led.setLED('red')

# Loop until joined
while not lora.has_joined():
    print('Not joined yet...')
    led.setLED('yellow')
    time.sleep(0.1)
    led.setLED('red')
    time.sleep(2)

print('Joined')
led.setLED('blue')
time.sleep(5)

while True:
    tStart = utime.ticks_ms()           # start cycle uptime
    time.sleep(5)
    latitude = my_gps.latitude[0]
    longitude = my_gps.longitude[0]
    altitude = my_gps.altitude
    print ("Latitude = ", latitude)
    print ("Longitude = ", longitude)
    print ("Altitude = ", altitude)
    tmFix = my_gps.time_since_fix()
    print ("time since last fix: ", tmFix)

    # continue loop until fix
    OkCoord = True                      # int flag for gps position ok
    if tmFix <= 0:
        OkCoord = False
        continue

    if (OkCoord):
        led.setLED('yellow')            # yellow: read gps coord. OK

        # valid range of latitude in degrees is -90 and +90
        lat = int(float(latitude) * 10000)
        # Longitude is in the range -180 and +180 specifying coordinates west and east of the Prime Meridian, respectively.
        lon = int(float(longitude) * 10000)
        alt = int(float(altitude))
        # now lat, lon are integer values with these limits:
        # lat: ( -900000,  +900000) in decimal format. Hex: (F2445F, 0DBBA0), 3 bytes, 24 bit
        # lon: (-1800000, +1800000) in decimal format. Hex: (E488BF, 1B7740), 3 bytes, 24 bit
        # alt: 2 bytes

        #----------------------------------------------
        # FORM THE MESSAGE TO SEND TTN
        #
        ttnData = bytearray()
        #
        # form msg to send
        # latitude, write 3 bytes
        ttnData.append((lat>>16) & 0xFF)
        ttnData.append((lat>>8) & 0xFF)
        ttnData.append( lat & 0xFF )
        # longitude, write 3 bytes
        ttnData.append((lon>>16) & 0xFF)
        ttnData.append((lon>>8) & 0xFF)
        ttnData.append( lon & 0xFF )
        # altitude, write 2 bytes
        ttnData.append((alt>>8) & 0xFF)
        ttnData.append( alt & 0xFF )

        print("Sending GPS position via LoRa")
        s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)
        s.setsockopt(socket.SOL_LORA, socket.SO_DR, 5)
        s.setblocking(False)
        s.send(ttnData)                 # send data to TTN
        s.settimeout(3.0) # configure a timeout value of 3 seconds
        try:
           rx_pkt = s.recv(64)   # get the packet received (if any)
           print(rx_pkt)
        except socket.timeout:
          print('No packet received')
        led.setLED('green')         # green: msg sent to TTN. OK

    # led lamp delay
    time.sleep(1)                   # delay 1 second
    led.setLED('off')               # led off

    tEnd = utime.ticks_ms()         # end cycle uptime
    msecSleep = DelayLoopLogger - (tEnd - tStart)
    print("start sleep ...{}msec".format(msecSleep))
    if msecSleep <= 0:
        msecSleep = 500             # 500msec min sleep time

    # sleep
    # machine.deepsleep(msecSleep)  # go to deepsleep.
    utime.sleep_ms(msecSleep)
