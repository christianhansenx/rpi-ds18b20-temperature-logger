import sys
from temperatur_logger import get_sensor_config


def main():
    print("== rpi-ds18b20-temperature-logger ==")
    print(f"Python version: {sys.version_info.major}.{sys.version_info.minor}")
    sensors = get_sensor_config()
    for sensor in sensors:
        print(f'Defined temperature sensor: {sensor}')


if __name__ == '__main__':
    main()
