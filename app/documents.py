"""Checking and storing uploaded bill files (photos, PDFs, Word .docx).

Never trust the file name or what the browser says the type is: anyone can
rename virus.exe to bill.pdf. The type comes from the file's first bytes
("magic numbers"), and then the file is really opened:
- photos are fully decoded by Pillow, after checking their size in pixels
  (a tiny file can claim to be 100000 x 100000 pixels and eat all memory)
- PDFs are read by pypdf, which counts pages even when they are packed
  away (compressed); a PDF whose pages can't be counted is refused
- at most MAX_BYTES, and at most MAX_PAGES pages
- a .docx is a zip file: check it isn't a "zip bomb" (a tiny file that
  unpacks to gigabytes) and really is a Word document. It is never unpacked
  to disk, and nothing it links to is ever fetched.
- old .doc files and password-protected files are refused with a clear message
- the file is saved in instance/uploads/ (not static/, so nobody can open it
  by guessing an address) under a random name the server makes up
"""

import hashlib
import io
import json
import subprocess
import sys
import re
import secrets
import warnings
import zipfile
from pathlib import Path

from flask import current_app
from PIL import Image
from pypdf import PdfReader
from pypdf.errors import PyPdfError

MAX_BYTES = 10 * 1024 * 1024  # 10 MB, the same limit the page shows
MAX_PAGES = 5
MAX_SIDE = 12_000  # pixels, the longest side of a photo
MAX_PIXELS = 30_000_000  # about a 30-megapixel photo: enough for any phone
MAX_NAME = 255
PARSE_SECONDS = 8
PARSER_SCRIPT = Path(__file__).resolve()
# A .docx: at most this many files inside, and this much once unpacked.
ZIP_MAX_FILES = 1000
ZIP_MAX_UNPACKED = 50 * 1024 * 1024
ZIP_MAX_RATIO = 100  # a part that unpacks to 100x its size is suspicious

EXTENSIONS = {"png": "png", "jpeg": "jpg", "webp": "webp", "pdf": "pdf", "docx": "docx"}
MIME_TYPES = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
IMAGES = ("png", "jpeg", "webp")
STORED_NAME = re.compile(r"[0-9a-f]{32}\.(png|jpg|webp|pdf|docx)")


class UploadError(Exception):
    """The file can't be accepted. The message is friendly and safe to show."""


def detect_kind(data: bytes) -> str:
    """Work out the real file type from its first bytes."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data.startswith(b"%PDF-"):
        return "pdf"
    if data.startswith(b"PK\x03\x04"):
        return "docx"  # a zip file: check_docx makes sure it's really Word
    if data.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        raise UploadError("Old .doc files aren't supported yet. Please save it as .docx or PDF and try again.")
    raise UploadError("Please upload a PNG, JPG or WEBP photo, a PDF, or a Word (.docx) file.")


PILLOW_FORMATS = {"png": "PNG", "jpeg": "JPEG", "webp": "WEBP"}
# What a broken file makes the parsers raise. Anything else is a real bug and is not hidden.
PDF_PROBLEMS = (PyPdfError, ValueError, KeyError, TypeError, IndexError, AttributeError, RecursionError, OSError)
IMAGE_PROBLEMS = (OSError, ValueError, SyntaxError, Image.DecompressionBombError)


def check_image(data: bytes, kind: str) -> None:
    """Open the photo, check its size in pixels FIRST, then decode all of it."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                # Image.open only reads the header, so this check is cheap.
                if image.format != PILLOW_FORMATS[kind]:
                    raise UploadError("This photo looks damaged. Please take or save it again.")
                width, height = image.size
                if max(width, height) > MAX_SIDE or width * height > MAX_PIXELS:
                    raise UploadError("This photo is too large in pixels. Please upload a smaller copy.")
                if getattr(image, "n_frames", 1) > 1:
                    raise UploadError("Animated pictures aren't supported. Please upload a normal photo.")
                image.load()  # decode every pixel: a cut-off or broken file fails here
    except IMAGE_PROBLEMS:
        raise UploadError("This photo looks damaged. Please take or save it again.") from None


