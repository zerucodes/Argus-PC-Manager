import yaml
import ctypes
import logging
from logging.handlers import TimedRotatingFileHandler
import re
from hwinfo import get_cpu_load,get_cpu_temperature,get_ram_usage,get_ram_temperature,get_disk_usage_simple,get_hw_attr,get_bluetooth_battery,get_last_boot,get_network_info
from enum import Enum
import paho.mqtt.client as mqtt
import threading
import json 
import time
from datetime import datetime
import subprocess
import functools
import socket
import GPUtil
import os,sys,traceback

def setup_logger():
    # Setup Logging:
    level = logging.INFO
    log = logging.getLogger()
    log.setLevel(level)

    file_handler = TimedRotatingFileHandler(f'C:\\Temp\\Argus\\argusmqtt_{datetime.now().strftime("%Y-%m-%d")}.log', when='midnight', interval=1, backupCount=5)
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(funcName)s: %(message)s'))
    file_handler.suffix = "%Y-%m-%d"
    # Create a console handler that logs messages to the console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(funcName)s: %(message)s'))

    # Add both handlers to the logger
    log.addHandler(file_handler)
    log.addHandler(console_handler)

global log
setup_logger()
log = logging.getLogger()


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
                    log.warning(f"Attempt {attempts} failed: {e}")
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
    if not os.path.exists('C:\\Temp'):
        os.mkdir('C:\\Temp\\')

    
    # log.basicConfig(level=log.DEBUG, format='%(asctime)s [%(levelname)s] %(funcName)s: %(message)s',filename='C:\\Temp\\argusmqtt.log')    
    log.debug('Looking for config')
    # Set up config
    if yaml is not None:
        try:
            with open('C:\\Argus\\\mqtt.yaml') as config_file:
                config = yaml.safe_load(config_file)
                log.debug(f'Using config at {config_file}')
        except FileNotFoundError:
            try:
                with open('C:\\Argus\\\mqtt.yaml') as config_file:
                    config = yaml.safe_load(config_file)
                    log.debug(f'Using config at {config_file}')
            except FileNotFoundError:
                log.error(f'No config available')
                config = None

    # If yaml module isn't available or config file isn't found, assign default values
    if config is None:
        log.debug(f'Using default config in demo mode')
        
        config = {
            "mqtt_username": input('Mqtt Username: '),
            "mqtt_password": input("Mqtt password: "),
            "cmmExe": "ControlMyMonitor.exe",
            "enabled": False
        }
    log.info(f'\n{"*"*50}\nLaunching Argus v{version}\n{"*"*50}\n')
    log.info(f'Latest feature: {featurecomment}')
    log.debug(f'Is Admin: {ctypes.windll.shell32.IsUserAnAdmin() != 0}')    
    log.debug(f'Config: {str(config)}')

    return config
class INPUT(Enum):
        DP = 15
        HDMI1 = 17
        HDMI2 = 18
        USBC = 27
class DeviceClass(Enum):
    BATTERY = 'battery'
    DATA_SIZE = 'data_size'
    TEMPERATURE = 'temperature'
    POWER = 'power_factor'
    LIGHT = 'light'
    TIMESTAMP = 'timestamp'
    BUTTON = 'button'
    SWITCH = 'switch'

