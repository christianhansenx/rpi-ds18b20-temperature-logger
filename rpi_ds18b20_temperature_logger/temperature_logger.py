import logging
import sys
import time
from pathlib import Path
from datetime import datetime

import yaml

from specifications import Specifications

APPLICATION_FILE_FOLDER = Path(__file__).resolve().parent.name
DEFAULT_SENSOR_NAME = 'T#'
CONFIG_DIR = Path.home() / '.config' / APPLICATION_FILE_FOLDER
CONFIG_PATH = CONFIG_DIR / 'config.yaml'
LOG_DIR = Path.home() / './tlogs' / APPLICATION_FILE_FOLDER
ONE_WIRE_DEVICES = Path('/sys/bus/w1/devices')

_terminal_logger = logging.getLogger(f'{__name__}-terminal')
_terminal_logger.setLevel(logging.INFO)
if not _terminal_logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter(fmt='%(asctime)s %(message)s', datefmt='%H:%M:%S'))
    _terminal_logger.addHandler(_handler)


class TemperatureSensor:
    """Represents a DS18B20 temperature sensor and handles reading its data."""

    def __init__(self, id: str, name: str) -> None:
        """
        Initializes a TemperatureSensor instance.

        Args:
            id: The unique 1-Wire ID of the sensor.
            name: The user-defined name for the sensor.
        """
        self._id = id
        self._name = name
        self._status_message = ''

    def get_name(self) -> str:
        """Returns the user-defined name of the sensor."""
        return self._name

    def get_id(self) -> str:
        """Returns the 1-Wire ID of the sensor."""
        return self._id

    def read_temperature(self) -> float | None:
        """
        Parses the raw data from the DS18B20 sensor file to extract the temperature in Celsius.
        It retries reading if the initial CRC check fails ('YES' not found in the first line).
        """
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
        """Returns a status message if an error occurred during the last read attempt."""
        status = f'{self._name}:{self._status_message}' if self._status_message else ''
        return status

    def _read_temperature_raw(self):
        """
        Reads the raw data lines from a DS18B20 sensor's w1_slave file.
        """
        try:
            with open(ONE_WIRE_DEVICES / Path(self._id) / 'w1_slave') as f:
                lines = f.readlines()
            return lines
        except FileNotFoundError:
            self._status_message = 'SensorNotFound'
            return None
        except Exception as e:
            self._status_message = f'UnexpetedError[{e}]'
            return None


class TemperatureLogger:
    """Manages a collection of temperature sensors and logs their readings."""

    def __init__(self, specifications: Specifications) -> None:
        """Initializes the logger and loads sensor configuration."""
        self._specifications = specifications
        self._sensors = self._get_sensors()
        self._last_log_date = None
        self._file_logger = self._setup_file_logger()
        self._last_log_time = False  # Ensure first logging right away

    def get_sensors(self) -> list[TemperatureSensor]:
        """Returns the list of configured sensors."""
        return self._sensors

    def log_temperatures(self):
        """Reads temperatures from all sensors and logs them to the terminal and file."""
        current_time = time.monotonic()
        if (
            self._last_log_time and
            current_time - self._last_log_time < self._specifications.temperature_logging_terminal_interval
        ):
            return
        self._last_log_time = current_time

        self._check_and_update_logger()

        terminal_line_fields = []
        file_line_fields = []
        overall_status = []
        for sensor in self._sensors:
            temperature = sensor.read_temperature()
            temperature_text = 'None' if temperature is None else f'{temperature:.2f}'
            terminal_line_fields.append(f'{sensor.get_name()} {temperature_text:>6}')
            file_line_fields.append(f'{sensor.get_name()}={temperature_text}')

            if status := sensor.get_status_message():
                overall_status.append(status)

        terminal_line = ', '.join(terminal_line_fields)
        file_line = ', '.join(file_line_fields)

        if overall_status:
            terminal_line += f', ERROR: {", ".join(overall_status)}'
            file_line += f', ERROR:{", ".join(overall_status)}'

        _terminal_logger.info(terminal_line)
        self._file_logger.info(file_line)

    def _setup_file_logger(self):
        """Sets up and returns a file logger instance based on the current date."""
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self._last_log_date = datetime.now().date()
        log_file_name = self._last_log_date.strftime('%Y-%m-%d') + '.log'
        log_file_path = LOG_DIR / log_file_name

        file_logger = logging.getLogger(f'{__name__}-file-logger')
        file_logger.setLevel(logging.INFO)

        if file_logger.hasHandlers():
            file_logger.handlers.clear()

        handler = logging.FileHandler(
            filename=log_file_path,
            mode='a'
        )
        handler.setFormatter(logging.Formatter(fmt='%(asctime)s %(message)s', datefmt='%Y-%m-%dT%H:%M:%S%z'))
        file_logger.addHandler(handler)
        return file_logger

    def _check_and_update_logger(self):
        """Checks if the date has changed and creates a new logger if necessary."""
        current_date = datetime.now().date()
        if current_date != self._last_log_date:
            self._file_logger = self._setup_file_logger()
            _terminal_logger.info(f"New log file created for {current_date}")

    def _get_sensors(self) -> list[TemperatureSensor]:
        """Reads and parses the YAML configuration file."""
        def _create_sensors(config_data):
            return [TemperatureSensor(id, name) for name, id in config_data.items()]

        if CONFIG_PATH.exists():
            with open(CONFIG_PATH) as yaml_file:
                config_data = yaml.safe_load(yaml_file)
            _terminal_logger.info(f"Temperature sensor ID's were read from: {CONFIG_PATH}")
            return _create_sensors(config_data)

        config_data = {}
        sensor_ids = self._get_w1_sensor_ids()
        for index, sensor_id in enumerate(sensor_ids):
            config_data[f'{DEFAULT_SENSOR_NAME}{index+1}'] = sensor_id
        sensors = _create_sensors(config_data)
        self._generate_sensor_config(sensors)
        return sensors

    def _generate_sensor_config(self, sensors: list[TemperatureSensor]) -> None:
        """Generates and saves a YAML configuration."""
        config_data = {sensor.get_name(): sensor.get_id() for sensor in sensors}
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, 'w') as yaml_file:
            yaml.dump(config_data, yaml_file, sort_keys=False)
        _terminal_logger.info(f"Temperature sensor ID's were written to: {CONFIG_PATH}")

    @staticmethod
    def _get_w1_sensor_ids() -> list[str]:
        """Reads list of 1-Wire sensor IDs from the system."""
        return [device.name for device in ONE_WIRE_DEVICES.iterdir() if device.is_dir() and device.name.startswith('28-')]
