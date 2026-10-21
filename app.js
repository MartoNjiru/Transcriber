const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const elements = {
  accessCode: document.querySelector("#accessCode"),
  consent: document.querySelector("#consent"),
  start: document.querySelector("#startButton"),
  stop: document.querySelector("#stopButton"),
  status: document.querySelector("#status"),
  indicator: document.querySelector("#liveIndicator"),
  micBadge: document.querySelector("#micBadge"),
  transcript: document.querySelector("#transcript"),
  wordCount: document.querySelector("#wordCount"),
  suggest: document.querySelector("#suggestButton"),
  summarize: document.querySelector("#summaryButton"),
  output: document.querySelector("#output"),
  save: document.querySelector("#saveButton"),
  clear: document.querySelector("#clearButton"),
  support: document.querySelector("#speechSupport"),
};

let recognition = null;
let listening = false;
let requestPending = false;
let finalTranscript = "";
let manuallyStopped = false;
let speechError = false;

function setStatus(message) {
  elements.status.textContent = message;
}

function updateTranscriptState() {
  const text = elements.transcript.value.trim();
  const words = text ? text.split(/\s+/).length : 0;
  elements.wordCount.textContent = `${words} ${words === 1 ? "word" : "words"}`;
  elements.suggest.disabled = requestPending || words === 0;
  elements.summarize.disabled = requestPending || words === 0;
}

function setListeningState(active) {
  listening = active;
  elements.start.disabled = active || !SpeechRecognition;
  elements.stop.disabled = !active;
  elements.indicator.classList.toggle("active", active);
  elements.micBadge.classList.toggle("active", active);
  elements.micBadge.textContent = active ? "MIC ON" : "MIC OFF";
}

function startListening() {
  if (!SpeechRecognition) {
    setStatus("Speech recognition is not supported in this browser.");
    return;
  }
  if (!elements.consent.checked) {
    setStatus("Please confirm participant consent before turning on the mic.");
    elements.consent.focus();
    return;
  }
  if (!elements.accessCode.value.trim()) {
    setStatus("Enter the app access code before starting.");
    elements.accessCode.focus();
    return;
  }

  finalTranscript = elements.transcript.value.trim();
  manuallyStopped = false;
  speechError = false;
  recognition = new SpeechRecognition();
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.lang = navigator.language || "en-US";

  recognition.onstart = () => {
    setListeningState(true);
    setStatus("Listening — microphone active. Click Stop when finished.");
  };
  recognition.onresult = (event) => {
    let interim = "";
    for (let index = event.resultIndex; index < event.results.length; index += 1) {
      const phrase = event.results[index][0].transcript;
      if (event.results[index].isFinal) {
        finalTranscript = `${finalTranscript}${finalTranscript ? " " : ""}${phrase.trim()}`;
      } else {
        interim += phrase;
      }
    }
    elements.transcript.value = [finalTranscript, interim].filter(Boolean).join(" ");
    elements.transcript.scrollTop = elements.transcript.scrollHeight;
    updateTranscriptState();
  };
  recognition.onerror = (event) => {
    const messages = {
      "not-allowed": "Microphone permission was denied. Allow mic access in your browser to continue.",
      "service-not-allowed": "The browser speech service is unavailable or blocked.",
      "audio-capture": "No microphone was found. Check your device settings.",
      "network": "The browser speech service reported a network error.",
    };
    speechError = true;
    setStatus(messages[event.error] || `Speech recognition error: ${event.error}.`);
    manuallyStopped = true;
    setListeningState(false);
  };
  recognition.onend = () => {
    if (listening && !manuallyStopped) {
      try {
        recognition.start();
        return;
      } catch {
        setStatus("Listening paused. Press Start listening to resume.");
      }
    }
    setListeningState(false);
    if (manuallyStopped && !speechError) setStatus("Microphone stopped.");
  };

  try {
    recognition.start();
  } catch (error) {
    setListeningState(false);
    setStatus(`Could not start microphone: ${error.message}`);
  }
}

function stopListening() {
  manuallyStopped = true;
  if (recognition && listening) recognition.stop();
  setListeningState(false);
}

async function requestAssistant(action) {
  const transcript = elements.transcript.value.trim();
  const accessCode = elements.accessCode.value;
  if (!transcript) {
    setStatus("Add some transcript text first.");
    return;
  }
  if (!accessCode) {
    setStatus("Enter the app access code to request AI output.");
    elements.accessCode.focus();
    return;
  }

  requestPending = true;
  updateTranscriptState();
  setStatus(action === "suggest" ? "Drafting a response..." : "Preparing meeting notes...");
  elements.output.textContent = "Working on it…";
  try {
    const response = await fetch("/api/assistant", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, transcript, accessCode }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || `Request failed (${response.status}).`);
    elements.output.textContent = result.text;
    setStatus("Done. Review the AI output before using it.");
  } catch (error) {
    elements.output.textContent = "No AI output was generated.";
    setStatus(error.message || "The request failed. Check your connection and try again.");
  } finally {
    requestPending = false;
    updateTranscriptState();
  }
}

elements.start.addEventListener("click", startListening);
elements.stop.addEventListener("click", stopListening);
elements.consent.addEventListener("change", () => {
  if (!elements.consent.checked && listening) stopListening();
});
elements.transcript.addEventListener("input", () => {
  if (!listening) finalTranscript = elements.transcript.value.trim();
  updateTranscriptState();
});
elements.suggest.addEventListener("click", () => requestAssistant("suggest"));
elements.summarize.addEventListener("click", () => requestAssistant("summarize"));
elements.save.addEventListener("click", () => {
  const content = elements.transcript.value.trim();
  if (!content) {
    setStatus("There is no transcript to download yet.");
    return;
  }
  const file = new Blob([content, "\n"], { type: "text/plain;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(file);
  link.download = "meeting-transcript.txt";
  link.click();
  URL.revokeObjectURL(link.href);
  setStatus("Transcript downloaded.");
});
elements.clear.addEventListener("click", () => {
  if (listening) stopListening();
  elements.transcript.value = "";
  finalTranscript = "";
  elements.output.textContent = "Your suggestion or meeting notes will show up here.";
  elements.output.classList.add("empty");
  updateTranscriptState();
  setStatus("Transcript cleared.");
});
elements.transcript.addEventListener("input", () => elements.output.classList.remove("empty"));

if (SpeechRecognition) {
  elements.support.textContent = "Speech recognition available in this browser";
} else {
  elements.support.textContent = "For microphone transcription, use Chrome or Edge";
  elements.start.disabled = true;
}
updateTranscriptState();
