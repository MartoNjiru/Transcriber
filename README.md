# Transcriber

## Meeting Companion

A small, visible, consent-based meeting assistant for transcription and meeting
notes. It transcribes microphone audio in five-second segments and can generate
a response suggestion or a meeting summary from the transcript.

## Setup (Windows PowerShell)

Use Python 3.10 or newer:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:OPENAI_API_KEY = "your-api-key"
python ".\Project 1.py"
```

Optional configuration:

```powershell
$env:OPENAI_BASE_URL = "https://your-compatible-provider.example/v1"
$env:OPENAI_TRANSCRIPTION_MODEL = "gpt-4o-mini-transcribe"
$env:OPENAI_CHAT_MODEL = "gpt-4o-mini"
```

The configured provider must support the OpenAI-compatible audio transcription
and chat completions endpoints, plus the selected model names.

## Privacy and consent

- The microphone is active only after the user presses **Start microphone** and
  confirms that participants have been informed and have given permission.
- Audio segments are sent to the configured transcription API. Audio is kept in
  memory by this app and is not written to disk.
- Transcripts remain in memory unless the user explicitly saves one.
- AI suggestions and summaries send the current transcript to the configured
  chat API when the corresponding button is pressed.
- The app does not hide itself, evade recording indicators, or record in the
  background.

Provider retention and data handling are governed by that provider's terms and
configuration; review them before sending meeting audio or transcripts.
