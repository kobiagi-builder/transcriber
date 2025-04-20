# check_drive.py — Final version with lock file, absolute paths, and stable CRON support

import os
import subprocess
from datetime import datetime

# === Configuration ===
LOCK_FILE = "pipeline.lock"
PYTHON_EXECUTABLE = "/Users/kobiagi/Documents/Transcriber/venv310/bin/python"
BASE_DIR = "/Users/kobiagi/Documents/Transcriber"

PIPELINE_STEPS = [
    f"{BASE_DIR}/monitor.py",
    f"{BASE_DIR}/transcribe.py",
    f"{BASE_DIR}/clean_text.py",
    f"{BASE_DIR}/summarize.py",
    f"{BASE_DIR}/create_doc.py",
]

# === Logger ===
def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    print(formatted)
    try:
        with open(os.path.join(BASE_DIR, "log.txt"), "a") as f:
            f.write(formatted + "\n")
    except:
        pass

# === Run Individual Step ===
def run_step(script_path):
    log(f"▶️ Running {os.path.basename(script_path)}...")
    try:
        result = subprocess.run(
            [PYTHON_EXECUTABLE, script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=True,
            text=True,
        )
        log("🔍 Output:\n" + result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        log(f"🛑 {os.path.basename(script_path)} failed with error:\n{e.stdout}")
        return False

# === Main Pipeline Execution ===
def run_pipeline():
    log("🔍 Checking Google Drive for new audio files...")
    for step_path in PIPELINE_STEPS:
        if not run_step(step_path):
            log(f"❌ Pipeline halted due to failure in {os.path.basename(step_path)}")
            break
    else:
        log("✅ Pipeline completed successfully!")

# === Entrypoint with Lock Protection ===
def main():
    lock_path = os.path.join(BASE_DIR, LOCK_FILE)

    if os.path.exists(lock_path):
        log("⛔ Another pipeline run is already in progress. Exiting.")
        return

    open(lock_path, "w").close()
    try:
        run_pipeline()
    finally:
        try:
            os.remove(lock_path)
        except Exception as e:
            log(f"⚠️ Failed to remove lock file: {e}")

if __name__ == "__main__":
    main()
