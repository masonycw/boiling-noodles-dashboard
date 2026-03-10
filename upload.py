import paramiko
import sys

def upload():
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect('34.81.51.45', username='mason_ycw', password='masonpass')
        sftp = ssh.open_sftp()
        sftp.put('db_schema.sql', '/home/mason_ycw/boiling-noodles-dashboard/db_schema.sql')
        sftp.put('data_pipeline.py', '/home/mason_ycw/boiling-noodles-dashboard/data_pipeline.py')
        sftp.close()
        ssh.close()
        print("Upload successful!")
    except Exception as e:
        print(f"Failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    upload()
