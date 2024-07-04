import json
import GPUtil
import requests
import json
import os
import shutil
import wmi
import time
import datetime
import subprocess
import psutil
import socket

def get_size(bytes, suffix="B"):
    factor = 1024
    for unit in ["", "K", "M", "G", "T", "P"]:
        if bytes < factor:
            return f"{bytes:.2f}{unit}{suffix}"
        bytes /= factor

def get_openHWSensor():
    w = wmi.WMI(namespace="root\OpenHardwareMonitor")
    temperature_infos = w.Sensor()
    for sensor in temperature_infos:
        if sensor.SensorType == 'Temperature':
            print(sensor.Name, sensor.Value)

def get_cpu_temperature():
    w = wmi.WMI(namespace="root\OpenHardwareMonitor")
    temperature_infos = w.Sensor()
    total = 0
    count = 0
    for sensor in temperature_infos:
        if sensor.SensorType == 'Temperature' and 'CPU' in sensor.Name:
            # print(sensor.Name, sensor.Value)
            total += sensor.Value
            count += 1
    return total/count if count else 0


def get_ram_temperature():
    w = wmi.WMI(namespace="root\OpenHardwareMonitor")
    temperature_infos = w.Sensor()
    total = 0
    count = 0
    for sensor in temperature_infos:
        if sensor.SensorType == 'Temperature' and 'Generic Memory' in sensor.Name:
            # print(sensor.Name, sensor.Value)
            total += sensor.Value
            count += 1
    if not count:
        for sensor in temperature_infos:
            if sensor.SensorType == 'Temperature' and 'Memory' in sensor.Name:
                # print(sensor.Name, sensor.Value)
                total += sensor.Value
                count += 1
    return total/count if count!=0 else None

def get_ram_usage():
    w = wmi.WMI(namespace="root\OpenHardwareMonitor")
    temperature_infos = w.Sensor()
    total = 0
    count = 0
    for sensor in temperature_infos:
        if sensor.SensorType == 'Load' and 'Generic Memory' == sensor.Name:
            # print(sensor.Name, sensor.Value)
            total += sensor.Value
            count += 1
    if not count:
        for sensor in temperature_infos:
            if sensor.SensorType == 'Load' and 'Memory' == sensor.Name:
                # print(sensor.Name, sensor.Value)
                total += sensor.Value
                count += 1
    return total/count if count else 0

def get_cpu_load():
    w = wmi.WMI(namespace="root\OpenHardwareMonitor")

    total = 0
    count = 0

    for _ in range(5):
        load_infos = w.Sensor()
        for sensor in load_infos:
            if sensor.SensorType == 'Load' and 'CPU Total' in sensor.Name:
                # print(sensor.Name, sensor.Value)
                total += sensor.Value
                count += 1
        time.sleep(.5)  # Sleep for 1 second

    return total/count if count else 0

def get_system_info():
    info = {}

    # CPU information
    info['CPU'] = {"load": round(get_cpu_load(),2),
                    "temperature" : round(get_cpu_temperature(),2) }

    info["RAM"] = {
        "load" : round(get_ram_usage(),2)
    }
    # GPU information
    gpus = GPUtil.getGPUs()
    if gpus:
        gpu_info = [{'name': gpu.name, 'load': gpu.load*100 ,
                    'temperature': gpu.temperature } for gpu in gpus]
        info["GPU"] = gpu_info[0]
    # Disk Information
    info["DISK"] = get_disk_usage()


    return info


def get_disk_usage():
    disk_usage_dict = {}

    for drive_letter in range(ord('A'), ord('Z')+1):
        drive = chr(drive_letter) + ':/'

        if os.path.exists(drive):
            usage = shutil.disk_usage(drive)

            total_gb = usage.total / (2**30)
            used_gb = usage.used / (2**30)
            free_gb = usage.free / (2**30)
            used_percent = (usage.used / usage.total) * 100

            disk_usage_dict[drive] = {
                'Total': f"{total_gb:.2f} GB",
                'Usage_GB': f"{used_gb:.2f} GB",
                'Free': f"{free_gb:.2f} GB",
                'Used': f"{used_percent:.2f}",
            }

    return disk_usage_dict

def get_disk_usage_simple():
    disk_usage_dict = {}
    for drive_letter in range(ord('A'), ord('Z')+1):
        drive = chr(drive_letter) + ':'
        if os.path.exists(drive):
            disk_usage_dict[drive] = shutil.disk_usage(drive)
    return disk_usage_dict

