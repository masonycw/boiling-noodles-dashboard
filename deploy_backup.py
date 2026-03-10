import paramiko
import sys
import time

def run():
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect('34.81.51.45', username='mason_ycw', password='masonpass')
        
        cmd = '''
cd /home/mason_ycw/boiling-noodles-dashboard-test

# Switch to Backup branch (old CSV version)
git fetch --all
git checkout Backup
git reset --hard origin/Backup

echo "=== Now on branch ==="
git log --oneline -3

echo ""
echo "=== Install requirements ==="
source venv/bin/activate && pip install -r requirements.txt -q

echo "=== Restarting 8502 ==="
if [ -f streamlit.pid ]; then
  kill $(cat streamlit.pid) 2>/dev/null || true
  rm streamlit.pid
fi
fuser -k 8502/tcp 2>/dev/null || true
sleep 2

nohup ./venv/bin/streamlit run app.py \
  --server.port=8502 \
  --server.address=0.0.0.0 \
  --server.headless=true \
  > streamlit_test.log 2>&1 &
echo $! > streamlit.pid

sleep 4
echo "=== Log ==="
tail -10 streamlit_test.log
'''
        sin, sout, serr = ssh.exec_command(cmd)
        # Stream output
        out = sout.read().decode('utf8')
        err = serr.read().decode('utf8')
        print(out)
        if err:
            print("STDERR:", err[:500])
        ssh.close()
    except Exception as e:
        print(f"Failed: {e}")
        import traceback; traceback.print_exc()

if __name__ == "__main__":
    run()
