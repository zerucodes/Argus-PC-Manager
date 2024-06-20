import paho.mqtt.client as mqtt
import json
import logging
import threading
import time
from hwinfo import get_cpu_load,get_cpu_temperature,get_ram_usage,get_ram_temperature,get_disk_usage
# Setup logging
logging.basicConfig(level=logging.INFO)



brightness = 0
device_name = "argus_mini_pc"
device_config = {
    "identifiers": ["argus_mini_pc_test_identifier"],
    "name": "Argus Mini PC",
    "model": "Mini PC",
    "manufacturer": "MinisForum"
}
sensors = [
   
    {"name": "CPU Usage", "unit_of_measurement": "%", "state_topic": f"homeassistant/sensor/{device_name}/cpu_usage/state", "unique_id": f"{device_name}_cpu_usage", "device_class": "power"},
    {"name": "CPU Temperature", "unit_of_measurement": "°C", "state_topic": f"homeassistant/sensor/{device_name}/cpu_temperature/state", "unique_id": f"{device_name}_cpu_temperature", "device_class": "temperature"},
    {"name": "RAM Usage", "unit_of_measurement": "%", "state_topic": f"homeassistant/sensor/{device_name}/ram_usage/state", "unique_id": f"{device_name}_ram_usage", "device_class": "power"},
    {"name": "RAM Temperature", "unit_of_measurement": "°C", "state_topic": f"homeassistant/sensor/{device_name}/ram_temperature/state", "unique_id": f"{device_name}_ram_temperature", "device_class": "temperature"},
    {"name": "C: free", "unit_of_measurement": "%", "state_topic": f"homeassistant/sensor/{device_name}/c_drive_free/state", "unique_id": f"{device_name}_c_drive_free", "device_class": "disk_usage"},
    {"name": "C: used", "unit_of_measurement": "MB", "state_topic": f"homeassistant/sensor/{device_name}/c_drive_free/state", "unique_id": f"{device_name}_c_drive_free", "device_class": "disk_usage"},
    {"name": "E: free", "unit_of_measurement": "%", "state_topic": f"homeassistant/sensor/{device_name}/e_drive_free/state", "unique_id": f"{device_name}_e_drive_free", "device_class": "disk_usage"},
    {"name": "E: used", "unit_of_measurement": "MB", "state_topic": f"homeassistant/sensor/{device_name}/e_drive_free/state", "unique_id": f"{device_name}_e_drive_free", "device_class": "disk_usage"}

]
lights = [
    {
        "name": "Screen Brightness", 
        "command_topic": f"homeassistant/light/{device_name}/screen_brightness/set", 
        "state_topic": f"homeassistant/light/{device_name}/screen_brightness/state",
        "unique_id": f"{device_name}_screen_brightness_control"
    }
]

def publish_config():
    for sensor in sensors:
        if "state_topic" in sensor:
            config_topic = f'homeassistant/{sensor["state_topic"].split("/")[1]}/{sensor["unique_id"]}/config'
        else:
            config_topic = f'homeassistant/{sensor["command_topic"].split("/")[1]}/{sensor["unique_id"]}/config'
        config_payload = sensor.copy()
        config_payload["device"] = device_config
        logging.debug(f"Publishing config to {config_topic}: {json.dumps(config_payload)}")
        client.publish(config_topic, json.dumps(config_payload), retain=True)
    
    for light in lights:
        config_topic = f'homeassistant/light/{light["unique_id"]}/config'
        config_payload = {
            "name": light["name"],
            "command_topic": light["command_topic"],
            "state_topic": light["state_topic"],
            "unique_id": light["unique_id"],
            "device": device_config,
            "schema": "json",
            "brightness": True
        }
        logging.debug(f"Publishing light config to {config_topic}: {json.dumps(config_payload)}")
        client.publish(config_topic, json.dumps(config_payload), retain=True)


def publish_sensor_data(temperature, usage):
    cpu_temp_topic = f"homeassistant/sensor/{device_name}/cpu_temperature/state"
    cpu_usage_topic = f"homeassistant/sensor/{device_name}/cpu_usage/state"
    logging.debug(f"Publishing temperature to {cpu_temp_topic}: {temperature}")
    logging.debug(f"Publishing usage to {cpu_usage_topic}: {usage}")
    client.publish(cpu_temp_topic, get_cpu_temperature())
    client.publish(cpu_usage_topic, get_cpu_load())

def publish_light_state(brightness):
    switch_topic = f"homeassistant/light/{device_name}/screen_brightness/state"
    logging.debug(f"Publishing screen brightness to {switch_topic}: {brightness}")
    if  brightness < 10:
        state = 'OFF'
    else:
        state = 'ON'
    payload = {
        "state": state,
        "brightness": brightness
    }
    client.publish(switch_topic, json.dumps(payload), retain=True)

def on_message(client, userdata, message):
    if message.topic == f"homeassistant/light/{device_name}/screen_brightness/set":
        payload = json.loads(message.payload)
        print(f'recieved payload {payload}')
        if 'brightness' in payload:
            brightness = payload['brightness']
        else:
            brightness = 0
        logging.debug(f"Received command to set screen brightness to {brightness}")
        # Implement your control logic here
        print(f"Setting screen brightness to {brightness}")


broker =  '192.168.1.101'
port = 1883
client = mqtt.Client()

# Set MQTT username and password if required
client.username_pw_set("mqtt", "#####")
client.connect(broker, port)

logging.info(f'Connecting MQTT client {client}')

client.on_connect = lambda self, userdata, flags, rc: logging.debug(f"Connected with result code {rc}")
client.on_publish = lambda self, userdata, mid: logging.debug(f"Message published with mid {mid}")
client.on_subscribe = lambda self, userdata, mid, granted_qos: logging.debug(f"Subscribed with mid {mid} and QoS {granted_qos}")

client.subscribe(f"homeassistant/light/{device_name}/screen_brightness/set")
client.on_message = on_message


publish_config()


threading.Thread(target=client.loop_forever, daemon=True).start()    

counter  = 0
while True:
    if counter % 15 == 0:
        publish_sensor_data(21, 58)
    publish_light_state(brightness)
    time.sleep(2)
    counter+=1