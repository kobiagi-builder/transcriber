import os
import io
import whisper
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from supabase import create_client
from config import SUPABASE_URL, SUPABASE_API_KEY, INPUT_FOLDER_ID, SERVICE_ACCOUNT_FILE

# --------------------------------------------
# 🔗 Initialize Supabase connection
# --------------------------------------------
supabase = create_client(SUPABASE_URL, SUPABASE_API_KEY)

# --------------------------------------------
# 🔗 Set up Google Drive API connection
# --------------------------------------------
def init_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=creds)

# --------------------------------------------
# 📥 Download an audio file if not already local
# --------------------------------------------
def download_file(service, filename):
    # Check if file is already downloaded
    if os.path.exists(filename):
        print(f"📂 Using local copy of {filename}")
        return filename

    print(f"⏬ Downloading {filename} from Google Drive...")

    # List files in the specified Drive folder
    results = service.files().list(
        q=f"'{INPUT_FOLDER_ID}' in parents and trashed = false",
        fields="files(id, name)",
        spaces="drive"
    ).execute()

    files = results.get("files", [])

    # Search for the matching file by name
    for f in files:
        if f["name"] == filename:
            request = service.files().get_media(fileId=f["id"])
            fh = io.FileIO(filename, "wb")
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            return filename

    # File not found in Drive
    return None

# --------------------------------------------
# 🧠 Main Transcription Logic
# --------------------------------------------
def main():
    print("🎙️ Loading Whisper model...")
    model = whisper.load_model("large-v2")

    print("📦 Fetching records with status = 'language_detected'...")
    # Get all audio files ready for transcription
    records = supabase.table("audio_files").select("*").eq("status", "language_detected").execute()

    if not records.data:
        print("🟡 No files ready for transcription.")
        return

    # Initialize Google Drive client
    drive_service = init_drive_service()

    # Loop through each file needing transcription
    for record in records.data:
        filename = record["filename"]
        language = record["language"]
        print(f"\n🎧 Transcribing: {filename} | Language: {language}")

        try:
            # Step 1: Download the audio file
            local_path = download_file(drive_service, filename)
            if not local_path:
                raise Exception("File not found in Drive.")

            # Step 2: Transcribe using Whisper
            result = model.transcribe(local_path, language=language)
            transcription_text = result["text"]
            print("📝 Transcription complete.")

            # Step 3: Update Supabase with raw transcription
            supabase.table("audio_files").update({
                "transcription": transcription_text,
                "status": "transcribed"  # Now ready for text cleaning
            }).eq("filename", filename).execute()

            # Step 4: Remove temporary local file
            os.remove(local_path)

        except Exception as e:
            # Log errors and update DB with error status
            print(f"❌ Error transcribing {filename}: {e}")
            supabase.table("audio_files").update({
                "status": "error",
                "error_message": str(e)
            }).eq("filename", filename).execute()

    print("\n✅ Step 1 Complete: Transcription finished.")

# --------------------------------------------
# 🔁 Entry point
# --------------------------------------------
if __name__ == "__main__":
    main()