@DeprecationWarning
class Sensor:
    def  __init__(self, entityClass=None,name=None,message=None, callback=None ):
        sensor = {}
        sensor['device_class'] = entityClass.value
        sensor['name'] = name

        match entityClass:
            case DeviceClass.BATTERY:
                sensor['name'] = 'Battery Level'
                sensor['unit_of_measurement'] = '%'           
            case 'power':
                log.debug('TBD')
            case DeviceClass.DATA_SIZE:
                if name:
                    sensor['entity_category'] = 'diagnostic'
                    sensor['unit_of_measurement'] = 'B'
                    sensor['suggested_display_precision'] = 0
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

        sensor_name = re.sub(r'[^a-zA-Z0-9]', '_', sensor["name"].lower())
        sensor_name =  re.sub(r'_{2,}','_',sensor_name) # duplicate  _ chars
        
        sensor['state_topic'] = f'homeassistant/sensor/{self.device_name}/{sensor_name}/state'
        sensor['unique_id'] = f"{self.device_name}_{sensor_name}"   
        sensor['device'] = self.config

        if 'unit_of_measurement' in sensor and sensor['unit_of_measurement']  == '%':
            sensor['suggested_display_precision'] = 2

        if callback: self.callback = callback
        self.sensor = sensor
        return sensor
    
    def publish(self):
        return self.sensor['name'], json.dumps(self.sensor['state_topic'])
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
        self.state_callbacks = {}
        self.state_intervals = {}
    def __str__(self):
        return (f"Device(name={self.name}, model={self.model}, manufacturer={self.manufacturer}, "
                f"mac={self.mac}, ip={self.ip}, bluetooth={self.bluetooth}, client={self.client}, "
                f"device_name={self.device_name}, identifiers={self.identifiers})")
    
    def set_config(self):
        config =  {
            "name" : self.name
        }
        if self.ip or self.mac or self.bluetooth:
            config['connections'] = []
        else:
            config['identifiers'] = self.identifiers
        if self.manufacturer: config["manufacturer"] = self.manufacturer
        if self.model: config["model"] = self.model
        if self.mac: config['connections'].append(['mac',self.mac])
        if self.ip: config['connections'].append(['ip',self.ip])
        if self.bluetooth: config['connections'].append(['bluetooth',self.bluetooth])
        self.config = config
    
    def generate_sensor_topic(self,device_class,name=None,message=None, callback=None,update_interval=15):
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
                    sensor['suggested_display_precision'] = 0
            case DeviceClass.POWER:
                sensor['name'] = f'{name} Usage'
                sensor['unit_of_measurement'] = '%'
                del sensor['device_class']
            case DeviceClass.TEMPERATURE:
                sensor['name'] = f'{name} Temperature'
                sensor['unit_of_measurement'] = '°C'
            case DeviceClass.TIMESTAMP:
                sensor['entity_category'] = 'diagnostic'
                sensor['value_template']  = '{{ value | int | timestamp_local | as_datetime }}'


        sensor_name = re.sub(r'[^a-zA-Z0-9]', '_', sensor["name"].lower()) #  battery_level
        sensor_name =  re.sub(r'_{2,}','_',sensor_name) # duplicate  _ chars
        
        sensor['state_topic'] = f'homeassistant/sensor/{self.device_name}/{sensor_name}/state'
        sensor['unique_id'] = f"{self.device_name}_{sensor_name}"  #  zeru_pc_battery_level
        sensor['device'] = self.config

        if callback and sensor['state_topic'] not in self.state_callbacks:
            self.state_callbacks[sensor['state_topic']] = callback
            self.state_intervals[sensor['state_topic']] = update_interval
        if 'unit_of_measurement' in sensor and sensor['unit_of_measurement']  == '%':
            sensor['suggested_display_precision'] = 2
        if 'unit_of_measurement' in sensor:
            sensor['state_class'] = 'measurement'
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
        sensor['command_topic'] = f'homeassistant/{sensor["device_class"]}/{self.device_name}/{sensor_name}/set'
        match device_class:
            case DeviceClass.LIGHT:
                sensor['optimistic'] = True
                sensor['brightness'] = True  
            case DeviceClass.SWITCH:
                sensor['optimistic'] = True
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

    def publish_sensor_topics(self):
        for topic in self.sensor_topics:
            sensor_topic = self.sensor_topics[topic]
            log.debug(f'Publishing topic: {topic} : {sensor_topic}')
            self.client.publish(sensor_topic['state_topic'].replace('/state','/config'), json.dumps(sensor_topic))
            
    def publish_command_topics(self):
        for topic in self.command_topics:
            sensor_topic = self.command_topics[topic]
            log.debug(f'Publishing topic: {topic} : {sensor_topic}')
            
            self.client.publish(sensor_topic['command_topic'].replace('/set','/config'), json.dumps(sensor_topic))
            self.client.subscribe(sensor_topic['command_topic'])

    def publish_sensor(self,value,name):
        sensor_name = re.sub(r'[^a-zA-Z0-9]', '_', name.lower()) 
        sensor_name =  re.sub(r'_{2,}','_',sensor_name)
        sensor_topic = self.sensor_topics[sensor_name]
        self.client.publish(sensor_topic['state_topic'], value, retain=True)

