from __future__ import annotations

import io
import os
import queue
import threading
import wave
from pathlib import Path
from tkinter import BooleanVar, StringVar, Tk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
from tkinter import ttk

from openai import OpenAI, OpenAIError


SAMPLE_RATE: int = 16_000
CHANNELS: int = 1
CHUNK_SECONDS: int = 5
FRAMES_PER_READ: int = 8_000


def encode_wav(audio: bytes) -> bytes:
    """Wrap mono 16-bit PCM samples in a WAV container for transcription."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(CHANNELS)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(audio)
    return buffer.getvalue()


class MeetingCompanion:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("Meeting Companion")
        self.root.geometry("900x720")
        self.root.minsize(680, 520)

        self._stop_event: threading.Event | None = None
        self._audio_queue: queue.Queue[bytes | None] | None = None
        self._client: OpenAI | None = None
        self._transcription_model = ""
        self._chat_model = ""
        self._capture_error: str | None = None
        self._transcription_error: str | None = None
        self._session_active = False
        self._ai_active = False
        self._close_requested = False
        self._consent = BooleanVar(value=False)
        self._status_text = StringVar(value="Idle")

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        container = ttk.Frame(self.root, padding=14)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(5, weight=1)

        ttk.Label(
            container,
            text="Meeting Companion",
            font=("Segoe UI", 18, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            container,
            text=(
                "Visible, consent-based meeting support. Audio is sent to the "
                "configured transcription API; nothing is recorded covertly."
            ),
            wraplength=850,
        ).grid(row=1, column=0, sticky="w", pady=(4, 12))

        controls = ttk.Frame(container)
        controls.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        self.start_button = ttk.Button(
            controls, text="Start microphone", command=self.start_listening
        )
        self.start_button.pack(side="left")
        self.stop_button = ttk.Button(
            controls,
            text="Stop",
            command=self.stop_listening,
            state="disabled",
        )
        self.stop_button.pack(side="left", padx=(8, 0))
        ttk.Label(controls, textvariable=self._status_text).pack(
            side="left", padx=(14, 0)
        )

        self.consent_check = ttk.Checkbutton(
            container,
            text="I have informed participants and have permission to capture this conversation.",
            variable=self._consent,
        )
        self.consent_check.grid(row=3, column=0, sticky="w", pady=(0, 12))

        ttk.Label(container, text="Live transcript").grid(
            row=4, column=0, sticky="w"
        )
        self.transcript = ScrolledText(container, wrap="word", height=12)
        self.transcript.grid(row=5, column=0, sticky="nsew", pady=(4, 10))

        actions = ttk.Frame(container)
        actions.grid(row=6, column=0, sticky="ew")
        self.suggest_button = ttk.Button(
            actions,
            text="Suggest a response",
            command=lambda: self._run_ai_action("suggest"),
        )
        self.suggest_button.pack(side="left")
        self.summary_button = ttk.Button(
            actions,
            text="Summarize meeting",
            command=lambda: self._run_ai_action("summarize"),
        )
        self.summary_button.pack(side="left", padx=(8, 0))
        ttk.Button(
            actions, text="Save transcript", command=self.save_transcript
        ).pack(side="right")

        ttk.Label(container, text="AI output").grid(
            row=7, column=0, sticky="w", pady=(10, 0)
        )
        self.output = ScrolledText(container, wrap="word", height=7, state="disabled")
        self.output.grid(row=8, column=0, sticky="nsew", pady=(4, 0))
        container.rowconfigure(8, weight=2)

    def start_listening(self) -> None:
        if not self._consent.get():
            messagebox.showwarning(
                "Consent required",
                "Confirm that participants have been informed and have given permission.",
            )
            return

        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            messagebox.showerror(
                "API key not configured",
                "Set OPENAI_API_KEY in your environment, then restart the app.",
            )
            return

        base_url = os.environ.get("OPENAI_BASE_URL", "").strip()
        try:
            if base_url:
                self._client = OpenAI(
                    api_key=api_key,
                    base_url=base_url,
                    timeout=45.0,
                    max_retries=1,
                )
            else:
                self._client = OpenAI(
                    api_key=api_key, timeout=45.0, max_retries=1
                )
        except OpenAIError as exc:
            messagebox.showerror("API configuration error", str(exc))
            return
        self._transcription_model = os.environ.get(
            "OPENAI_TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe"
        ).strip()
        self._chat_model = os.environ.get("OPENAI_CHAT_MODEL", "gpt-4o-mini").strip()
        if not self._transcription_model or not self._chat_model:
            messagebox.showerror("Model not configured", "Model names cannot be empty.")
            return

        self._stop_event = threading.Event()
        self._audio_queue = queue.Queue()
        self._capture_error = None
        self._transcription_error = None
        self._session_active = True
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self._set_status("Listening - microphone active")

        threading.Thread(target=self._capture_audio, daemon=True).start()
        threading.Thread(target=self._transcribe_audio, daemon=True).start()

    def stop_listening(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()
        self.stop_button.configure(state="disabled")
        self._set_status("Stopping microphone and finishing queued audio...")

    def _on_close(self) -> None:
        if self._session_active or self._ai_active:
            self._close_requested = True
            if (
                self._session_active
                and self._stop_event is not None
                and not self._stop_event.is_set()
            ):
                self.stop_listening()
            return
        self.root.destroy()

    def _capture_audio(self) -> None:
        try:
            import sounddevice as sd
        except ImportError:
            self._capture_error = (
                "Microphone support is missing. Install dependencies from requirements.txt."
            )
            self._audio_queue.put(None)
            return

        assert self._stop_event is not None
        assert self._audio_queue is not None
        frames_per_chunk = SAMPLE_RATE * CHUNK_SECONDS
        chunk: list[bytes] = []
        chunk_frames = 0

        try:
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                blocksize=FRAMES_PER_READ,
            ) as stream:
                while not self._stop_event.is_set():
                    samples, overflowed = stream.read(FRAMES_PER_READ)
                    if overflowed:
                        self.root.after(
                            0, self._set_status, "Listening - microphone buffer overflow"
                        )
                    chunk.append(samples.tobytes())
                    chunk_frames += len(samples)
                    if chunk_frames >= frames_per_chunk:
                        self._audio_queue.put(encode_wav(b"".join(chunk)))
                        chunk.clear()
                        chunk_frames = 0

            if chunk:
                self._audio_queue.put(encode_wav(b"".join(chunk)))
        except sd.PortAudioError as exc:
            self._capture_error = f"Microphone error: {exc}"
        finally:
            self._audio_queue.put(None)

    def _transcribe_audio(self) -> None:
        assert self._audio_queue is not None
        assert self._client is not None
        while True:
            audio = self._audio_queue.get()
            if audio is None:
                break
            wav_file = io.BytesIO(audio)
            wav_file.name = "meeting-segment.wav"
            try:
                result = self._client.audio.transcriptions.create(
                    model=self._transcription_model,
                    file=wav_file,
                )
            except OpenAIError as exc:
                self._transcription_error = f"Transcription API error: {exc}"
                self.root.after(
                    0, self._set_status, f"Transcription API error: {exc}"
                )
                continue

            text = result.text.strip()
            if text:
                self.root.after(0, self._append_transcript, text)

        self.root.after(0, self._finish_capture)

    def _finish_capture(self) -> None:
        self._session_active = False
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        if self._capture_error:
            self._set_status(self._capture_error)
        elif self._transcription_error:
            self._set_status(self._transcription_error)
        else:
            self._set_status("Stopped")
        if self._close_requested and not self._ai_active:
            self.root.destroy()

    def _append_transcript(self, text: str) -> None:
        self.transcript.insert("end", text + "\n")
        self.transcript.see("end")

    def _run_ai_action(self, action: str) -> None:
        if self._client is None:
            messagebox.showinfo(
                "Start a session first",
                "Configure the API key and start a session before requesting AI output.",
            )
            return
        transcript = self.transcript.get("1.0", "end").strip()
        if not transcript:
            messagebox.showinfo("No transcript yet", "Wait for speech to be transcribed.")
            return

        self.suggest_button.configure(state="disabled")
        self.summary_button.configure(state="disabled")
        self._ai_active = True
        self._set_status("Generating AI output...")
        threading.Thread(
            target=self._generate_output,
            args=(action, transcript),
            daemon=True,
        ).start()

    def _generate_output(self, action: str, transcript: str) -> None:
        assert self._client is not None
        if action == "suggest":
            system_prompt = (
                "You are a meeting companion. Suggest a concise, truthful response "
                "based only on the transcript. Clearly label assumptions and do not "
                "invent facts. Keep the suggestion easy to review before the user speaks."
            )
            user_prompt = f"Suggest a helpful response to the latest discussion:\n\n{transcript}"
        else:
            system_prompt = (
                "Summarize the provided meeting transcript. Separate key points, "
                "decisions, open questions, and action items. Do not invent details."
            )
            user_prompt = f"Summarize this meeting:\n\n{transcript}"

        try:
            response = self._client.chat.completions.create(
                model=self._chat_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except OpenAIError as exc:
            self.root.after(0, self._show_ai_error, str(exc))
            return

        if not response.choices:
            self.root.after(0, self._show_ai_error, "The AI returned no choices.")
            return
        content = response.choices[0].message.content
        if not isinstance(content, str) or not content:
            self.root.after(0, self._show_ai_error, "The AI returned an empty response.")
            return
        self.root.after(0, self._show_ai_output, content.strip())

    def _show_ai_output(self, text: str) -> None:
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("1.0", text)
        self.output.configure(state="disabled")
        self.suggest_button.configure(state="normal")
        self.summary_button.configure(state="normal")
        self._ai_active = False
        self._set_status("Ready")
        if self._close_requested and not self._session_active:
            self.root.destroy()

    def _show_ai_error(self, error: str) -> None:
        self.suggest_button.configure(state="normal")
        self.summary_button.configure(state="normal")
        self._ai_active = False
        self._set_status("AI request failed")
        messagebox.showerror("AI request failed", error)
        if self._close_requested and not self._session_active:
            self.root.destroy()

    def save_transcript(self) -> None:
        transcript = self.transcript.get("1.0", "end").strip()
        if not transcript:
            messagebox.showinfo("Nothing to save", "The transcript is empty.")
            return
        destination = filedialog.asksaveasfilename(
            title="Save transcript",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not destination:
            return
        try:
            Path(destination).write_text(transcript + "\n", encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("Could not save transcript", str(exc))
            return
        self._set_status(f"Transcript saved to {destination}")

    def _set_status(self, text: str) -> None:
        self._status_text.set(text)


def main() -> None:
    root = Tk()
    MeetingCompanion(root)
    root.mainloop()


if __name__ == "__main__":
    main()