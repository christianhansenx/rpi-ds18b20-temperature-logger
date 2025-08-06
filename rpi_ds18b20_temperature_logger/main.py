import sys
import time

from temperature_logger import TemperatureLogger


def main():
    print('== rpi-ds18b20-temperature-logger ==')
    print(f'Python version: {sys.version_info.major}.{sys.version_info.minor}')

    temperature_logger = TemperatureLogger()
    while True:
        temperature_logger.log_temperatures()
        temperature_logger.log_temperatures()
        time.sleep(2)

if __name__ == '__main__':
    mainx()
