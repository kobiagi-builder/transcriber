import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from supabase import create_client
from config import (
    SUPABASE_URL,
    SUPABASE_API_KEY,
    SERVICE_ACCOUNT_FILE,
    OUTPUT_FOLDER_ID
)

# ------------------ Init APIs ------------------
def init_google_services():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=[
            "https://www.googleapis.com/auth/documents",
            "https://www.googleapis.com/auth/drive"
        ]
    )
    docs_service = build("docs", "v1", credentials=creds)
    drive_service = build("drive", "v3", credentials=creds)
    return docs_service, drive_service

supabase = create_client(SUPABASE_URL, SUPABASE_API_KEY)

# ------------------ Create insertText requests in REVERSE ------------------
def build_reversed_insert_requests(filename, transcription, summary, actions):
    title = filename.replace(".m4a", "") + " (Transcription)\n\n"
    transcription_text = f"🧠 Cleaned Transcription\n{transcription}\n\n"
    summary_text = f"📌 Main Talking Points\n{summary}\n\n"
    actions_text = f"✅ Action Items\n{actions}\n"

    # Insert in reverse order so it appears correctly in doc
    return [
        {"insertText": {"location": {"index": 1}, "text": actions_text}},
        {"insertText": {"location": {"index": 1}, "text": summary_text}},
        {"insertText": {"location": {"index": 1}, "text": transcription_text}},
        {"insertText": {"location": {"index": 1}, "text": title}},
    ]

# ------------------ Main logic ------------------
def main():
    print("📦 Fetching records with status='summarized' or 'error'...")
    records = supabase.table("audio_files").select("*").in_("status", ["summarized", "error"]).execute()

    if not records.data:
        print("🟡 No files to process.")
        return

    docs_service, drive_service = init_google_services()

    for record in records.data:
        filename = record["filename"]
        transcription = record.get("transcription_clean")
        summary = record.get("summary_points")
        actions = record.get("action_items")

        if not all([transcription, summary, actions]):
            print(f"⚠️ Skipping {filename} — missing required fields.")
            continue

        try:
            print(f"\n📄 Creating Google Doc for: {filename}")
            doc_title = filename.replace(".m4a", ".doc")

            # 1. Create a new doc
            doc = docs_service.documents().create(body={"title": doc_title}).execute()
            doc_id = doc["documentId"]

            # 2. Insert all content using reversed order
            requests = build_reversed_insert_requests(filename, transcription, summary, actions)
            docs_service.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()

            # 3. Move doc into output folder
            drive_service.files().update(
                fileId=doc_id,
                addParents=OUTPUT_FOLDER_ID,
                fields="id, parents"
            ).execute()

            # 4. Update Supabase
            doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
            timestamp = datetime.datetime.utcnow().isoformat()

            supabase.table("audio_files").update({
                "transcription_url": doc_url,
                "transcription_created_at": timestamp,
                "status": "documented",
                "error_message": None
            }).eq("filename", filename).execute()

            print(f"✅ Document created: {doc_url}")

        except Exception as e:
            print(f"❌ Error for {filename}: {e}")
            supabase.table("audio_files").update({
                "status": "error",
                "error_message": str(e)
            }).eq("filename", filename).execute()

    print("\n✅ Step 4 Complete: Document creation finished.")

# ------------------ Run ------------------
if __name__ == "__main__":
    main()
