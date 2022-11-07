from doctest import ELLIPSIS_MARKER
import os
import paho.mqtt.client as mqtt
from apscheduler.schedulers.background import BackgroundScheduler
import random


BROKER_IP = "192.168.0.2"
BROKER_PORT = 1883

SN_INV = ["1", "2"]
INV_SOUTH = 0

INV_NORTH = 1

DTU_TOPIC = "solar/"

SET_ABS_LIMIT = {}
SET_INV_ON = {}

for sn in SN_INV:
    SET_ABS_LIMIT[sn] = DTU_TOPIC + sn + "/cmd/limit_nonpersistent_absolute"
    SET_INV_ON[sn] = DTU_TOPIC + sn + "/cmd/power"

SIMUALTOR_INTERVAL = 5.0

YES = 1
NO = 0

POWER_CURVE = random.sample(range(0, 800), 20)
POWER_CURVE.sort()

for num in reversed(POWER_CURVE):
	POWER_CURVE.append(num)

# Variabels
invAcPower = {}
invIsProducting = {}
powerCurveCounter = 0
invLimit = {SN_INV[INV_NORTH] : 300, SN_INV[INV_SOUTH] : 600}


for sn in SN_INV:
    invAcPower[sn] = 0
    invIsProducting[sn] = YES

def simualtor():
    global invAcPower
    global powerCurveCounter
    
    powerCurveCounter += 1
    if powerCurveCounter > len(POWER_CURVE):
        powerCurveCounter = 0

    snSouth = SN_INV[INV_SOUTH]
    snNorth = SN_INV[INV_NORTH]

    for sn in SN_INV:
        client.publish(DTU_TOPIC + sn + "/status/reachable", "1")

    # BKW north
    if invIsProducting[snNorth] == YES:
        invAcPower[snNorth] = 60
        client.publish(DTU_TOPIC + snNorth + "/status/producing", "1")

    else:
        invAcPower[snNorth] = 0     
        client.publish(DTU_TOPIC + snNorth + "/status/producing", "0")   


    # BKW south
    if invIsProducting[snSouth] == YES:
        if POWER_CURVE[powerCurveCounter] <= invLimit[snSouth]:
            invAcPower[snSouth] = POWER_CURVE[powerCurveCounter]
        else:
            invAcPower[snSouth] = invLimit[snSouth] 
            client.publish(DTU_TOPIC + snSouth + "/status/producing", "1")

    else:
        invAcPower[snSouth] = 0     
        client.publish(DTU_TOPIC + snSouth + "/status/producing", "0")   

    # publish power and current limits
    for sn in SN_INV:
        client.publish(DTU_TOPIC + sn + "/0/power", str(invAcPower[sn]))
        client.publish(DTU_TOPIC + sn + "/status/limit_absolute", str(invLimit[sn]))



# Start background job for limiter
scheduler = BackgroundScheduler()
limiterJob = scheduler.add_job(simualtor, 'interval', seconds = SIMUALTOR_INTERVAL)
scheduler.start()   

# Mqtt
def getSnFromTopic(topic):
    return topic.split("/")[1]

def on_message(client, userdata, message):
    msg = str(message.payload.decode("utf-8"))
    print("message received: ", msg)
    print("message topic: ", message.topic)

def on_connect(client, userdata, flags, rc):
    print("Connected to MQTT Broker: " + BROKER_IP)

def on_message_limit_absolute(client, userdata, message):
    msg = str(message.payload.decode("utf-8"))
    sn = getSnFromTopic(message.topic)
    invLimit[sn] = int(float(msg))

def on_message_producing(client, userdata, message):
    msg = str(message.payload.decode("utf-8"))
    sn = getSnFromTopic(message.topic)
    invIsProducting[sn] = int(float(msg))    

client = mqtt.Client("SIMU")
client.connect(BROKER_IP, BROKER_PORT)

client.on_message = on_message
for sn in SN_INV:
    client.message_callback_add(SET_ABS_LIMIT[sn], on_message_limit_absolute)
    client.message_callback_add(SET_INV_ON[sn], on_message_producing)


client.subscribe([(DTU_TOPIC + "#", 0)])
client.on_connect = on_connect

client.loop_forever()