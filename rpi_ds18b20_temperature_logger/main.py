import sys
import time
from pathlib import Path

from specifications import parse_specifications_from_readme
from temperature_logger import TemperatureLogger

from pathlib import Path
from pydantic import BaseModel


def main():
    print('== rpi-ds18b20-temperature-logger ==')
    print(f'Python version: {sys.version_info.major}.{sys.version_info.minor}')

    specifications = parse_specifications_from_readme(Path('README.md'))
    temperature_logger = TemperatureLogger(specifications=specifications)
    while True:
        temperature_logger.log_temperatures()
        time.sleep(0.5)

if __name__ == '__main__':
    main()
