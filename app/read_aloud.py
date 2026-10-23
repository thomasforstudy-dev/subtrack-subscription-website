"""Read aloud: upload a Word file or a PDF (or paste text) and listen to it,
like "Read aloud" in Microsoft Edge.

- The file goes through the same safety checks as bill uploads
  (documents.inspect_bounded, then doc_text.read_text_bounded in a separate,
  time-limited process). It is read once and NOT saved.
- The page shows the text in paragraphs. static/read-aloud.js sends one
  paragraph at a time to /tools/read-aloud/speak, which asks Gemini for the audio
  (ai_providers.speak). If Gemini is busy or out of free quota, the page
  uses the browser's own voice instead.
"""

import logging

from flask import Blueprint, Response, flash, jsonify, render_template, request
from flask_login import current_user, login_required

from app.ai_providers import VOICES, ProviderUnavailable, speak as gemini_speak
from app.doc_text import TextError, read_text_bounded
from app.documents import UploadError, inspect_bounded, read_upload
from app.security import RateLimiter

bp = Blueprint("read_aloud", __name__, url_prefix="/tools/read-aloud")
log = logging.getLogger(__name__)

MAX_TEXT = 30_000  # characters shown and read: about 10 pages
MAX_CHUNK = 1_500  # characters per audio request (one paragraph, or part of one)
chunks = RateLimiter(150, 3600)  # audio requests per user per hour (free quota)


def split_paragraphs(text: str) -> list[str]:
    """Paragraphs, with very long ones cut at sentence ends so each audio
    request stays short (faster to start, and under the size limit)."""
    out = []
    for block in text.replace("\r", "").split("\n"):
        block = " ".join(block.split())
        while len(block) > MAX_CHUNK:
            cut = max(block.rfind(". ", 0, MAX_CHUNK), block.rfind("? ", 0, MAX_CHUNK), block.rfind("! ", 0, MAX_CHUNK))
            cut = cut + 1 if cut > 0 else block.rfind(" ", 0, MAX_CHUNK)
            cut = cut if cut > 0 else MAX_CHUNK
            out.append(block[:cut].strip())
            block = block[cut:].strip()
        if block:
            out.append(block)
    return out


def text_from_upload(file) -> str:
    data = read_upload(file.stream)
    kind = inspect_bounded(data)["kind"]
    if kind not in ("docx", "pdf"):
        raise UploadError("Please upload a Word (.docx) file or a PDF.")
    try:
        pages = read_text_bounded(data, kind)
    except TextError:
        raise UploadError("We couldn't read the text in that file.") from None
    text = "\n".join(p["text"] for p in pages)
    if not text.strip():
        raise UploadError("That file has no text we can read (a scanned PDF needs OCR).")
    return text


@bp.route("/", methods=["GET", "POST"])
@login_required
def show():
    paragraphs, title, cut = [], "", False
    if request.method == "POST":
        file = request.files.get("document")
        try:
            if file and file.filename:
                text, title = text_from_upload(file), file.filename.replace("\\", "/").rsplit("/", 1)[-1][:120]
            else:
                text = request.form.get("text", "")
            cut = len(text) > MAX_TEXT
            paragraphs = split_paragraphs(text[:MAX_TEXT])
            if not paragraphs:
                flash("Upload a file or paste some text first.")
        except UploadError as problem:
            flash(str(problem))
    return render_template("read_aloud.html", paragraphs=paragraphs, title=title, cut=cut, voices=VOICES)


@bp.post("/speak")
@login_required
def speak():
    # JSON only (with the CSRF header), like Subby: other sites can't use our quota.
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Send JSON."), 400
    text = " ".join(str(data.get("text", "")).split())[:MAX_CHUNK]
    voice = data.get("voice") if data.get("voice") in VOICES else VOICES[0]
    if not text:
        return jsonify(error="empty"), 400
    if not chunks.hit(f"user:{current_user.id}"):
        return jsonify(error="too-many"), 429
    try:
        audio = gemini_speak(text, voice)
    except ProviderUnavailable as problem:
        log.info("Read aloud voice unavailable: %s", problem)
        return jsonify(error="voice-unavailable"), 503  # the page switches to the browser voice
    return Response(audio, mimetype="audio/wav", headers={"Cache-Control": "no-store"})
