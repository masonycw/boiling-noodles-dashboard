#!/usr/bin/env python3
"""
file_watcher.py
---------------
Monitors configured data directories for new/modified CSV/JSON/XLSX files.
When a change is detected, waits for the file to stabilize (upload complete),
then triggers data_pipeline.py to ingest the new data into PostgreSQL.

Run as a background service:
    nohup python3 file_watcher.py > /home/mason_ycw/watcher.log 2>&1 &
"""

import os
import sys
import time
import logging
import subprocess
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ---- Config ----
WATCH_DIRS = [
    "/home/eats365/data",
    "/home/eats365/upload",
]

# Only trigger on these file extensions
TRIGGER_EXTENSIONS = {'.csv', '.xlsx', '.xls', '.json', '.txt'}

# How many seconds to wait after last file change before triggering ETL
# (Prevents triggering while a large file is still being uploaded)
STABILIZE_SECS = 10

# Path to the ETL script
PIPELINE_DIR = Path(__file__).parent
PIPELINE_SCRIPT = PIPELINE_DIR / "data_pipeline.py"
PYTHON = PIPELINE_DIR.parent / "venv" / "bin" / "python3"

# Log setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger("file_watcher")


class UploadHandler(FileSystemEventHandler):
    def __init__(self):
        self._pending = False  # ETL trigger pending
        self._last_event_time = 0

    def _should_trigger(self, path: str) -> bool:
        ext = Path(path).suffix.lower()
        return ext in TRIGGER_EXTENSIONS

    def on_created(self, event):
        if not event.is_directory and self._should_trigger(event.src_path):
            log.info(f"📁 New file detected: {event.src_path}")
            self._schedule_etl()

    def on_modified(self, event):
        if not event.is_directory and self._should_trigger(event.src_path):
            log.info(f"✏️  File modified: {event.src_path}")
            self._schedule_etl()

    def on_moved(self, event):
        if not event.is_directory and self._should_trigger(event.dest_path):
            log.info(f"🚚 File moved/renamed to: {event.dest_path}")
            self._schedule_etl()

    def _schedule_etl(self):
        """Mark that we have a pending ETL run. Actual debounced check happens in main loop."""
        self._pending = True
        self._last_event_time = time.time()

    def should_run_now(self) -> bool:
        """Returns True if file events have been stable for STABILIZE_SECS."""
        if not self._pending:
            return False
        return (time.time() - self._last_event_time) >= STABILIZE_SECS

    def reset(self):
        self._pending = False
        self._last_event_time = 0


def run_pipeline():
    """Execute data_pipeline.py and log the result."""
    log.info("🚀 Triggering ETL pipeline (data_pipeline.py)...")
    try:
        result = subprocess.run(
            [str(PYTHON), str(PIPELINE_SCRIPT)],
            capture_output=True,
            text=True,
            cwd=str(PIPELINE_DIR),
            timeout=600  # 10 minute max
        )
        if result.returncode == 0:
            log.info("✅ ETL pipeline completed successfully.")
            if result.stdout:
                for line in result.stdout.strip().split('\n')[-10:]:  # last 10 lines
                    log.info(f"   >> {line}")
        else:
            log.error(f"❌ ETL pipeline failed (exit {result.returncode}).")
            if result.stderr:
                for line in result.stderr.strip().split('\n')[-10:]:
                    log.error(f"   >> {line}")
    except subprocess.TimeoutExpired:
        log.error("⏰ ETL pipeline timed out (>10 min). Killed.")
    except Exception as e:
        log.error(f"💥 Failed to run ETL: {e}")


def main():
    log.info("=" * 60)
    log.info("📡 File Watcher Service Started")
    log.info(f"   Watching: {[d for d in WATCH_DIRS if os.path.exists(d)]}")
    log.info(f"   Trigger extensions: {TRIGGER_EXTENSIONS}")
    log.info(f"   Stabilize delay: {STABILIZE_SECS}s")
    log.info("=" * 60)

    handler = UploadHandler()
    observer = Observer()

    watched_count = 0
    for d in WATCH_DIRS:
        if os.path.exists(d):
            observer.schedule(handler, d, recursive=True)
            log.info(f"👁  Watching: {d}")
            watched_count += 1
        else:
            log.warning(f"⚠️  Directory not found (skipped): {d}")

    if watched_count == 0:
        log.error("No valid watch directories found. Exiting.")
        sys.exit(1)

    observer.start()
    log.info("Watcher running. Press Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(2)
            if handler.should_run_now():
                handler.reset()
                run_pipeline()
    except KeyboardInterrupt:
        log.info("Stopping watcher...")
        observer.stop()

    observer.join()
    log.info("File watcher stopped.")


if __name__ == "__main__":
    main()
