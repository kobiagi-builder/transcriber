import openai
from supabase import create_client
from config import SUPABASE_URL, SUPABASE_API_KEY, OPENAI_API_KEY

# ------------------------------------------------------
# 🔐 API Initialization
# ------------------------------------------------------
openai.api_key = OPENAI_API_KEY
supabase = create_client(SUPABASE_URL, SUPABASE_API_KEY)

# ------------------------------------------------------
# 🧠 Prompt: Executive Assistant-style summarizer
# ------------------------------------------------------
summary_prompt = (
    "You are a laser-sharp executive assistant.\n"
    "Your task is to create a summary of the text as follows:\n"
    "* Main talking points\n"
    "* Action items\n\n"
    "Example:\n"
    "Input: I went to the garden and picked a flower. I'll put it in the vase.\n"
    "Result:\n"
    "Main talking points:\n"
    "* A walk in the garden\n"
    "Action items:\n"
    "* Put the flower in the vase."
)

# ------------------------------------------------------
# 🧠 GPT-4-Turbo Summarization Function
# ------------------------------------------------------
def gpt_generate_summary(text):
    response = openai.ChatCompletion.create(
        model="gpt-4-turbo",  # Use GPT-4-Turbo for speed + quality
        messages=[
            {"role": "system", "content": summary_prompt},
            {"role": "user", "content": text}
        ],
        temperature=0.3
    )
    return response.choices[0].message.content.strip()

# ------------------------------------------------------
# 🔍 Split summary output into two fields (bullets, dashes, numbers)
# ------------------------------------------------------
def split_summary(gpt_output):
    summary = []
    actions = []
    section = None

    for line in gpt_output.splitlines():
        line = line.strip()

        # Detect section headers
        if line.lower().startswith("main talking points"):
            section = "summary"
            continue
        if line.lower().startswith("action items"):
            section = "actions"
            continue

        # Match bullet formats: -, *, 1. etc.
        if section == "summary" and line:
            if line.startswith(("-", "*")) or line[:2].isdigit():
                summary.append(line)
        elif section == "actions" and line:
            if line.startswith(("-", "*")) or line[:2].isdigit():
                actions.append(line)

    # Fallback: return entire GPT output if we couldn't parse cleanly
    if not summary and not actions:
        print("⚠️ Could not parse sections. Saving full output in summary_points only.")
        return gpt_output.strip(), ""

    return "\n".join(summary), "\n".join(actions)

# ------------------------------------------------------
# 🚀 Main process to summarize eligible records
# ------------------------------------------------------
def main():
    print("📦 Fetching records with status='cleaned' or 'error'...")

    # Fetch all cleaned or previously failed records for retry
    records = supabase.table("audio_files").select("*").in_("status", ["cleaned", "error"]).execute()

    if not records.data:
        print("🟡 No files to summarize.")
        return

    for record in records.data:
        filename = record["filename"]
        clean_text = record.get("transcription_clean")

        # ✅ Skip if transcription_clean is missing
        if not clean_text:
            print(f"⚠️ Skipping {filename} — no cleaned transcription found.")
            continue

        print(f"\n🧠 Summarizing: {filename}")

        try:
            # 🔁 Get summary from GPT
            summary_output = gpt_generate_summary(clean_text)

            # 📤 Print GPT output (for debug)
            print(f"📤 GPT Output:\n{summary_output}\n")

            # ✂️ Extract summary + action items
            summary_points, action_items = split_summary(summary_output)

            # 💾 Update Supabase
            supabase.table("audio_files").update({
                "summary_points": summary_points,
                "action_items": action_items,
                "status": "summarized",
                "error_message": None
            }).eq("filename", filename).execute()

            print("✅ Summary saved to database.")

        except Exception as e:
            print(f"❌ Error summarizing {filename}: {e}")
            supabase.table("audio_files").update({
                "status": "error",
                "error_message": str(e)
            }).eq("filename", filename).execute()

    print("\n✅ Step 3 Complete: Summarization finished.")

# ------------------------------------------------------
# 🏁 Run the script
# ------------------------------------------------------
if __name__ == "__main__":
    main()
