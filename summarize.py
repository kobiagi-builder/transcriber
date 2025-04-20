# summarize.py — FINAL patched version using cleaned_text and status=cleaned

import os
import sys
from datetime import datetime
from supabase import create_client
import openai
from openai.error import OpenAIError
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

# === 🔌 Init Supabase ===
def init_supabase():
    return create_client(config.SUPABASE_URL, config.SUPABASE_API_KEY)

# === 🔌 Init OpenAI ===
openai.api_key = config.OPENAI_API_KEY

# === 📄 Parse GPT Output ===
def parse_summary_output(output):
    try:
        lines = output.strip().split("\n")
        action_items, talking_points = [], []
        section = None
        for line in lines:
            if "action items" in line.lower():
                section = "actions"
                continue
            elif "main talking points" in line.lower():
                section = "points"
                continue
            elif not line.strip():
                continue
            if section == "actions":
                action_items.append(line.strip("-• "))
            elif section == "points":
                talking_points.append(line.strip("-• "))
        return action_items, talking_points
    except Exception as e:
        log(f"⚠️ Failed to parse summary output: {e}")
        return [], []

# === 🧠 Summarize Text ===
def summarize_text(text):
    prompt = (
        "You are a business productivity assistant. "
        "Summarize the following text into two sections: Main Talking Points and Action Items.\n\n"
        f"Text: \n{text}\n\n"
        "Respond in markdown with clear bullet points under each section."
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
        )
        return response.choices[0].message.content.strip()
    except OpenAIError as e:
        log(f"❌ OpenAI API error: {e}")
        return None

# === 🚀 Main ===
def main():
    log("📦 Fetching records with status='cleaned' or 'summary_error'...")
    sb = init_supabase()
    records = sb.table("audio_files").select("id, filename, cleaned_text, status").in_("status", ["cleaned", "summary_error"]).execute().data

    if not records:
        log("🟡 No cleaned records to summarize.")
        return

    for record in records:
        file_id = record["id"]
        filename = record["filename"]
        text = record.get("cleaned_text")

        if not text:
            log(f"⚠️ Skipping {filename} — no cleaned text found.")
            continue

        log(f"🧠 Summarizing: {filename}")
        summary = summarize_text(text)

        if not summary:
            sb.table("audio_files").update({"status": "summary_error"}).eq("id", file_id).execute()
            continue

        action_items, talking_points = parse_summary_output(summary)

        if action_items and talking_points:
            sb.table("audio_files").update({
                "status": "summarized",
                "summary_points": talking_points,
                "action_items": action_items,
                "full_summary": summary
            }).eq("id", file_id).execute()
            log(f"✅ Summary complete for: {filename}")
        else:
            log(f"⚠️ Failed to extract bullet points for {filename}, saving raw summary.")
            sb.table("audio_files").update({
                "status": "summary_error",
                "full_summary": summary
            }).eq("id", file_id).execute()

    log("✅ Step Complete: Summarization finished.")

if __name__ == "__main__":
    main()
