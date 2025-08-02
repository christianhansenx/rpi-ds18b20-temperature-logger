import os
import argparse
import paramiko
import yaml
import getpass
#from scp import SCPClient

CONFIG_FILE = 'rpi_host_config.yaml'
LOCAL_PROJECT_DIRECTORY = 'rpi_ds18b20_temperature_logger'


def upload_app_to_rpi() -> bool:
    exclude_folders = ['.venv']
    exclude_files = [] # Add specific file names here if needed, e.g., ['my_temp_file.txt']
    all_exclude_patterns = exclude_folders + exclude_files
    try:
        config = _create_ssh_client()
        ssh_client = config['client']
        _sftp_upload_recursive(config, exclude=all_exclude_patterns)
        return True
    finally:
        if 'ssh_client' in locals() is not None:
            ssh_client.close()


def _sftp_upload_recursive(config, exclude=None):    
    exclude = exclude or []
    remote_dir = f'/home/{config['username']}/{LOCAL_PROJECT_DIRECTORY}'
    print(f'Uploading {LOCAL_PROJECT_DIRECTORY} folder to {config['username']}@{config['hostname']}:{remote_dir}')

    def upload_dir(local_path, remote_path):
        """Recursive directory upload with exclusion support."""
        try:
            sftp.mkdir(remote_path)
        except IOError:
            pass  # Directory already exists
        for item in os.listdir(local_path):
            local_item = os.path.join(local_path, item)
            remote_item = f"{remote_path}/{item}"
            if any(
                os.path.basename(local_item) == pattern or local_item.endswith(pattern)
                for pattern in exclude
            ):
                continue
            if os.path.isdir(local_item):
                upload_dir(local_item, remote_item)
            else:
                sftp.put(local_item, remote_item)

    sftp = config['client'].open_sftp()
    upload_dir(LOCAL_PROJECT_DIRECTORY, remote_dir)
    sftp.close()


def _create_ssh_client(key_filename=None):
    config = _load_or_create_config()
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=config['hostname'],
        username=config['username'],
        password=config['password'],
        key_filename=key_filename
    )
    config['client'] = client
    return config


def _load_or_create_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as file:
            config = yaml.safe_load(file) or {}
    else:
        config = {}
    required_keys = ['hostname', 'username', 'password']
    missing = [key for key in required_keys if key not in config or not config[key]]

    if missing:
        print(f'{CONFIG_FILE} file not found or missing fields. Please enter the details:')
        if 'hostname' in missing:
            config['hostname'] = input('Rasberry Pi hostname: ').strip()
        if 'username' in missing:
            config['username'] = input('Rasberry Pi username: ').strip()
        if 'password' in missing:
            config['password'] = getpass.getpass('Password: ')
        with open(CONFIG_FILE, 'w') as file:
            yaml.safe_dump(config, file)
        print(f'Configuration saved to {CONFIG_FILE}')
    print(f'Rasberry Pi hostname: {config['hostname']}')
    print(f'Rasberry Pi username: {config['username']}')
    return config


def main():
    parser = argparse.ArgumentParser(description="Raspberry Pi Temperature Logger Tools")
    parser.add_argument(
        "--copy-code-to-rpi",
        action="store_true",
        help="Copy code recursively to the Raspberry Pi"
    )
    args = parser.parse_args()
    if args.copy_code_to_rpi:
        sucess = upload_app_to_rpi()
    if sucess:
        print('SUCCESS!')


if __name__ == '__main__':
    main()
