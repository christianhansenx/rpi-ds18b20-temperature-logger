import os
import paramiko
from scp import SCPClient
import getpass # Remember to use this for production!

def create_ssh_client(server, user, password=None, key_filename=None):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=server, username=user, password=password, key_filename=key_filename)
    return client

def scp_upload_recursive(ssh_client, local_base_path, remote_base_path, exclude_patterns):
    local_base_path = os.path.abspath(local_base_path)
    
    with SCPClient(ssh_client.get_transport()) as scp:
        print(f'Local source directory: {local_base_path}')
        print(f'Remote destination base path: {remote_base_path}')

        for root, dirs, files in os.walk(local_base_path):
            # --- CORRECTED LINE HERE ---
            dirs[:] = [d for d in dirs if d not in exclude_patterns]

            relative_path = os.path.relpath(root, local_base_path)
            
            if relative_path == '.':
                current_remote_dir = remote_base_path
            else:
                current_remote_dir = os.path.join(remote_base_path, relative_path).replace("\\", "/")
            
            print(f'Processing local directory: {root}')
            print(f'Corresponding remote directory: {current_remote_dir}')

            try:
                stdin, stdout, stderr = ssh_client.exec_command(f'mkdir -p "{current_remote_dir}"')
                stdout.read()
                stderr.read()
            except Exception as e:
                print(f"Failed to create directory {current_remote_dir} on remote: {e}")
                continue

            for file_name in files:
                # Ensure files are also checked against exclude_patterns if they are names like '.python-version'
                if file_name not in exclude_patterns: 
                    local_file = os.path.join(root, file_name)
                    remote_file = os.path.join(current_remote_dir, file_name).replace("\\", "/")
                    
                    try:
                        scp.put(local_file, remote_file)
                        print(f'Uploaded: {local_file} -> {remote_file}')
                    except Exception as e:
                        print(f"Failed to upload {local_file} to {remote_file}: {e}")

# --- Main script (remains unchanged from your last paste) ---
if __name__ == "__main__":
    local_project_folder_name = 'rpi_ds18b20_temperature_logger'
    local_project_path = os.path.join(os.getcwd(), local_project_folder_name) 

    remote_host = 'rpi3temp'
    remote_user = 'pi'
    
    exclude_folders = ['.venv']
    exclude_files = [] # Add specific file names here if needed, e.g., ['my_temp_file.txt']
    all_exclude_patterns = exclude_folders + exclude_files

    # Temporarily hardcoding password for testing, use getpass in production!
    password = 'pi' # getpass.getpass(prompt='Enter SSH password: ')
    
    try:
        ssh_client = create_ssh_client(remote_host, remote_user, password=password)

        stdin, stdout, stderr = ssh_client.exec_command('echo $HOME')
        remote_home_dir = stdout.read().decode('utf-8').strip()
        print(f'Remote home directory found: {remote_home_dir}')
        
        remote_base_directory = os.path.join(remote_home_dir, local_project_folder_name).replace("\\", "/")
        
        scp_upload_recursive(ssh_client, local_project_path, remote_base_directory, all_exclude_patterns)
        
        print('SUCCESS!')
    except paramiko.ssh_exception.AuthenticationException:
        print('Authentication failed. Please check your username and password.')
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        if 'ssh_client' in locals() and ssh_client.get_transport() is not None:
            ssh_client.close()
