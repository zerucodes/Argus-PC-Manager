import yaml
import ctypes
import logging as log
import re
from hwinfo import get_cpu_load,get_cpu_temperature,get_ram_usage,get_ram_temperature,get_disk_usage_simple,get_hw_attr,get_bluetooth_battery
from enum import Enum
import paho.mqtt.client as mqtt
import threading
import json 
import time


def setup_config():
    config = None

    version = '0.1.0'
    featurecomment = 'Initial Revision'
    log.basicConfig(level=log.INFO)

    log.debug('Looking for config')
    # Set up config
    if yaml is not None:
        try:
            with open('mqtt.yaml') as config_file:
                config = yaml.safe_load(config_file)
                log.debug(f'Using config at {config_file}')
        except FileNotFoundError:
            try:
                with open(r'mqtt.yaml') as config_file:
                    config = yaml.safe_load(config_file)
                    log.debug(f'Using config at {config_file}')
            except FileNotFoundError:
                log.error(f'No config available')
                config = None

    
    # If yaml module isn't available or config file isn't found, assign default values
    if config is None:
        log.debug(f'Using default config in demo mode')
        config = {
            "mqtt_username": "argus",
            "mqtt_password": "##########",
            "cmmExe": "ControlMyMonitor.exe",
            "enabled": False
        }

    log.info(f'Launching Argus v{version}...')
    log.info(f'Latest feature: {featurecomment}')
    log.debug(f'Is Admin: {ctypes.windll.shell32.IsUserAnAdmin() != 0}')    
    log.debug(f'Config: {str(config)}')

    return config

class DeviceClass(Enum):
    BATTERY = 'battery'
    DATA_SIZE = 'data_size'
    TEMPERATURE = 'temperature'
    POWER = 'power'
    LIGHT = 'light'
class Device:

    def __init__(self, name, model=None,manufacturer=None,client=None):
        self.name = name    
        self.model = model
        self.manufacturer = manufacturer
        self.device_name = re.sub(r'[^a-zA-Z0-9]', '_', name.lower()) # self.name.lower().replace(' ','_').replace('-','_')
        self.identifiers = [f'{self.device_name}_zmqtt_identifier']
        self.set_config()
        self.sensor_topics = {}
        self.client = client
    def set_config(self):
        config =  {
            "name" : self.name,
            "identifiers" : self.identifiers
        }
        if self.manufacturer:
            config["manufacturer"] = self.manufacturer
        if self.model:
            config["model"] = self.model
        self.config = config
    
    def generate_sensor_topic(self,device_class,name=None):
        sensor = {}
        
        match device_class:
            case DeviceClass.BATTERY:
                sensor['name'] = 'Battery Level'
                sensor['unit_of_measurement'] = '%'
            case DeviceClass.LIGHT:
                log.debug('TBD')
                if name:
                    sensor['name'] = name
                else:
                    sensor['name'] = 'Brightness'
                sensor['optimistic'] = True
                sensor['brightness'] = True                
            case 'power':
                log.debug('TBD')
            case DeviceClass.DATA_SIZE:
                if name:
                    # "C:"
                    sensor['name'] = name
                    sensor['unit_of_measurement'] = 'B'
            case DeviceClass.POWER:
                sensor['name'] = f'{name} Usage'
                sensor['unit_of_measurement'] = '%'
            case DeviceClass.TEMPERATURE:
                sensor['name'] = f'{name} Temperature'
                sensor['unit_of_measurement'] = '°C'

        sensor_name = re.sub(r'[^a-zA-Z0-9]', '_', sensor["name"].lower()) #  battery_level
        sensor_name =  re.sub(r'_{2,}','_',sensor_name) # duplicate  _ chars
        sensor['device_class'] = device_class.value
        sensor['state_topic'] = f'homeassistant/sensor/{self.device_name}/{sensor_name}/state'
        sensor['unique_id'] = f"{self.device_name}_{sensor_name}"  #  zeru_pc_battery_level
        sensor['device'] = self.config

        # Some values are only for some
        match device_class:
            case DeviceClass.LIGHT:
                sensor['command_topic'] = sensor['state_topic'].replace('/state','/set')
        if sensor_name not in self.sensor_topics:
            self.sensor_topics[sensor_name] = sensor
            log.debug(f'Adding {sensor_name} to sensor_topics dict')
        else:
            log.error(f'Sensor {sensor_name} is already in sensor_topics dict')
        return sensor
    
    def publish_sensor_topics(self):
        for topic in self.sensor_topics:
            sensor_topic = self.sensor_topics[topic]
            log.debug(f'Publishing topic: {topic} : {sensor_topic}')
            self.client.publish(sensor_topic['state_topic'].replace('/state','/config'), json.dumps(sensor_topic),retain=True)
    
    def publish_sensor(self,value,name):
        sensor_name = re.sub(r'[^a-zA-Z0-9]', '_', name.lower()) 
        sensor_name =  re.sub(r'_{2,}','_',sensor_name)
        sensor_topic = self.sensor_topics[sensor_name]
        self.client.publish(sensor_topic['state_topic'], value)

