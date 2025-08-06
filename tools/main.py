import sys
import os
import time
import argparse
import paramiko
import yaml
import getpass

from upload_app_to_rpi import upload_recursive

CONFIG_FILE = 'rpi_host_config.yaml'
LOCAL_PROJECT_DIRECTORY = 'rpi_ds18b20_temperature_logger'
RPI_LOGGER_PROCESS_NAME = f'{LOCAL_PROJECT_DIRECTORY}/.venv/bin/python3 main.py'
TMUX_SESSION_NAME = 'tlog'
TMUX_LOG_PATH = f'/tmp/{LOCAL_PROJECT_DIRECTORY}.tmux-log'


class FailedToRunRpiTmux(Exception):
    pass


class FailedToKillRpiProcessError(Exception):
    pass

class FailedToInstallRpiTmux(Exception):
    pass


class SshClient:

    def __init__(self):
        self._config = self._load_or_create_config()
        self._client = None

    def __enter__(self) -> tuple[paramiko.SSHClient, dict[str,str]]:
        print(f'Create SSH connection to {self._config['username']}@{self._config['hostname']}')
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._client.connect(
            hostname=self._config['hostname'],
            username=self._config['username'],
            password=self._config['password'],
        )
        return self._client, self._config

    def __exit__(self, exc_type, exc_value, traceback):
        if self._client:
            self._client.close()
            print(f'SSH connection is closed')

    @staticmethod
    def _load_or_create_config():
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as file:
                config = yaml.safe_load(file) or {}
        else:
            config = {}
            print(f'Configuration file {CONFIG_FILE} has not been created yet. Please enter the details:')
            print(f'Please enter the details:')
            config['hostname'] = input(' Raspberry Pi hostname: ').strip()
            config['username'] = input(' Raspberry Pi username: ').strip()
            config['password'] = getpass.getpass(' Password: ')
            with open(CONFIG_FILE, 'w') as file:
                yaml.safe_dump(config, file)
            print(f"Configuration saved to {CONFIG_FILE}")
        print(f'Raspberry Pi hostname: {config['hostname']}')
        print(f'Raspberry Pi username: {config['username']}')
        return config


def rpi_check_logger(ssh_client: paramiko.SSHClient, process_name: str, message_no_process: bool = True) -> list[str]:
    """Check about processes are running.
    
    return: list of running process id's
    """
    find_pid_cmd = f'pgrep -f "{process_name}"'
    stdin, stdout, stderr = ssh_client.exec_command(find_pid_cmd)
    proc_ids = stdout.read().decode('utf-8').strip().split('\n')
    valid_proc_ids = [pid for pid in proc_ids if pid]
    if valid_proc_ids:
        print(f'Process "{process_name}" running')
        print(f'Found existing PID(s): {", ".join(valid_proc_ids)}')
    else:
        if message_no_process:
            print(f'No existing process found for "{process_name}"')
    return valid_proc_ids


def rpi_kill_logger(ssh_client: paramiko.SSHClient, process_name: str, valid_proc_ids: list[str]):

    if valid_proc_ids:
        for pid in valid_proc_ids:
            kill_cmd = f"kill {pid}"
            stdin, stdout_kill, stderr_kill = ssh_client.exec_command(kill_cmd)
            exit_status = stdout_kill.channel.recv_exit_status()
            if exit_status != 0:
                error_msg = stderr_kill.read().decode('utf-8').strip()
                raise FailedToKillRpiProcessError(f'Failed to kill PID {pid}: {error_msg}')
        time.sleep(2)
        print(f'Successfully killed "{process_name}"')


def rpi_tmux(ssh_client: paramiko.SSHClient, ssh_config: dict[str,str], restart_application: bool = False):

    rpi_ssh_connection = f'{ssh_config['username']}@{ssh_config['hostname']}'
    tmux_session_msg = (
        f'\ntmux session "{TMUX_SESSION_NAME}" is running on {rpi_ssh_connection}, to access it from rpi terminal:'
        f'\n\ttmux attach -t {TMUX_SESSION_NAME}'
        '\n'
    )

    # Restart session if required
    _install_tmux(ssh_client, ssh_config)
    tmux_command = None
    if restart_application:
        tmux_command = (
            f'tmux kill-session -t {TMUX_SESSION_NAME} 2>/dev/null; '
            f'rm {TMUX_LOG_PATH} 2>/dev/null; '
            f'tmux new-session -d -s {TMUX_SESSION_NAME} \\; '
            f'pipe-pane -t {TMUX_SESSION_NAME}:0.0 -o "cat >> {TMUX_LOG_PATH}"'
        )
        ssh_client.exec_command(tmux_command)
    else:
        stdin, stdout, stderr = ssh_client.exec_command(f'tmux has-session -t {TMUX_SESSION_NAME}')
        exit_code = stdout.channel.recv_exit_status()
        if exit_code != 0:
            raise FailedToRunRpiTmux(
                f'Could not open tmux session "{TMUX_SESSION_NAME}" on {rpi_ssh_connection}:'
                f'\n{stderr.read().decode().strip()}'
            )
        tmux_check_pipe = f'tmux display-message -p -t {TMUX_SESSION_NAME}:0.0 "#{{pane_pipe}}"'
        stdin, stdout, stderr = ssh_client.exec_command(tmux_check_pipe)
        if stdout.read().decode()[0] != '1':
            tmux_command = (
                f'rm {TMUX_LOG_PATH} 2>/dev/null; '
                f'tmux pipe-pane -t {TMUX_SESSION_NAME}:0.0 -o "cat >> {TMUX_LOG_PATH}"'
            )
    if tmux_command:
        ssh_client.exec_command(tmux_command)
        time.sleep(1)

    # start sftp
    max_retries = 10
    sftp_client = None
    for _ in range(max_retries):
        try:
            sftp = ssh_client.open_sftp()
            sftp.stat(TMUX_LOG_PATH)
            sftp_client = sftp
            break
        except IOError as e:
            if e.errno == 2:  # File not found
                time.sleep(0.5)
            else:
                raise
    else:
        raise FileNotFoundError(f'Failed to find log file on rpi: {TMUX_LOG_PATH}')
    remote_tmux_log = sftp_client.open(TMUX_LOG_PATH, 'r', bufsize=4096)

    # Start application (if required) and show tmux output in terminal
    if restart_application:
        remote_dir = f'/home/{ssh_config['username']}/{LOCAL_PROJECT_DIRECTORY}'
        command = f'cd {remote_dir} && uv run main.py'
        ssh_client.exec_command(f'tmux send-keys -t {TMUX_SESSION_NAME} "{command}" C-m')
    try:
        print(f'{tmux_session_msg}')
        while True:
            line = remote_tmux_log.readline()
            if line:
                sys.stdout.write(line)
                sys.stdout.flush()
            else:
                time.sleep(0.5)
    except KeyboardInterrupt:
        print(f'{tmux_session_msg}')


