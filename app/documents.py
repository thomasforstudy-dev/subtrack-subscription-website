"""Checking and storing uploaded bill files (photos, PDFs, Word .docx).

Never trust the file name or what the browser says the type is: anyone can
rename virus.exe to bill.pdf. The type comes from the file's first bytes
("magic numbers"). Then:
- at most MAX_BYTES, and at most MAX_PAGES pages for a PDF
- a .docx is a zip file: check it isn't a "zip bomb" (a tiny file that
  unpacks to gigabytes) and really is a Word document. It is never unpacked
  to disk.
- old .doc files and password-protected PDFs are refused with a clear message
- the file is saved in instance/uploads/ (not static/, so nobody can open it
  by guessing an address) under a random name the server makes up
"""

import hashlib
import io
import re
import secrets
import zipfile
from pathlib import Path

from flask import current_app

MAX_BYTES = 10 * 1024 * 1024  # 10 MB, the same limit the page shows
MAX_PAGES = 5
MAX_NAME = 255
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


def pdf_page_count(data: bytes) -> int | None:
    """Count "/Type /Page" objects. Some PDFs pack these away (compressed), and
    then the count is unknown (None) rather than a wrong number."""
    count = len(re.findall(rb"/Type\s*/Page(?![a-zA-Z])", data))
    return count or None


def check_pdf(data: bytes) -> int | None:
    if b"/Encrypt" in data:
        raise UploadError("This PDF is password-protected. Please upload a copy without a password.")
    pages = pdf_page_count(data)
    if pages is not None and pages > MAX_PAGES:
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
    if "word/document.xml" not in archive.namelist():
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
    pages = 1 if kind in IMAGES else None
    if kind == "pdf":
        pages = check_pdf(data)
    elif kind == "docx":
        check_docx(data)
    return {"kind": kind, "page_count": pages, "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}


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
