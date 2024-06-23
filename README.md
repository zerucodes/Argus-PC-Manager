# Argus - Home Assistant Companion

Campanion application for Home Assistant (https://www.home-assistant.io/) Computer and Display Monitor control

V1.0:
Initial release
V1.1:
Working release with unit test
V1.2:
Config file, fixed bugs
V2.0:
Custom CPP Monitor Controller, MQTT Hass Support

(NEW Method)
Version 2.0 aims to remove as much user configuration as possible, support getting/setting monitor information with a built in cpp windows application
This will support automatically detecting monitors as well as controlling by monitor name (see image below)

MQTT Support:
Both argus.py (HASS http server for monitor control inputs) and hwinfo.py (pc sensor reader) are combined into a unified MQTT Python
application that will detect Sensors, battery powered BL devices, and publish them to a HASS server as custom devices! This removes
the need to manually configure HASS automations and config.yaml template sensors.  

> Device created entirely by default ArgusMqtt.py configuration

![image](https://github.com/zerucodes/Argus-PC-Manager/assets/123906605/f4af8120-b8ff-4c98-9c2b-71a90798a359)

![image](https://github.com/zerucodes/argus/assets/123906605/797784cd-d097-4d12-8273-43c7c7cf91a2)


New Custom Monitor Control:

> .\ZMM.exe -getMonitors

> .\ZMM.exe -setVCP --vcp=0x10 --value=75 --monitor=0

> .\ZMM.exe -setVCP --vcp=0x10 --value=85 --monitor=DP

> .\ZMM.exe -setVCP --vcp=16 --value=85 --monitor=U2722DE

![image](https://github.com/zerucodes/argus/assets/123906605/eb4f2418-e723-4b94-b394-4f502a086a83)


Required Components:
1. ControlMyMonitor.exe Available: https://www.nirsoft.net/utils/control_my_monitor.html
2. Python 3 w/ pip
3. 2nd Device


Set-up:
1. Install required components
2. Update python configuration vars
    a. cmm.Exe (REQUIRED)
3. Run argus.py
4. Use argustest.py to send test commands 

Sample UDP Commands:

0. secret.class [target] [command] [parameter]
1. argus.monitor 1 input usbc
2. argus.pc sleep
3. argus.monitor 2 brightness 100

# Additional Information

Feel free to send UDP packets however you like, for android phones Macrodroid is a lightweight and powerful automation app making for easy shortcut creations
1. Create a macro with any Trigger  (Ie 'Quick Tile On/Press') 
2. Select 'UDP Command' for Action
3. Set Destination field to IP address (displayed in log) 
4. Set Port (default 169)
5. Set Message to any command (ie: prefix.input pc)



# VCP Codes
VCP Code                          VCP Code Name               
02                               New Control Value                 
04                               Restore Factory Defaults          
05                               Restore Factory Luminance/Contrast
08                               Restore Factory Color Defaults    
0B                               Color Temperature Increment       
0C                               Color Temperature Request         
10                               Brightness                        
12                               Contrast                          
14                               Select Color Preset               
16                               Video Gain (Drive): Red           
18                               Video Gain (Drive): Green         
1A                               Video Gain (Drive): Blue          
52                               Active Control                    
60                               Input Select                      
62                               Audio: Speaker Volume             
6C                               Video Black Level: Red            
6E                               Video Black Level: Green          
70                               Video Black Level: Blue           
87                               Sharpness                         
8D                               Audio Mute / Screen Blank         
AC                               Horizontal Frequency              
AE                               Vertical Frequency                
B2                               Flat Panel Sub-Pixel Layout       
B6                               Display Technology Type           
C0                               Display Usage Time                
C6                               Application Enable Key            
C8                               Display Controller ID             
C9                               Display Firmware Level            
CA                               OSD                               
CC                               OSD Language                      
D6                               Power Mode                        
DC                               Display Application               
DF                               VCP Version                       
