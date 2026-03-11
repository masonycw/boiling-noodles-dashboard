import paramiko
import sys
import time

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect('34.81.51.45', username='mason_ycw', password='masonpass')

    cmds = [
        "sudo systemctl status erp-backend --no-pager",
        "sudo journalctl -u erp-backend -n 50 --no-pager",
        "ss -tulnp | grep 8000"
    ]
    for cmd in cmds:
        print(f"=== {cmd} ===")
        stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True)
        time.sleep(1)
        
        # Read available output
        out = ""
        while stdout.channel.recv_ready():
            out += stdout.channel.recv(1024).decode(errors='replace')
            
        if 'password' in out.lower():
            stdin.write('masonpass\n')
            stdin.flush()
            time.sleep(1)
            while stdout.channel.recv_ready():
                out += stdout.channel.recv(1024).decode(errors='replace')
                
        print(out)

    ssh.close()

if __name__ == '__main__':
    main()
