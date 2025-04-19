import os
import mimetypes
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from supabase import create_client
from config import SUPABASE_URL, SUPABASE_API_KEY, INPUT_FOLDER_ID, SERVICE_ACCOUNT_FILE

# === 🕒 Logger ===
def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

# === Supported audio MIME types
AUDIO_MIME_TYPES = ["audio/mpeg", "audio/wav", "audio/x-wav", "audio/mp4", "audio/x-m4a"]

# === Supabase client init
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_API_KEY)

# === Google Drive API client init
def init_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=creds)

# === List audio files from Drive
def list_audio_files(service):
    query = f"'{INPUT_FOLDER_ID}' in parents and trashed = false"
    results = service.files().list(
        q=query,
        spaces='drive',
        fields="files(id, name, mimeType)"
    ).execute()

    files = results.get("files", [])

    # Filter by MIME type or .m4a extension
    audio_files = [
        f for f in files if (
            f["mimeType"] in AUDIO_MIME_TYPES or
            f["name"].lower().endswith(".m4a")
        )
    ]
    return audio_files

# === Fetch filenames already in DB
def get_existing_filenames(supabase):
    result = supabase.table("audio_files").select("filename").execute()
    if result.data:
        return set(row["filename"] for row in result.data)
    return set()

# === Insert new audio file into Supabase
def insert_new_file_record(supabase, file):
    log(f"🆕 Inserting new file: {file['name']}")
    supabase.table("audio_files").insert({
        "filename": file["name"],
        "status": "new"
    }).execute()

# === Main logic
def main():
    log("⏳ Initializing services...")
    supabase = init_supabase()
    drive_service = init_drive_service()

    log("📁 Fetching audio files from Google Drive...")
    audio_files = list_audio_files(drive_service)

    log("🧾 Checking against existing DB records...")
    existing_files = get_existing_filenames(supabase)

    new_files = [f for f in audio_files if f["name"] not in existing_files]

    log(f"🆕 Found {len(new_files)} new audio file(s).")
    for file in new_files:
        insert_new_file_record(supabase, file)

    log("✅ Monitoring complete.")

# === Run it
if __name__ == "__main__":
    main()