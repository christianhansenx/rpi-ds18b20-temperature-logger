import argparse
import sys
import time

from ssh_client import SshClient, SshClientHandler

CONFIG_FILE = 'rpi_host_config.yaml'
LOCAL_PROJECT_DIRECTORY = 'rpi_ds18b20_temperature_logger'
RPI_LOGGER_PROCESS_NAME = f'{LOCAL_PROJECT_DIRECTORY}/.venv/bin/python3 main.py'
TMUX_SESSION_NAME = 'tlog'
TMUX_LOG_PATH = f'/tmp/{LOCAL_PROJECT_DIRECTORY}.tmux-log'
UPLOAD_EXCLUDES_FOLDERS = ['.venv', '.git', '.ruff_cache', '__pycache__']
UPLOAD_EXCLUDES_FILES = []  # Add specific file names here if needed


class FailedToRunRpiTmux(Exception):
    pass


class FailedToKillRpiProcessError(Exception):
    pass


class FailedToInstallRpiTmux(Exception):
    pass


def rpi_check_logger(ssh_client: SshClient, process_name: str, message_no_process: bool = True) -> list[str]:
    """Check about processes are running.
    
    return: list of running process id's
    """
    find_pid_cmd = f'pgrep -f "{process_name}"'
    stdin, stdout, stderr = ssh_client.client.exec_command(find_pid_cmd)
    proc_ids = stdout.read().decode('utf-8').strip().split('\n')
    valid_proc_ids = [pid for pid in proc_ids if pid]
    if valid_proc_ids:
        print(f'Process "{process_name}" running')
        print(f'Found existing PID(s): {", ".join(valid_proc_ids)}')
    elif message_no_process:
        print(f'No existing process found for "{process_name}"')
    return valid_proc_ids


def rpi_kill_logger(ssh_client: SshClient, process_name: str, valid_proc_ids: list[str]):

    if valid_proc_ids:
        for pid in valid_proc_ids:
            kill_cmd = f'kill {pid}'
            stdin, stdout_kill, stderr_kill = ssh_client.client.exec_command(kill_cmd)
            exit_status = stdout_kill.channel.recv_exit_status()
            if exit_status != 0:
                error_msg = stderr_kill.read().decode('utf-8').strip()
                raise FailedToKillRpiProcessError(f'Failed to kill PID {pid}: {error_msg}')
        time.sleep(2)
        print(f'Successfully killed "{process_name}"')


def rpi_tmux(ssh_client: SshClient, restart_application: bool = False):

    tmux_session_msg = (
        f'\ntmux session "{TMUX_SESSION_NAME}" is running on {ssh_client.connection}, to access it from rpi terminal:'
        f'\n\ttmux attach -t {TMUX_SESSION_NAME}'
        '\n'
    )

    # Restart session if required
    _install_tmux(ssh_client)
    tmux_command = None
    if restart_application:
        tmux_command = (
            f'tmux kill-session -t {TMUX_SESSION_NAME} 2>/dev/null; '
            f'rm {TMUX_LOG_PATH} 2>/dev/null; '
            f'tmux new-session -d -s {TMUX_SESSION_NAME} \\; '
            f'pipe-pane -t {TMUX_SESSION_NAME}:0.0 -o "cat >> {TMUX_LOG_PATH}"'
        )
        ssh_client.client.exec_command(tmux_command)
    else:
        stdin, stdout, stderr = ssh_client.client.exec_command(f'tmux has-session -t {TMUX_SESSION_NAME}')
        exit_code = stdout.channel.recv_exit_status()
        if exit_code != 0:
            raise FailedToRunRpiTmux(
                f'Could not open tmux session "{TMUX_SESSION_NAME}" on {ssh_client.connection}:'
                f'\n{stderr.read().decode().strip()}',
            )
        tmux_check_pipe = f'tmux display-message -p -t {TMUX_SESSION_NAME}:0.0 "#{{pane_pipe}}"'
        stdin, stdout, stderr = ssh_client.client.exec_command(tmux_check_pipe)
        if stdout.read().decode()[0] != '1':
            tmux_command = (
                f'rm {TMUX_LOG_PATH} 2>/dev/null; '
                f'tmux pipe-pane -t {TMUX_SESSION_NAME}:0.0 -o "cat >> {TMUX_LOG_PATH}"'
            )
    if tmux_command:
        ssh_client.client.exec_command(tmux_command)
        time.sleep(1)

    # start sftp
    max_retries = 10
    sftp_client = None
    for _ in range(max_retries):
        try:
            sftp = ssh_client.client.open_sftp()
            sftp.stat(TMUX_LOG_PATH)
            sftp_client = sftp
            break
        except OSError as e:
            if e.errno == 2:  # File not found
                time.sleep(0.5)
            else:
                raise
    else:
        raise FileNotFoundError(f'Failed to find log file on rpi: {TMUX_LOG_PATH}')
    remote_tmux_log = sftp_client.open(TMUX_LOG_PATH, 'r', bufsize=4096)

    # Start application (if required) and show tmux output in terminal
    if restart_application:
        remote_dir = f'/home/{ssh_client.username}/{LOCAL_PROJECT_DIRECTORY}'
        command = f'cd {remote_dir} && uv run main.py'
        ssh_client.client.exec_command(f'tmux send-keys -t {TMUX_SESSION_NAME} "{command}" C-m')
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


def _install_tmux(ssh_client):
    """Installs tmux on the remote Raspberry Pi (if not already installed).
    """
    stdin, stdout, stderr = ssh_client.client.exec_command('which tmux')
    exit_code = stdout.channel.recv_exit_status()
    if exit_code != 0:
        print(f'Installing tmux on {ssh_client.client.connection}')
        stdin, stdout, stderr = ssh_client.client.exec_command('sudo apt install tmux -y')
        stdout_output = stdout.read().decode()
        stderr_output = stderr.read().decode()
        for line in stdout_output.splitlines():
            print(f'\t{line}')
        for line in stderr_output.splitlines():
            print(f'\t{line}')
        exit_code = stdout.channel.recv_exit_status()
        if exit_code != 0:
            raise FailedToInstallRpiTmux(f'Installation failed on {ssh_client.connection}:\n{stderr_output.strip()}')


def rpi_upload_app(ssh_client: SshClient):
    all_exclude_patterns = UPLOAD_EXCLUDES_FOLDERS + UPLOAD_EXCLUDES_FILES
    ssh_client.upload_recursive(LOCAL_PROJECT_DIRECTORY, all_exclude_patterns)


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
    with SshClientHandler(CONFIG_FILE) as ssh_client:
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
            rpi_tmux(ssh_client, restart_application=True)
        if args.rpi_tmux:
            rpi_tmux(ssh_client)
        if args.rpi_copy_code:
            rpi_upload_app(ssh_client)
            proc_ids = rpi_check_logger(ssh_client, RPI_LOGGER_PROCESS_NAME, message_no_process=False)
            rpi_kill_logger(ssh_client, RPI_LOGGER_PROCESS_NAME, proc_ids)
            rpi_tmux(ssh_client, restart_application=True)

    if success:
        print('\nSUCCESS!')


if __name__ == '__main__':
    main()
