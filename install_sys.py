import paramiko
import sys

def run():
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect('34.81.51.45', username='mason_ycw', password='masonpass')
        
        # Try sudo pip3 install - the Streamlit runs as root
        cmd = 'sudo pip3 install psycopg2-binary --break-system-packages'
        print(f"Running: {cmd}")
        
        # Need to use sudo with password
        channel = ssh.get_transport().open_session()
        channel.get_pty()
        channel.exec_command(cmd)
        
        import time
        time.sleep(2)
        
        out = channel.recv(4096).decode('utf8')
        print(out)
        
        # Send password if needed
        if 'password' in out.lower() or 'sudo' in out.lower():
            channel.send('masonpass\n')
            time.sleep(3)
            out2 = channel.recv(4096).decode('utf8')
            print(out2)
        
        channel.close()
        ssh.close()
        print("Done!")
    except Exception as e:
        print(f"Failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run()
