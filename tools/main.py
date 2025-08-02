import sys
import os
import argparse
import paramiko
import yaml
import getpass

CONFIG_FILE = 'rpi_host_config.yaml'
LOCAL_PROJECT_DIRECTORY = 'rpi_ds18b20_temperature_logger'


def upload_app_to_rpi() -> bool:
    exclude_folders = ['.venv', '.git', '__pycache__']
    exclude_files = []  # Add specific file names here if needed
    all_exclude_patterns = exclude_folders + exclude_files
    try:
        config = _create_ssh_client()
        ssh_client = config['client']
        _sftp_upload_recursive(config, exclude=all_exclude_patterns)
        return True
    finally:
        if 'ssh_client' in locals():
            ssh_client.close()


def _sftp_upload_recursive(config, exclude=None):
    exclude = exclude or []
    script_dir = os.path.dirname(os.path.abspath(__file__))
    local_dir = os.path.abspath(os.path.join(script_dir, '..', LOCAL_PROJECT_DIRECTORY))
    remote_dir = f'/home/{config['username']}/{LOCAL_PROJECT_DIRECTORY}'
    print(f'Syncing {LOCAL_PROJECT_DIRECTORY} to {config['username']}@{config['hostname']}:{remote_dir}')
    sftp = config['client'].open_sftp()

    def _is_excluded(path):
        return any(
            pattern in path or os.path.basename(path) == pattern or path.endswith(pattern)
            for pattern in exclude
        )

    def _delete_extra_remote_files(local_path, remote_path):
        try:
            for item in sftp.listdir(remote_path):
                remote_item = f"{remote_path}/{item}"
                local_item = os.path.join(local_path, item)

                if _is_excluded(remote_item):
                    continue

                try:
                    attr = sftp.stat(remote_item)
                    if str(attr.st_mode).startswith('16877'):  # Directory
                        if not os.path.isdir(local_item):
                            _remove_remote_dir(remote_item)
                        else:
                            _delete_extra_remote_files(local_item, remote_item)
                    else:
                        if not os.path.exists(local_item):
                            sftp.remove(remote_item)
                except IOError:
                    pass
        except IOError:
            pass

    def _remove_remote_dir(path):
        for item in sftp.listdir(path):
            remote_item = f"{path}/{item}"
            attr = sftp.stat(remote_item)
            if str(attr.st_mode).startswith('16877'):  # Directory
                _remove_remote_dir(remote_item)
            else:
                sftp.remove(remote_item)
        sftp.rmdir(path)

    def _upload_dir(local_path, remote_path):
        try:
            sftp.mkdir(remote_path)
        except IOError:
            pass
        for item in os.listdir(local_path):
            local_item = os.path.join(local_path, item)
            remote_item = f"{remote_path}/{item}"

            if _is_excluded(local_item):
                continue

            if os.path.isdir(local_item):
                _upload_dir(local_item, remote_item)
            else:
                _upload_file_if_newer(local_item, remote_item)

    def _upload_file_if_newer(local_file, remote_file):
        local_mtime = os.path.getmtime(local_file)
        try:
            remote_attr = sftp.stat(remote_file)
            remote_mtime = remote_attr.st_mtime
            if local_mtime > remote_mtime:  # Local file is newer
                print(f'Updating remote file: {remote_file}')
                sftp.put(local_file, remote_file)
        except IOError:
            # File does not exist remotely, so upload it
            print(f'Uploading new file: {remote_file}')
            sftp.put(local_file, remote_file)

    _delete_extra_remote_files(local_dir, remote_dir)
    _upload_dir(local_dir, remote_dir)
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
        print(f"{CONFIG_FILE} file not found or missing fields. Please enter the details:")
        if 'hostname' in missing:
            config['hostname'] = input('Raspberry Pi hostname: ').strip()
        if 'username' in missing:
            config['username'] = input('Raspberry Pi username: ').strip()
        if 'password' in missing:
            config['password'] = getpass.getpass('Password: ')
        with open(CONFIG_FILE, 'w') as file:
            yaml.safe_dump(config, file)
        print(f"Configuration saved to {CONFIG_FILE}")

    print(f'Raspberry Pi hostname: {config['hostname']}')
    print(f'Raspberry Pi username: {config['username']}')
    return config


def main():
    print(f'Python version: {sys.version_info.major}.{sys.version_info.minor}')

    parser = argparse.ArgumentParser(description='Raspberry Pi Temperature Logger Tools')
    parser.add_argument(
        '--copy-code-to-rpi',
        action='store_true',
        help='Copy code recursively to the Raspberry Pi'
    )
    args = parser.parse_args()

    success = False
    if args.copy_code_to_rpi:
        success = upload_app_to_rpi()

    if success:
        print('SUCCESS!')


if __name__ == '__main__':
    main()
