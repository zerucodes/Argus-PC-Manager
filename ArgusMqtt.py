import yaml
import ctypes
import logging as log
import re
from hwinfo import get_cpu_load,get_cpu_temperature,get_ram_usage,get_ram_temperature,get_disk_usage_simple,get_hw_attr,get_bluetooth_battery,get_last_boot,get_network_info
from enum import Enum
import paho.mqtt.client as mqtt
import threading
import json 
import time
from datetime import datetime
import subprocess
import os
import functools

def retry(times,delay=1):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            while attempts < times:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    log.warn(f"Attempt {attempts} failed: {e}")
                    if attempts == times:
                        log.error(f"Attempt {attempts} failed: {e}")
                        raise
                    time.sleep(delay)  # Optional: wait for 1 second before retrying
        return wrapper
    return decorator

def setup_config():
    config = None
    version = '2.0.0'
    featurecomment = 'MQTT Integration'
    log.basicConfig(level=log.DEBUG, format='%(asctime)s [%(levelname)s] %(funcName)s: %(message)s')    
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
    POWER = 'power_factor'
    LIGHT = 'light'
    TIMESTAMP = 'timestamp'
    BUTTON = 'button'
class Device:

    def __init__(self, name, model=None,manufacturer=None,mac=None,ip=None,bluetooth=None,client=None):
        self.name = name    
        self.model = model
        self.manufacturer = manufacturer
        self.device_name = re.sub(r'[^a-zA-Z0-9]', '_', name.lower()) # self.name.lower().replace(' ','_').replace('-','_')
        self.identifiers = [f'{self.device_name}_zmqtt_identifier']
        self.mac = mac
        self.ip = ip
        self.bluetooth = bluetooth
        self.set_config()
        self.sensor_topics = {}
        self.command_topics = {}
        self.client = client
        self.callbacks = {}
    def set_config(self):
        config =  {
            "name" : self.name
        }
        if self.ip or self.mac or self.bluetooth:
            config['connections'] = []
        else:
            config['identifiers'] = self.identifiers
        if self.manufacturer:
            config["manufacturer"] = self.manufacturer
        if self.model:
            config["model"] = self.model
        if self.mac:
            config['connections'].append(['mac',self.mac])
        if self.ip:
            config['connections'].append(['ip',self.ip])
        self.config = config
    
    def generate_sensor_topic(self,device_class,name=None,message=None):
        sensor = {}
        sensor['device_class'] = device_class.value
        sensor['name'] = name
        match device_class:
            case DeviceClass.BATTERY:
                sensor['name'] = 'Battery Level'
                sensor['unit_of_measurement'] = '%'           
            case 'power':
                log.debug('TBD')
            case DeviceClass.DATA_SIZE:
                if name:
                    sensor['entity_category'] = 'diagnostic'
                    sensor['unit_of_measurement'] = 'B'
            case DeviceClass.POWER:
                sensor['name'] = f'{name} Usage'
                sensor['unit_of_measurement'] = '%'
                del sensor['device_class']
            case DeviceClass.TEMPERATURE:
                sensor['name'] = f'{name} Temperature'
                sensor['unit_of_measurement'] = '°C'
            case DeviceClass.TIMESTAMP:
                sensor['entity_category'] = 'diagnostic'
                sensor['value_template']  = '{{ value | int | timestamp_local | as_datetime  }}'



        sensor_name = re.sub(r'[^a-zA-Z0-9]', '_', sensor["name"].lower()) #  battery_level
        sensor_name =  re.sub(r'_{2,}','_',sensor_name) # duplicate  _ chars
        
        sensor['state_topic'] = f'homeassistant/sensor/{self.device_name}/{sensor_name}/state'
        sensor['unique_id'] = f"{self.device_name}_{sensor_name}"  #  zeru_pc_battery_level
        sensor['device'] = self.config

        if 'unit_of_measurement' in sensor and sensor['unit_of_measurement']  == '%':
            sensor['suggested_display_precision'] = 2
        # Some values are only for some

        if sensor_name not in self.sensor_topics:
            self.sensor_topics[sensor_name] = sensor
            log.debug(f'Adding {sensor_name} to sensor_topics dict')
        else:
            log.error(f'Sensor {sensor_name} is already in sensor_topics dict')
        return sensor
    

    def generate_command_topic(self,device_class,name=None,callback=None):
        sensor = {}
        sensor['device_class'] = device_class.value
        sensor['name'] = name

        sensor_name = re.sub(r'[^a-zA-Z0-9]', '_', sensor["name"].lower()) #  battery_level
        sensor_name =  re.sub(r'_{2,}','_',sensor_name) # duplicate  _ chars
        sensor['state_topic'] = f'homeassistant/{sensor["device_class"]}/{self.device_name}/{sensor_name}/state'
        sensor['command_topic'] = f'homeassistant/{sensor["device_class"]}/{self.device_name}/{sensor_name}/set'
        match device_class:
            case DeviceClass.LIGHT:
                sensor['optimistic'] = True
                sensor['brightness'] = True  
        sensor['schema'] = 'json'
             
        sensor['state_topic'] = f'homeassistant/sensor/{self.device_name}/{sensor_name}/state'
        sensor['unique_id'] = f"{self.device_name}_{sensor_name}"  #  zeru_pc_battery_level
        sensor['device'] = self.config


        del sensor['device_class']
        if callback:
            if sensor['command_topic'] not in self.callbacks:
                self.callbacks[sensor['command_topic']] = callback
                log.debug(f'Adding {sensor["command_topic"]} to callbacks dict')
            else:
                log.error(f'Command {sensor["command_topic"]} is already in callbacks dict')
        if sensor_name not in self.command_topics:
            self.command_topics[sensor_name] = sensor
            log.debug(f'Adding {sensor_name} to command_topics dict')
        else:
            log.error(f'Command {sensor_name} is already in command_topics dict')
        # if sensor_name not in self.sensor_topics:
        #     self.sensor_topics[sensor_name] = sensor
        #     log.debug(f'Adding {sensor_name} to sensor_topics dict')
        # else:
        #     log.error(f'Sensor {sensor_name} is already in sensor_topics dict')

    def publish_sensor_topics(self):
        for topic in self.sensor_topics:
            sensor_topic = self.sensor_topics[topic]
            log.debug(f'Publishing topic: {topic} : {sensor_topic}')
            self.client.publish(sensor_topic['state_topic'].replace('/state','/config'), json.dumps(sensor_topic),retain=True)
            
    def publish_command_topics(self):
        for topic in self.command_topics:
            sensor_topic = self.command_topics[topic]
            log.debug(f'Publishing topic: {topic} : {sensor_topic}')
            
            self.client.publish(sensor_topic['command_topic'].replace('/set','/config'), json.dumps(sensor_topic),retain=True)
            self.client.subscribe(sensor_topic['command_topic'])

    def publish_sensor(self,value,name):
        sensor_name = re.sub(r'[^a-zA-Z0-9]', '_', name.lower()) 
        sensor_name =  re.sub(r'_{2,}','_',sensor_name)
        sensor_topic = self.sensor_topics[sensor_name]
        self.client.publish(sensor_topic['state_topic'], value)

