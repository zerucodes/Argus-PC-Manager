import socket
import subprocess
import datetime
import pytz
from enum import Enum
import ctypes
import yaml  # Using pip install pyyaml

version = "1.2"
featurecomment = "Config update"

# =====================#
#   Script Instructions
# =====================#
#
# Modify config.yaml with for your specs
#   Run argus.py along with argus test
#   if the command is showing correctly
#   update config enabled=True


local_ip = socket.gethostbyname(socket.gethostname())
enabled = False


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
        'm27q': DEVICE.M27Q,
        'u2722de': DEVICE.U2722DE
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
        return f'{cmmExe} /SetValue {monitor} {vcp_code} {param}'


class Windows():
    def sleep():
        return "C:\\Windows\\System32\\rundll32.exe powrprof.dll,SetSuspendState Standby"

    def shutdown():
        return "C:\\Windows\\System32\\shutdown.exe -s"

    def start_plex():
        return "C:\\Program Files\\Plex\\Plex Media Server\\Plex Media Server.exe"

    def sleep():
        return None


def setup_sender_socket(port=168):
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
        log.info(f"Connecting ip {local_ip}:{port}")
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect((local_ip, port))
    except Exception as e:
        log.warn(f'Socket error: {e}')
    return sock


def setup_reciever_socket(port=169):
    try:
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
            req_target = str(req[1]) if len(req)> 1 and req_class == "monitor" else None
            req_command = req[2] if len(req)> 2 and req_class == "monitor" else req[1] if len(req) > 1 else None
            req_param = req[3] if len(req)> 3 and req_class == "monitor" else req[2] if len(req) > 2 else None

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
                        out = subprocess.run(command)
                        if (out.returncode != 0):
                            log.warn(f'{out}')
                except Exception as e:
                    log.warn(f'Command Error {e}')
            else:
                log.warn(f'Unknown command request!')
        
def setup_config():
    config = None
    global secret
    global log_path
    global cmmExe
    global enabled
    
    # Set up config
    with open('config.yaml') as config_file:
        config = yaml.safe_load(config_file)

    secret = config['secret']
    log_path = config['log_path']
    cmmExe = config['cmmExe']
    enabled = config['enabled']

    log.info(f'Launching Argus v{version}...')
    log.info(f'Latest feature: {featurecomment}')
    log.info(f'Logging at: {log_path}')
    log.info(f'Is Admin: {ctypes.windll.shell32.IsUserAnAdmin() != 0}')
    log.info(f'Config: {str(config)}')
    return config

def main():
    config = setup_config()
    sock = setup_reciever_socket()
    # Listen
    listen_loop(sock)
    sock.close()


if __name__ == '__main__':
    main()
