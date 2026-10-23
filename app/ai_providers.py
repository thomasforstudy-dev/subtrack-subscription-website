"""The AI models behind Subby, the spending forecast and Read aloud,
swappable without changing any page.

SUBBY_PROVIDER in .env picks the chat model:
  gemini  -> Google Gemini in the cloud (Google AI Studio key; the default)
  phi     -> Phi-3.5-mini on our own laptop, through a small private chat
             server (llama.cpp / Ollama / LM Studio speak the same
             "OpenAI-style" chat API). Kept as an option.
  fake    -> canned answers, for tests and demos only (labelled as fake)

Read aloud's voice always comes from Gemini (speak() below).

If Phi is chosen but switched off, Subby says it's offline. It does NOT
quietly send the question to the cloud instead. Only if the owner sets
SUBBY_FALLBACK=gemini does it use Gemini, and then the reply says so
("provider": "gemini", "fallback": true) so the page can tell the visitor.

Nothing here downloads or starts a model.
"""

import base64
import io
import os
import re
import wave
from dataclasses import dataclass

import requests

TIMEOUT = 20  # seconds


class ProviderUnavailable(Exception):
    """The model isn't set up, is switched off, or is too busy right now."""


@dataclass
class Turn:
    role: str  # "user" or "assistant"
    text: str


class ChatProvider:
    """Answer a question, given the rules (system prompt) and earlier turns."""

    name = "base"
    is_cloud = False  # True = the text leaves this PC / laptop

    def chat(self, system: str, history: list[Turn], question: str, temperature: float) -> str:
        raise NotImplementedError


class ExtractionProvider:
    """Turn OCR text into the fields of a bill (used later by the bills feature).

    Must return only what the text supports: unknown fields are None, never guessed.
    """

    name = "base"
    is_cloud = False

    def extract(self, text: str, fields: list[str]) -> dict:
        raise NotImplementedError


# ---------- Gemini (cloud, temporary) ----------------------------------------

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite"


class GeminiProvider(ChatProvider):
    name = "gemini"
    is_cloud = True

    def __init__(self):
        self.key = os.getenv("GEMINI_API_KEY", "").strip()
        # GEMINI_MODEL can list backups: "gemini-3.1-flash-lite,gemini-flash-lite-latest".
        names = [m.strip() for m in os.getenv("GEMINI_MODEL", "").split(",") if m.strip()]
        self.models = names or [DEFAULT_GEMINI_MODEL]

    def chat(self, system, history, question, temperature):
        if not self.key:
            raise ProviderUnavailable("not-set-up")
        contents = [
            {"role": "model" if t.role == "assistant" else "user", "parts": [{"text": t.text}]}
            for t in history
        ]
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": contents + [{"role": "user", "parts": [{"text": question}]}],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": 1024},
        }
        for model in self.models:
            try:
                res = requests.post(
                    GEMINI_URL.format(model=model),
                    headers={"x-goog-api-key": self.key},  # in a header, never in the URL
                    json=payload,
                    timeout=TIMEOUT,
                )
            except requests.RequestException as exc:
                raise ProviderUnavailable("unreachable") from exc
            # 429 = quota used up, 5xx = Google is busy: try the next model.
            if res.status_code == 429 or res.status_code >= 500:
                continue
            if not res.ok:
                raise ProviderUnavailable(f"http-{res.status_code}")
            return gemini_text(read_json(res))
        raise ProviderUnavailable("busy")


def read_json(res) -> object:
    try:
        return res.json()
    except ValueError as exc:  # not JSON at all
        raise ProviderUnavailable("bad-reply") from exc