def initialize_bluetooth_batteries(client):
    devices = []
    log.info(f'Inititalizing Bluetooth devices with battery data')
    bl_batteries = get_bluetooth_battery()
    log.debug(f'Found {bl_batteries}')
    for device_name in bl_batteries:
        battery = bl_batteries[device_name]
        device = Device(device_name,client=client) # Device.generate_device_config(device_name)
        sensor_topic = device.generate_sensor_topic(DeviceClass.BATTERY)
        devices.append(device)
        log.info(f'{device_name} at {battery}%')
    return devices


def initialize_pc_sensors(this_pc):
    log.debug(f'Initializing Drive Sensors')
    for drive in get_disk_usage_simple():
        this_pc.generate_sensor_topic(DeviceClass.DATA_SIZE,f'{drive} Drive Free')
        this_pc.generate_sensor_topic(DeviceClass.DATA_SIZE,f'{drive} Drive Total')
    
    log.debug(f'Initializing PC Sensors')
    sensors = ['CPU','GPU','RAM']
    for sensor in sensors:
        this_pc.generate_sensor_topic(DeviceClass.TEMPERATURE,sensor)
        this_pc.generate_sensor_topic(DeviceClass.POWER,sensor)

    this_pc.generate_sensor_topic(DeviceClass.TIMESTAMP,"Boot Time")

def publish_pc_disk_sensors(this_pc):
    log.debug(f'Publishing Drive Sensors')
    usage = get_disk_usage_simple()
    for drive in usage:
        this_pc.publish_sensor(usage[drive].free,f'{drive} Drive Free')
        this_pc.publish_sensor(usage[drive].total,f'{drive} Drive Total')

def publish_pc_sensors(this_pc):    
    log.debug(f'Publishing PC Sensors')
    sensors = ['CPU','GPU','RAM']
    for sensor in sensors:
        try:
            temp = get_pc_sensor(sensor,'Temperature')
            usage = get_pc_sensor(sensor,'Usage')
            if temp:
                this_pc.publish_sensor(temp,f'{sensor} Temperature')
            if usage:
                this_pc.publish_sensor(usage,f'{sensor} Usage')
        except Exception as e:
            log.error(f'Unable to publish {sensor}')
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

