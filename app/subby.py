"""Subby's brain: the help bot's questions go to Gemini from here.

The browser never sees the Gemini key; it only talks to /subby/ask.
If Gemini isn't set up or fails, the browser falls back to its small
built-in answer list (static/subby.js).
"""

import os

import requests
from flask import Blueprint, jsonify, request

from app.security import RateLimiter, client_ip

bp = Blueprint("subby", __name__, url_prefix="/subby")

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODEL = "gemini-3.1-flash-lite"
HANDOFF = "[HANDOFF]"  # Gemini writes this when a human should answer
MAX_QUESTION = 300  # characters
MAX_HISTORY = 6  # earlier messages sent along, so follow-up questions make sense
LIMIT_PER_HOUR = 30  # questions per visitor, to protect the free Gemini quota

FACTS = """
SubTrack is a website that tracks your subscriptions so you can renew or
cancel in time. Reminder emails before each renewal are being built and are
not being sent yet.
- Sign up with a username, email + password, or with Google or GitHub. Signing
  up is free. You can reset a forgotten password by email.
- Add a subscription: name, price, currency, cycle (weekly, monthly or yearly),
  next renewal date, how many days before to remind you, and notes.
  You can edit or archive it later.
- Each subscription already has its own "remind days before" number (for
  example 14, 7 or 3); reminder emails will use it once they are switched on.
- Credit card payments: add the card's payment due date like a subscription,
  so it gets the same early reminder once reminders are switched on.
- Pinned links: save any http/https link, the page title fills in by itself,
  add tags and notes, search them, and pin important ones to the top.
  Good for cancel pages, billing pages and support chats.
- SubTrack cannot cancel subscriptions for you, cannot see your bank, cannot
  give refunds, and never asks for card numbers or passwords.
- Coming soon: reminder emails, a dashboard, Google Calendar buttons, a Chrome
  extension, voice chat.
"""


def system_prompt(fun: bool) -> str:
    style = (
        "Personality: cheeky and witty like Grok. At most one short joke, then the "
        "real answer. Never rude, never mean about the user, no swearing."
        if fun
        else "Personality: friendly, calm and plain. No jokes."
    )
    return f"""You are Subby, the help bot on the SubTrack website.
{style}
Rules:
- Answer only from the facts below. Never invent features, prices or policies.
- Keep answers to 1-3 short sentences. Reply in the same language as the user.
- Never ask for passwords, card numbers or other private details.
- If the question needs a human (refunds, billing problems, a bug, account or
  data problems, business questions) or the facts don't cover it, reply with
  one short friendly sentence that ends with {HANDOFF}.
Facts:
{FACTS}"""


# Kept in memory: it resets when the server restarts, which is fine for a simple limit.
questions = RateLimiter(LIMIT_PER_HOUR, 3600)


def clean_history(raw) -> list[dict]:
    """Turn the browser's [{role, text}, ...] into Gemini's format, safely."""
    if not isinstance(raw, list):
        return []
    turns = []
    for item in raw[-MAX_HISTORY:]:
        if not isinstance(item, dict):
            continue
        role = "model" if item.get("role") == "bot" else "user"
        text = str(item.get("text", ""))[:600]
        if text:
            turns.append({"role": role, "parts": [{"text": text}]})
    return turns


def models() -> list[str]:
    """GEMINI_MODEL can list backups, e.g. "gemini-3.1-flash-lite,gemini-flash-lite-latest"."""
    names = [m.strip() for m in os.getenv("GEMINI_MODEL", "").split(",") if m.strip()]
    return names or [DEFAULT_MODEL]


def ask_gemini(key: str, question: str, history: list[dict], fun: bool) -> str:
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt(fun)}]},
        "contents": history + [{"role": "user", "parts": [{"text": question}]}],
        "generationConfig": {"temperature": 0.8 if fun else 0.3, "maxOutputTokens": 1024},
    }
    for model in models():
        res = requests.post(
            GEMINI_URL.format(model=model),
            headers={"x-goog-api-key": key},
            json=payload,
            timeout=20,
        )
        # 429 = quota used up, 5xx = Google is busy: try the next model.
        if res.status_code == 429 or res.status_code >= 500:
            continue
        res.raise_for_status()
        parts = res.json()["candidates"][0]["content"]["parts"]
        return "".join(part.get("text", "") for part in parts).strip()
    raise requests.ConnectionError("All Gemini models are busy right now.")


@bp.post("/ask")
def ask():
    # get_json only accepts real JSON requests, so other websites can't
    # quietly use up our quota with a hidden form.
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Send JSON."), 400
    question = str(data.get("question", "")).strip()[:MAX_QUESTION]
    if not question:
        return jsonify(error="Ask a question."), 400

    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        return jsonify(answer=None, reason="not-set-up"), 503
    if not questions.hit(client_ip()):
        return jsonify(answer="Whoa, that's a lot of questions! Give me a little break and try again later.", handoff=False), 429

    try:
        text = ask_gemini(key, question, clean_history(data.get("history")), bool(data.get("fun", True)))
    except (requests.RequestException, KeyError, IndexError, ValueError):
        return jsonify(answer=None, reason="gemini-failed"), 502

    handoff = HANDOFF in text
    answer = text.replace(HANDOFF, "").strip()
    if not answer:
        return jsonify(answer=None, reason="empty"), 502
    return jsonify(answer=answer, handoff=handoff)