def gemini_text(data: object) -> str:
    """Pull the answer out of Gemini's reply, checking every level's type.

    {"candidates": [{"content": {"parts": [{"text": "..."}]}}]}
    Anything else (blocked answer, nulls, wrong types) -> "bad-reply".
    """
    candidates = data.get("candidates") if isinstance(data, dict) else None
    first = candidates[0] if isinstance(candidates, list) and candidates else None
    content = first.get("content") if isinstance(first, dict) else None
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list):
        raise ProviderUnavailable("bad-reply")
    texts = [part.get("text") for part in parts if isinstance(part, dict)]
    if not texts or not all(isinstance(text, str) for text in texts):
        raise ProviderUnavailable("bad-reply")
    return "".join(texts).strip()


def phi_text(data: object) -> str:
    """{"choices": [{"message": {"content": "..."}}]} -> the text, else "bad-reply"."""
    choices = data.get("choices") if isinstance(data, dict) else None
    first = choices[0] if isinstance(choices, list) and choices else None
    message = first.get("message") if isinstance(first, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str):
        raise ProviderUnavailable("bad-reply")
    return content.strip()


# ---------- Phi-3.5-mini (our own laptop, planned) ----------------------------

class PhiProvider(ChatProvider):
    """Talks to an OpenAI-style chat server running Phi-3.5-mini.

    PHI_BASE_URL is the server on a *private* connection (for example a
    Tailscale address), never a public one. PHI_API_KEY is a shared secret
    the server checks. Nothing about the laptop's address is hard-coded.
    """

    name = "phi"
    is_cloud = False

    def __init__(self):
        self.base_url = os.getenv("PHI_BASE_URL", "").strip().rstrip("/")
        self.key = os.getenv("PHI_API_KEY", "").strip()
        self.model = os.getenv("PHI_MODEL", "").strip() or "phi-3.5-mini-instruct"

    def chat(self, system, history, question, temperature):
        if not self.base_url:
            raise ProviderUnavailable("not-set-up")
        messages = [{"role": "system", "content": system}]
        messages += [{"role": t.role, "content": t.text} for t in history]
        messages.append({"role": "user", "content": question})
        headers = {"Authorization": f"Bearer {self.key}"} if self.key else {}
        try:
            res = requests.post(
                f"{self.base_url}/v1/chat/completions",
                json={"model": self.model, "messages": messages,
                      "temperature": temperature, "max_tokens": 512},
                headers=headers,
                timeout=TIMEOUT,
            )
        except requests.RequestException as exc:
            raise ProviderUnavailable("offline") from exc  # laptop off or asleep
        if not res.ok:
            raise ProviderUnavailable(f"http-{res.status_code}")
        return phi_text(read_json(res))


# ---------- Fake (tests and demos only) --------------------------------------

class FakeProvider(ChatProvider, ExtractionProvider):
    """Canned answers. Clearly labelled: it never pretends to be a real model."""

    name = "fake"
    is_cloud = False

    def __init__(self, answer: str = "[fake model] This is a test answer."):
        self.answer = answer
        self.calls: list[dict] = []

    def chat(self, system, history, question, temperature):
        self.calls.append({"system": system, "history": history, "question": question})
        return self.answer

    def extract(self, text, fields):
        return {field: None for field in fields}  # knows nothing, so guesses nothing


PROVIDERS = {"gemini": GeminiProvider, "phi": PhiProvider, "fake": FakeProvider}


# ---------- Gemini voice (Read aloud) -----------------------------------------

# GEMINI_TTS_MODEL can list backups, like GEMINI_MODEL.
DEFAULT_TTS_MODELS = "gemini-3.8-flash-lite-tts,gemini-2.5-flash-preview-tts"
VOICES = ("Kore", "Puck", "Charon", "Aoede")  # Gemini's built-in voices we offer
TTS_TIMEOUT = 60  # seconds: making audio takes longer than a text answer


