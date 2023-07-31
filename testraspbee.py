from flask import Flask, render_template, url_for, request, redirect, make_response
import os
import threading
import requests
import RPi.GPIO as GPIO
import cgitb
import spidev
import time
from pushbullet import Pushbullet
import json

# Ubeac vars
url = "http://orientationproject2.hub.ubeac.io/Raspbee"
uid = "raspbee"


# GPIO Setup
GPIO.setwarnings(False)
cgitb.enable()
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
pins = [17, 18, 2]
for i in pins:
    GPIO.setup(i, GPIO.OUT)
Light = GPIO.input(2)

# Flask & SPI vars
app = Flask(__name__)
spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1000000

# Bushbullet setup
pb = Pushbullet("o.vGKOskJDOGrPWgFwwcGSAkt1J3mC5XdR")
print(pb.devices)
dev = pb.get_device('OnePlus 7 Pro')

# Fucntions
# Potentiometer fucntion
def readpot(potmeter):
    if ((potmeter > 7) or (potmeter < 0)):
        return -1
    r = spi.xfer2([1, (8 + potmeter) << 4, 0])
    time.sleep(0.000005)
    potout = ((r[1] & 3) << 8) + r[2]
    return potout

# LED Blink function
def blink(pin):
	GPIO.output(pin, 1)
	time.sleep(0.2)
	GPIO.output(pin, 0)
	time.sleep(0.2)
	
# LED SOS function
def sos(pin):
    for i in range(3):
        GPIO.output(pin, 1)
        time.sleep(0.5)
        GPIO.output(pin, 0)
        time.sleep(0.5)

# Starting program
print("Aan het berekenen...")
warmte = round(((readpot(0)/1024)*100-50), 2)
oogst = readpot(1)

#Flask
@app.route('/', methods=["GET", "POST"])
def main():
    # Turning LED on and off via webapp
    status = request.args.get('status')
    if status == "on":
        GPIO.output(2, GPIO.HIGH)
        Light = True
    elif status == "off":
        GPIO.output(2, GPIO.LOW)
        Light = False
    sound = request.args.get('sound')
    # Playing sound via webapp
    if sound == "on":
        os.system('mpg321 sound.mp3 &')
    return render_template('index.html')

# Sending data
@app.route('/data', methods=["GET", "POST"])
def data():
    temperature = round(((readpot(0)/1024)*100-50), 2)
    weight = round(((readpot(1)/1024)*50), 2)
    data = [time.time() * 1000, temperature, weight, Light]
    response = make_response(json.dumps(data))
    response.content_type = 'application/json'
    return response

# Thead for running flask
def thread_webapp():
    if __name__ == '__main__':
        app.run(debug=False, host='192.168.0.163')

# Main thread
def thread_main():
    try:
        # Vars so pushbullet doesn't send a notification on every read
        alertWarmte = False
        alertOogst = False
        while True:       
            warmte = round(((readpot(0)/1024)*100-50), 2)
            oogst = round(((readpot(1)/1024)*50), 2)
            
            # Checking upper and lower limits
            if warmte > 30 != True:
                print("WARNING - ", "Temperatuur is te hoog!", warmte, "°C")
                sos(17)
                sos(18)
                if not alertWarmte:
                    push = dev.push_note("Opgelet!","De temperatuur is te hoog!")
                    alertWarmte = True

            elif 0 < warmte < 30  != True:
                print("Temperatuur is Goed", warmte, "°C")
                alertWarmte = False

            elif warmte < 0 != True:
                print("Warning - ", "Temperatuur is Te koud!", warmte, "°C")
                blink(17)
                if not alertWarmte:
                    push = dev.push_note("Opgelet!","De temperatuur is te laag!")
                    alertWarmte = True

            if oogst > 18 != True:
                print("Warning - ", "Korf is Vol!")
                sos(18)
                if not alertOogst:
                    push = dev.push_note("Opgelet!","De korf is vol!")
                    alertOogst = True

            elif 2 < oogst < 18 != True:
                print("Korf is Goed")
                alertOogst = False

            elif oogst < 2 != True:
                print("WARNING ", " Korf is Leeg")
                if not alertOogst:
                    push = dev.push_note("Opgelet!","De korf is leeg! Vul honingraten aan.")
                    alertOogst = True
            time.sleep(2)

    except KeyboardInterrupt:
        GPIO.cleanup()

# Ubeac thread
# Using ubeac since the webapp doesn't have data consistancy and for extra redundancy      
def thread_ubeac():
    while True:
        data1= {
            "id": "raspbee",
            "sensors": [{
                "id": "adc kanaal0",
                "data": round(((readpot(0)/1024)*100-50), 2)
            }]
        }

        data2= {
            "id": "raspbee",
            "sensors": [{
                "id": "adc kanaal1",
                "data": round(((readpot(1)/1024)*50), 2)
            }]
        }

        requests.post(url, verify=False, json=data1)
        print("sending data 1:", round(((readpot(0)/1024)*100-50), 2))
        time.sleep(1)
        requests.post(url, verify=False, json=data2)
        print("sending data 2:", round(((readpot(1)/1024)*50), 2))
        time.sleep(1)

# Threads
t1 = threading.Thread(target=thread_main)
t2 = threading.Thread(target=thread_webapp)
t3 = threading.Thread(target=thread_ubeac)
t1.start()
t2.start()
t3.start()