def _install_tmux(ssh_client, ssh_config):
    """
    Installs tmux on the remote Raspberry Pi (if not already installed).
    """
    rpi_ssh_connection = f'{ssh_config['username']}@{ssh_config['hostname']}'
    stdin, stdout, stderr = ssh_client.exec_command("which tmux")
    exit_code = stdout.channel.recv_exit_status()
    if exit_code != 0:
        print(f'Installing tmux on {rpi_ssh_connection}')
        stdin, stdout, stderr = ssh_client.exec_command('sudo apt install tmux -y')
        stdout_output = stdout.read().decode()
        stderr_output = stderr.read().decode()
        for line in stdout_output.splitlines():
            print(f'\t{line}')
        for line in stderr_output.splitlines():
            print(f'\t{line}')
        exit_code = stdout.channel.recv_exit_status()
        if exit_code != 0:
            raise FailedToInstallRpiTmux(f'Installation failed on {rpi_ssh_connection}:\n{stderr_output.strip()}')


def rpi_upload_app(ssh_client: SshClient, ssh_config: dict[str,str]) -> bool:
    exclude_folders = ['.venv', '.git', '__pycache__']
    exclude_files = []  # Add specific file names here if needed
    all_exclude_patterns = exclude_folders + exclude_files
    upload_recursive(ssh_client, ssh_config, LOCAL_PROJECT_DIRECTORY, all_exclude_patterns)


def main():
    print(f'Python version: {sys.version_info.major}.{sys.version_info.minor}')

    parser = argparse.ArgumentParser(description='Raspberry Pi Temperature Logger Tools')
    parser.add_argument(
        '--rpi-check-logger',
        action='store_true',
        help='Check about logger application is already running on Raspberry Pi device',
    )
    parser.add_argument(
        '--rpi-kill-logger',
        action='store_true',
        help='Kill logger application on Raspberry Pi device',
    )
    parser.add_argument(
        '--rpi-run-logger',
        action='store_true',
        help='Run logger application on Raspberry Pi device',
    )
    parser.add_argument(
        '--rpi-copy-code',
        action='store_true',
        help='Copy code recursively to the Raspberry Pi device',
    )
    parser.add_argument(
        '--rpi-tmux',
        action='store_true',
        help='Live stream from Raspberry Pi device tmux session',
    )
    args = parser.parse_args()

    success = False
    with SshClient() as (ssh_client, ssh_config):
        if args.rpi_check_logger:
            rpi_check_logger(ssh_client, RPI_LOGGER_PROCESS_NAME)
            success = True
        if args.rpi_kill_logger:
            proc_ids = rpi_check_logger(ssh_client, RPI_LOGGER_PROCESS_NAME, message_no_process=False)
            rpi_kill_logger(ssh_client, RPI_LOGGER_PROCESS_NAME, proc_ids)
            success = True
        if args.rpi_run_logger:
            proc_ids = rpi_check_logger(ssh_client, RPI_LOGGER_PROCESS_NAME, message_no_process=False)
            rpi_kill_logger(ssh_client, RPI_LOGGER_PROCESS_NAME, proc_ids)
            rpi_tmux(ssh_client, ssh_config, restart_application=True)
        if args.rpi_tmux:
            rpi_tmux(ssh_client, ssh_config)
        if args.rpi_copy_code:
            rpi_upload_app(ssh_client, ssh_config)
            proc_ids = rpi_check_logger(ssh_client, RPI_LOGGER_PROCESS_NAME, message_no_process=False)
            rpi_kill_logger(ssh_client, RPI_LOGGER_PROCESS_NAME, proc_ids)
            rpi_tmux(ssh_client, ssh_config, restart_application=True)

    if success:
        print('\nSUCCESS!')


if __name__ == '__main__':
    main()
