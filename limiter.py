from doctest import ELLIPSIS_MARKER
import os
import paho.mqtt.client as mqtt
from apscheduler.schedulers.background import BackgroundScheduler

# Constants
try:
    DEBUG = os.environ["DEBUG"]
except:
    DEBUG = True

LIMITER_INTERVAL = 10.0 if DEBUG else float(os.environ["LIMITER_INTERVAL"])
MAX_AC_PWR = 600 if DEBUG else int(os.environ["MAX_AC_PWR"])
INCREMENT = 10 if DEBUG else int(os.environ["INCREMENT"])

BROKER_IP = "192.168.0.2" if DEBUG else os.environ["BROKER_IP"]
BROKER_PORT = 1883 if DEBUG else int(os.environ["BROKER_PORT"])
CLIENT_ID = "pvLimiter" if DEBUG else os.environ["CLIENT_ID"]

SN_INV = ["1", "2"] if DEBUG else str(os.environ['SN_INV']).split(',')
INV_SOUTH = 0
INV_NORTH = 1
LIMIT_SOUTH = 1200

YES = 1
NO = 0

# MQTT Topics
DTU_TOPIC = "solar/#" if DEBUG else os.environ["CLIENT_ID"]
SET_ABS_LIMIT = {}
SET_INV_ON = {}
GET_ABS_LIMIT = {}
GET_AC_PWR = {}
GET_IS_PRODUCING = {}
GET_IS_REACHABLE = {}

for sn in SN_INV:
    SET_ABS_LIMIT[sn] = "solar/" + sn + "/cmd/limit_persistent_absolute"
    SET_INV_ON[sn] = "solar/" + sn + "/cmd/power"
    GET_ABS_LIMIT[sn] = "solar/" + sn + "/status/limit_absolute"
    GET_IS_PRODUCING[sn] = "solar/" + sn + "/status/producing"
    GET_IS_REACHABLE[sn] = "solar/" + sn + "/status/reachable"
    GET_AC_PWR[sn] = "solar/" + sn + "/0/power"

# Variabels
systemAcPower = 5
invAcPower = {}
invLimit = {}
invIsProducting = {}
invIsReachable = {}
threshold = 0;

for sn in SN_INV:
    invAcPower[sn] = 0
    invLimit[sn] = 0
    invIsProducting[sn] = NO
    invIsReachable[sn] = NO

# Limiter
def calcDynamicThreshold(value):
    global threshold
    if (value > threshold):
        threshold = value

def limiter():
    global systemAcPower

    # calc the ac power of the system
    systemAcPower = 0
    for sn in SN_INV:
        systemAcPower += invAcPower[sn]
 
    # This code section is especially for my setup of several BKW
    ############################################################################
    snSouth = SN_INV[INV_SOUTH]
    snNorth = SN_INV[INV_NORTH]

    # If south BKW is not online but north then power it on and control nothing
    if (invIsReachable[snSouth] == NO and invIsReachable[snNorth] == YES):
        if (invIsProducting[snNorth] == NO):
            tunrInverterOn(snNorth, YES)
            return
    
    # If none BKW is reachable then don't control anything
    systemIsReachable = False
    for sn in SN_INV:
        if (invIsReachable[sn] == YES):
            systemIsReachable = True

    if (not systemIsReachable):
        return
      
    # Is the system power < as max AC power?
    # If yes then try to produce more
    if (systemAcPower <= MAX_AC_PWR - threshold - INCREMENT):
        # Is BKW north producing?
        # If not then turn it on
        if (invIsProducting[snNorth] == NO):
            tunrInverterOn(snNorth, YES)
            return
        # If yes check if the power limit of BKW south is already maxed out   
        else:
            # If yes nothing to do
            if (invLimit[snSouth] >= LIMIT_SOUTH):
                return
            # If not then increas the limit by step
            else:
                setLimitNonpersistentAbsolute(snSouth, invLimit[snSouth] + INCREMENT)

    # If not then limit the System to max alowed AC power
    if (systemAcPower > MAX_AC_PWR):
        # Is BKW north producing?
        # If yes then turn it off
        if (invIsProducting[snNorth] == YES):
            tunrInverterOn(snNorth, NO)
            return
        # If not then decrease the limit of BKW south
        else:
            setLimitNonpersistentAbsolute(snSouth, invLimit[snSouth] - INCREMENT)
    ############################################################################

# Start background job for limiter
scheduler = BackgroundScheduler()
scheduler.add_job(limiter, 'interval', seconds = LIMITER_INTERVAL)
scheduler.start()    

# Setup MQTT Client
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

def on_message_reachable(client, userdata, message):
    msg = str(message.payload.decode("utf-8"))
    sn = getSnFromTopic(message.topic)
    invIsReachable[sn] = int(float(msg))

def on_message_power(client, userdata, message):
    msg = str(message.payload.decode("utf-8"))
    sn = getSnFromTopic(message.topic)
    invAcPower[sn] = int(float(msg))

    if (sn == SN_INV[INV_NORTH]):
        calcDynamicThreshold(invAcPower[sn])

#mqtt.Client.connected_flag=False
client = mqtt.Client(CLIENT_ID)
client.connect(BROKER_IP, BROKER_PORT)

client.on_message = on_message

for sn in SN_INV:
    client.message_callback_add(GET_ABS_LIMIT[sn], on_message_limit_absolute)
    client.message_callback_add(GET_IS_PRODUCING[sn], on_message_producing)
    client.message_callback_add(GET_IS_REACHABLE[sn], on_message_reachable)
    client.message_callback_add(GET_AC_PWR[sn], on_message_power)

client.subscribe(DTU_TOPIC)
client.on_connect = on_connect

def setLimitNonpersistentAbsolute(sn, limit):
    client.publish(GET_ABS_LIMIT[sn], limit)

def tunrInverterOn(sn, power):
    client.publish(SET_INV_ON[sn], power)

client.loop_forever()