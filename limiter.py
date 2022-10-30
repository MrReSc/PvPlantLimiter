
import paho.mqtt.client as mqtt
from apscheduler.schedulers.background import BackgroundScheduler

# Constants
LIMITER_INTERVAL = 5.0  # s
MAX_AC_PWR = 600        # W
INCREMENT = 10          # W

BROKER_IP = "192.168.0.2"
BROKER_PORT = 1883
CLIENT_ID = "pvLimiter"

SN_INV = ["1234567", "11225544"]
INV_SUD = 1
INV_NORD = 2

# MQTT Topics
DTU_TOPIC = "solar/#"
SET_ABS_LIMIT = {}
SET_INV_ON = {}
GET_ABS_LIMIT = {}
GET_AC_PWR = {}
GET_IS_PRODUCING = {}

for sn in SN_INV:
    SET_ABS_LIMIT[sn] = "solar/" + sn + "/cmd/limit_persistent_absolute"
    SET_INV_ON[sn] = "solar/" + sn + "/cmd/power"
    GET_ABS_LIMIT[sn] = "solar/" + sn + "/status/limit_absolute"
    GET_IS_PRODUCING[sn] = "solar/" + sn + "/status/producing"
    GET_AC_PWR[sn] = "solar/" + sn + "/0/power"

# Variabels
systemAcPower = 0
invAcPower = {}
invLimit = {}
invIsProducting = {}

for sn in SN_INV:
    invAcPower[sn] = 0
    invLimit[sn] = 0
    invIsProducting[sn] = 0

# Functions
def getSnFromTopic(topic):
    return topic.split("/")[1]

def limiter():
    print(systemAcPower)
    print(invAcPower)
    print(invLimit)
    print(invIsProducting)

# Background Job starten
scheduler = BackgroundScheduler()
scheduler.add_job(limiter, 'interval', seconds = LIMITER_INTERVAL)
scheduler.start()

# MQTT Client
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

def on_message_power(client, userdata, message):
    msg = str(message.payload.decode("utf-8"))
    sn = getSnFromTopic(message.topic)
    invAcPower[sn] = int(float(msg))

mqtt.Client.connected_flag=False
client = mqtt.Client(CLIENT_ID)
client.connect(BROKER_IP, BROKER_PORT)

client.on_message = on_message

for sn in SN_INV:
    client.message_callback_add(GET_ABS_LIMIT[sn], on_message_limit_absolute)
    client.message_callback_add(GET_IS_PRODUCING[sn], on_message_producing)
    client.message_callback_add(GET_AC_PWR[sn], on_message_power)

client.subscribe(DTU_TOPIC)
client.on_connect = on_connect
client.loop_forever()



