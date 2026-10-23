"""Read aloud: upload a PDF (up to 300 pages) or a Word file, or paste text,
and listen to it, like "Read aloud" in Microsoft Edge.

- A PDF is read by doc_text in a separate, time-limited process ("long-pdf":
  up to LONG_PDF_PAGES pages, 40 MB). A Word file goes through the same checks
  as bill uploads (10 MB). Files are read once and NOT saved.
- The text is cut into parts of about PART_CHARS characters at sentence ends,
  grouped by PDF page. static/read-aloud.js sends one part at a time to
  /tools/read-aloud/speak, which asks Gemini for the audio (ai_providers.speak).
  If Gemini is busy or out of free quota, the page uses the browser's own voice.
"""

import logging
import re

from flask import Blueprint, Response, flash, jsonify, render_template, request
from flask_login import current_user, login_required

from app.ai_providers import VOICES, ProviderUnavailable, speak as gemini_speak
from app.doc_text import LONG_READ_SECONDS, TextError, read_text_bounded
from app.documents import MAX_BYTES as WORD_MAX_BYTES, UploadError, inspect_bounded
from app.security import RateLimiter

bp = Blueprint("read_aloud", __name__, url_prefix="/tools/read-aloud")
log = logging.getLogger(__name__)

MAX_PDF_BYTES = 40 * 1024 * 1024  # a long report or a book; see bigger_upload_limit in __init__.py
MAX_TEXT = 600_000  # characters on one page of the site: about 200 dense PDF pages
PART_CHARS = 900  # one audio request: short enough to start quickly
MAX_CHUNK = 1_500  # the most /speak accepts in one request
chunks = RateLimiter(150, 3600)  # audio requests per user per hour (free quota)
SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


def split_paragraphs(text: str, size: int = PART_CHARS) -> list[str]:
    """Paragraphs (one per line), with long ones cut at sentence ends."""
    out = []
    for line in text.replace("\r", "").split("\n"):
        out += cut_at_sentences(" ".join(line.split()), size)
    return out


def cut_at_sentences(text: str, size: int) -> list[str]:
    """Join sentences into parts of at most `size` characters. A sentence longer
    than that is cut at a space."""
    parts, current = [], ""
    for sentence in SENTENCE_END.split(text):
        while len(sentence) > size:
            cut = sentence.rfind(" ", 0, size)
            cut = cut if cut > 0 else size
            parts, current = flush(parts, current), ""
            parts.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if current and len(current) + 1 + len(sentence) > size:
            parts, current = flush(parts, current), ""
        current = f"{current} {sentence}".strip()
    return flush(parts, current)


def flush(parts: list[str], current: str) -> list[str]:
    return parts + [current] if current else parts


def pdf_page_parts(text: str) -> list[str]:
    """A PDF page's text has a line break at the end of every printed line.
    Join the lines (and words split with a hyphen) so sentences flow, keep
    blank lines as paragraph breaks, then cut into parts."""
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text.replace("\r", ""))
    parts = []
    for paragraph in re.split(r"\n\s*\n", text):
        parts += cut_at_sentences(" ".join(paragraph.split()), PART_CHARS)
    return parts


def read_upload(file) -> tuple[bytes, str]:
    data = file.stream.read(MAX_PDF_BYTES + 1)
    if not data:
        raise UploadError("That file is empty.")
    if data.startswith(b"%PDF-"):
        if len(data) > MAX_PDF_BYTES:
            raise UploadError("That PDF is bigger than 40 MB.")
        return data, "pdf"
    if len(data) > WORD_MAX_BYTES:
        raise UploadError("Word files can be up to 10 MB. A PDF can be up to 40 MB.")
    if inspect_bounded(data)["kind"] != "docx":
        raise UploadError("Please upload a PDF or a Word (.docx) file.")
    return data, "docx"


def pages_from_upload(file) -> tuple[list[dict], str]:
    data, kind = read_upload(file)
    try:
        if kind == "pdf":
            return read_text_bounded(data, "long-pdf", LONG_READ_SECONDS), kind
        return read_text_bounded(data, "docx"), kind
    except TextError as error:
        if error.code == "timeout":
            raise UploadError("That PDF took too long to read. Try a smaller part of it.") from None
        raise UploadError("We couldn't read that file. A PDF must not be locked and can have up to 300 pages.") from None


def build_sections(pages: list[dict], is_pdf: bool) -> dict:
    """Pages -> [{"page": 3, "parts": [(index, text), ...]}], numbered across
    the whole document, stopping at MAX_TEXT characters."""
    sections, skipped, index, used, cut = [], [], 0, 0, False
    for page in pages:
        if page.get("needs_ocr"):
            skipped.append(page["page"])
            continue
        parts = pdf_page_parts(page["text"]) if is_pdf else split_paragraphs(page["text"])
        numbered = []
        for part in parts:
            if used + len(part) > MAX_TEXT:
                cut = True
                break
            numbered.append((index, part))
            index, used = index + 1, used + len(part)
        if numbered:
            sections.append({"page": page["page"] if is_pdf else None, "parts": numbered})
        if cut:
            break
    return {"sections": sections, "skipped": skipped, "cut": cut, "count": index}


@bp.route("/", methods=["GET", "POST"])
@login_required
def show():
    doc, title = None, ""
    if request.method == "POST":
        file = request.files.get("document")
        try:
            if file and file.filename:
                title = file.filename.replace("\\", "/").rsplit("/", 1)[-1][:120]
                pages, kind = pages_from_upload(file)
                doc = build_sections(pages, is_pdf=kind == "pdf")
            else:
                doc = build_sections([{"page": 1, "text": request.form.get("text", "")}], is_pdf=False)
            if not doc["count"]:
                flash("There is no text to read. A scanned PDF needs OCR, which isn't switched on yet."
                      if title else "Upload a file or paste some text first.")
                doc = None
        except UploadError as problem:
            flash(str(problem))
    return render_template("read_aloud.html", doc=doc, title=title, voices=VOICES)


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
