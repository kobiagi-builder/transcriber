# monitor.py — Refactored for Robustness, Safe Retries, and Clarity

import os
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from supabase import create_client
import config

# === 🧠 Constants ===
AUDIO_MIME_TYPES = [
    "audio/mpeg", "audio/wav", "audio/x-wav",
    "audio/mp4", "audio/x-m4a"
]

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

# === 🔌 INIT SUPABASE ===
def init_supabase():
    return create_client(config.SUPABASE_URL, config.SUPABASE_API_KEY)

# === 🔌 INIT GOOGLE DRIVE ===
def init_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        config.SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=creds)

# === 📁 List audio files in the input folder ===
def list_audio_files(service):
    query = f"'{config.INPUT_FOLDER_ID}' in parents and trashed = false"
    results = service.files().list(
        q=query,
        spaces='drive',
        fields="files(id, name, mimeType)"
    ).execute()

    files = results.get("files", [])
    return [f for f in files if (
        f["mimeType"] in AUDIO_MIME_TYPES or f["name"].lower().endswith(".m4a")
    )]

# === 📄 Get already processed files from Supabase ===
def get_existing_filenames(supabase):
    result = supabase.table("audio_files").select("filename").execute()
    if result.data:
        return set(row["filename"] for row in result.data)
    return set()

# === ➕ Insert file record ===
def insert_new_file_record(supabase, file):
    log(f"🆕 Inserting new file: {file['name']}")
    supabase.table("audio_files").insert({
        "filename": file["name"],
        "status": "new"
    }).execute()

# === 🚀 MAIN ===
def main():
    log("⏳ Initializing services...")
    try:
        supabase = init_supabase()
        drive_service = init_drive_service()
    except Exception as e:
        log(f"❌ Initialization failed: {e}")
        return False

    try:
        audio_files = list_audio_files(drive_service)
        log("📁 Fetched audio files from Google Drive.")

        existing_files = get_existing_filenames(supabase)
        new_files = [f for f in audio_files if f["name"] not in existing_files]

        log(f"🆕 Found {len(new_files)} new audio file(s).")
        for file in new_files:
            insert_new_file_record(supabase, file)

        log("✅ Monitoring complete.")
        return len(new_files) > 0

    except Exception as e:
        log(f"❌ Monitoring failed: {e}")
        return False

if __name__ == "__main__":
    main()
