import yaml
from pathlib import Path

APPLICATION_NAME = 'DS18B20 Temperature Logger'

def get_sensor_config() -> dict[str,dict[str,str]]:
    """
    Reads and parses YAML configuration file from the user's home directory.

    Returns:
        dict or None: A dictionary containing the sensor configuration.
    """
    config_file_path = _get_sensor_config_file_path()
    if config_file_path.exists():
        with open(config_file_path, 'r') as yaml_file:
            config_data = yaml.safe_load(yaml_file)
        print(f'Temperature sensor definations were read from: {config_file_path}')
        return config_data
    config_data = []
    sensor_ids = _get_w1_sensor_ids()
    for index, sensor_id in enumerate(sensor_ids):
        config_data.append({'name': f'T#{index+1}', 'id': sensor_id})
    generate_sensor_config(config_data)
    print(f'Temperature sensor(s) have been been detected and stored to {config_file_path}')
    return config_data


def generate_sensor_config(sensors: dict[str,dict[str,str]]) -> None:
    """
    Generates and saves a YAML configuration for a list of temperature sensors
    in the user's home directory, overwriting the file if it already exists.

    Args:
        sensors: A list of dictionaries, where each dictionary represents a sensor.
    """
    config_data = {}
    for sensor in sensors:
        config_data[sensor['name']] = {'id': sensor['id']}
    _get_sensor_config_file_directory().mkdir(parents=True, exist_ok=True)
    with open(_get_sensor_config_file_path(), 'w') as yaml_file:
        yaml.dump(config_data, yaml_file, sort_keys=False)


def _get_w1_sensor_ids() -> list[str]:
    """
    Reads and returns a list of 1-Wire sensor IDs from /sys/bus/w1/devices.

    Returns:
        A list of strings, where each string is a sensor ID (e.g., '28-000000000001').
            Returns an empty list if no sensors are found or the directory doesn't exist.
    """
    w1_devices_directory = Path('/sys/bus/w1/devices')
    sensor_ids = []
    for item in w1_devices_directory.iterdir():
        # Sensor IDs typically start with '28-' and are directories
        if item.is_dir() and item.name.startswith('28-'):
            sensor_ids.append(item.name)
    return sensor_ids


def _get_sensor_config_file_directory() -> Path:
    home_dir = Path.home()
    config_dir = home_dir / '.config' / APPLICATION_NAME.lower().replace(' ', '_')
    return config_dir


def _get_sensor_config_file_path() -> Path:
    config_file_path = _get_sensor_config_file_directory() / 'config.yaml'
    return config_file_path
