from doctest import ELLIPSIS_MARKER
import os
import paho.mqtt.client as mqtt
from apscheduler.schedulers.background import BackgroundScheduler

# Constants
try:
    DEBUG = os.environ["DEBUG_LIMITER"]
except:
    DEBUG = True

LIMITER_INTERVAL = 20.0 if DEBUG else float(os.environ["LIMITER_INTERVAL"])
MAX_AC_PWR = 600 if DEBUG else int(os.environ["MAX_AC_PWR"])
INCREMENT = 20 if DEBUG else int(os.environ["INCREMENT"])

BROKER_IP = "192.168.0.2" if DEBUG else os.environ["BROKER_IP"]
BROKER_PORT = 1883 if DEBUG else int(os.environ["BROKER_PORT"])
CLIENT_ID = "pvLimiter"

SN_INV = ["1", "2"] if DEBUG else str(os.environ['SN_INV']).split(',')

INV_SOUTH = 0
INV_NORTH = 1
TYPE_SOUTH = 1200
TYPE_NORTH = 600

YES = 1
NO = 0

# MQTT Topics
DTU_TOPIC = "solar/" if DEBUG else os.environ["DTU_TOPIC"]
LIMITER_TOPIC = "limiter/" if DEBUG else os.environ["LIMITER_TOPIC"]
SET_ABS_LIMIT = {}
SET_INV_ON = {}
GET_ABS_LIMIT = {}
GET_AC_PWR = {}
GET_IS_PRODUCING = {}
GET_IS_REACHABLE = {}
GET_CHANNEL_PWR = {}

for sn in SN_INV:
    SET_ABS_LIMIT[sn] = DTU_TOPIC + sn + "/cmd/limit_nonpersistent_absolute"
    SET_INV_ON[sn] = DTU_TOPIC + sn + "/cmd/power"
    GET_ABS_LIMIT[sn] = DTU_TOPIC + sn + "/status/limit_absolute"
    GET_IS_PRODUCING[sn] = DTU_TOPIC + sn + "/status/producing"
    GET_IS_REACHABLE[sn] = DTU_TOPIC + sn + "/status/reachable"
    GET_AC_PWR[sn] = DTU_TOPIC + sn + "/0/power"
    GET_CHANNEL_PWR[sn] = list(range(4))
    for i in range(4):
        GET_CHANNEL_PWR[sn][i] = DTU_TOPIC + sn + "/" + str(i + 1) + "/power"


SET_LIMITER_MAX_AC_PWR = LIMITER_TOPIC + "cmd/limit_nonpersistent_absolute"
SET_LIMITER_INTERVAL = LIMITER_TOPIC + "cmd/controler_interval"
SET_LIMITER_INCREMENT = LIMITER_TOPIC + "cmd/controler_increment"
LIMITER_SYSTEM_AC_PWR = LIMITER_TOPIC + "status/system_power"
LIMITER_SYSTEM_LIMIT = LIMITER_TOPIC + "status/system_limit"
LIMITER_CONTROLER_INTERVAL = LIMITER_TOPIC + "status/controler_interval"
LIMITER_CONTROLER_INCREMENT = LIMITER_TOPIC + "status/controler_increment"

# Variabels
systemAcPower = 0
invAcPower = {}
invDcPower = {}
invLimit = {}
invIsProducting = {}
invIsReachable = {}

limiterInterval = LIMITER_INTERVAL
maxAcPower = MAX_AC_PWR
increment = INCREMENT

for sn in SN_INV:
    invAcPower[sn] = 0
    invLimit[sn] = 0
    invIsProducting[sn] = NO
    invIsReachable[sn] = NO
    invDcPower[sn] = list(range(4))

def get_new_limit(val, limit):
    if val > limit:
        return limit
    else:
        return val

