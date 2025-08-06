import os
from pathlib import Path, PurePosixPath

import paramiko
import yaml
import getpass


class SshClient:

    def __init__(self, client, config):
        self._client = client
        self._username = config['username']
        self._connection = f'{config['username']}@{config['hostname']}'

    @property
    def client(self):
        return self._client

    @property
    def username(self):
        return self._username

    @property
    def connection(self):
        return self._connection

    def upload_recursive(self, root_directory: str, exclude_patterns: list[str] | None) -> None:
        exclude = exclude_patterns or []
        script_dir = Path(__file__).parent
        local_dir = (script_dir / '..' / root_directory).resolve()

        # Use PurePosixPath for remote paths
        remote_dir = PurePosixPath(f'/home/{self.username}') / root_directory

        print(f'Syncing {root_directory} to {self.connection}:{remote_dir}')
        sftp = self.client.open_sftp()

        def _is_excluded(path: Path) -> bool:
            return any(
                pattern in str(path) or path.name == pattern or str(path).endswith(pattern)
                for pattern in exclude
            )

        def _delete_extra_remote_files(local_path: Path, remote_path: PurePosixPath):
            try:
                for item in sftp.listdir(str(remote_path)):
                    remote_item = remote_path / item
                    local_item = local_path / item

                    if _is_excluded(remote_item):
                        continue

                    try:
                        attr = sftp.stat(str(remote_item))
                        if str(attr.st_mode).startswith('16877'):  # Directory
                            if not local_item.is_dir():
                                _remove_remote_dir(remote_item)
                            else:
                                _delete_extra_remote_files(local_item, remote_item)
                        else:
                            if not local_item.exists():
                                sftp.remove(str(remote_item))
                    except IOError:
                        pass
            except IOError:
                pass

        def _remove_remote_dir(path: PurePosixPath):
            for item in sftp.listdir(str(path)):
                remote_item = path / item
                attr = sftp.stat(str(remote_item))
                if str(attr.st_mode).startswith('16877'):  # Directory
                    _remove_remote_dir(remote_item)
                else:
                    sftp.remove(str(remote_item))
            sftp.rmdir(str(path))

        def _upload_dir(local_path: Path, remote_path: PurePosixPath):
            try:
                sftp.mkdir(str(remote_path))
            except IOError:
                pass
            for item in local_path.iterdir():
                local_item = item
                remote_item = remote_path / item.name
                if _is_excluded(local_item):
                    continue
                if local_item.is_dir():
                    _upload_dir(local_item, remote_item)
                else:
                    _upload_file_if_newer(local_item, remote_item)

        def _upload_file_if_newer(local_file: Path, remote_file: PurePosixPath):
            local_mtime = local_file.stat().st_mtime
            try:
                remote_attr = sftp.stat(str(remote_file))
                remote_mtime = remote_attr.st_mtime
                if local_mtime > remote_mtime:  # Local file is newer
                    print(f'Updating remote file: {remote_file}')
                    sftp.put(str(local_file), str(remote_file))
            except IOError:
                # File does not exist remotely, so upload it
                print(f'Uploading new file: {remote_file}')
                sftp.put(str(local_file), str(remote_file))

        _delete_extra_remote_files(local_dir, remote_dir)
        _upload_dir(local_dir, remote_dir)
        sftp.close()


class SshClientHandler:

    def __init__(self, config_file: Path):
        self._config = self._load_or_create_config(config_file)
        self._client = None

    def __enter__(self) -> tuple[paramiko.SSHClient, dict[str,str]]:
        print(f'Create SSH connection to {self._config['username']}@{self._config['hostname']}')
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=self._config['hostname'],
            username=self._config['username'],
            password=self._config['password'],
        )
        self._client = SshClient(client, self._config)
        return self._client

    def __exit__(self, exc_type, exc_value, traceback):
        if self._client:
            self._client.client.close()
            print(f'SSH connection is closed')


    @staticmethod
    def _load_or_create_config(config_file):
        if os.path.exists(config_file):
            with open(config_file, 'r') as file:
                config = yaml.safe_load(file) or {}
        else:
            config = {}
            print(f'Configuration file {config_file} has not been created yet. Please enter the details:')
            print(f'Please enter the details:')
            config['hostname'] = input(' Raspberry Pi hostname: ').strip()
            config['username'] = input(' Raspberry Pi username: ').strip()
            config['password'] = getpass.getpass(' Password: ')
            with open(config_file, 'w') as file:
                yaml.safe_dump(config, file)
            print(f"Configuration saved to {config_file}")
        print(f'Raspberry Pi hostname: {config['hostname']}')
        print(f'Raspberry Pi username: {config['username']}')
        return config
