import subprocess
import sys

# Ordered list of pipeline scripts
pipeline = [
    "monitor.py",          # Step 1: Watch Drive for new audio files
    "detect_language.py",  # Step 2: Detect spoken language using Whisper
    "transcribe.py",       # Step 3: Transcribe audio
    "clean_text.py",       # Step 4: Clean transcription with GPT
    "summarize.py",        # Step 5: Summarize and extract action items with GPT
    "create_doc.py"        # Step 6: Create Google Doc and update Supabase
]

# Execute each step in sequence
for script in pipeline:
    print(f"\n▶️ Running {script}...")
    
    result = subprocess.run(["python", script])

    # If the script exits with a non-zero code, stop the pipeline
    if result.returncode != 0:
        print(f"\n🛑 Pipeline stopped: {script} did not process any files or failed.")
        sys.exit(1)

print("\n✅ Pipeline complete: All steps ran successfully.")
