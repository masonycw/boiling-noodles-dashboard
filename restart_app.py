import paramiko
import sys
import time

def run():
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect('34.81.51.45', username='mason_ycw', password='masonpass')
        
        print("=== Killing old Streamlit process (PID 569) ===")
        channel = ssh.get_transport().open_session()
        channel.get_pty()
        channel.exec_command("sudo kill -9 569 && echo 'Killed'")
        time.sleep(1)
        out = channel.recv(2048).decode('utf8')
        print(out)
        if '[sudo]' in out or 'password' in out.lower():
            channel.send('masonpass\n')
            time.sleep(2)
            print(channel.recv(2048).decode('utf8'))
        channel.close()
        
        print("=== Waiting 3s then checking if github actions revived it ===")
        time.sleep(8)
        
        sin, sout, serr = ssh.exec_command('ps aux | grep streamlit | grep -v grep')
        print(sout.read().decode('utf8'))
        
        time.sleep(5)
        sin2, sout2, _ = ssh.exec_command('tail -20 /home/mason_ycw/boiling-noodles-dashboard/streamlit.log')
        print("=== Log ===")
        print(sout2.read().decode('utf8'))
        
        ssh.close()
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    run()
