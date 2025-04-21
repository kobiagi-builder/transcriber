# transcribe.py — Refactored to include language detection via Whisper

import os
import sys
import io
import whisper
from datetime import datetime
from supabase import create_client
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

import config

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

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

# === 🔌 INIT SERVICES ===
def init_supabase():
    return create_client(config.SUPABASE_URL, config.SUPABASE_API_KEY)

def init_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        config.SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=creds)

# === 🔽 DOWNLOAD AUDIO FROM DRIVE ===
def download_from_drive(filename, drive_service, download_path="downloads"):
    log(f"🔽 Downloading from Drive: {filename}")
    query = f"name='{filename}' and '{config.INPUT_FOLDER_ID}' in parents and trashed = false"
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

# === 🧠 TRANSCRIBE + DETECT LANGUAGE ===
def transcribe_audio(model, file_path):
    try:
        result = model.transcribe(file_path, fp16=False)
        return result["text"], result.get("language", "unknown")
    except Exception as e:
        log(f"❌ Transcription failed for {file_path}: {e}")
        return None, None

# === 🚀 MAIN ===
def main():
    log("🎙️ Loading Whisper model...")
    model = whisper.load_model("medium")  # or "medium" for CPU-friendly

    log("📦 Connecting to Supabase...")
    supabase = init_supabase()
    drive_service = init_drive_service()

    result = supabase.table("audio_files").select("id", "filename", "status").eq("status", "new").execute()
    files = result.data if result.data else []

    if not files:
        log("🟡 No new files to transcribe.")
        return

    for file in files:
        filename = file['filename']
        file_id = file['id']
        log(f"🔤 Transcribing: {filename}")

        try:
            local_path = download_from_drive(filename, drive_service)
        except Exception as e:
            log(f"❌ Failed to download {filename} from Drive: {e}")
            supabase.table("audio_files").update({"status": "error"}).eq("id", file_id).execute()
            continue

        text, lang = transcribe_audio(model, local_path)
        if not text:
            supabase.table("audio_files").update({"status": "error"}).eq("id", file_id).execute()
            continue

        supabase.table("audio_files").update({
            "status": "transcribed",
            "transcription": text,
            "language": lang,
            "error_message": ""
        }).eq("id", file_id).execute()

        log(f"✅ Transcription complete for: {filename} — language: {lang}")

        try:
            os.remove(local_path)
        except Exception as cleanup_err:
            log(f"⚠️ Couldn't delete temp file: {cleanup_err}")

    log("✅ Step Complete: Transcription and language detection finished.")

if __name__ == '__main__':
    main()
