import RPi.GPIO as gpio
import time
import spidev
from threading import Thread
import csv
from datetime import datetime
import math


def RGB_LED(R, G, B):
    p1.ChangeDutyCycle(R)
    p2.ChangeDutyCycle(G)
    p3.ChangeDutyCycle(B)


# Function to read SPI data from MCP3008 chip
# Channel must be an integer 0-7
def ReadChannel(channel):
    response = spi.xfer2([1,(8+channel)<<4,0])   #1000 0000    Start byte 00000001, channel selection: end byte
    data = ((response[1]&3) << 8) + response[2]         #011
    return data


# Function to convert data to voltage level,
# rounded to specified number of decimal places.
def ConvertVolts(data, places):
    volts = (data * 3.3) / float(1023)
    volts = round(volts, places)
    return volts


def translate(value, leftMin, leftMax, rightMin, rightMax):
    # Figure out how 'wide' each range is
    leftSpan = leftMax - leftMin
    rightSpan = rightMax - rightMin

    # Convert the left range into a 0-1 range (float)
    valueScaled = float(value - leftMin) / float(leftSpan)

    # Convert the 0-1 range into a value in the right range.
    return rightMin + (valueScaled * rightSpan)


# Round up numbers, used in syncronizing time stamps for sensor data
def round_up(n, decimals=0):
    multiplier = 10 ** decimals
    return math.ceil(n * multiplier) / multiplier


# Used to track the operating mode of Pi
class ModeDevice:
    
    def __init__(self, mode='ms'):
        self._running = True
        self._mode = mode

    def terminate(self):
        self._running = False
        #gpio.cleanup()
    
    def set_value(self, new_value):
        if self._mode != new_value:
            
            # pre change
            
            temp = self._mode
            
            if new_value == 'ms':
                print("Stopped recording...", self._filename)
            
            self._mode = new_value
            
            time.sleep(.1)
            
            # post
            if temp is 'ms' and new_value in ['ord','rdm']:
                
                # Set filename to date
                self._filename = datetime.now().strftime('%Y%m%d%H%M%S')+'.txt'
                print("Recording data... {1}".format(new_value, self._filename))
                
        

    def run(self):
        
        while self._running:
            
            if gpio.event_detected(sw_in):
                
                gpio.remove_event_detect(sw_in)
                now = time.time()
                count = 1
                gpio.add_event_detect(sw_in,gpio.RISING)
                while time.time() < now + 1: # 1 second period
                 if gpio.event_detected(sw_in):
                    count +=1
                    time.sleep(.3) # debounce time
                #print (count)
                gpio.remove_event_detect(sw_in)
                gpio.add_event_detect(sw_in,gpio.FALLING)

                if count == 1:
                    #self._mode = 'ord'
                    self.set_value('ord')
                elif count == 2:
                    #self._mode = 'ms'
                    self.set_value('ms')
                elif count == 3:
                    #self._mode = 'rdm'
                    self.set_value('rdm')
                    

# Class for threading sonic sensor
class Sonic(Thread):
    
    def __init__(self):
        self._running = True
        self._distance = None
        self._RGB_Values = None

    def terminate(self):  
        self._running = False
        #gpio.cleanup()

    def run(self):
        
        while self._running:
        
            time.sleep(.1)  # sampling rate
            
            #sending a pulese to trig pin
            gpio.output(trig, True)
            time.sleep(0.00001)
            gpio.output(trig, False)
    
            while gpio.input(ECHO)==0:               #Check whether the ECHO is LOW
                pulse_start = time.time()              #Saves the last known time of LOW pulse

            while gpio.input(ECHO)==1:               #Check whether the ECHO is HIGH
                pulse_end = time.time()                #Saves the last known time of HIGH pulse 

            pulse_duration = (pulse_end - pulse_start)*1000000 #Get pulse duration to a variable in uS

            self._distance = pulse_duration / 58.0        #Multiply pulse duration by 17150 to get distance
            self._distance = round(self._distance - 0.5, 2)            #Round to two decimal points

            if self._distance < 3:      #Check whether the distance is within range
                
                scale = 0
                
            elif self._distance > 3 and self._distance < 20:
                
                # map rgb to distance
                scale = translate(self._distance, 3, 20, 0, 50)               
                
            else:
                scale = 50

            
            # Turn off RGB in ORD mode
            if mode_obj._mode != 'ord':
            
                RGB_LED(100-scale,0,scale)
                x = int(scale*2.55)        
                self._RGB_Values = [255 - x, 0, x]
                
                # blink if less than 3 cm
                
                if scale == 0:
                    time.sleep(.25)
                    RGB_LED(0,0,0)
                    time.sleep(.15)
            else:
                RGB_LED(0,0,0)


