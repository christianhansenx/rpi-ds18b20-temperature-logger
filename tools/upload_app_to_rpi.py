import paramiko
from pathlib import Path, PurePosixPath


def upload_recursive(
    ssh_client: paramiko.SSHClient,
    ssh_config: dict[str, str],
    project_directory: str,
    exclude_patterns: list[str] | None,
) -> None:
    exclude = exclude_patterns or []
    script_dir = Path(__file__).parent
    local_dir = (script_dir / '..' / project_directory).resolve()

    # Use PurePosixPath for remote paths
    remote_dir = PurePosixPath(f'/home/{ssh_config['username']}') / project_directory

    print(f'Syncing {project_directory} to {ssh_config['username']}@{ssh_config['hostname']}:{remote_dir}')
    sftp = ssh_client.open_sftp()

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
