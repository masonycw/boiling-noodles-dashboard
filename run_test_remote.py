import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('34.81.51.45', username='mason_ycw', password='masonpass')

sftp = ssh.open_sftp()
sftp.put('test_order.py', '/home/mason_ycw/test_order.py')
sftp.close()

stdin, stdout, stderr = ssh.exec_command('PYTHONPATH=/home/mason_ycw/boiling-noodles-dashboard /home/mason_ycw/boiling-noodles-dashboard/erp/backend/venv/bin/python /home/mason_ycw/test_order.py')
print(stdout.read().decode())
print("ERR:", stderr.read().decode())
