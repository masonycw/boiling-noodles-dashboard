import paramiko
import sys

def run():
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect('34.81.51.45', username='mason_ycw', password='masonpass')
        
        cmd = '''
cd /home/mason_ycw/boiling-noodles-dashboard
source venv/bin/activate

python3 - << 'EOF'
import psycopg2
import sys
sys.path.insert(0, '.')
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=== orders_fact by data_source ===")
cur.execute("""
    SELECT data_source, 
           MIN(date)::DATE as earliest, 
           MAX(date)::DATE as latest, 
           COUNT(*) as cnt
    FROM orders_fact
    GROUP BY data_source ORDER BY data_source
""")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]} ~ {row[2]} ({row[3]} rows)")

print("")
print("=== order_details_fact coverage ===")
cur.execute("""
    SELECT data_source,
           MIN(date)::DATE as earliest,
           MAX(date)::DATE as latest,
           COUNT(*) as cnt
    FROM order_details_fact
    GROUP BY data_source ORDER BY data_source
""")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]} ~ {row[2]} ({row[3]} rows)")

print("")
print("=== member_id distribution in orders_fact ===")
cur.execute("""
    SELECT 
        CASE 
            WHEN member_id IS NULL OR member_id = '' THEN '(NULL/empty)'
            WHEN member_id = '非會員' THEN '非會員'
            WHEN member_id LIKE 'CRM_%' THEN 'CRM phone member'
            WHEN member_id LIKE 'Carrier_%' THEN 'Carrier/Invoice member'
            WHEN member_id LIKE '/%' THEN 'Carrier (/ prefix)'
            ELSE 'Other: ' || LEFT(member_id, 20)
        END as member_type,
        COUNT(*) as cnt
    FROM orders_fact
    GROUP BY 1
    ORDER BY 2 DESC
    LIMIT 15
""")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

print("")
print("=== Sample non-NULL member_ids (first 5) ===")
cur.execute("""
    SELECT DISTINCT member_id FROM orders_fact
    WHERE member_id IS NOT NULL AND member_id != '' AND member_id != '非會員'
    LIMIT 10
""")
for row in cur.fetchall():
    print(f"  '{row[0]}'")

conn.close()
EOF
'''
        sin, sout, serr = ssh.exec_command(cmd)
        out = sout.read().decode('utf8')
        err = serr.read().decode('utf8')
        print(out)
        if err.strip():
            print("STDERR:", err[:300])
        ssh.close()
    except Exception as e:
        print(f"Failed: {e}")
        import traceback; traceback.print_exc()

if __name__ == "__main__":
    run()
