# create_doc.py — Final version to generate Google Docs from summaries

import os
import sys
from datetime import datetime
from supabase import create_client
from google.oauth2 import service_account
from googleapiclient.discovery import build
import config

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# === 🕒 Logger ===
def log(msg):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {msg}")
    try:
        with open("log.txt", "a") as f:
            f.write(f"[{timestamp}] {msg}\n")
    except:
        pass

# === 🔌 Supabase & Drive ===
def init_supabase():
    return create_client(config.SUPABASE_URL, config.SUPABASE_API_KEY)

def init_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        config.SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/documents"]
    )
    return build("drive", "v3", credentials=creds), build("docs", "v1", credentials=creds)

# === 📄 Generate Google Doc Content ===
def build_doc_body(summary_points, action_items):
    body = [
        {"insertText": {"location": {"index": 1}, "text": "📝 Meeting Summary\n\n"}}
    ]
    if summary_points:
        body.append({"insertText": {"location": {"index": 1}, "text": "Main Talking Points:\n"}})
        for point in summary_points:
            body.append({"insertText": {"location": {"index": 1}, "text": f"• {point}\n"}})
        body.append({"insertText": {"location": {"index": 1}, "text": "\n"}})

    if action_items:
        body.append({"insertText": {"location": {"index": 1}, "text": "Action Items:\n"}})
        for action in action_items:
            body.append({"insertText": {"location": {"index": 1}, "text": f"• {action}\n"}})

    return list(reversed(body))  # reversed so the first text ends up at top

# === 🚀 Main ===
def main():
    log("📦 Fetching records with status='summarized' or 'error'...")
    sb = init_supabase()
    drive_service, docs_service = init_drive_service()

    records = sb.table("audio_files").select("id, filename, summary_points, action_items, full_summary, status").in_("status", ["summarized", "error"]).execute().data

    if not records:
        log("🟡 No summarized records to process.")
        return

    for record in records:
        file_id = record["id"]
        filename = record["filename"]
        summary = record.get("full_summary")
        points = record.get("summary_points")
        actions = record.get("action_items")

        if not (summary and points and actions):
            log(f"⚠️ Skipping {filename} — missing required fields.")
            continue

        try:
            log(f"📄 Creating Google Doc for: {filename}")
            doc_title = f"Summary - {filename}"
            doc = docs_service.documents().create(body={"title": doc_title}).execute()
            doc_id = doc["documentId"]

            requests = build_doc_body(points, actions)
            docs_service.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()

            # Optionally move the file to a Drive folder
            if config.OUTPUT_FOLDER_ID:
                drive_service.files().update(fileId=doc_id, addParents=config.OUTPUT_FOLDER_ID).execute()

            sb.table("audio_files").update({
                "status": "document_created"
            }).eq("id", file_id).execute()

            log(f"✅ Document created for {filename}")

        except Exception as e:
            log(f"❌ Error creating doc for {filename}: {e}")
            sb.table("audio_files").update({
                "status": "error",
                "error_message": str(e)
            }).eq("id", file_id).execute()

    log("✅ Step 4 Complete: Document creation finished.")

if __name__ == "__main__":
    main()