@DeprecationWarning
def initialize_bluetooth_batteries(client):
    devices = []
    try:
        log.info(f'Inititalizing Bluetooth devices with battery data')
        bl_devices = get_bluetooth_battery()
        if bl_devices:
            log.debug(f'Found {bl_devices}')
        for bl_device in bl_devices:
            device = Device(name=bl_device['name'],bluetooth=bl_device['mac'],client=client)
            battery = bl_device['battery']
            device.generate_sensor_topic(DeviceClass.BATTERY)
            devices.append(device)
            log.info(f'{bl_device["name"]} at {battery}%')
    except Exception as e:
        log.error(f'{e}')
    return devices

@DeprecationWarning
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
    this_pc.generate_command_topic(DeviceClass.SWITCH,name='Power', callback= lambda payload,device:pc_power(device, status=getPayloadAttr(payload,'status')))

def pc_power(device, status):
    if status == 'ON':
        # wake_on_lan()
        print(f"test  {status}")
    elif status == 'OFF':
        global shutdown
        shutdown = True
        publish_pc_sensors(device)
        time.sleep(3)        
        runCommand(command="C:\\Windows\\System32\\shutdown.exe -s -t 0",enabled=True)
        sys.exit()

def publish_pc_disk_sensors(this_pc):
    log.debug(f'Publishing Drive Sensors')
    usage = get_disk_usage_simple()
    for drive in usage:
        this_pc.publish_sensor(usage[drive].free,f'{drive} Drive Free')
        this_pc.publish_sensor(usage[drive].total,f'{drive} Drive Total')

def get_disk_remaining(total=False, drive=None):
    usage = get_disk_usage_simple(drive) 
    if drive is None:
        return usage.total if total else usage.free
    else:
        return usage[drive].total if total else usage[drive].free
    
@DeprecationWarning
def publish_pc_sensors(this_pc):    
    log.debug(f'Publishing PC Sensors')
    sensors = ['CPU','GPU','RAM']
    global shutdown
    for sensor in sensors:
        try:
            temp = get_pc_sensor(sensor,'Temperature')
            usage = get_pc_sensor(sensor,'Usage')
            if temp is not None:
                this_pc.publish_sensor(0 if shutdown else temp,f'{sensor} Temperature')
            if usage is not None:
                this_pc.publish_sensor(0 if shutdown else usage,f'{sensor} Usage')
        except Exception as e:
            log.error(f'Unable to publish {sensor}: {e}')


def get_pc_sensor(sensor,type):
    value = 0
    global valid_sensors,shutdown
    valid_sensors = []
    
    # During shutdown check if the sensor has been sent before
    #  if not, send None for faster shutdown
    # Todo: send Unavailable for temp, 0 for usage
    if shutdown and tuple((sensor,type)) not in valid_sensors:
        log.info(f'Shutdown flag {shutdown}, sending 0')
        return 0
    match sensor:
        case 'CPU':
            match type:
                case 'Usage':
                    value = get_cpu_load()
                case 'Temperature':
                    value = get_cpu_temperature()
        case 'GPU':
            gpus = GPUtil.getGPUs()
            if len(gpus) > 1:
                log.error(f'Multiple GPUs not supported yet found ({len(gpus)}), using first')
            match type:
                case 'Usage':
                    value = gpus[0].load if len(gpus)>= 1 else None
                case 'Temperature':
                    value =  gpus[0].temperature if len(gpus)>= 1 else None
        case 'RAM':
            match type:
                case 'Usage':
                    value = get_ram_usage()
                case 'Temperature':
                    value = get_ram_temperature()
    value = None if value is None else round(value,3) 
    if value is not None and tuple((sensor,type)) not in valid_sensors:
        valid_sensors.append(tuple((sensor,type)))

    return  value