class log:
    def info(message, level='INFO'):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
        log_message = f"[{level}] {timestamp} - {message}"
        print(log_message)
        try:
            with open(log_path, 'a') as log_file:
                log_file.write(log_message + "\n")
        except IOError as e:
            print(f'File error: {e}')

    def debug(message):
        log.info(message, level='DEBUG')

    def warn(message):
        log.info(message, level='WARNING')

def get_hw_info():
    info = get_system_info()
    json_dump = json.dumps(info, indent=4)
    url = 'https://arguszeru.duckdns.org/api/webhook/arguspc.hwinfo'
    log.info(json_dump)
    response = requests.post(url, data=json_dump, headers={
                            'Content-Type': 'application/json'})
    log.info(response)


def get_battery_level(friendly_name):
    powershell_script = f"""
        function Get-Battery {{
            param(
                [Parameter(Mandatory=$true)]
                [string]$friendly_name
            )
            $battery_level = -1
            Get-PnpDevice -FriendlyName "*$friendly_name*" | ForEach-Object {{
                $test = $_ |
                Get-PnpDeviceProperty -KeyName '{{104EA319-6EE2-4701-BD47-8DDBF425BBE5}} 2' |
                    Where-Object Type -ne 'Empty'
                if ($test) {{
                    $battery_level = Get-PnpDeviceProperty -InstanceId $($test.InstanceId) -KeyName '{{104EA319-6EE2-4701-BD47-8DDBF425BBE5}} 2' | ForEach-Object Data
                }}
                return $battery_level
            }}
        }}

        Get-Battery -friendly_name '{friendly_name}'
        """

    result = subprocess.run(
        ["powershell", "-Command", powershell_script],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise Exception(f"Error executing PowerShell: {result.stderr}")
    r = result.stdout.strip()
    try:
        return int(r)
    except  Exception as e:
        return -1

def get_bluetooth_battery():
    bt_command = '''
    $bl = Get-PnpDevice -FriendlyName "*"  -Class Bluetooth
        $bl | ForEach-Object {
            $battery = Get-PnpDeviceProperty -InstanceId $_.InstanceId  -KeyName "{104EA319-6EE2-4701-BD47-8DDBF425BBE5} 2"  | Where-Object Type -ne 'Empty' 
            if ($battery.Data) {
                Write-Host "$($_.FriendlyName),,,$($battery.Data)"
            }
        }
    '''
    result = subprocess.run(
        ["powershell", "-Command", bt_command],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        raise Exception(f"Error executing PowerShell: {result.stderr}")
    r = result.stdout.strip()
    try:
        batteries = {}
        for line in r.split("\n"):
            batteries[line.split(",,,")[0]] = int(line.split(",,,")[1])
        return batteries
    except  Exception as e:
        return {}
    
def get_last_boot():

    boot_time_timestamp = psutil.boot_time()
    boot_time = datetime.datetime.fromtimestamp(boot_time_timestamp)
    return boot_time
    
def get_hw_attr(attr):
    try:
        c = wmi.WMI()
        v = c.Win32_ComputerSystem()[0]
        return getattr(v,attr)
    except Exception as e:
        print(e)
        
# Test
def get_bt_info():
    devices = ['G915 Keyboard', 'MX Master 3']
    battery_level = {}
    for device in devices:
        battery = get_battery_level(device)
        if battery != -1:
            battery_level[device.replace(' ','_')] = battery

    json_dump = json.dumps(battery_level, indent=4)
    url = 'https://HASSURL.duckdns.org/api/webhook/arguspc.battery_level'
    log.info(json_dump)
    response = requests.post(url, data=json_dump, headers={
                            'Content-Type': 'application/json'})
    log.info(response)
    return battery_level


def get_default_interface():
    # Get default gateway details
    gateways = psutil.net_if_addrs()
    default_gateway = psutil.net_if_stats()
    for interface, status in default_gateway.items():
        if status.isup:
            return interface
    return None

def get_network_info(interface=get_default_interface()):
    network_info = {'MAC':None,'IP':None}
    if not interface:
        return network_info
    addrs = psutil.net_if_addrs().get(interface, [])
    
    for addr in addrs:
        if addr.family == socket.AF_INET:
            network_info['IP'] = addr.address
        elif addr.family == psutil.AF_LINK:
            network_info['MAC'] = addr.address
    return network_info

if __name__ == "__main__":
    global log_path
    log_path = 'C:\zdev\logs\hwinfo_log.ztxt'
    log.info('Starting HWInfo')
    while True:
        try:
            get_hw_info()
            print(get_bt_info())
            time.sleep(90)
        except Exception as e:
            print(e)
        