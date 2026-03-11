import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('34.81.51.45', username='mason_ycw', password='masonpass')

script = """
import psycopg2
conn = psycopg2.connect('postgresql://dashboard_user:noodles2026@localhost/boiling_noodles')
cur = conn.cursor()
try:
    cur.execute('ALTER TABLE erp_purchase_order_details ADD COLUMN IF NOT EXISTS adhoc_name VARCHAR;')
    cur.execute('ALTER TABLE erp_purchase_order_details ADD COLUMN IF NOT EXISTS adhoc_unit VARCHAR;')
    cur.execute('ALTER TABLE erp_purchase_order_details ADD COLUMN IF NOT EXISTS actual_qty NUMERIC(10,2);')
    cur.execute('ALTER TABLE erp_purchase_order_details ADD COLUMN IF NOT EXISTS price_at_order NUMERIC(10,2);')
    conn.commit()
    print('Migration success')
except Exception as e:
    print('Error:', e)
"""

sftp = ssh.open_sftp()
with sftp.file('/home/mason_ycw/migrate_adhoc.py', 'w') as f:
    f.write(script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('PYTHONPATH=/home/mason_ycw/boiling-noodles-dashboard/erp/backend/venv/lib/python3.13/site-packages /home/mason_ycw/boiling-noodles-dashboard/erp/backend/venv/bin/python /home/mason_ycw/migrate_adhoc.py')
print("OUT:", stdout.read().decode())
print("ERR:", stderr.read().decode())
