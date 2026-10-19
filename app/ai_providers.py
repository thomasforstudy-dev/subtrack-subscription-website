"""The AI models behind Subby, swappable without changing any page.

SUBBY_PROVIDER in .env picks the model:
  gemini  -> Google Gemini in the cloud (today's temporary choice, the default)
  phi     -> Phi-3.5-mini on our own laptop, through a small private chat
             server (llama.cpp / Ollama / LM Studio speak the same
             "OpenAI-style" chat API). The planned long-term choice.
  fake    -> canned answers, for tests and demos only (labelled as fake)

If Phi is chosen but switched off, Subby says it's offline. It does NOT
quietly send the question to the cloud instead. Only if the owner sets
SUBBY_FALLBACK=gemini does it use Gemini, and then the reply says so
("provider": "gemini", "fallback": true) so the page can tell the visitor.

Nothing here downloads or starts a model.
"""

import os
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
            try:
                parts = res.json()["candidates"][0]["content"]["parts"]
            except (KeyError, IndexError, ValueError) as exc:
                raise ProviderUnavailable("bad-reply") from exc
            return "".join(part.get("text", "") for part in parts).strip()
        raise ProviderUnavailable("busy")


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
        try:
            return res.json()["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, ValueError, AttributeError) as exc:
            raise ProviderUnavailable("bad-reply") from exc


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


def chat_provider(name: str | None = None) -> ChatProvider:
    chosen = (name or os.getenv("SUBBY_PROVIDER", "") or "gemini").strip().lower()
    if chosen not in PROVIDERS:
        raise ProviderUnavailable(f"unknown provider {chosen!r}")
    return PROVIDERS[chosen]()


def fallback_provider() -> ChatProvider | None:
    """Only when the owner asked for it: SUBBY_FALLBACK=gemini (or another name)."""
    name = os.getenv("SUBBY_FALLBACK", "").strip().lower()
    return chat_provider(name) if name and name != "none" else None
