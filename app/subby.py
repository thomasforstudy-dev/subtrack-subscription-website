"""Subby's brain: the help bot's questions go to an AI model from here.

Which model (Gemini today, Phi-3.5-mini later) is chosen in app/ai_providers.py.
The browser never sees any key; it only talks to /subby/ask. If the model
isn't set up or is offline, the browser falls back to its small built-in
answer list (static/subby.js).
"""

from flask import Blueprint, jsonify, request

from app.ai_providers import ProviderUnavailable, Turn, chat_provider, fallback_provider
from app.security import RateLimiter, client_ip

bp = Blueprint("subby", __name__, url_prefix="/subby")

HANDOFF = "[HANDOFF]"  # the model writes this when a human should answer
MAX_QUESTION = 300  # characters
MAX_HISTORY = 6  # earlier messages sent along, so follow-up questions make sense
LIMIT_PER_HOUR = 30  # questions per visitor, to protect the free model quota

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


def clean_history(raw) -> list[Turn]:
    """Turn the browser's [{role, text}, ...] into a short, safe list of turns."""
    if not isinstance(raw, list):
        return []
    turns = []
    for item in raw[-MAX_HISTORY:]:
        if not isinstance(item, dict):
            continue
        role = "assistant" if item.get("role") == "bot" else "user"
        text = str(item.get("text", ""))[:600]
        if text:
            turns.append(Turn(role, text))
    return turns


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
    if not questions.hit(client_ip()):
        return jsonify(answer="Whoa, that's a lot of questions! Give me a little break and try again later.", handoff=False), 429

    fun = bool(data.get("fun", True))
    args = (system_prompt(fun), clean_history(data.get("history")), question, 0.8 if fun else 0.3)
    try:
        provider = chat_provider()
    except ProviderUnavailable:
        return jsonify(answer=None, reason="not-set-up"), 503
    used, fallback = provider, False
    try:
        text = provider.chat(*args)
    except ProviderUnavailable as problem:
        backup = fallback_provider()
        if backup is None or backup.name == provider.name:
            # No silent switch to another model: the page uses its built-in answers.
            if str(problem) == "not-set-up":
                return jsonify(answer=None, reason="not-set-up", provider=provider.name), 503
            reason = "model-offline" if provider.name == "phi" else "model-failed"
            return jsonify(answer=None, reason=reason, provider=provider.name), 502
        try:
            text = backup.chat(*args)
        except ProviderUnavailable:
            return jsonify(answer=None, reason="model-failed", provider=backup.name), 502
        used, fallback = backup, True  # the reply says so, so the page can tell the visitor

    handoff = HANDOFF in text
    answer = text.replace(HANDOFF, "").strip()
    if not answer:
        return jsonify(answer=None, reason="empty", provider=used.name), 502
    return jsonify(answer=answer, handoff=handoff, provider=used.name, fallback=fallback)
