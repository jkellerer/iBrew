#!/usr/bin/python
# -*- coding: utf8 -*-

import socket
import sys
import struct
import random
import select

from iBrewProtocol import *

#------------------------------------------------------
# iBrew CLIENT
#
# Client to iKettle 2.0 or Smarter Coffee Devices
#------------------------------------------------------

class iBrewClient:

    #------------------------------------------------------
    # NETWORK CONNECTION: iKettle 2.0 & Smarter Coffee
    #------------------------------------------------------

    def connect(self, host):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except socket.error, msg:
            print 'iBrew: Failed to create socket. Error code: ' + str(msg[0]) + ' , Error message : ' + msg[1]
            return False
        try:
            self.socket.connect((host, iBrewPort))
        except socket.error, msg:
            print 'iBrew: Failed to connect to host (' + host + ') Error code: ' + str(msg[0]) + ' , Error message : ' + msg[1]
            return False
        self.log = False
        self.read()
        self.info()
        self.calibrate_base()
        self.host = host
        
        return True

    def __init__(self,host, auto_connect = "True"):
        if auto_connect:
            if not self.connect(host):
                sys.exit()

    def __del__(self):
        self.socket.close()

    #------------------------------------------------------
    #  NETWORK PROTOCOL: iKettle 2.0 & Smarter Coffee
    #------------------------------------------------------

    # read a protocol message
    def read_message(self):
        try:
            message = ""
            i = 0
            # let the buffer of the os handle this
            data = self.socket.recv(1)
            while data != iBrewTail:
                message += data
                data = self.socket.recv(1)
                i += 1
            message += data
            return message
        except socket.error, msg:
            print 'iBrew: Failed to read message. Error code: ' + str(msg[0]) + ' , Error message : ' + msg[1]

    # read a protocol message and decode it to internal variables
    def read(self):
     
        message = self.read_message()
     
        # Command Status
        if message[0] == iBrewResponeStatus:
            statusCommand = struct.unpack('B',message[1])[0]
            if not iBrewStatusCommand.has_key(statusCommand):
                statusCommand = 0xff
    
        # Calibration
        elif message[0] == iBrewResponeCalibrationBase:
            self.waterlevelBase = struct.unpack('B',message[2])[0] + 256 * struct.unpack('B',message[1])[0]
        
        # Device Info
        elif message[0] == iBrewResponeDeviceInfo:
            self.isSmarterCoffee = False
            self.isKettle2 = False
            if struct.unpack('B',message[1])[0] == 1:
                self.isKettle2 = True
                self.device = "iKettle 2.0"
            if struct.unpack('B',message[1])[0] == 2:
                self.isSmarterCoffee = True
                self.device = "SmarterCoffee"
            self.version = struct.unpack('B',message[2])[0]
        
        # Device Status
        elif message[0] == iBrewResponeStatusDevice:
            #self.unknown      = struct.unpack('B',message[5])[0]
            self.status      = struct.unpack('B',message[1])[0]
            self.temperature = struct.unpack('B',message[2])[0]
            self.waterlevel  = struct.unpack('B',message[4])[0] + 256 * struct.unpack('B',message[3])[0]
            if self.temperature == iBrewOffBase:
                self.onbase = False
            else:
                self.onbase = True
                
        if self.log:
            self.print_message_received(message)
     
        return message

    # send a protocol message and wait's for response...
    def send(self,message):
        try:
            if len(message) > 0 and message[len(message)-1] == iBrewTail:
                self.socket.send(message)
                if self.log:
                    self.print_message_send(message)
            elif len(message) > 0:
                self.socket.send(message+iBrewTail)
                if self.log:
                    self.print_message_send(message+iBrewTail)
            else:
                return
    

        except socket.error, msg:
            print 'iBrew: Failed to send message. Error code: ' + str(msg[0]) + ' , Error message : ' + msg[1]

        # keep reading until we got the response message
        # if a message does not generate a response... we're in deep shit... FIX!
        x = self.read()
        while x[0] == iBrewResponeStatusDevice:
            x = self.read()
 
        self.local = False
        
        # keep reading until we got the device status message
        y = self.read()
        while y[0] != iBrewResponeStatusDevice:
            y = self.read()
            self.local = True
        return x

    #------------------------------------------------------
    #  NETWORK CONVERTERS: iKettle 2.0 & Smarter Coffee
    #------------------------------------------------------

    # Convert raw data to hex string without 0x seperated by spaces
    def message_to_string(self,message):
        raw = ""
        for x in range(0,len(message)):
            y = struct.unpack('B',message[x])[0]
            if y < 0x10:
               raw += "0"
            raw += hex(y)[2:4] + " "
        return raw

    # Convert hex string without 0x input maybe seperated by spaces or not
    def string_to_message(self,code):
        message = ""
        
        if len(code) > 2 and code[2] != " ":
            if len(code) % 2 == 0:
                try:
                    message = code.decode("hex")
                except:
                    print "iBrew: Invalid Input: Error encoding hex \'" + code + "\'"
            else:
                print "iBrew: Invalid Input: Missing character on position: " + str(len(code)+1)
        elif len(code) % 3 == 2:
            for x in range(0,(len(code) / 3)+1):
                if x > 0:
                    if code[x*3-1] != ' ':
                        print "iBrew: Invalid Input: Expected space character on position: " + str(x*3)
                        break
                s = code[x*3]+code[x*3+1]
                try:
                    message +=  s.decode("hex")
                except:
                    print "iBrew: Invalid Input: Error encoding hex \'" + s + "\' on position: " + str(x*3+1)
        else:
            print "iBrew: Invalid Input: Missing character on position: " + str(len(code)+1)
        return message


    #------------------------------------------------------
    # CONVERTERS: iKettle 2.0
    #------------------------------------------------------

    def cups(self):
        s = cups_string()
        if s == "Empty" or s == "Not enough water":
            return 0
        if s == "Full":
            return 7
        return s[1]

    # Fix Check value's
    def cups_string(self):
        if self.waterlevel < 850:
            return "Empty"
        elif self.waterlevel >=  850 and self.waterlevel < 1050:
            return "Not enough water"
        elif self.waterlevel >= 1050 and self.waterlevel < 1380:
            return "1 Cup"
        elif self.waterlevel >= 1400 and self.waterlevel < 1600:
            return "2 Cups"
        elif self.waterlevel >= 1600 and self.waterlevel < 1800:
            return "3 Cups"
        elif self.waterlevel >= 1800 and self.waterlevel < 2000:
            return "4 Cups"
        elif self.waterlevel >= 2000 and self.waterlevel < 2200:
            return "5 Cups"
        elif self.waterlevel >= 2200 and self.waterlevel < 2500:
            return "6 Cups"
        elif self.waterlevel >= 2500:
            return "Full"

    #------------------------------------------------------
    # PRINT: iKettle 2.0 & Smarter Coffee
    #------------------------------------------------------

    def print_message_send(self,message):
        print "iBrew: Message Send " + self.message_to_string(message)
        # FIX print from protocol here...

    def print_message_received(self,message):
      #  if message[0] != iBrewResponeStatusDevice:
        print "iBrew: Message Received: " + self.message_to_string(message)
        """
        if message[0] == iBrewResponeStatus:
            print
            #print "       Action Status: " + iBrewStatusCommand[message[1]]
        elif message[0] == iBrewResponeWifiList:
            print '       Wifi Not Implemented'
        elif message[0] == iBrewResponeWifiFirmware:
            print '       Wifi Firmware Not Implemented'
        elif message[0] == iBrewResponeUnknown:
            print '       Unknown Message Not Implemented'
        elif message[0] == iBrewResponeDeviceInfo:
            print "       Device Info: " + self.device + " Firmware v" + str(self.version)
        elif message[0] == iBrewResponeCalibrationBase:
            print "       Calibration Base Value: " +  str(self.calibration)
        elif message[0] != iBrewResponeStatusDevice:
            print "       Unknown Reply Message"
        """

    def print_status(self):
        print
        if self.isKettle2 == True:
            if self.onbase:
                print "Status       " + iBrewStatusKettle[self.status]
                print "Kettle       On Base"
                print "Temperature  " + str(self.temperature) +  "ºC"
                print "Water level  " + self.cups_string() + " left " + str(self.waterlevel-self.waterlevelBase) + "ml (" + str(self.waterlevel) + ":" + str(self.waterlevelBase) + ")"
            else:
                print "Status       " + iBrewStatusKettle[self.status]
                print "Kettle       Not On Base"
        if self.isSmarterCoffee == True:
            print "Status       ?"
        print

    def print_short_status(self):
        if self.isKettle2 == True:
            if self.onbase:
                print "iBrew: " + iBrewStatusKettle[self.status] + " On Base (" + str(self.temperature) + "ºC, " + str(self.waterlevel) + " ["+ self.cups_string() + "])"
            else:
                print "iBrew: " + iBrewStatusKettle[self.status] + " Not On Base"
        if self.isSmarterCoffee == True:
            print "iBrew: ?"

    def print_connect_status(self):
        print "iBrew: Connected to " + self.device + " Firmware v" + str(self.version) + " (" + self.host + ")"

    #------------------------------------------------------
    # COMMANDS: iKettle 2.0 & Smarter Coffee
    #------------------------------------------------------

    def info(self):
        self.send(iBrewCommandInfo)
  
    #------------------------------------------------------
    # COMMANDS: iKettle 2.0
    #------------------------------------------------------

    def calibrate(self):
        self.send(iBrewCommandCalibrate)

    def calibrate_base(self):
        self.send(iBrewCommandCalibrateBase)

    def off(self):
        self.send(iBrewCommandOff)
    
    def on(self):
        self.send(iBrewCommandOn)

    #------------------------------------------------------
    # COMMANDS: Smarter Coffee
    #------------------------------------------------------

    def hotplate_off(self):
        if self.isSmarterCoffee == True:
            self.send(iBrewCommandHotplateOff)
        else:
            print 'iBrew: The device does not have a hotplate'

    def hotplate_on(self, timer=5):
        if self.isSmarterCoffee == True:
            self.send(iBrewCommandHotplateOn)
            print 'iBrew: The device does not have a hotplate'

    def grinder(self):
        if self.isSmarterCoffee == True:
            self.send(iBrewCommandGrinder)
        else:
            print 'iBrew: The device does not have a grinder'

    def number_of_cups(self,number=1):
        if self.isSmarterCoffee == True:
            if number < 1 or number > 12:
                print 'iBrew: Invalid Number of Cups: ',number
            self.send(iBrewCommandGrinder+str(number))
        else:
            print 'iBrew: The device does not let you choose the number of cups to brew'

    def coffee_strength(self,strength=1):
        if self.isSmarterCoffee == True:
            if strength == "weak":
                number = 0
            elif strength == "medium":
                number = 1
            elif strength == "strong":
                number = 2
            else:
                print 'iBrew: Invalid Strength: ',strength
            if number:
                self.send(iBrewCommandStrenght+str(number))
        else:
            print 'iBrew: The device does not let you choose the coffee strength'

    def raw(self,code):
        self.send(self.string_to_message(code))