import socket
import subprocess
import datetime, pytz
from enum import Enum
import ctypes

version = "1.0"

#=====================#
#   Configuration
#=====================#
secret = "prefix."                          # Required piece of string to allow commands
log_filename = "log.txt"                    # path to log file
cmmExe = "C:\\path\\ControlMyMonitor.exe"   # path to CMM exe

class log:
    def info( message):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
        log_message = f"[INFO] {timestamp} - {message}"
        print(log_message)
        with open(log_filename, 'a') as log_file:
            log_file.write(log_message + "\n")
    def warn( message):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
        log_message = f"[WARNING] {timestamp} - {message}"
        print(log_message)
        with open(log_filename, 'a') as log_file:
            log_file.write(log_message + "\n")

class Monitor(Enum):
    # Find the monitor Serial Number/Monitor Name/ Short Monitor ID from CMM
    M27Q,GIGABYTE = "GBT270D"
    DELL,U2722DE = "DVRP1H3"

class VCPCode(Enum):
    # Standard Vesa Monitor Codes
    INPUT = 60                  # (15,17,18,27)
    BRIGHTNESS = 10             # (0-100)
    CONTRAST = 12               # (0-100)
    ORIENTATION = 0xAA          # (1,2,4) untested 

    # TODO: Are inputs really manufacturer specific?
class INPUT(Enum):
    DP = 15
    HDMI1 = 17
    HDMI2 = 18
    USBC = 27

def setup_socket():
    # IP address and port to listen on
    local_ip = socket.gethostbyname(socket.gethostname())
    local_port = 169

    log.info(f"Connecting ip {local_ip}:{local_port}")
    # Create a UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # Set the socket to reuse the address
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # Bind the socket to the local IP address and port
    sock.bind((local_ip, local_port))

    # Enable broadcasting on the socket
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    log.info(f"Successfuly setup sock {sock}")
    return sock

def listen_loop(sock):  
    # Listen for incoming UDP packets
    while True:
        data, addr = sock.recvfrom(1024)  # Buffer size is 1024 bytes
        data = data.decode()
        log.info(f"{addr} \t {data}")

        if secret in data:
            request = data.split(secret)
            if len(request) <= 1 :
                continue
            req = request[1].split(" ")[0]
            args = ""
            if (" " in request[1]):
                args = request[1].split(" ")[1:]
            log.info(f"Request :{req} {str(args)}")

            target = Monitor.U2722DE #default target
            if req in ("input","brightness","contrast","orientation") :
                monitorcmd = ""
                if req == "input": # ie: prefix.input pc
                    monitorcmd = VCPCode.INPUT
                    if (args[0].lower() in ["pc","desktop","displayport"]):
                        monitorparam = INPUT.DP
                    if (args[0].lower() in ["work","laptop","usbc"]):
                        monitorparam = INPUT.USBC
                    if (args[0].lower() in ["latitude","argus","hdmi"]):
                        monitorparam = INPUT.HDMI1    
                    if (args[0].lower() in ["chromecast","hdmi1"]):
                        target = Monitor.M27Q
                        monitorparam = INPUT.HDMI1  
                elif req == "brightness": # ie: prefix.brightness M27Q 100
                    # todo: implement
                    monitorcmd = VCPCode.BRIGHTNESS  
                elif req == "contrast": # ie: prefix.contrast U2722DE 75
                    # todo: implement
                    monitorcmd = VCPCode.CONTRAST   
                elif req == "orientation":
                    # todo: implement
                    monitorcmd = VCPCode.ORIENTATION   
                command = f'{cmmExe} /SetValue {target.value} {monitorcmd.value} {monitorparam.value}"'
            elif req == "sleep":
                log.info("Sleeping...")
                command = "C:\\Windows\\System32\\rundll32.exe powrprof.dll,SetSuspendState Standby"
            elif req == "poweroff":
                log.info("Shutting down...")
                command = "C:\\Windows\\System32\\shutdown.exe -s"
            if (command):
                log.info(f'Running command: {command}')
                out = subprocess.run(command)
                if (out.returncode != 0):
                    log.warn(f'{out}')
                
def main():
    log.info(f'Launching Argus v{version}...')
    log.info(f'Is Admin: {ctypes.windll.shell32.IsUserAnAdmin() != 0}')
    sock = setup_socket()
    # Listen
    listen_loop(sock)
    sock.close()

if __name__ == '__main__':
    main()     


