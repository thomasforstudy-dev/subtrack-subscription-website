"""Read the text that is already inside an uploaded file (no OCR here).

- PDF: the text layer of each page (pypdf). A page with almost no text is
  probably a scan: it is marked "needs_ocr" instead of being guessed.
- Word (.docx): paragraphs and table rows from word/document.xml, as one
  "page". Same size limits as the upload check; nothing it links to is fetched.
- Photos: no text layer at all, so every photo needs OCR.

Long card numbers are masked except the last 4 digits ("•••• •••• •••• 1234"),
keeping the same length, so positions in the text (evidence) still line up.

It runs in a separate, time-limited process (read_text_bounded), like the
upload check in documents.py: a broken or hostile file can't hang the worker.
This file only imports the standard library and pypdf, because the child
process runs it with "python -I" (no app package, no .env).
"""

import io
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree

MAX_PAGES = 5  # same as documents.MAX_PAGES
MAX_PAGE_CHARS = 20_000  # more than any real bill page; longer text is cut and marked
MIN_USABLE_CHARS = 20  # fewer letters/digits than this on a PDF page = probably a scan
DOCX_MAX_XML = 5 * 1024 * 1024  # word/document.xml bigger than 5 MB is not a bill
READ_SECONDS = 15
SCRIPT = Path(__file__).resolve()

WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
CARD_NUMBER = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")


class TextError(Exception):
    """The file's text couldn't be read. .code is short and safe to store."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def mask_card_numbers(text: str) -> str:
    """"4111 1111 1111 1234" -> "•••• •••• •••• 1234" (same length)."""
    def mask(match):
        digits_seen = 0
        total = sum(ch.isdigit() for ch in match.group())
        out = []
        for ch in match.group():
            if ch.isdigit():
                digits_seen += 1
                out.append(ch if digits_seen > total - 4 else "•")
            else:
                out.append(ch)
        return "".join(out)
    return CARD_NUMBER.sub(mask, text)


def page(number: int, text: str, needs_ocr: bool = False) -> dict:
    text = mask_card_numbers(text.replace("\r\n", "\n").replace("\r", "\n"))
    return {"page": number, "text": text[:MAX_PAGE_CHARS], "truncated": len(text) > MAX_PAGE_CHARS,
            "needs_ocr": needs_ocr}


def usable(text: str) -> bool:
    return sum(ch.isalnum() for ch in text) >= MIN_USABLE_CHARS


def pdf_pages(data: bytes) -> list[dict]:
    from pypdf import PdfReader  # imported here: photos and Word files don't need it
    from pypdf.errors import PyPdfError

    # What a broken PDF makes pypdf raise (as in documents.py). A real bug still shows.
    broken = (PyPdfError, ValueError, KeyError, TypeError, IndexError, AttributeError, RecursionError, OSError)
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted or not 1 <= len(reader.pages) <= MAX_PAGES:
            raise TextError("bad-document")
        pages = []
        for number, pdf_page in enumerate(reader.pages, start=1):
            text = pdf_page.extract_text() or ""
            pages.append(page(number, text if usable(text) else "", needs_ocr=not usable(text)))
        return pages
    except broken:
        raise TextError("bad-document") from None


def docx_pages(data: bytes) -> list[dict]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
        info = archive.getinfo("word/document.xml")
    except (zipfile.BadZipFile, KeyError, ValueError):
        raise TextError("bad-document") from None
    if info.file_size > DOCX_MAX_XML:
        raise TextError("too-big")
    try:
        # ElementTree never fetches outside files or URLs, and Python's XML parser
        # refuses "billion laughs" entity expansion.
        root = ElementTree.fromstring(archive.read(info))
    except (ElementTree.ParseError, zipfile.BadZipFile, ValueError):
        raise TextError("bad-document") from None
    body = root.find(f"{WORD}body")
    lines = []
    for block in (body if body is not None else []):
        if block.tag == f"{WORD}p":
            lines.append(paragraph_text(block))
        elif block.tag == f"{WORD}tbl":
            for row in block.iter(f"{WORD}tr"):
                cells = [" ".join(paragraph_text(p) for p in cell.iter(f"{WORD}p")) for cell in row.iter(f"{WORD}tc")]
                lines.append(" | ".join(cells))
    return [page(1, "\n".join(lines))]


def paragraph_text(paragraph) -> str:
    parts = []
    for node in paragraph.iter():
        if node.tag == f"{WORD}t" and node.text:
            parts.append(node.text)
        elif node.tag == f"{WORD}tab":
            parts.append("\t")
        elif node.tag in (f"{WORD}br", f"{WORD}cr"):
            parts.append("\n")
    return "".join(parts)


def read_text(data: bytes, kind: str) -> list[dict]:
    if kind == "pdf":
        return pdf_pages(data)
    if kind == "docx":
        return docx_pages(data)
    if kind in ("png", "jpeg", "webp"):
        return [page(1, "", needs_ocr=True)]
    raise TextError("bad-document")


def read_text_bounded(data: bytes, kind: str) -> list[dict]:
    """read_text in a child process with a deadline. Raises TextError."""
    try:
        result = subprocess.run([sys.executable, "-I", str(SCRIPT), kind], input=data,
                                capture_output=True, timeout=READ_SECONDS)
    except subprocess.TimeoutExpired:
        raise TextError("timeout") from None
    if result.returncode:
        raise TextError("reader-crashed")
    try:
        answer = json.loads(result.stdout)
    except ValueError:
        raise TextError("reader-crashed") from None
    if "error" in answer:
        raise TextError(answer["error"])
    return answer["pages"]


if __name__ == "__main__":
    # Run as "python -I doc_text.py <kind>" with the file on stdin.
    try:
        output = {"pages": read_text(sys.stdin.buffer.read(), sys.argv[1])}
    except TextError as error:
        output = {"error": error.code}
    # ASCII-only JSON (\u escapes): Windows may not print Vietnamese to a pipe.
    sys.stdout.write(json.dumps(output))
