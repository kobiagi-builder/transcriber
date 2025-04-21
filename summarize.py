# summarize.py — strict prompt, robust parser, fallback models

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
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    formatted = f"[{timestamp}] {msg}"
    print(formatted)
    try:
        with open("log.txt", "a") as f:
            f.write(formatted + "\n")
    except Exception as e:
        print(f"[Logger Error] Could not write to log.txt: {e}")

# === Supabase & OpenAI ===
def init_supabase():
    return create_client(config.SUPABASE_URL, config.SUPABASE_API_KEY)

openai.api_key = config.OPENAI_API_KEY

# === Parser ===
def parse_summary_output(output):
    try:
        lines = output.strip().split("\n")
        action_items, talking_points = [], []
        section = None

        for line in lines:
            lowered = line.lower()
            if "action items" in lowered:
                section = "actions"
                continue
            elif "main talking points" in lowered or "talking points" in lowered:
                section = "points"
                continue
            elif not line.strip():
                continue

            bullet = line.strip().lstrip("-*•").strip()
            if section == "actions":
                action_items.append(bullet)
            elif section == "points":
                talking_points.append(bullet)

        return action_items, talking_points
    except Exception as e:
        log(f"⚠️ Failed to parse summary output: {e}")
        return [], []

# === GPT Call with Fallback ===
def summarize_text(text):
    prompt = (
        "You are a business meeting assistant. Summarize the following meeting transcription into "
        "**two sections only**: Main Talking Points and Action Items.\n\n"
        "**Respond in strict markdown format with this exact structure (the example include only two points but you can add as many points as needed):**\n\n"
        "## Main Talking Points\n"
        "- First point\n"
        "- Second point\n\n"
        "## Action Items\n"
        "- First action\n"
        "- Second action\n\n"
        "Do not include any extra text or introduction.\n\n"
        f"Meeting transcription:\n{text}"
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

# === Main ===
def main():
    log("📦 Fetching records with status='cleaned' or 'summary_error'...")
    sb = init_supabase()
    records = sb.table("audio_files").select(
        "id, filename, cleaned_text, status"
    ).in_("status", ["cleaned", "summary_error"]).execute().data

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
            log("📄 GPT returned:\n" + summary)
            sb.table("audio_files").update({
                "status": "summary_error",
                "full_summary": summary
            }).eq("id", file_id).execute()

    log("✅ Step Complete: Summarization finished.")

if __name__ == "__main__":
    main()
