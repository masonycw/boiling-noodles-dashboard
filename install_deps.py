import paramiko
import sys
import time

def run():
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect('34.81.51.45', username='mason_ycw', password='masonpass')
        
        # Install psycopg2 directly in the venv using the venv's pip
        cmd = '/home/mason_ycw/boiling-noodles-dashboard/venv/bin/pip install psycopg2-binary'
        print(f"Running: {cmd}")
        sin, sout, serr = ssh.exec_command(cmd)
        print(sout.read().decode('utf8'))
        
        # Verify installation
        sin2, sout2, serr2 = ssh.exec_command('/home/mason_ycw/boiling-noodles-dashboard/venv/bin/python3 -c "import psycopg2; print(psycopg2.__version__)"')
        result = sout2.read().decode('utf8')
        print(f"Verified - psycopg2 version: {result}")
        
        ssh.close()
    except Exception as e:
        print(f"Failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run()
