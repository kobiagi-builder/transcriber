import openai
from supabase import create_client
from config import SUPABASE_URL, SUPABASE_API_KEY, OPENAI_API_KEY

# ------------------------------------------------------
# 🔐 Set up API clients
# ------------------------------------------------------
openai.api_key = OPENAI_API_KEY
supabase = create_client(SUPABASE_URL, SUPABASE_API_KEY)

# ------------------------------------------------------
# 🧠 Prompt to clean transcription
# ------------------------------------------------------
therapist_prompt = (
    "You are a linguistic therapist expert in understanding text that was written by people with cognitive issues. "
    "Your task is:\n"    
    "1. Read the whole text and understand its concepts.\n"
    "2. Correct the text so it will be linguistically, cognitively and logically correct.\n" 
    "After this step every word, sequence of words and sentance will make sense and be correct linguistically and cognitively\n"
    "The output must not include any preface or suffix. It will include only a corrected version of the text.\n"
    "Do not change the text content - Just make it correct linguistically."
)

# ------------------------------------------------------
# 🧠 Run GPT-4-Turbo to clean the transcription
# ------------------------------------------------------
def gpt_clean_text(text):
    response = openai.ChatCompletion.create(
        model="gpt-4-turbo",  # Fast, supports long input, high quality
        messages=[
            {"role": "system", "content": therapist_prompt},
            {"role": "user", "content": text}
        ],
        temperature=0.5
    )
    return response.choices[0].message.content.strip()

# ------------------------------------------------------
# 🚀 Main logic: fetch, validate, clean, update
# ------------------------------------------------------
def main():
    print("📦 Fetching records with status='transcribed' or 'error'...")
    
    # Include error records so we can retry failed ones
    records = supabase.table("audio_files").select("*").in_("status", ["transcribed", "error"]).execute()

    if not records.data:
        print("🟡 No files to clean.")
        return

    for record in records.data:
        filename = record["filename"]
        raw_text = record.get("transcription")

        # ✅ Skip if transcription is missing
        if not raw_text:
            print(f"⚠️ Skipping {filename} — no transcription data found.")
            continue

        print(f"\n🧼 Cleaning transcription for: {filename}")

        try:
            # 🧠 Clean the text with GPT-4-Turbo
            cleaned_text = gpt_clean_text(raw_text)

            # ✅ Update Supabase with cleaned result and mark as 'cleaned'
            supabase.table("audio_files").update({
                "transcription_clean": cleaned_text,
                "status": "cleaned",
                "error_message": None  # clear old errors if any
            }).eq("filename", filename).execute()

            print("✅ Cleaned and updated successfully.")

        except Exception as e:
            # ❌ If it fails, log error and preserve for retry
            print(f"❌ Error cleaning {filename}: {e}")
            supabase.table("audio_files").update({
                "status": "error",
                "error_message": str(e)
            }).eq("filename", filename).execute()

    print("\n✅ Step 2 Complete: Cleaning process finished.")

# ------------------------------------------------------
# 🏁 Run when executed directly
# ------------------------------------------------------
if __name__ == "__main__":
    main()
