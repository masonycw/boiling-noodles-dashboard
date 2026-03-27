"""
p8: 金流紀錄新增 payment_method + ref_payable_ids 欄位
- erp_cash_flow_records.payment_method VARCHAR（付款方式）
- erp_cash_flow_records.ref_payable_ids JSONB（關聯的應付帳款 ID 列表）
"""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('34.81.51.45', username='mason_ycw', password='masonpass')

sql = """
ALTER TABLE erp_cash_flow_records
  ADD COLUMN IF NOT EXISTS payment_method VARCHAR,
  ADD COLUMN IF NOT EXISTS ref_payable_ids JSONB;
"""

cmd = f"""cd /home/mason_ycw/boiling-noodles-dashboard && \
source erp/backend/venv/bin/activate && \
PYTHONPATH=/home/mason_ycw/boiling-noodles-dashboard python3 -c "
from erp.backend.db.session import engine
from sqlalchemy import text
with engine.connect() as conn:
    conn.execute(text('''{sql}'''))
    conn.commit()
print('Migration p8 completed.')
"
"""

stdin, stdout, stderr = ssh.exec_command(cmd)
out = stdout.read().decode()
err = stderr.read().decode()
print('STDOUT:', out)
if err:
    print('STDERR:', err)
ssh.close()
