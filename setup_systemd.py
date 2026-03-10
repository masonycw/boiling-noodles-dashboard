import paramiko
import sys
import time

SYSTEMD_SERVICE = """[Unit]
Description=Boiling Noodles File Watcher (Auto ETL Trigger)
After=network.target postgresql.service
Wants=network.target

[Service]
Type=simple
User=mason_ycw
WorkingDirectory=/home/mason_ycw/boiling-noodles-dashboard
ExecStart=/home/mason_ycw/boiling-noodles-dashboard/venv/bin/python3 database/file_watcher.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""

def run():
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect('34.81.51.45', username='mason_ycw', password='masonpass')
        
        # 1. Write service file content to a temp location
        sin, sout, serr = ssh.exec_command(f"cat > /tmp/file-watcher.service << 'EOF'\n{SYSTEMD_SERVICE.strip()}\nEOF")
        time.sleep(1)
        
        # 2. Install and enable it with sudo
        steps = [
            "sudo mv /tmp/file-watcher.service /etc/systemd/system/file-watcher.service",
            "sudo systemctl daemon-reload",
            "sudo systemctl stop file-watcher 2>/dev/null || true",
            "sudo systemctl enable file-watcher",
            "sudo systemctl start file-watcher",
        ]
        
        for cmd in steps:
            channel = ssh.get_transport().open_session()
            channel.get_pty()
            channel.exec_command(cmd)
            time.sleep(1.5)
            out = b""
            while channel.recv_ready():
                out += channel.recv(2048)
            if b"[sudo]" in out or b"password" in out.lower():
                channel.send("masonpass\n")
                time.sleep(1.5)
                while channel.recv_ready():
                    out += channel.recv(2048)
            print(f"  [{cmd.split()[0]} {cmd.split()[1] if len(cmd.split())>1 else ''}] {out.decode('utf8', errors='ignore').strip()}")
            channel.close()
        
        # 3. Check status
        time.sleep(3)
        sin2, sout2, _ = ssh.exec_command("sudo systemctl status file-watcher --no-pager -l")
        channel = ssh.get_transport().open_session()
        channel.get_pty()
        channel.exec_command("systemctl status file-watcher --no-pager -l")
        time.sleep(2)
        out = b""
        while channel.recv_ready():
            out += channel.recv(4096)
        channel.close()
        print("\n=== Service Status ===")
        print(out.decode('utf8', errors='ignore'))
        
        ssh.close()
        print("Done!")
    except Exception as e:
        print(f"Failed: {e}")
        import traceback; traceback.print_exc()

if __name__ == "__main__":
    run()