def check_pdf(data: bytes) -> int:
    """Read the PDF properly and count its pages. Returns the page count."""
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise UploadError("This PDF is password-protected. Please upload a copy without a password.")
        pages = len(reader.pages)  # walks the real page tree, compressed or not
    except PDF_PROBLEMS:
        raise UploadError("This PDF looks damaged. Please save or export it again and retry.") from None
    if pages < 1:
        raise UploadError("This PDF has no pages.")
    if pages > MAX_PAGES:
        raise UploadError(f"This PDF has {pages} pages. Please upload at most {MAX_PAGES} pages.")
    return pages


def check_docx(data: bytes) -> None:
    """Look inside the zip without unpacking it."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
        parts = archive.infolist()
    except (zipfile.BadZipFile, ValueError):
        raise UploadError("This Word file looks damaged. Please save it again and retry.") from None
    if len(parts) > ZIP_MAX_FILES:
        raise UploadError("This Word file is too complicated to read.")
    unpacked = 0
    for part in parts:
        unpacked += part.file_size
        if part.flag_bits & 0x1:  # bit 0 = encrypted
            raise UploadError("This Word file is password-protected. Please upload a copy without a password.")
        if part.compress_size and part.file_size / part.compress_size > ZIP_MAX_RATIO:
            raise UploadError("This Word file is too big once opened.")
    if unpacked > ZIP_MAX_UNPACKED:
        raise UploadError("This Word file is too big once opened.")
    names = archive.namelist()
    if "word/document.xml" not in names or "[Content_Types].xml" not in names:
        raise UploadError("Please upload a PNG, JPG or WEBP photo, a PDF, or a Word (.docx) file.")


def clean_name(name: str | None) -> str:
    """The name to SHOW. Folder parts and odd characters are removed; it is
    never used to find the file on disk."""
    name = (name or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(ch for ch in name if ch.isprintable()).strip()
    return name[-MAX_NAME:] or "bill"


def read_upload(stream) -> bytes:
    """Read at most one byte more than allowed, so a huge file isn't kept in memory."""
    data = stream.read(MAX_BYTES + 1)
    if not data:
        raise UploadError("That file is empty.")
    if len(data) > MAX_BYTES:
        raise UploadError("That file is bigger than 10 MB. Please upload a smaller one.")
    return data


def inspect(data: bytes) -> dict:
    """Check the file. Returns its kind, page count and fingerprint, or raises UploadError."""
    kind = detect_kind(data)
    pages = None  # a Word file has no fixed pages
    if kind in IMAGES:
        check_image(data, kind)
        pages = 1
    elif kind == "pdf":
        pages = check_pdf(data)
    else:
        check_docx(data)
    return {"kind": kind, "page_count": pages, "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}


def inspect_bounded(data: bytes) -> dict:
    """Keep malformed document parsing out of the web worker, with a hard timeout.

    The child receives bytes on stdin, never a private filename or credential.
    subprocess.run kills and waits for its child if the deadline expires.
    """
    try:
        result = subprocess.run([sys.executable, "-I", str(PARSER_SCRIPT)], input=data,
                                capture_output=True, timeout=PARSE_SECONDS)
    except subprocess.TimeoutExpired:
        raise UploadError("This file took too long to check. Please upload a simpler copy.") from None
    if result.returncode:
        raise RuntimeError("Document parser failed unexpectedly; no file was saved.")
    response = json.loads(result.stdout)
    if "error" in response:
        raise UploadError(response["error"])
    return response["document"]


def upload_folder() -> Path:
    folder = Path(current_app.instance_path) / "uploads"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def save_file(data: bytes, kind: str) -> str:
    """Write the file under a new random name. Returns that name."""
    name = f"{secrets.token_hex(16)}.{EXTENSIONS[kind]}"
    (upload_folder() / name).write_bytes(data)
    return name


def file_path(stored_name: str) -> Path:
    """Where a stored file is. The name is checked again, so even a bad value
    in the database can't point outside the uploads folder."""
    if not STORED_NAME.fullmatch(stored_name or ""):
        raise UploadError("File not found.")
    return upload_folder() / stored_name


if __name__ == "__main__":
    # Executed as a standalone file: no app factory, .env, DB, or provider load.
    try:
        document = inspect(read_upload(sys.stdin.buffer))
        output = {"document": document}
    except UploadError as error:
        output = {"error": str(error)}
    sys.stdout.write(json.dumps(output))
