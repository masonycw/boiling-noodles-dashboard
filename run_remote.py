import paramiko
import sys
import time

def run():
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect('34.81.51.45', username='mason_ycw', password='masonpass')
        
        print("Executing data_pipeline.py on remote server (This may take a minute to process 160k rows)...")
        stdin, stdout, stderr = ssh.exec_command('cd /home/mason_ycw/boiling-noodles-dashboard && python3 data_pipeline.py')
        
        print(stdout.read().decode('utf8', errors='replace'))
        err = stderr.read().decode('utf8', errors='replace')
        if err:
             print(err, file=sys.stderr)
             
        status = stdout.channel.recv_exit_status()
        ssh.close()
        sys.exit(status)
    except Exception as e:
        print(f"Failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run()