def limiter():
    global systemAcPower

    # calc the ac power of the system
    systemAcPower = 0
    for sn in SN_INV:
        systemAcPower += invAcPower[sn]

    publishSystemAcPwr(systemAcPower)
    publishSystemLimit(maxAcPower)
    publishLimiterInterval(limiterInterval)
    publishLimiterIncrement(increment)
    
    # This code section is especially for my setup of several BKW
    ############################################################################
    snSouth = SN_INV[INV_SOUTH]
    snNorth = SN_INV[INV_NORTH]
  
    # If no BKW is reachable then don't control anything
    if (invIsReachable[snSouth] == NO and invIsReachable[snNorth] == NO):
        return
    
    # If system power > as max AC power then limit the System to max alowed AC power
    if (systemAcPower > maxAcPower):
        # Determine which BKW is currently sunlit based on the utilization rate
        percentSouth = (100 / TYPE_SOUTH) * invAcPower[snSouth]
        percentNorth = (100 / TYPE_NORTH) * invAcPower[snNorth]

        # The BKW that receives more sunlight is controlled first, as it is likely to respond more dynamically
        if (percentSouth >= percentNorth):
            setLimitNonpersistentAbsolute(snSouth, invAcPower[snSouth] - (systemAcPower - maxAcPower))
        else:
            setLimitNonpersistentAbsolute(snNorth, invAcPower[snNorth] - (systemAcPower - maxAcPower))

    # Is the system power < as max AC power?
    # If yes then try to produce more
    if (systemAcPower < maxAcPower - increment):
        if (invLimit[snSouth] < TYPE_SOUTH):
            setLimitNonpersistentAbsolute(snSouth, get_new_limit(invLimit[snSouth] + increment, TYPE_SOUTH))

        if (invLimit[snNorth] < TYPE_NORTH):    
            setLimitNonpersistentAbsolute(snNorth, get_new_limit(invLimit[snNorth] + increment, TYPE_NORTH))

    ############################################################################

def resetNonpersitentValues():
    global maxAcPower
    maxAcPower = MAX_AC_PWR

# Start background job for limiter
scheduler = BackgroundScheduler()
limiterJob = scheduler.add_job(limiter, 'interval', seconds = LIMITER_INTERVAL)
resetJob = scheduler.add_job(resetNonpersitentValues, 'cron', minute=0, hour=0)
scheduler.start()

# Setup MQTT Client
def getSnFromTopic(topic):
    return topic.split("/")[1]

def getChFromTopic(topic):
    return int(topic.split("/")[2])

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

def on_message_channel_power(client, userdata, message):
    msg = str(message.payload.decode("utf-8"))
    sn = getSnFromTopic(message.topic)
    ch = getChFromTopic(message.topic)
    invDcPower[sn][ch - 1] = int(float(msg))    

def on_message_limit_nonpersistent_absolute(client, userdata, message):
    global maxAcPower
    msg = str(message.payload.decode("utf-8"))
    maxAcPower = int(msg)

def on_message_controler_interval(client, userdata, message):
    global limiterInterval
    msg = str(message.payload.decode("utf-8"))
    limiterInterval = float(msg)
    limiterJob.reschedule(trigger = "interval", seconds = limiterInterval)

def on_message_controler_increment(client, userdata, message):
    global increment
    msg = str(message.payload.decode("utf-8"))
    increment = int(msg)

#mqtt.Client.connected_flag=False
client = mqtt.Client(CLIENT_ID)
client.connect(BROKER_IP, BROKER_PORT)

client.on_message = on_message

for sn in SN_INV:
    client.message_callback_add(GET_ABS_LIMIT[sn], on_message_limit_absolute)
    client.message_callback_add(GET_IS_PRODUCING[sn], on_message_producing)
    client.message_callback_add(GET_IS_REACHABLE[sn], on_message_reachable)
    client.message_callback_add(GET_AC_PWR[sn], on_message_power)
    for i in range(4):
        client.message_callback_add(GET_CHANNEL_PWR[sn][i], on_message_channel_power)

client.message_callback_add(SET_LIMITER_MAX_AC_PWR, on_message_limit_nonpersistent_absolute)
client.message_callback_add(SET_LIMITER_INTERVAL, on_message_controler_interval)
client.message_callback_add(SET_LIMITER_INCREMENT, on_message_controler_increment)

client.subscribe([(DTU_TOPIC + "#", 0), (LIMITER_TOPIC + "#", 0)])
client.on_connect = on_connect

def setLimitNonpersistentAbsolute(sn, limit):
    client.publish(SET_ABS_LIMIT[sn], float(limit))

def tunrInverterOn(sn, power):
    client.publish(SET_INV_ON[sn], power)

def publishSystemAcPwr(power):
    client.publish(LIMITER_SYSTEM_AC_PWR, float(power))  

def publishSystemLimit(power):
    client.publish(LIMITER_SYSTEM_LIMIT, power)

def publishLimiterInterval(value):
    client.publish(LIMITER_CONTROLER_INTERVAL, float(value))

def publishLimiterIncrement(value):
    client.publish(LIMITER_CONTROLER_INCREMENT, value)

client.loop_forever()