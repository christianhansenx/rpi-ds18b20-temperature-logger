# rpi-ds18b20-temperature-logger
Temperature logger for Raspberry Pi with DS18B20 temperature sensors

## Hardware Connections

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

## Install just

Install **just** according to: [installation of just](https://github.com/christianhansenx/hansen-developer-notes/blob/main/tools-and-apps/just/README.MD)

Too see list of just recipes, execute just without recipe argument: ```just```

If you are on Windows, then run the just recipes in Git Bash (download from  [git](https://git-scm.com/))<br>
[Setting up VS code to use Git Bash terminal](https://github.com/christianhansenx/hansen-developer-notes/blob/main/tools-and-apps/vs-code/README.MD#windows---git-bash-terminal)

## Interfacing with Raspberry Pi from PC


## TODO

- Log CPU temperature
- Use DuckDB
- Send to Google Drive
- Flask server
