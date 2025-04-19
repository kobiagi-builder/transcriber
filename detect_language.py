import os
import io
import whisper
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2 import service_account
from googleapiclient.discovery import build
from supabase import create_client
from config import SUPABASE_URL, SUPABASE_API_KEY, INPUT_FOLDER_ID, SERVICE_ACCOUNT_FILE

# Initialize Supabase client for database interaction
supabase = create_client(SUPABASE_URL, SUPABASE_API_KEY)

# Set up and return Google Drive service client
def init_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=creds)

# Download a specific file by name from the Google Drive input folder
def download_file(service, filename):
    # Get list of all files in the specified input folder
    results = service.files().list(
        q=f"'{INPUT_FOLDER_ID}' in parents and trashed = false",
        fields="files(id, name)",
        spaces="drive"
    ).execute()

    files = results.get("files", [])
    
    # Find the matching file and download it
    for f in files:
        if f["name"] == filename:
            request = service.files().get_media(fileId=f["id"])
            fh = io.FileIO(filename, "wb")
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
            return filename
    return None

# Main logic of the language detection script
def main():
    print("🧠 Loading Whisper model...")
    model = whisper.load_model("base")  # Use a small but accurate model

    print("📦 Connecting to Supabase...")
    # Get all records where audio files are ready for language detection
    records = supabase.table("audio_files").select("*").in_("status", ["new", "error"]).execute()
    print(f"🔎 Found {len(records.data)} file(s) to process.")

    if not records.data:
        print("🟡 No new audio files found.")
        return

    # Initialize the Drive API client
    drive_service = init_drive_service()

    # Process each new audio file
    for record in records.data:
        filename = record["filename"]
        print(f"\n🎧 Processing: {filename}")

        try:
            # Download audio file from Google Drive
            local_path = download_file(drive_service, filename)
            if not local_path:
                raise Exception("File not found in Drive")

            # Run Whisper language detection
            print("🔍 Detecting language...")
            result = model.transcribe(local_path, task="transcribe", language=None)

            # Extract detected language from result
            detected_lang = result["language"]
            print(f"🌍 Detected language: {detected_lang}")

            # Update record in Supabase
            supabase.table("audio_files").update({
                "language": detected_lang,
                "status": "language_detected"
            }).eq("filename", filename).execute()

            # Remove the downloaded file from local storage
            os.remove(local_path)

        except Exception as e:
            # On error, update the record with status = error and log message
            print(f"❌ Error processing {filename}: {e}")
            supabase.table("audio_files").update({
                "status": "error",
                "error_message": str(e)
            }).eq("filename", filename).execute()

    print("\n✅ Language detection complete.")

# Run the main function
if __name__ == "__main__":
    main()