def initialize_bluetooth_batteries():
    log.info(f'Inititalizing Bluetooth devices with battery data')
    bl_batteries = get_bluetooth_battery()
    log.debug(f'Found {bl_batteries}')
    for device_name in bl_batteries:
        battery = bl_batteries[device_name]
        device = Device(device_name) # Device.generate_device_config(device_name)
        sensor_topic = device.generate_sensor_topic(DeviceClass.BATTERY)
        log.info(f'{device_name} at {battery}%')


def initialize_pc_sensors(this_pc):
    log.debug(f'Initializing Disk Sensors')
    for drive in get_disk_usage_simple():
        this_pc.generate_sensor_topic(DeviceClass.DATA_SIZE,f'{drive} Free')
        this_pc.generate_sensor_topic(DeviceClass.DATA_SIZE,f'{drive} Total')
    
    log.debug(f'Initializing PC Sensors')
    sensors = ['CPU','GPU','RAM']
    for sensor in sensors:
        this_pc.generate_sensor_topic(DeviceClass.TEMPERATURE,sensor)
        this_pc.generate_sensor_topic(DeviceClass.POWER,sensor)

def publish_pc_disk_sensors(this_pc):
    log.debug(f'Publishing Disk Sensors')
    usage = get_disk_usage_simple()
    for drive in usage:
        this_pc.publish_sensor(usage[drive].free,f'{drive} Free')
        this_pc.publish_sensor(usage[drive].total,f'{drive} Total')

def publish_pc_sensors(this_pc):    
    log.debug(f'Publishing PC Sensors')
    sensors = ['CPU','GPU','RAM']
    for sensor in sensors:
        temp = get_pc_sensor(sensor,'Temperature')
        usage = get_pc_sensor(sensor,'Usage')
        if temp:
            this_pc.publish_sensor(temp,f'{sensor} Temperature')
        if usage:
            this_pc.publish_sensor(usage,f'{sensor} Usage')

def get_pc_sensor(sensor,type):
    match sensor:
        case 'CPU':
            match type:
                case 'Usage':
                    return get_cpu_load()
                case 'Temperature':
                    return get_cpu_temperature()
        case 'GPU':
            match type:
                case 'Usage':
                    return None
                case 'Temperature':
                    return None
            print("")
        case 'RAM':
            match type:
                case 'Usage':
                    return get_ram_usage()
                case 'Temperature':
                    return get_ram_temperature()
    return None

def main():
    config = setup_config()

    broker =  config['mqtt_ip']
    port = 1883
    client = mqtt.Client()

    # Set MQTT username and password if required
    client.username_pw_set(config['mqtt_username'], config['mqtt_password'])
    client.connect(broker, port)
    client.on_connect = lambda self, userdata, flags, rc: log.debug(f"Connected with result code {rc}")
    client.on_publish = lambda self, userdata, mid: log.debug(f"Message published with mid {mid}")
    client.on_subscribe = lambda self, userdata, mid, granted_qos: log.debug(f"Subscribed with mid {mid} and QoS {granted_qos}")

    log.info(f'Initializing PC Device')
    pc = Device(name=get_hw_attr('name'),model=get_hw_attr('model'),manufacturer=get_hw_attr('manufacturer'),client=client)
    initialize_pc_sensors(pc)
    pc.publish_sensor_topics()
  

    threading.Thread(target=client.loop_forever, daemon=True).start()    
    log.info(f'Sending Sensor data on loop...')
    counter  = 0
    while True:
        try:
            if counter % 3 == 0:
                publish_pc_sensors(pc)
            if counter % 15 == 0:
                publish_pc_disk_sensors(pc)
                
            time.sleep(1)
        except Exception as e:
            log.error(e)
        counter+=1
if __name__ == '__main__':
    main()

