I've created a comprehensive script for transcription automation. Here's the functionalities:
Features:
✅ Login Detection - Checks if you're logged in, waits for you if not
✅ Dual Transcription Support - Choose between local Whisper or OpenAI API
✅ Automatic Code-Switching - Detects English/Sheng words and adds [cs] tags
✅ Auto-progression - Moves to next audio after you click Submit
✅ Continuous Processing - Handles multiple audios in sequence
✅ URL via CLI - No hardcoded URLs, fully flexible
Installation:
bash# Install required packages
pip install selenium webdriver-manager requests

`# For local Whisper (recommended - free):`
pip install openai-whisper

# For OpenAI API method:
pip install openai n<br>
Usage:<br>
Option 1: Local Whisper (Free, no API key needed):<br>
bashpython transcribe.py --url <url here> --method whisper-local<br>
Option 2: OpenAI API (Paid, more accurate):<br>
bashpython transcribe.py --url <url here> --method openai-api --api-key YOUR_API_KEY<br>
How it works:

Opens browser and checks login status
If not logged in, waits for you to login manually
Extracts audio URL from the page
Downloads and transcribes the audio
Detects code-switching and adds [cs] markers
Inserts transcription into the textarea
WAITS FOR YOU to review and click Submit
Automatically moves to next audio
Repeats until no more audios

Notes:

The code-switching detection is heuristic-based (looks for English patterns)
You can edit the transcription before submitting
Press Ctrl+C to stop anytime
The browser stays open so you can manually verify each transcription

Would you like me to adjust the code-switching detection logic or add any other features?