def on_message(client, userdata, message,managed_devices=None):
    if isinstance(message.payload,bytes):
        payload = message.payload.decode()
    try:
        payload = json.loads(message.payload)
    except Exception as e:
        log.debug(f'Non json payload')
    log.info(f'recieved payload {payload}')
    for device in  managed_devices:
        for callback_topic in device.callbacks:
            if message.topic == callback_topic:
                device.callbacks[callback_topic](payload=payload,device=device)
    # if message.topic == f"homeassistant/light/m27q/screen_brightness/set":
    #     if 'brightness' in payload:
    #         value = payload['brightness']
    #     else:
    #         value = 0
    #     log.debug(f"Received command to set screen brightness to {value}")

def runCommand(command,enabled=False):
    if (command):
        try:
            log.debug(f'Running command: {command}' if enabled else 'Running demo: {command}')
            if enabled:
                out = subprocess.run(command,capture_output=True)
                if (out.returncode != 0):
                    log.warning(f'{out}')
                log.debug(f'{out}')
                return json.loads(out.stdout.decode())
        except Exception as e:
            log.warning(f'Command Error {e}')

def getPayloadAttr(payload,attr,default=0):
    if attr in payload:
        return payload[attr]
    elif attr == 'brightness':
        return 255 if payload['state'] == 'ON' else 0
    else:
        return default
    
def setMonitorInput(monitorName,input):
    log.debug(f"Setting {monitorName} {input} input")

def getMonitors(client):
    monitors = []
    log.info(f'Initializing Display Monitors')
    output = runCommand("VCPController.exe -getMonitors",enabled=True)['monitors']
    for m in output:
        monitor = Device(name=m['model'],model=m['name'],client=client) # Swap name and monitor due to model containing friendlier name and model being unique
        monitor.generate_command_topic(DeviceClass.LIGHT,name='Screen Brightness',callback= lambda payload,device:runCommand(enabled=True, command=f'VCPController.exe -setVCP --vcp=0x10 --value={int(getPayloadAttr(payload,"brightness",0)/255*100 )} --monitor="{device.model}"'))
        monitor.generate_command_topic(DeviceClass.BUTTON,name='USB-C', callback= lambda device,payload=None:setMonitorInput(device.model,'USB-C'))
        monitor.generate_command_topic(DeviceClass.BUTTON,name='HDMI-1', callback= lambda device,payload=None:setMonitorInput(device.model,'HDMI-1'))
        monitor.generate_command_topic(DeviceClass.BUTTON,name='HDMI-2', callback= lambda device,payload=None:setMonitorInput(device.model,'HDMI-2'))
        monitor.generate_command_topic(DeviceClass.BUTTON,name='DisplayPort', callback= lambda device,payload=None:setMonitorInput(device.model,'DisplayPort'))
        monitors.append(monitor)
    return monitors

@retry(times=10,delay=60)
def main():
    config = setup_config()
    broker =  config['mqtt_ip']
    port = 1883
    client = mqtt.Client()
    managed_devices = []
    
    client.username_pw_set(config['mqtt_username'], config['mqtt_password'])
    client.connect(broker, port)
    client.on_connect = lambda self, userdata, flags, rc: log.debug(f"Connected with result code {rc}")
    client.on_publish = lambda self, userdata, mid: log.debug(f"Message published with mid {mid}")
    client.on_subscribe = lambda self, userdata, mid, granted_qos: log.debug(f"Subscribed with mid {mid} and QoS {granted_qos}")

    log.info(f'Initializing PC Device')
    net = get_network_info()
    pc = Device(name=get_hw_attr('name'),model=get_hw_attr('model'),manufacturer=get_hw_attr('manufacturer'),ip=net['IP'],mac=net['MAC'],client=client)
    managed_devices.append(pc)
    monitors = getMonitors(client=client)
    managed_devices.extend(monitors)
    initialize_pc_sensors(pc)
    bluetooth_devices = initialize_bluetooth_batteries(client)
    managed_devices.extend(bluetooth_devices)
    for device in managed_devices:
        device.publish_command_topics()
        device.publish_sensor_topics()

    client.on_message = functools.partial(on_message,managed_devices=managed_devices)
    threading.Thread(target=client.loop_forever, daemon=True).start()    
    log.info(f'Sending Sensor data on loop...')
    counter  = 0
    exception_count = 0
    while True:
        try:
            if counter % 15 == 0:
                publish_pc_sensors(pc)
            if counter % 60*15 == 0:
                publish_pc_disk_sensors(pc)
                pc.publish_sensor(int(get_last_boot().timestamp())  ,"Boot Time")  
                for bl_device in bluetooth_devices:
                    bl_batteries = get_bluetooth_battery()
                    bl_device.publish_sensor(bl_batteries[bl_device.name], "Battery Level")
            time.sleep(1)
        except Exception as e:
            exception_count += 1
            log.error(f'[Exeption.{exception_count}]: {e}')
            if exception_count > 3:
                raise f'Too many exceptions, restart required'
        counter+=1

if __name__ == '__main__':
    main()

