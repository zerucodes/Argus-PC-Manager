import socket
import subprocess
import datetime
import os
from enum import Enum
import ctypes
try:
    import yaml  # Using pip install pyyaml
except ImportError:
    yaml = None

version = "1.3"
featurecomment = "Made yaml optional, improved local ip detection"

# =====================#
#   Script Instructions
# =====================#
#
# Modify config.yaml with for your specs
#   Run argus.py along with argus test
#   if the command is showing correctly
#   update config enabled=True

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


class Monitor():
    class DEVICE(Enum):
        # Find the monitor Serial Number/Monitor Name/ Short Monitor ID from CMM
        M27Q = GIGABYTE = "GBT270D"
        DELL = U2722DE = "DELL U2722DE"

    class VCPCode(Enum):
        # Standard Vesa Monitor Codes
        INPUT = 60                  # (15,17,18,27)
        BRIGHTNESS = 10             # (0-100)
        CONTRAST = 12               # (0-100)
        ORIENTATION = 0xAA          # (1,2,4) untested

    class INPUT(Enum):
        DP = 15
        HDMI1 = 17
        HDMI2 = 18
        USBC = 27
    monitor_dict = {
        '1': 'Primary',
        '2': 'Secondary',
        '3':  DEVICE.M27Q.value,
        'm27q': DEVICE.M27Q.value,
        'u2722de': DEVICE.U2722DE.value
    }
    vcp_dict = {
        'input': VCPCode.INPUT.value,
        'brightness': VCPCode.BRIGHTNESS.value,
        'contrast': VCPCode.CONTRAST.value,
        'orientation': VCPCode.ORIENTATION.value
    }
    input_dict = {
        'dp': INPUT.DP.value,
        'displayport': INPUT.DP.value,
        'hdmi': INPUT.HDMI1.value,
        'hdmi1': INPUT.HDMI1.value,
        'hdmi2': INPUT.HDMI2.value,
        'usbc': INPUT.USBC.value
    }
    # Get control command string

    def control(monitor, vcp_code, param):
        return f'{cmmExe} /SetValueIfNeeded  {monitor} {vcp_code} {param}'


class Windows():
    def sleep():
        return "C:\\Windows\\System32\\rundll32.exe powrprof.dll,SetSuspendState Standby"

    def shutdown():
        return "C:\\Windows\\System32\\shutdown.exe -s"

    def start_plex():
        return "C:\\Program Files\\Plex\\Plex Media Server\\Plex Media Server.exe"

    def sleep():
        return None


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '192.168.1.100' 
    finally:
        s.close()
    return IP

def setup_sender_socket(port=168):
    try:
        log.info(f"Connecting ip {local_ip}:{port}")
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect((local_ip, port))
    except Exception as e:
        log.warn(f'Socket error: {e}')
    return sock

def setup_reciever_socket(port=169):
    try:
        local_ip = get_local_ip()
        # IP address and port to listen on
        log.info(f"Connecting ip {local_ip}:{port}")
        # Create a UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Set the socket to reuse the address
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Bind the socket to the local IP address and port
        sock.bind((local_ip, port))
        # Enable broadcasting on the socket
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        log.info(f"Successfuly setup sock {sock}")
    except Exception as e:
        log.warn(f'Socket error: {e}')
    return sock

def listen_loop(sock):
    # Listen for incoming UDP packets
    while True:
        data, addr = sock.recvfrom(1024)  # Buffer size is 1024 bytes
        data = data.decode()
        log.info(f"{addr} \t {data}")
        # Format: secret.class (target) command parameter
        if secret in data:
            request = data.lower().split(secret)
            if len(request) <= 1:
                continue
            req = request[1].split(" ")  # monitor 1 input usbc
            req_class = req[0]
            req_target = str(req[1]) if req_class == "monitor" else None
            req_command = req[2] if req_class == "monitor" else req[1]
            req_param = req[3] if req_class == "monitor" else req[2]

            if req_class == "monitor":
                target_monitor = Monitor.monitor_dict[req_target]
                vcp_code = Monitor.vcp_dict[req_command]
                if req_command == "input":
                    req_param = Monitor.input_dict[req_param]
                command = Monitor.control(
                    monitor=target_monitor, vcp_code=vcp_code, param=req_param)

            elif req_class == "pc":
                if req_command == "sleep":
                    log.info("Sleeping...")
                    command = Windows.sleep()
                elif req_command == "poweroff":
                    log.info("Shutting down...")
                    command = Windows.shutdown()
                elif req_command == "startplex":
                    log.info("Staring plex...")
                    command = Windows.start_plex()

            if (command):
                try:
                    log.info(f'Running command: {command}' if enabled else 'Running demo: {command}')
                    if enabled:
                        out = subprocess.run(command,cwd=os.path.dirname(command.split()[0]), capture_output=True)
                        if (out.returncode != 0):
                            log.warn(f'{out}')
                        log.info(f'{out}')
                except Exception as e:
                    log.warn(f'Command Error {e}')

def setup_config():
    config = None
    global secret
    global log_path
    global cmmExe
    global enabled
    global local_ip
   

    # Set up config
    if yaml is not None:
        try:
            with open('argus.yaml') as config_file:
                config = yaml.safe_load(config_file)
        except FileNotFoundError:
            try:
                with open(r'C:\Argus\argus.yaml') as config_file:
                    config = yaml.safe_load(config_file)
            except FileNotFoundError:
                config = None
            
    
    # If yaml module isn't available or config file isn't found, assign default values
    if config is None:
        config = {
            "secret": "argus.",
            "log_path": r"C:\Logs\argus.log",
            "cmmExe": "ControlMyMonitor.exe",
            "enabled": False
        }
    secret = config['secret']
    log_path = config['log_path']
    cmmExe = config['cmmExe']
    enabled = config['enabled']

    log.info(f'\n\n')
    log.info(f'Launching Argus v{version}...')
    log.info(f'Latest feature: {featurecomment}')
    log.info(f'Is Admin: {ctypes.windll.shell32.IsUserAnAdmin() != 0}')    
    log.info(f'Config: {str(config)}')
    return config

def main():
    setup_config()
    sock = setup_reciever_socket()
    # Listen
    listen_loop(sock)
    sock.close()

if __name__ == '__main__':
    main()