"""Rules for usernames, emails and passwords. docs/CONTRACT.md lists the same rules for the UI."""

import re
import unicodedata

USERNAME_RE = re.compile(r"[a-z0-9_]{3,30}")
EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
MIN_PASSWORD = 12
MAX_PASSWORD = 128  # very long passwords only slow the server down


def normalize_username(raw: str) -> str:
    """Make look-alike spellings the same name.

    NFKC turns "ｔｏａｎ" (full-width letters) into "toan", and lower() makes
    "Toan" and "toan" one name. After this, only a-z, 0-9 and _ are allowed,
    so letters from other alphabets that look like Latin ones can't be used
    to pretend to be someone else.
    """
    return unicodedata.normalize("NFKC", raw or "").strip().lower()


def username_error(username: str) -> str | None:
    if not USERNAME_RE.fullmatch(username):
        return "Usernames are 3–30 characters: letters a–z, numbers and _ only."
    return None


def escape_like(value: str) -> str:
    """So searching for "50%" finds "50%" instead of treating % as a wildcard.
    SQL Server also treats [ as special in LIKE. Use with escape="\\"."""
    for ch in ("\\", "%", "_", "["):
        value = value.replace(ch, "\\" + ch)
    return value


def normalize_email(raw: str) -> str:
    return (raw or "").strip().lower()


def email_error(email: str) -> str | None:
    if len(email) > 255 or not EMAIL_RE.fullmatch(email):
        return "Please type a real email address, like name@example.com."
    return None


def password_error(password: str) -> str | None:
    """Return what's missing from a new password, or None if it's fine."""
    if not MIN_PASSWORD <= len(password) <= MAX_PASSWORD:
        return f"Your password needs {MIN_PASSWORD} to {MAX_PASSWORD} characters."
    missing = []
    if not any(ch.isupper() for ch in password):
        missing.append("an upper-case letter")
    if not any(ch.isdigit() for ch in password):
        missing.append("a number")
    if all(ch.isalnum() for ch in password):
        missing.append("a special character like ! or #")
    if missing:
        return "Your password also needs " + " and ".join(missing) + "."
    return None