@DeprecationWarning
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

def runCommand(command,enabled=False):
    if (command):
        try:
            log.debug(f'Running command: {command}' if enabled else f'Running demo: {command}')
            if enabled:
                out = subprocess.run(command,capture_output=True)
                if (out.returncode != 0):
                    log.warning(f'{out}')
                # log.debug(f'{out}')
                return json.loads(out.stdout.decode())
        except Exception as e:
            log.warning(f'Command Error {e}')
            return None

def getPayloadAttr(payload,attr,default=0):
    if attr in payload:
        return payload[attr]
    elif attr == 'brightness':
        return 255 if payload['state'] == 'ON' else 0
    elif attr == 'status': 
        return payload
    else:
        return default
    
def setMonitorInput(monitorName,input):
    selection = INPUT.DP
    match input:
        case 'USB-C':
            selection = INPUT.USBC
        case 'HDMI-1':
            selection = INPUT.HDMI1
        case 'HDMI-2':
            selection = INPUT.HDMI2
        case 'DisplayPort':
            selection = INPUT.DP
    global exe_dir
    output = runCommand(f'{os.path.join(exe_dir, "VCPController.exe")}  -setVCP --monitor="{monitorName}" --vcp=0x60 --value={selection.value} ',enabled=True)
    log.debug(f"{output}")

def wake_on_lan(mac_address= '2C:F0:5D:A9:51:B9'):
    # Forming the magic packet to turn on the PC
    mac_address = mac_address.replace(':', '').replace('-','')
    magic_packet = 'FF' * 6 + mac_address * 16
    magic_packet_bytes = bytes.fromhex(magic_packet)

    # Broadcasting the magic packet on the local network
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.connect((socket.gethostbyname(socket.gethostname()), 368))
    sock.sendto(magic_packet_bytes, ('192.168.1.255', 9))
    sock.close()

@DeprecationWarning
def getMonitors(client):
    monitors = []
    log.info(f'Initializing Display Monitors')
    global exe_dir
    output = runCommand(f'{os.path.join(exe_dir, "VCPController.exe")} -getMonitors',enabled=True)
    if output and 'monitors' in output:
        output = output['monitors']
    if output:
        for m in output:
            monitor = Device(name=m['model'],model=m['name'],client=client) # Swap name and monitor due to model containing friendlier name and model being unique
            monitor.generate_command_topic(DeviceClass.LIGHT,name='Screen Brightness',callback= lambda payload,device:runCommand(enabled=True, command=f'{os.path.join(exe_dir, "VCPController.exe")} -setVCP --vcp=0x10 --value={int(getPayloadAttr(payload,"brightness",0)/255*100 )} --monitor="{device.model}"'))
            monitor.generate_command_topic(DeviceClass.BUTTON,name='USB-C', callback= lambda device,payload=None:setMonitorInput(device.model,'USB-C'))
            monitor.generate_command_topic(DeviceClass.BUTTON,name='HDMI-1', callback= lambda device,payload=None:setMonitorInput(device.model,'HDMI-1'))
            monitor.generate_command_topic(DeviceClass.BUTTON,name='HDMI-2', callback= lambda device,payload=None:setMonitorInput(device.model,'HDMI-2'))
            monitor.generate_command_topic(DeviceClass.BUTTON,name='DisplayPort', callback= lambda device,payload=None:setMonitorInput(device.model,'DisplayPort'))
            monitors.append(monitor)
    log.info(f'Created {len(monitors)} monitors')
    return monitors

