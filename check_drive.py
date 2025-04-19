import os
import sys
import subprocess
from datetime import datetime

# === 📦 Ensure local import works regardless of how script is run ===
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config

from google.oauth2 import service_account
from googleapiclient.discovery import build
from supabase import create_client, Client

# Path to the venv Python
VENV_PYTHON = "/Users/kobiagi/Documents/Transcriber/venv310/bin/python"

# === 🕒 Logger ===
def log(msg):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    formatted = f"[{timestamp}] {msg}"
    print(formatted)
    try:
        with open("log.txt", "a") as f:
            f.write(formatted + "\n")
    except Exception as e:
        print(f"[Logger Error] Could not write to log.txt: {e}")

# === 🔌 INIT GOOGLE DRIVE ===
def init_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        config.SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build('drive', 'v3', credentials=creds)

# === 📦 INIT SUPABASE ===
def init_supabase():
    return create_client(config.SUPABASE_URL, config.SUPABASE_API_KEY)

# === 📁 GET AUDIO FILES ===
def fetch_audio_files(drive_service):
    log("📁 Fetching audio files from Google Drive...")
    results = drive_service.files().list(
        q=f"'{config.INPUT_FOLDER_ID}' in parents and mimeType contains 'audio'",
        fields="files(id, name)"
    ).execute()
    return results.get('files', [])

# === 📄 CHECK WHICH FILES TO PROCESS ===
def get_new_files(supabase: Client, drive_files):
    log("🗾 Checking against existing DB records...")
    db_files = supabase.table('audio_files').select('filename').execute()
    db_filenames = {record['filename'] for record in db_files.data}
    return [f for f in drive_files if f['name'] not in db_filenames]

# === ▶️ RUN PIPELINE STEP ===
def run_step(script: str) -> bool:
    script_path = os.path.join(os.path.dirname(__file__), script)
    log(f"▶️ Running {script}...")
    try:
        subprocess.run([VENV_PYTHON, script_path], check=True)
        return True
    except subprocess.CalledProcessError:
        log(f"😛 Pipeline stopped: {script} did not process any files or failed.")
        return False
    except FileNotFoundError:
        log(f"😛 Script not found: {script_path}")
        return False

# === 🚀 MAIN ===
def main():
    log("🔍 Checking Google Drive for new audio files...")

    try:
        drive_service = init_drive_service()
        supabase = init_supabase()
    except Exception as e:
        log(f"❌ Error initializing services: {e}")
        return

    try:
        drive_files = fetch_audio_files(drive_service)
        new_files = get_new_files(supabase, drive_files)
    except Exception as e:
        log(f"❌ Error during file fetch/check: {e}")
        return

    if not new_files:
        log("📟 No new files to process. Exiting.")
        return

    log(f"🔟 Found {len(new_files)} new file(s). Running pipeline...")

    steps = [
        "monitor.py",
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

# === ENTRY POINT ===
if __name__ == '__main__':
    main()
