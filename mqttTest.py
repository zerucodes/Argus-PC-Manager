import paho.mqtt.client as mqtt
import json
import logging
import threading
import time
from hwinfo import get_cpu_load,get_cpu_temperature,get_ram_usage,get_ram_temperature,get_disk_usage_simple,get_hw_attr,get_battery_level
# Setup logging
logging.basicConfig(level=logging.INFO)



brightness = 37
device_name = get_hw_attr("name").lower().replace(" ","_") # "argus_mini_pc"
device_config = {
    "identifiers": [f"{device_name}_test_identifier"],
    "name": get_hw_attr("name"), # "Argus Mini PC",
    "model": get_hw_attr("model"), # "Mini PC",
    "manufacturer": get_hw_attr("manufacturer") # "MinisForum"
    # "status": get_hw_attr("status"),
    # "primaryOwnerName" : get_hw_attr("primaryOwnerName"),
    # "systemType" : get_hw_attr("systemType")
}
mx3_config = {
    "identifiers": [f"mx3_test_identifier"],
    "name": "MX3", 
    "model": "MX Master 3 Mouse", 
    "manufacturer": "Logitech" 
}
g915_config = {
    "identifiers": [f"g915_test_identifier"],
    "name": "G915", 
    "model": "G915 Lightspeed Wireless RGB Keyboard", 
    "manufacturer": "Logitech" 
}

config = mx3_config
mx3_sensors =  {"name": f"{config['name']} Battery", "unit_of_measurement": "%", "state_topic": f"homeassistant/sensor/{config['name'].lower()}/battery_level/state", "unique_id": f"{config['name'].lower()}_battery_level", "device_class": "battery", "device": mx3_config}
    

config = g915_config
g915_sensors =  {"name": f"{config['name']} Battery", "unit_of_measurement": "%", "state_topic": f"homeassistant/sensor/{config['name'].lower()}/battery_level/state", "unique_id": f"{config['name'].lower()}_battery_level", "device_class": "battery", "device":g915_config}
    


sensors = [
    {"name": "CPU Usage", "unit_of_measurement": "%", "state_topic": f"homeassistant/sensor/{device_name}/cpu_usage/state", "unique_id": f"{device_name}_cpu_usage", "device_class": "power"},
    {"name": "CPU Temperature", "unit_of_measurement": "°C", "state_topic": f"homeassistant/sensor/{device_name}/cpu_temperature/state", "unique_id": f"{device_name}_cpu_temperature", "device_class": "temperature"},
    {"name": "RAM Usage", "unit_of_measurement": "%", "state_topic": f"homeassistant/sensor/{device_name}/ram_usage/state", "unique_id": f"{device_name}_ram_usage", "device_class": "power"},
    {"name": "RAM Temperature", "unit_of_measurement": "°C", "state_topic": f"homeassistant/sensor/{device_name}/ram_temperature/state", "unique_id": f"{device_name}_ram_temperature", "device_class": "temperature"},
]


lights = [
    {
        "name": "Screen Brightness", 
        "command_topic": f"homeassistant/light/{device_name}/screen_brightness/set", 
        "state_topic": f"homeassistant/light/{device_name}/screen_brightness/state",
        "unique_id": f"{device_name}_screen_brightness_control"
    }
]

def initialize_drives(drives):
    for drive_path in drives:
        drive = drive_path.replace(":","")
        sensors.append({
            "name": f"{drive.upper()}: Free",
            "unit_of_measurement": "B",
            "state_topic": f"homeassistant/sensor/{device_name}/{drive.lower()}_drive_free/state",
            "unique_id": f"{device_name}_{drive.lower()}_drive_free",
            "device_class": "data_size"
        })
        sensors.append({
            "name": f"{drive.upper()}: Total",
            "unit_of_measurement": "B",
            "state_topic": f"homeassistant/sensor/{device_name.lower()}/{drive.lower()}_drive_total/state",
            "unique_id": f"{device_name}_{drive.lower()}_drive_total",
            "device_class": "data_size"
        })

def publish_config():
    initialize_drives(get_disk_usage_simple())
    for sensor in sensors:
        if "state_topic" in sensor:
            config_topic = f'homeassistant/{sensor["state_topic"].split("/")[1]}/{sensor["unique_id"]}/config'
 
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
            "optimistic": True,
            "brightness": True
        }
        logging.debug(f"Publishing light config to {config_topic}: {json.dumps(config_payload)}")
        client.publish(config_topic, json.dumps(config_payload), retain=True)
    
    mx3_config_topic = f'homeassistant/sensor/mx3/config'
    g915_config_topic = f'homeassistant/sensor/g915/config'
    client.publish(mx3_config_topic,json.dumps(mx3_sensors), retain=True)
    client.publish(g915_config_topic,json.dumps(g915_sensors), retain=True)

def publish_diskspace_data():
    disks = get_disk_usage_simple()
    for disk in disks:
        drive = disk.replace(":","")
        free_topic = f"homeassistant/sensor/{device_name}/{drive.lower()}_drive_free/state"
        free_value = disks[disk].free
        total_topic = f"homeassistant/sensor/{device_name}/{drive.lower()}_drive_total/state"
        total_value = disks[disk].total
        logging.debug(f"Publishing temperature to {free_topic}: {free_value}")
        logging.debug(f"Publishing usage to {total_topic}: {total_value}")
        client.publish(free_topic,free_value)
        client.publish(total_topic,total_value)

def publish_battery_data():
    mx3_config_topic = f'homeassistant/sensor/mx3/config'
    g915_config_topic = f'homeassistant/sensor/g915/config'
    mx3_b = get_battery_level('MX Master 3')
    g915_b = get_battery_level('G915 Keyboard') 
    if mx3_b != -1:
        client.publish(mx3_sensors["state_topic"],mx3_b )
    if g915_b != -1:
        client.publish(g915_sensors["state_topic"],g915_b)


def publish_sensor_data():
    cpu_temp_topic = f"homeassistant/sensor/{device_name}/cpu_temperature/state"
    cpu_usage_topic = f"homeassistant/sensor/{device_name}/cpu_usage/state"

    ram_temp_topic = f"homeassistant/sensor/{device_name}/ram_temperature/state"
    ram_usage_topic = f"homeassistant/sensor/{device_name}/ram_usage/state"

    cpu_temp = get_cpu_temperature()
    cpu_load = get_cpu_load()

    # ram_temp = get_ram_temperature()
    ram_load = get_ram_usage()

    logging.debug(f"Publishing temperature to {cpu_temp_topic}: {cpu_temp}")
    logging.debug(f"Publishing usage to {cpu_usage_topic}: {cpu_load}")

    # logging.debug(f"Publishing temperature to {ram_temp_topic}: {ram_temp}")
    logging.debug(f"Publishing usage to {ram_usage_topic}: {ram_load}")
    client.publish(cpu_temp_topic, cpu_temp)
    client.publish(cpu_usage_topic, cpu_load)

    # client.publish(ram_temp_topic, ram_temp)
    client.publish(ram_usage_topic, ram_load)


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
            value = payload['brightness']
        else:
            value = 0
        logging.debug(f"Received command to set screen brightness to {value}")
        print(f"Setting screen brightness to {value}")
        return value


broker =  '192.168.1.101'
port = 1883
client = mqtt.Client()

# Set MQTT username and password if required
client.username_pw_set("mqtt", "######")
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
        publish_sensor_data()
    if counter % 1000 == 0:
        publish_diskspace_data()
        publish_battery_data()
    time.sleep(1)
    counter+=1