class MQTTMgr:
    
    _last_cache = 0
    _cache_duration = 300
    global shutdown
    shutdown = False

    def __init__(self):
        self.devices = []
  
        self.battery_cache = []
    
    def setup(self, broker, port, username, password):
        # self.client = mqtt.Client()
        # self.client.username_pw_set(username, password)
        # self.client.connect(broker, port)
        self.connect_mqtt(broker, port, username, password)
        self.client.on_connect = lambda self, userdata, flags, rc: log.info(f"Connected with result code {rc}")
        self.client.on_publish = lambda self, userdata, mid: log.debug(f"Message published with mid {mid}")
        self.client.on_subscribe = lambda self, userdata, mid, granted_qos: log.debug(f"Subscribed with mid {mid} and QoS {granted_qos}")
        
        self.start_listener()

        global exe_dir

        exe_dir = os.path.dirname("C:\Argus\\")

    def connect_mqtt(self, broker, port, username, password, keepalive=60):
        while True:
            try:
                self.client = mqtt.Client()
                self.client.username_pw_set(username, password)
                result_code = self.client.connect(broker, port, keepalive)
                
                if result_code == 0:
                    log.info("Connected successfully!")
                    return True
                else:
                    log.error("Connection failed with code:", result_code)
            except Exception as e:
                log.exception("Error while connecting:", e)
            
            log.info("Retrying in 60 seconds...")
            time.sleep(60)
            
    def add_device(self, new_devices):
        if isinstance(new_devices,list):
            for device in new_devices:
                if device not in self.devices:
                    self.devices.append(device)
                    log.info(f'Added new device: {device}')
        elif new_devices not in self.devices:
            self.devices.append(device)
    
    def initialize_pc(self):
        net = get_network_info()
        pc = Device(name=get_hw_attr('name'),model=get_hw_attr('model'),manufacturer=get_hw_attr('manufacturer'),ip=net['IP'],mac=net['MAC'],client=self.client)
        log.debug(f'Initializing PC Drive Sensors')
        for drive in get_disk_usage_simple():
            pc.generate_sensor_topic(DeviceClass.DATA_SIZE,f'{drive} Drive Free', callback= lambda drive=drive: get_disk_remaining(total=False,drive=drive),update_interval=120 )
            pc.generate_sensor_topic(DeviceClass.DATA_SIZE,f'{drive} Drive Total', callback= lambda drive=drive: get_disk_remaining(total=True,drive=drive) ,update_interval=120)
        
        log.debug(f'Initializing PC Sensors')
        sensors = ['CPU','GPU','RAM']
        for sensor in sensors:
            pc.generate_sensor_topic(DeviceClass.TEMPERATURE,sensor,callback= lambda sensor=sensor: get_pc_sensor(sensor,'Temperature'),update_interval=15)
            pc.generate_sensor_topic(DeviceClass.POWER,sensor, callback= lambda sensor=sensor: get_pc_sensor(sensor,'Usage'),update_interval=15)

        pc.generate_sensor_topic(DeviceClass.TIMESTAMP,"Boot Time", callback= lambda: int(get_last_boot().timestamp()) ,update_interval=240)
        pc.generate_command_topic(DeviceClass.SWITCH,name='Power', callback= lambda payload,device:pc_power(device, status=getPayloadAttr(payload,'status')))
        self.devices.append(pc)
        return pc

    def initialize_monitors(self):
        monitors = []
        log.info(f'Initializing Display Monitors')
        global exe_dir
        output = runCommand(f'{os.path.join(exe_dir, "VCPController.exe")} -getMonitors',enabled=True)
        if output and 'monitors' in output:
            output = output['monitors']
        if output:
            for m in output:
                monitor = Device(name=m['model'],model=m['name'],client=self.client) # Swap name and monitor due to model containing friendlier name and model being unique
                monitor.generate_command_topic(DeviceClass.LIGHT,name='Screen Brightness',callback= lambda payload,device:runCommand(enabled=True, command=f'{os.path.join(exe_dir, "VCPController.exe")} -setVCP --vcp=0x10 --value={int(getPayloadAttr(payload,"brightness",0)/255*100 )} --monitor="{device.model}"'))
                monitor.generate_command_topic(DeviceClass.BUTTON,name='USB-C', callback= lambda device,payload=None:setMonitorInput(device.model,'USB-C'))
                monitor.generate_command_topic(DeviceClass.BUTTON,name='HDMI-1', callback= lambda device,payload=None:setMonitorInput(device.model,'HDMI-1'))
                monitor.generate_command_topic(DeviceClass.BUTTON,name='HDMI-2', callback= lambda device,payload=None:setMonitorInput(device.model,'HDMI-2'))
                monitor.generate_command_topic(DeviceClass.BUTTON,name='DisplayPort', callback= lambda device,payload=None:setMonitorInput(device.model,'DisplayPort'))
                monitors.append(monitor)

        log.info(f'Created {len(monitors)} monitors')
        self.add_device(monitors)
        return  monitors

    def helper_get_bt_battery(self,name):
        if  (not self.battery_cache or (time.time() - self._last_cache) > self._cache_duration):
            log.debug(f'Refreshing bt battery data...')
            self.battery_cache = get_bluetooth_battery()
            self._last_cache = time.time()
        # if self.battery_cache and self.battery_cache["name"] == name  and bl_device['battery']:
        #     return bl_device['battery']
        for bl_device in  self.battery_cache:
            if  bl_device['name'] == name:
                log.debug(f'{bl_device["name"]} at {bl_device["battery"]}%')
                return bl_device['battery']
        return None
    
    def initialize_bluetooth_batteries(self):
        devices = []
        try:
            log.info(f'Inititalizing Bluetooth devices with battery data...')

            self.battery_cache = get_bluetooth_battery()
            self._last_cache = time.time()
            for bl_device in self.battery_cache:
                device = Device(name=bl_device['name'],bluetooth=bl_device['mac'],client=self.client)
                battery = bl_device['battery']
                device_name = bl_device['name']
                device.generate_sensor_topic(
                    DeviceClass.BATTERY,
                    callback=lambda n=device_name: self.helper_get_bt_battery(n),
                    update_interval=10
                )
                # device.generate_sensor_topic(DeviceClass.BATTERY, callback= lambda device:self.helper_get_bt_battery(bl_device['name']),update_interval=300)
                devices.append(device)
                log.info(f'{bl_device["name"]} at {battery}%')
        except Exception as e:
            log.error(f'{e}')

        self.add_device(devices)
        return devices
    
    def publish_all_topics(self):
        for device in self.devices:
            device.publish_command_topics()
            device.publish_sensor_topics()

    def start_listener(self):
        self.client.on_message = functools.partial(self.on_message)
        self.listen_thread = threading.Thread(target=self.client.loop_forever, daemon=True)
        self.listen_thread.start()    

    def on_message(self,client, userdata, message):
        if isinstance(message.payload,bytes):
            payload = message.payload.decode()
        try:
            payload = json.loads(message.payload)
        except Exception as e:
            log.debug(f'Non json payload')
        log.info(f'recieved payload {payload}')
        for device in self.devices:
            for callback_topic in device.callbacks:
                if message.topic == callback_topic:
                    device.callbacks[callback_topic](payload=payload,device=device)

    def publish_all_sensors(self, index):
        for device in self.devices:
            for callback in device.state_callbacks:
                if index % device.state_intervals[callback]  == 0:
                    try:
                        val = device.state_callbacks[callback]()
                        log.debug(f'callback: {callback} > {val}')
                        self.client.publish(callback,val, retain=True)
                    except Exception as e:
                        log.error(f'{callback} failed')


@retry(times=10,delay=60)
def main():
    mgr = MQTTMgr()
    config = setup_config()
    mgr.setup(config['mqtt_ip'], 1883, config['mqtt_username'],config['mqtt_password'])
    mgr.initialize_monitors()
    mgr.initialize_pc()
    mgr.initialize_bluetooth_batteries()
    mgr.publish_all_topics()
    index = 0
    while True:
        mgr.publish_all_sensors(index=index)
        time.sleep(1)
        index+=1


if __name__ == '__main__':
    main()

