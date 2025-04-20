import subprocess
import os
from datetime import datetime

# === 🕒 Logger ===
def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    print(formatted)
    try:
        with open("log.txt", "a") as f:
            f.write(formatted + "\n")
    except Exception as e:
        print(f"[Logger Error] Could not write to log.txt: {e}")

# === ▶️ RUN STEP ===
def run_step(script):
    log(f"\n▶️ Running {script}...")
    try:
        result = subprocess.run(["python", script], check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError:
        log(f"🛑 Pipeline stopped: {script} did not process any files or failed.")
        return False
    except FileNotFoundError:
        log(f"🛑 Script not found: {script}")
        return False

# === 🚀 MAIN ===
def main():
    log("\n🔍 Checking Google Drive for new audio files...")
    check = run_step("monitor.py")
    if not check:
        log("❌ Halting pipeline due to failure in: monitor.py")
        return

    steps = [
        "detect_language.py",
        "transcribe.py",
        "clean_text.py",
        "summarize.py",
        "create_doc.py"
    ]

    for step in steps:
        if not run_step(step):
            log(f"❌ Halting pipeline due to failure in: {step}")
            return

    log("✅ Pipeline completed successfully!")

if __name__ == '__main__':
    main()