def speak(text: str, voice: str = "Kore") -> bytes:
    """Turn text into a .wav file with Gemini. Raises ProviderUnavailable."""
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise ProviderUnavailable("not-set-up")
    models = [m.strip() for m in (os.getenv("GEMINI_TTS_MODEL", "") or DEFAULT_TTS_MODELS).split(",") if m.strip()]
    payload = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
    }
    for model in models:
        try:
            res = requests.post(GEMINI_URL.format(model=model), headers={"x-goog-api-key": key},
                                json=payload, timeout=TTS_TIMEOUT)
        except requests.RequestException as exc:
            raise ProviderUnavailable("unreachable") from exc
        if res.status_code == 429 or res.status_code >= 500:
            continue  # quota used up or Google busy: try the next model
        if not res.ok:
            raise ProviderUnavailable(f"http-{res.status_code}")
        return gemini_audio(read_json(res))
    raise ProviderUnavailable("busy")


def gemini_audio(data: object) -> bytes:
    """Pull the audio out of Gemini's reply and return it as a .wav file.

    Newer voice models send a ready .wav; older ones send raw 16-bit samples
    ("audio/L16;codec=pcm;rate=24000"), which only need a .wav header.
    """
    candidates = data.get("candidates") if isinstance(data, dict) else None
    first = candidates[0] if isinstance(candidates, list) and candidates else None
    content = first.get("content") if isinstance(first, dict) else None
    parts = content.get("parts") if isinstance(content, dict) else None
    part = parts[0] if isinstance(parts, list) and parts else None
    inline = part.get("inlineData") if isinstance(part, dict) else None
    if not isinstance(inline, dict) or not isinstance(inline.get("data"), str):
        raise ProviderUnavailable("bad-reply")
    try:
        audio = base64.b64decode(inline["data"], validate=True)
    except ValueError as exc:
        raise ProviderUnavailable("bad-reply") from exc
    mime = str(inline.get("mimeType", "")).lower()
    if mime.startswith(("audio/wav", "audio/x-wav")):
        return audio
    if mime.startswith("audio/l16"):
        rate = re.search(r"rate=(\d+)", mime)
        return pcm_to_wav(audio, int(rate.group(1)) if rate else 24000)
    raise ProviderUnavailable("bad-reply")


AUDIO_TYPES = ("audio/webm", "audio/ogg", "audio/mp4", "audio/wav", "audio/mpeg")  # what browsers record


def transcribe(audio: bytes, mime: str) -> str:
    """Write down what is said in a short recording (Subby's mic in browsers
    without speech recognition, like Firefox). Raises ProviderUnavailable."""
    gemini = GeminiProvider()
    if not gemini.key:
        raise ProviderUnavailable("not-set-up")
    payload = {
        "contents": [{"role": "user", "parts": [
            {"inline_data": {"mime_type": mime, "data": base64.b64encode(audio).decode()}},
            {"text": "Write down exactly what is said, in the language spoken. "
                     "Reply with the words only. If nobody speaks, reply with nothing."},
        ]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 256},
    }
    for model in gemini.models:
        try:
            res = requests.post(GEMINI_URL.format(model=model), headers={"x-goog-api-key": gemini.key},
                                json=payload, timeout=TIMEOUT)
        except requests.RequestException as exc:
            raise ProviderUnavailable("unreachable") from exc
        if res.status_code == 429 or res.status_code >= 500:
            continue
        if not res.ok:
            raise ProviderUnavailable(f"http-{res.status_code}")
        return gemini_text(read_json(res))
    raise ProviderUnavailable("busy")


def pcm_to_wav(samples: bytes, rate: int) -> bytes:
    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)  # 16-bit
        wav.setframerate(rate)
        wav.writeframes(samples)
    return out.getvalue()


def chat_provider(name: str | None = None) -> ChatProvider:
    chosen = (name or os.getenv("SUBBY_PROVIDER", "") or "gemini").strip().lower()
    if chosen not in PROVIDERS:
        raise ProviderUnavailable(f"unknown provider {chosen!r}")
    return PROVIDERS[chosen]()


def fallback_provider() -> ChatProvider | None:
    """Only when the owner asked for it: SUBBY_FALLBACK=gemini (or another name)."""
    name = os.getenv("SUBBY_FALLBACK", "").strip().lower()
    return chat_provider(name) if name and name != "none" else None
