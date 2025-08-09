"""Temperature logger with support for Texas DS18B20 sensor."""
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml
from specifications import Specifications

APPLICATION_FILE_FOLDER = Path(__file__).resolve().parent.name
DEFAULT_SENSOR_NAME = 'T#'
CONFIG_DIR = Path.home() / '.config' / APPLICATION_FILE_FOLDER
CONFIG_PATH = CONFIG_DIR / 'config.yaml'
CONFIG_TEMPERATURE_SENSORS_KW = 'temperature_sensors'
LOG_DIR = Path.home() / './tlogs'

ONE_WIRE_DEVICES = Path('/sys/bus/w1/devices')
DS18B20_SENSOR_TYPE = 'DS18B20'
CPU_TEMPERATURE_NAME = 'CPU'
CPU_TEMPERATURE_SENSOR_TYPE = 'RPI-CPU'

_terminal_logger = logging.getLogger(f'{__name__}-terminal')
_terminal_logger.setLevel(logging.INFO)
if not _terminal_logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter(fmt='%(asctime)s\t%(message)s', datefmt='%Y-%m-%d\t%H:%M:%S'))
    _terminal_logger.addHandler(_handler)


class TemperatureSensor:
    """Represents a general RPI temperature sensor and handles reading its raw data."""

    def __init__(self, name: str, sensor_id: str, sensor_type: str, devices: Path, device_file: Path) -> None:
        """Initialize a instance for a temperature sensor."""
        self._name = name
        self._id = sensor_id
        self._sensor_type = sensor_type
        self._sensor_file_path = devices / Path(self._id) / device_file

    def read_temperature(self) -> tuple[float|None,str]:
        """Read temperature.

        Method must be implemented by all subclasses.
        """
        error = f'Subclass {self.__class__.__name__}'
        raise NotImplementedError(error)

    def read_temperature_raw(self) -> tuple[list[str],str]:
        """Read the raw data lines from device file."""
        try:
            with Path.open(self._sensor_file_path) as f:
                lines = f.readlines()
        except FileNotFoundError:
            return None, 'SensorNotFound'
        except Exception as e:  # noqa: BLE001 blind exception
            return None, f'UnexpectedError[{e}]'
        return lines, ''

    def get_name(self) -> str:
        """Return the user-defined name of the sensor."""
        return self._name

    def get_type(self) -> str:
        """Return the the sensor type."""
        return self._sensor_type

    def get_id(self) -> str:
        """Return the ID of the sensor."""
        return self._id


class Ds18b20TemperatureSensor(TemperatureSensor):
    """Represents a DS18B20 temperature sensor and handles reading its data."""

    def __init__(self, name: str, sensor_id: str) -> None:
        """Initialize a instance for a DS18B20 sensor.

        Args:
            sensor_id: The unique 1-Wire ID of the sensor.
            name: The user-defined name for the sensor.

        """
        super().__init__(name, sensor_id, DS18B20_SENSOR_TYPE, ONE_WIRE_DEVICES, Path('w1_slave'))

    def read_temperature(self) -> tuple[float|None,str]:
        """Parse raw data from DS18B20 sensor file to extract the temperature in Celsius.

        It retries reading if the initial CRC check fails ('YES' not found in the first line).
        """
        retries = 5
        while True:
            lines, status = self.read_temperature_raw()
            if lines is None:
                return None, status
            if lines[0].strip()[-3:] == 'YES':
                break
            time.sleep(0.2)
            if retries == 0:
                return None, 'SensorDataCorrupted'
            retries -= 1

        # The second line contains 't=' followed by the temperature in millidegrees Celsius.
        equals_pos = lines[1].find('t=')
        if equals_pos == -1:
            return None, 'TemperatureValueMissing'
        try:
            temp_string = lines[1][equals_pos+2:]
            try:
                return round(float(temp_string) / 1000.0, 1), ''
            except ValueError:
                return None, 'TemperatureValueError'
        except Exception as e:  # noqa: BLE001 blind exception
            return None, f'UnexpectedError[{e}]'


class CpuTemperatureSensor(TemperatureSensor):
    """Represents RPI temperature sensor and handles reading its data."""

    def __init__(self, name: str) -> None:
        """Initialize a instance for RPI CPU temperature sensor."""
        super().__init__(name, 'thermal_zone0', CPU_TEMPERATURE_SENSOR_TYPE, Path('/sys/class/thermal'), Path('temp'))

    def read_temperature(self) -> tuple[float|None,str]:
        """Read RPI CPU temperature."""
        lines, status = self.read_temperature_raw()
        if lines is None:
            return None, status
        try:
            return round(float(lines[0]) / 1000.0, 1), ''
        except ValueError:
            return None, 'CpuTemperatureValueError'


