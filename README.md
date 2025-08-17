# rpi-ds18b20-temperature-logger
Temperature logger for Raspberry Pi with DS18B20 temperature sensors

## Raspberry Pi Hardware Connections

DS18B20 temperature sensor<br>
One Wire, pin 7 / 4k7 pull-up to 3V3<br>
GND, pin 9<br>
3V3, pin 17<br>

[Raspberry HW pinout](]https://www.youngwonks.com/blog/Raspberry-Pi-3-Pinout)

## Enable the 1-Wire Interface

The Raspberry Pi's operating system needs to have the 1-Wire interface enabled.<br>
Open Terminal: On your Raspberry Pi, open a terminal window.<br>
Run raspi-config: Type sudo raspi-config and press Enter.<br>
Use the arrow keys to navigate to Interface Options.<br>
Select 1-Wire.<br>
Select Yes to enable the 1-Wire interface.<br>
Select Finish.<br>
Reboot: ```sudo reboot```<br>

## Install UV on Raspberry Pi

[Install uv on RPI with Snap](https://snapcraft.io/install/astral-uv/raspbian)

## Install "just" on the PC

Install **just** according to: [installation of just](https://github.com/christianhansenx/hansen-developer-notes/blob/main/tools-and-apps/just/README.MD)

Too see list of just recipes, execute just without recipe argument: ```just```

If you are on Windows, then run the just recipes in Git Bash (download from  [git](https://git-scm.com/))<br>
[Setting up VS code to use Git Bash terminal](https://github.com/christianhansenx/hansen-developer-notes/blob/main/tools-and-apps/vs-code/README.MD#windows---git-bash-terminal)

## Interfacing with Raspberry Pi from PC

Instead of having to SSH into the RPI, then many operations can be applied by using the just recipes in **justfile**.
To get a list of RPI tool commands then just execute ```just``` without arguments and look for recipes where comment begins with **# RPI:**.

Some of the connections to th RPI is using [tmux](https://github.com/tmux/tmux/wiki) terminal on the RPI. There is no need to install it - it will be done automatic from the tools commands.

When running tmux from tools terminal, it can be stopped by pressing **enter** key.

## TODO

- SQL (or https://github.com/ytyou/ticktock)
- Flask server (or taipy)
- activate w1 by CLI commands https://github.com/ronanguilloux/temperature-pi/blob/master/README.md
- check this https://github.com/alberttxu/Raspberry-PI-Web-Temperature-Logger---ds18b20
- ram disk for TMUX_LOG_PATH = f'/tmp/{LOCAL_PROJECT_DIRECTORY}.tmux-log'
- Sudo
```
import paramiko

hostname = 'your_hostname'
username = 'your_username'
password = 'your_password'
sudo_password = 'your_sudo_password'
command = 'sudo ls -l /root'

try:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname, username=username, password=password)

    stdin, stdout, stderr = client.exec_command(command)

    # Write the sudo password to stdin
    stdin.write(sudo_password + '\n')
    stdin.flush()

    # Read the output and errors
    output = stdout.read().decode('utf-8')
    error = stderr.read().decode('utf-8')

    print("Command Output:\n", output)
    print("Command Error:\n", error)

finally:
    client.close()
```