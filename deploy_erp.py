import paramiko
import os
import time
import sys

# Deployment Config
REMOTE_HOST = '34.81.51.45'
REMOTE_USER = 'mason_ycw'
REMOTE_PASS = 'masonpass'
REMOTE_DIR = '/home/mason_ycw/boiling-noodles-dashboard/erp'
LOCAL_ERP_DIR = './erp'

def run():
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(REMOTE_HOST, username=REMOTE_USER, password=REMOTE_PASS)
        
        sftp = ssh.open_sftp()
        
        print("=== 1. Creating remote directory structure ===")
        ssh.exec_command(f'mkdir -p {REMOTE_DIR}')
        
        print("=== 2. Uploading ERP components (Backend & Frontend) ===")
        def upload_dir(local_path, remote_path):
            ssh.exec_command(f'mkdir -p {remote_path}')
            for item in os.listdir(local_path):
                if item in ['.venv', 'venv', 'node_modules', '__pycache__', '.git', '.DS_Store']:
                    continue
                l_item = os.path.join(local_path, item)
                r_item = os.path.join(remote_path, item)
                if os.path.isdir(l_item):
                    upload_dir(l_item, r_item)
                else:
                    print(f"  Uploading {l_item} -> {r_item}")
                    sftp.put(l_item, r_item)

        upload_dir(LOCAL_ERP_DIR, REMOTE_DIR)
        
        # Upload production .env files
        print("  Uploading production configs...")
        sftp.put('./erp/backend/.env.production', f'{REMOTE_DIR}/backend/.env')
        sftp.put('./erp/frontend/.env.production', f'{REMOTE_DIR}/frontend/.env.production')
        
        sftp.close()

        print("=== 3. Setting up remote environments ===")
        setup_cmd = f'''
cd {REMOTE_DIR}/backend
python3 -m venv venv
./venv/bin/pip install -r requirements.txt

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \\. "$NVM_DIR/nvm.sh"

cd {REMOTE_DIR}/frontend
npm install
'''
        stdin, stdout, stderr = ssh.exec_command(setup_cmd)
        print(stdout.read().decode())
        
        print("=== 4. Initializing ERP Database on Server ===")
        # Note: Set PYTHONPATH to the root 'erp' parent directory so 'erp.backend' imports work
        python_path = os.path.dirname(REMOTE_DIR)
        init_db_cmd = f'cd {REMOTE_DIR} && PYTHONPATH={python_path} ./backend/venv/bin/python backend/scripts/init_local_db.py'
        stdin, stdout, stderr = ssh.exec_command(init_db_cmd)
        print(stdout.read().decode())
        err = stderr.read().decode()
        if err: print("DEBUG ERR:", err)

        print("=== 5. Setting up Systemd Services ===")
        
        # Backend Service
        BACKEND_SERVICE = f"""[Unit]
Description=Boiling Noodles ERP Backend
After=network.target postgresql.service

[Service]
Type=simple
User={REMOTE_USER}
Environment="PYTHONPATH={os.path.dirname(REMOTE_DIR)}"
WorkingDirectory={REMOTE_DIR}/backend
ExecStart={REMOTE_DIR}/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
"""
        # Frontend Service (for initial test)
        FRONTEND_SERVICE = f"""[Unit]
Description=Boiling Noodles ERP Frontend
After=network.target

[Service]
Type=simple
User={REMOTE_USER}
Environment="PATH=/home/mason_ycw/.nvm/versions/node/v20.20.1/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
WorkingDirectory={REMOTE_DIR}/frontend
ExecStart=/home/mason_ycw/.nvm/versions/node/v20.20.1/bin/npm run dev -- --host 0.0.0.0 --port 5173
Restart=always

[Install]
WantedBy=multi-user.target
"""
        def install_service(name, content):
            tmp_path = f"/tmp/{name}.service"
            ssh.exec_command(f"cat > {tmp_path} << 'EOF'\n{content}\nEOF")
            time.sleep(1)
            cmds = [
                f"sudo mv {tmp_path} /etc/systemd/system/{name}.service",
                "sudo systemctl daemon-reload",
                f"sudo systemctl enable {name}",
                f"sudo systemctl restart {name}"
            ]
            for c in cmds:
                chan = ssh.get_transport().open_session()
                chan.get_pty()
                chan.exec_command(c)
                time.sleep(1.5)
                if chan.recv_ready():
                    out = chan.recv(2048).decode()
                    if 'password' in out.lower():
                        chan.send(f"{REMOTE_PASS}\n")
                        time.sleep(1)
                chan.close()
            print(f"  Service {name} installed and started.")

        install_service("erp-backend", BACKEND_SERVICE)
        # Note: Frontend service requires Node.js/npm on server. 
        # For simplicity, we assume it's installed or we might need a separate build step later.
        install_service("erp-frontend", FRONTEND_SERVICE)

        ssh.close()
        print("Done!")

    except Exception as e:
        print(f"Failed: {e}")
        import traceback; traceback.print_exc()

if __name__ == "__main__":
    run()
