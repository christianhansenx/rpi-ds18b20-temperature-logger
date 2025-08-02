import os
import argparse
import paramiko
import yaml
import getpass
from scp import SCPClient

CONFIG_FILE = 'rpi_host_config.yaml'
LOCAL_PROJECT_DIRECTORY = 'rpi_ds18b20_temperature_logger'


def upload_app_to_rpi() -> bool:
    local_project_path = os.path.join(os.getcwd(), LOCAL_PROJECT_DIRECTORY) 
    exclude_folders = ['.venv']
    exclude_files = [] # Add specific file names here if needed, e.g., ['my_temp_file.txt']
    all_exclude_patterns = exclude_folders + exclude_files
    try:
        ssh_client = _create_ssh_client()
        stdin, stdout, stderr = ssh_client.exec_command('echo $HOME')
        remote_home_dir = stdout.read().decode('utf-8').strip()
        print(f'Remote home directory found: {remote_home_dir}')
        remote_base_directory = os.path.join(remote_home_dir, LOCAL_PROJECT_DIRECTORY).replace('\\', '/')
        _scp_upload_recursive(ssh_client, local_project_path, remote_base_directory, all_exclude_patterns)
        return True
    except paramiko.ssh_exception.AuthenticationException:
        print('Authentication failed. Please check your username and password.')
    except Exception as e:
        print(f'An unexpected error occurred: {e}')
    finally:
        if 'ssh_client' in locals() and ssh_client.get_transport() is not None:
            ssh_client.close()
    return False


def _scp_upload_recursive(ssh_client, local_base_path, remote_base_path, exclude_patterns):
    local_base_path = os.path.abspath(local_base_path)
    with SCPClient(ssh_client.get_transport()) as scp:
        print(f'Local source directory: {local_base_path}')
        print(f'Remote destination base path: {remote_base_path}')
        for root, dirs, files in os.walk(local_base_path):
            dirs[:] = [d for d in dirs if d not in exclude_patterns]
            relative_path = os.path.relpath(root, local_base_path)
            if relative_path == '.':
                current_remote_dir = remote_base_path
            else:
                current_remote_dir = os.path.join(remote_base_path, relative_path).replace('\\', '/')
            print(f'Processing local directory: {root}')
            print(f'Corresponding remote directory: {current_remote_dir}')
            try:
                stdin, stdout, stderr = ssh_client.exec_command(f'mkdir -p "{current_remote_dir}"')
                stdout.read()
                stderr.read()
            except Exception as e:
                print(f'Failed to create directory {current_remote_dir} on remote: {e}')
                return
            for file_name in files:
                if file_name not in exclude_patterns: 
                    local_file = os.path.join(root, file_name)
                    remote_file = os.path.join(current_remote_dir, file_name).replace('\\', '/')
                    try:
                        scp.put(local_file, remote_file)
                        print(f'Uploaded: {local_file} -> {remote_file}')
                    except Exception as e:
                        print(f'Failed to upload {local_file} to {remote_file}: {e}')


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
    return client


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
