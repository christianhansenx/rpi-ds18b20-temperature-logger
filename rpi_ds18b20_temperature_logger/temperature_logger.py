import logging
from logging.handlers import TimedRotatingFileHandler
import sys
import time
import yaml
from pathlib import Path

APPLICATION_FILE_FOLDER = Path(__file__).resolve().parent.name
DEFAULT_SENSOR_NAME = "T#"
CONFIG_DIR = Path.home() / '.config' / APPLICATION_FILE_FOLDER
CONFIG_PATH = CONFIG_DIR / 'config.yaml'
LOG_DIR = Path.home() / './tlogs' / APPLICATION_FILE_FOLDER
LOG_FILE = LOG_DIR / 't.log'
ONE_WIRE_DEVICES = Path('/sys/bus/w1/devices')

_terminal_logger = logging.getLogger(f'{__name__}-teminal')
_terminal_logger.setLevel(logging.INFO)
if not _terminal_logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter(fmt='%(asctime)s %(message)s', datefmt='%H:%M:%S'))
    _terminal_logger.addHandler(_handler)
LOG_DIR.mkdir(parents=True, exist_ok=True)
_file_logger = logging.getLogger(f'{__name__}-file')
_file_logger.setLevel(logging.INFO)
if not _file_logger.handlers:
    _handler = TimedRotatingFileHandler(
        filename=LOG_FILE,
        when='midnight',
        interval=1,
        backupCount=365
    )
    _handler.setFormatter(logging.Formatter(fmt='%(asctime)s %(message)s', datefmt='%Y-%m-%dT%H:%M:%S%z'))
    _file_logger.addHandler(_handler)

class TemperatureSensor:

    def __init__(self, id: str, name: str) -> None:
        self._id = id
        self._name = name
        self._status_message = ''

    def get_name(self) -> str:
        return self._name

    def get_id(self) -> str:
        return self._id

    def read_temperature(self) -> float | None:
        """
        Parses the raw data from the DS18B20 sensor file to extract the temperature in Celsius.
        It retries reading if the initial CRC check fails ('YES' not found in first line).
        """

        # The first line of the w1_slave file contains a CRC check result.
        # 'YES' indicates a successful read. If not 'YES', wait and retry.
        retries = 5
        while True:
            lines = self._read_temperature_raw()
            if lines is None:
                return None
            if lines[0].strip()[-3:] == 'YES':
                break
            self._status_message = 'SensorDataCorrupted'
            time.sleep(0.2)
            if retries == 0:
                return None
            retries -= 1

        # The second line contains 't=' followed by the temperature in millidegrees Celsius.
        equals_pos = lines[1].find('t=')
        if equals_pos == -1:
            self._status_message = 'TemperatureValueMissing'
            return None
        if equals_pos != -1:
            temp_string = lines[1][equals_pos+2:]
            try:
                temp_c = float(temp_string) / 1000.0
                return temp_c
            except ValueError:
                self._status_message = 'TemperatureValueError'
        return None

    def get_status_message(self) -> str:
        status = f'{self._name}:{self._status_message}' if self._status_message else ''
        return status

    def _read_temperature_raw(self):
        """
        Reads the raw data lines from a DS18B20 sensor's w1_slave file.
        Handles FileNotFoundError if the sensor path is incorrect or sensor is not found.
        """
        try:
            with open(ONE_WIRE_DEVICES / Path(self._id) / 'w1_slave', 'r') as f:
                lines = f.readlines()
            return lines
        except FileNotFoundError:
            self._status_message = 'SensorNotFound'
            return None
        except Exception as e:
            self._status_message = f'UnexpetedError[{e}]'
            return None


class TemperatureLogger:

    def __init__(self) -> None:
        self._sensors = _get_sensors()
    
    def get_sensors(self) -> list[TemperatureSensor]:
        return self._sensors

    def log_temperatures(self):
        terminal_line = ''
        overall_status = ''
        for sensor in self._sensors:
            temperature = sensor.read_temperature()
            if terminal_line:
                terminal_line += ', '
            temperature_text = 'None' if temperature is None else f'{temperature:.2f}'
            terminal_line += f'{sensor.get_name()} {temperature_text:>6}'
            if status := sensor.get_status_message():
                if overall_status:
                    overall_status += ', '
                overall_status += status
        if overall_status:
            terminal_line += f', ERROR: {overall_status}'
        _terminal_logger.info(terminal_line)


def _get_sensors() -> list[TemperatureSensor]:
    """
    Reads and parses YAML configuration file from the user's home directory.
    If YALM file doesn't exist, a file will be generated.

    Returns:
        List of sensors defined in YALM file.
    """

    def _create_sensors(config_data):
        sensors = []
        for name, id in config_data.items():
            sensors.append(TemperatureSensor(id, name))
        return sensors

    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, 'r') as yaml_file:
            config_data = yaml.safe_load(yaml_file)
        _terminal_logger.info(f'Temperature sensor ID\'s were read from: {CONFIG_PATH}')
        return _create_sensors(config_data)
    config_data = {}
    sensor_ids = _get_w1_sensor_ids()
    for index, sensor_id in enumerate(sensor_ids):
        config_data[f'{DEFAULT_SENSOR_NAME}{index+1}'] = sensor_id
    sensors = _create_sensors(config_data)
    _generate_sensor_config(sensors)
    return sensors


def _generate_sensor_config(sensors: list[TemperatureSensor]) -> None:
    """
    Generates and saves a YAML configuration for a list of temperature sensors
    in the user's home directory, overwriting the file if it already exists.

    Args:
        sensors: A list of sensors.
    """
    config_data = {}
    for sensor in sensors:
        config_data[sensor.get_name()] = sensor.get_id()
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, 'w') as yaml_file:
        yaml.dump(config_data, yaml_file, sort_keys=False)
        _terminal_logger.info(f'Temperature sensor ID\'s were written to: {CONFIG_PATH}')


def _get_w1_sensor_ids() -> list[str]:
    """
    Reads list of 1-Wire sensor IDs.

    Returns:
        A list of sensor ID's.
        Returns an empty list if no sensors are found or the directory doesn't exist.
    """
    sensors_ids = []
    for device in ONE_WIRE_DEVICES.iterdir():
        # Sensor ID's typically start with '28-' and are directories
        if device.is_dir() and device.name.startswith('28-'):
            sensors_ids.append(device.name)
    return sensors_ids
