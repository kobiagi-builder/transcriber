import os
import tempfile
import traceback
from datetime import datetime

import whisper
from supabase import create_client
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

from config import SUPABASE_URL, SUPABASE_API_KEY, SERVICE_ACCOUNT_FILE, INPUT_FOLDER_ID

# === Logging ===
def log(msg):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {msg}")

# === Initialize Supabase ===
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_API_KEY)

# === Initialize Google Drive API ===
def init_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=creds)

# === Download File from Google Drive ===
def download_from_drive(filename, drive_service, download_path="downloads"):
    log(f"🔽 Downloading from Drive: {filename}")
    query = f"name='{filename}' and '{INPUT_FOLDER_ID}' in parents and trashed = false"
    results = drive_service.files().list(
        q=query,
        fields="files(id, name)"
    ).execute()

    items = results.get("files", [])
    if not items:
        raise FileNotFoundError(f"No file found in Drive with name: {filename}")

    file_id = items[0]['id']
    request = drive_service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)

    done = False
    while not done:
        status, done = downloader.next_chunk()
        log(f"⬇️ Download progress: {int(status.progress() * 100)}%")

    os.makedirs(download_path, exist_ok=True)
    local_path = os.path.join(download_path, filename)
    with open(local_path, "wb") as f:
        f.write(fh.getvalue())

    return local_path

# === Detect Language ===
def detect_language(audio_path):
    model = whisper.load_model("medium")  # Change to "large-v3" if you want more accuracy
    result = model.transcribe(audio_path, task="transcribe", fp16=False)
    return result.get("language", "unknown")

# === Main ===
def main():
    log("🧠 Loading Whisper model...")
    supabase = init_supabase()
    drive_service = init_drive_service()

    log("📦 Connecting to Supabase...")
    response = supabase.table("audio_files").select("id, filename").eq("status", "new").execute()
    rows = response.data or []
    log(f"🔎 Found {len(rows)} file(s) to process.")

    for row in rows:
        filename = row["filename"]
        log(f"\n🎧 Processing: {filename}")

        temp_audio = None
        try:
            log("🔍 Detecting language...")
            temp_audio = download_from_drive(filename, drive_service)
            lang = detect_language(temp_audio)

            supabase.table("audio_files").update({
                "language": lang,
                "status": "language_detected",
                "error_message": ""
            }).eq("id", row["id"]).execute()

            log(f"✅ Language detected: {lang}")
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            log(f"❌ Error processing {filename}: {error_msg}")
            log(traceback.format_exc())

            supabase.table("audio_files").update({
                "status": "error",
                "error_message": error_msg
            }).eq("id", row["id"]).execute()
        finally:
            try:
                if temp_audio and os.path.exists(temp_audio):
                    os.remove(temp_audio)
            except Exception:
                pass

    log("✅ Language detection complete.")

if __name__ == "__main__":
    main()
