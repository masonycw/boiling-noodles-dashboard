import paramiko
import sys
import time

def run():
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect('34.81.51.45', username='mason_ycw', password='masonpass')
        
        # Use disown so nohup doesn't hold the SSH channel open
        cmd = 'cd /home/mason_ycw/boiling-noodles-dashboard && nohup /home/mason_ycw/boiling-noodles-dashboard/venv/bin/python3 file_watcher.py > /home/mason_ycw/watcher.log 2>&1 & disown && echo "OK:$!"'
        
        # Non-blocking exec with short timeout
        transport = ssh.get_transport()
        chan = transport.open_session()
        chan.exec_command(cmd)
        
        # Wait briefly for the echo to come back
        time.sleep(3)
        if chan.recv_ready():
            print("Start:", chan.recv(512).decode('utf8'))
        
        chan.close()
        
        # Check log
        time.sleep(3)
        sin, sout, _ = ssh.exec_command('cat /home/mason_ycw/watcher.log && echo "---" && ps aux | grep file_watcher | grep -v grep')
        print(sout.read().decode('utf8'))
        
        ssh.close()
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    run()
