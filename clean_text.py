# clean_text.py — Updates cleaned_text column, not cleaned_transcription

import os
import sys
from datetime import datetime
from supabase import create_client
import config
import re

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
        print(f"[Logger Error] Could not write to log file: {e}")

# === 🔌 Init Supabase ===
def init_supabase():
    return create_client(config.SUPABASE_URL, config.SUPABASE_API_KEY)

# === 🧹 Clean Transcript ===
def clean_transcript(text):
    # Basic cleanup: remove filler words and repeated punctuation
    text = re.sub(r"\b(um+|uh+|like|you know)\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

# === 🚀 Main ===
def main():
    log("🧹 Starting transcript cleaning...")
    sb = init_supabase()

    log("📦 Fetching records with status='transcribed' or 'error'...")
    records = sb.table("audio_files").select("id, filename, transcription, status").in_("status", ["transcribed", "error"]).execute().data

    if not records:
        log("🟡 No records to clean.")
        return

    for record in records:
        file_id = record["id"]
        filename = record["filename"]
        raw_text = record.get("transcription")

        if not raw_text:
            log(f"⚠️ Skipping {filename} — no transcription found.")
            continue

        try:
            cleaned = clean_transcript(raw_text)
            sb.table("audio_files").update({
                "status": "cleaned",
                "cleaned_text": cleaned
            }).eq("id", file_id).execute()
            log(f"✅ Cleaned: {filename}")
        except Exception as e:
            log(f"❌ Error cleaning {filename}: {type(e).__name__}: {str(e)}")
            sb.table("audio_files").update({
                "status": "error",
                "error_message": str(e)
            }).eq("id", file_id).execute()

    log("✅ Step 2 Complete: Cleaning process finished.")

if __name__ == "__main__":
    main()