class TemperatureLogger:
    """Manages a collection of temperature sensors and logs their readings."""

    def __init__(self, specifications: Specifications) -> None:
        """Initialize the logger and loads sensor configuration."""
        self._specifications = specifications
        self._sensors = self._get_sensors()
        self._last_log_date = None
        self._file_logger = self._setup_file_logger()
        self._last_log_time = False  # Ensure first logging right away

    def get_sensors(self) -> list[TemperatureSensor]:
        """Return the list of configured sensors."""
        return self._sensors

    def log_temperatures(self) -> None:
        """Read temperatures from all sensors and logs them to the terminal and file."""
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
            temperature, status = sensor.read_temperature()
            temperature_text = 'None' if temperature is None else f'{temperature:.1f}'
            terminal_line_fields.append(f'{sensor.get_name()} {temperature_text:>6}')
            file_line_fields.append(f'{sensor.get_name()}\t{temperature_text}')
            if status:
                overall_status.append(f'{sensor.get_name()}:{status}')

        terminal_line = '\t'.join(terminal_line_fields)
        file_line = '\t'.join(file_line_fields)

        if overall_status:
            terminal_line += f'\tERROR: {", ".join(overall_status)}'
            file_line += f'\tERROR: {", ".join(overall_status)}'
        else:
            file_line += '\tOK'

        _terminal_logger.info(terminal_line)
        self._file_logger.info(file_line)

    def _setup_file_logger(self) -> logging.Logger:
        """Set up and returns a file logger instance based on the current date."""
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self._last_log_date = datetime.now().date()  # noqa: DTZ005 call without tz argument
        log_file_name = self._last_log_date.strftime('%Y-%m-%d') + '.log'
        log_file_path = LOG_DIR / log_file_name

        file_logger = logging.getLogger(f'{__name__}-file-logger')
        file_logger.setLevel(logging.INFO)

        if file_logger.hasHandlers():
            file_logger.handlers.clear()

        handler = logging.FileHandler(
            filename=log_file_path,
            mode='a',
        )
        handler.setFormatter(logging.Formatter(fmt='%(asctime)s\t%(message)s', datefmt='%Y-%m-%dT%H:%M:%S%z'))
        file_logger.addHandler(handler)
        return file_logger

    def _check_and_update_logger(self) -> None:
        """Check if the date has changed and creates a new logger if necessary."""
        current_date = datetime.now().date()  # noqa: DTZ005 call without tz argument
        if current_date != self._last_log_date:
            self._file_logger = self._setup_file_logger()

    @classmethod
    def _get_sensors(cls) -> list[TemperatureSensor]:
        """Read and parses the YAML configuration file."""

        def _create_sensors(config_data: dict[str,dict[str,str]]) -> list[TemperatureSensor]:
            sensors_config = config_data[CONFIG_TEMPERATURE_SENSORS_KW]
            sensors = []
            for name, sensor_data in sensors_config.items():
                if sensor_data['sensor_type'] == DS18B20_SENSOR_TYPE:
                    sensors.append(Ds18b20TemperatureSensor(name, sensor_data['id']))
                elif sensor_data['sensor_type'] == CPU_TEMPERATURE_SENSOR_TYPE:
                    sensors.append(CpuTemperatureSensor(name))
            return sensors

        if CONFIG_PATH.exists():
            with Path.open(CONFIG_PATH) as yaml_file:
                config_data = yaml.safe_load(yaml_file)
            _terminal_logger.info('Temperature sensors info read from: %s', CONFIG_PATH)
            return _create_sensors(config_data)

        config_data = {CONFIG_TEMPERATURE_SENSORS_KW: {}}
        sensors_config = config_data[CONFIG_TEMPERATURE_SENSORS_KW]

      # DS18B20 sensors
        sensor_ids = [
            device.name for device in ONE_WIRE_DEVICES.iterdir() if device.is_dir() and device.name.startswith('28-')
        ]
        for index, sensor_id in enumerate(sensor_ids):
            sensors_config[f'{DEFAULT_SENSOR_NAME}{index+1}'] = {'id': sensor_id, 'sensor_type': DS18B20_SENSOR_TYPE}

        # RPI CPU sensor
        sensors_config[CPU_TEMPERATURE_NAME] = {'sensor_type': CPU_TEMPERATURE_SENSOR_TYPE}

        sensors = _create_sensors(config_data)
        cls._generate_sensor_config(sensors)
        return sensors

    @staticmethod
    def _generate_sensor_config(sensors: list[TemperatureSensor]) -> None:
        """Generate and save a YAML configuration."""
        sensors = {
            sensor.get_name(): {'id': sensor.get_id(), 'sensor_type': sensor.get_type()} for sensor in sensors
        }
        config_data = {CONFIG_TEMPERATURE_SENSORS_KW: sensors}
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with Path.open(CONFIG_PATH, 'w') as yaml_file:
            yaml.dump(config_data, yaml_file, sort_keys=False)
        _terminal_logger.info('Temperature sensors info written to: %s', CONFIG_PATH)
