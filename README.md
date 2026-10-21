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

## Web app (Vercel)

The repository also includes a browser-based version that can be deployed to
Vercel. It uses the browser's SpeechRecognition API for microphone transcription
(best supported by Chrome and Edge), while summaries and response suggestions
are sent to a server-side API function. The desktop app above remains available.

### Deploy

1. Import this repository into Vercel and deploy it with the default settings.
   The root `index.html` is served as a static site and `api/assistant.js` is a
   Vercel Node.js Function; no build command is needed.
2. In **Project Settings → Environment Variables**, add:
   - `OPENAI_API_KEY`: your provider API key.
   - `APP_ACCESS_CODE`: a strong, private code required to use the AI endpoint.
   - Optionally `OPENAI_BASE_URL`, `OPENAI_CHAT_MODEL`, and
     `OPENAI_MAX_COMPLETION_TOKENS` for an OpenAI-compatible provider.
3. Redeploy after setting the variables. Share the deployed site and access
   code only with intended users.

The browser asks for microphone permission only after a user starts listening
and checks the participant-consent box. Browser speech recognition may process
audio using browser-vendor services; review the browser's privacy terms. The app
does not save microphone audio. AI requests send the transcript to the configured
provider. The access code is a basic shared gate, not individual-user
authentication; enable Vercel Deployment Protection as well when your plan and
use case support it.