# Class for threading SPI Sensor
class SPIDevice(Thread):
    
    def __init__(self):
        self._running = True
        self._angle = None
        self._freq = None

    def terminate(self):  
        self._running = False
        #gpio.cleanup()

    def run(self):
 
        while self._running:
            
            time.sleep(.03)
            
            pot_level = ReadChannel(pot_channel)
            pot_volts = ConvertVolts(pot_level, 2)
            self._angle = round((pot_volts*100)/3.3,2)
            
            self._freq = int(translate(pot_level, 0, 1024, 100, 2000))
            
            # Turn off Buzzer in ORD mode 
            if mode_obj._mode != 'ord':
                Buzz.ChangeFrequency(self._freq)
                Buzz.ChangeDutyCycle(50)
            else:
                Buzz.ChangeDutyCycle(0)
            

# Class to simultaneously thread LED      
class LED(Thread):
    
    def __init__(self):
        self._running = True

    def terminate(self):  
        self._running = False
        #gpio.cleanup()

    def run(self):
       
        while self._running:
            
            time.sleep(.5)
            
            if mode_obj._mode == 'ms':
                gpio.output(LED_pin, False)
                
            elif mode_obj._mode == 'rdm':
                gpio.output(LED_pin, True)
                
            elif mode_obj._mode == 'ord':
                            
                gpio.output(LED_pin, True)
                time.sleep(.5)
                gpio.output(LED_pin, False)            


## GPIO Setup

RGB_r = 29
RGB_g = 31
RGB_b = 33

LED_pin = 8

Buzzer = 12

ECHO = 18
trig = 22

sw_in = 36

pot_channel = 0


gpio.setmode(gpio.BOARD)
gpio.setwarnings(False)

# Switch
gpio.setup(sw_in, gpio.IN, pull_up_down=gpio.PUD_UP)
gpio.add_event_detect(sw_in,gpio.FALLING)

# RGB
RGB = [RGB_r, RGB_g, RGB_b]
gpio.setup(RGB, gpio.OUT, initial=gpio.HIGH)

rgbfreq = 100
rgbdc = 50

p1 = gpio.PWM(RGB[0], rgbfreq)
p2 = gpio.PWM(RGB[1], rgbfreq)
p3 = gpio.PWM(RGB[2], rgbfreq)

p1.start(rgbdc)
p2.start(rgbdc)
p3.start(rgbdc)

RGB_LED(0,0,0)

# LED
gpio.setup(LED_pin, gpio.OUT, initial=gpio.LOW)

# Buzzer
gpio.setup(Buzzer, gpio.OUT)
global Buzz # Assign a global variable to replace GPIO.PWM
Buzz = gpio.PWM(Buzzer,440) # 440 is initial frequency.
Buzz.start(50)


# Sonic
gpio.setup(ECHO, gpio.IN)
gpio.setup(trig, gpio.OUT, initial=gpio.LOW)


# SPI

spi = spidev.SpiDev()
spi.open(0, 0)  # open spi port 0, device (CS) 0
spi.max_speed_hz=1000000

        
if __name__ == '__main__': # Program start from here
    
    try:   
 
        print('Starting sonic..')
        sonic = Sonic()
        sonicThread = Thread(target=sonic.run)
        sonicThread.start()
        
        print('Starting SPI..')
        SPI = SPIDevice()
        SpiThread = Thread(target=SPI.run) 
        SpiThread.start()
        
        print('Starting LED..')
        led = LED()
        ledThread = Thread(target=led.run) 
        ledThread.start()
        
        print('Starting ModeDevice..')
        mode_obj = ModeDevice()
        modeThread = Thread(target=mode_obj.run) 
        modeThread.start()
        
        # Start threads
        time.sleep(.5)
        
        # Pre configure parameteres for running socket connections
        count = 0
        buffer = []
        
        while True:
            
            #time.sleep(.0933)
            
            now = time.time()
            
            
            if mode_obj._mode == 'ms':
                print('Dist: {:<7}, RGB: {:<13}, Angle: {:<5}, Freq: {:<4}'.format(sonic._distance,
                                                                     str(sonic._RGB_Values),
                                                                     SPI._angle,
                                                                     SPI._freq))
                
            else:
                
                time.sleep( round_up(time.time(), 1) - time.time() )
                
                buffer.append(['Sonic',datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],round(sonic._distance, 2)])
                count += 1
                                
                # upload SPI every .5 seconds
                if count % 5 == 0:
                    buffer.append(['SPI',datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],round(SPI._angle, 2)])
                    
                # send / reset buffer every 4 seconds
                if count % 30 == 0:
                    
                    with open(mode_obj._filename, "a", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerows(buffer)
                    buffer = []
                    count = 0
            
        
    except KeyboardInterrupt: # When 'Ctrl+C' is pressed, the child program destroy() will be executed.
        
            
        SPI.terminate()
        sonic.terminate()
        led.terminate()
        mode_obj.terminate()
    
        # Wait for while loops to end
        time.sleep(1)

        Buzz.stop() # Stop the BuzzerPin
        spi.close() # Stop SPI 
        
        p1.stop()
        p2.stop()
        p3.stop()
        
        gpio.cleanup() # Release resource


