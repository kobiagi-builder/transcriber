# clean_text.py — GPT-based linguistic cleanup with token fallback

import os
import sys
from datetime import datetime
from supabase import create_client
import openai
from openai.error import OpenAIError
import config

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# === Logger ===
def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    print(formatted)
    try:
        with open("log.txt", "a") as f:
            f.write(formatted + "\n")
    except Exception as e:
        print(f"[Logger Error] Could not write to log file: {e}")

# === Supabase & OpenAI ===
def init_supabase():
    return create_client(config.SUPABASE_URL, config.SUPABASE_API_KEY)

openai.api_key = config.OPENAI_API_KEY

# === GPT Cleaner ===
def clean_text_gpt(text):
    prompt = (
        "You are a distinguished professor of linguistics from the world's top linguistics faculty. "
        "You specialize in understanding texts written by individuals with cognitive challenges and fixing them "
        "while fully preserving their meaning and intent. You correct broken words, redundant letters, fragmented "
        "sentences, and other linguistic issues.\n\n"
        "Please review the following text and fix it if needed:\n\n"
        f"{text}"
    )

    models = ["gpt-4", "gpt-3.5-turbo-16k"]
    for model in models:
        try:
            log(f"🧠 Using model: {model}")
            response = openai.ChatCompletion.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
            )
            return response.choices[0].message.content.strip()
        except OpenAIError as e:
            log(f"❌ OpenAI error with model {model}: {e}")
            if "maximum context length" not in str(e) and "too many tokens" not in str(e):
                break
    return None

# === Main Cleaning Flow ===
def main():
    log("🧹 Starting GPT-based transcript cleaning...")
    sb = init_supabase()

    log("📦 Fetching records with status='transcribed' or 'error'...")
    records = sb.table("audio_files").select("id, filename, transcription, status").in_(
        "status", ["transcribed", "error"]
    ).execute().data

    if not records:
        log("🟡 No transcribed records to clean.")
        return

    for record in records:
        file_id = record["id"]
        filename = record["filename"]
        raw_text = record.get("transcription")

        if not raw_text:
            log(f"⚠️ Skipping {filename} — no transcription found.")
            continue

        try:
            cleaned = clean_text_gpt(raw_text)
            if not cleaned:
                raise Exception("No cleaned text returned from GPT")

            sb.table("audio_files").update({
                "status": "cleaned",
                "cleaned_text": cleaned,
                "error_message": ""
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
