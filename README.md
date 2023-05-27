# argus
Local network communication. Use to send commands to a local server (nicknamed Argus) and have custom control over the machine. Currently supporting monitor control and machine power state control. 

V1.0:
Initial release
V1.1:
Working release with unit test
V1.2:
Config file, fixed bugs

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
