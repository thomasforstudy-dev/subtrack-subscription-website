"""Sending email. MAIL_BACKEND in .env picks how:

  resend  -> really send it, through Resend (needs RESEND_API_KEY)
  file    -> save it as a .txt file in instance/outbox/, to read on this PC
  memory  -> keep it in the `sent` list below (automated tests)
  none    -> email isn't set up; sending raises MailNotReady

If MAIL_BACKEND is empty: resend when RESEND_API_KEY is set, file when
APP_ENV=development, otherwise none. So a test setup never emails real people,
and the live site never pretends it sent something it didn't.
"""

import logging
import os
import secrets
import time
from dataclasses import dataclass
from pathlib import Path

import requests
from flask import current_app, request, url_for

log = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"
TIMEOUT = 10  # seconds
RETRY_WAITS = (1, 3)  # seconds to wait before the 2nd and 3rd try


@dataclass
class Email:
    to: str
    subject: str
    text: str
    # Resend ignores a repeat with the same key for 24 hours, so a retry
    # after a timeout can't send the same email twice.
    idempotency_key: str = ""
    # None means use current configuration; reminders freeze these with their payload.
    sender: str | None = None
    reply_to: str | None = None


class MailNotReady(Exception):
    """Email sending isn't set up on this server."""


class MailError(Exception):
    """The email provider refused or couldn't be reached."""


sent: list[Email] = []  # the "memory" backend puts emails here


def backend() -> str:
    chosen = os.getenv("MAIL_BACKEND", "").strip().lower()
    if chosen:
        return chosen
    if os.getenv("RESEND_API_KEY", "").strip():
        return "resend"
    if os.getenv("APP_ENV", "production").strip().lower() == "development":
        return "file"
    return "none"


def mail_ready() -> bool:
    return backend() in ("resend", "file", "memory")


def external_url(endpoint: str, **values) -> str:
    """A full link for emails and Google/GitHub, e.g. https://alloutdeepclean.com/...

    SITE_URL is needed behind Cloudflare, because this server itself only
    sees plain http://127.0.0.1.
    """
    base = os.getenv("SITE_URL", "").strip().rstrip("/") or request.host_url.rstrip("/")
    return base + url_for(endpoint, **values)


def send_email(email: Email) -> None:
    kind = backend()
    if kind == "memory":
        sent.append(email)
    elif kind == "file":
        _save_to_file(email)
    elif kind == "resend":
        _send_with_resend(email)
    else:
        raise MailNotReady("Email sending isn't set up (MAIL_BACKEND / RESEND_API_KEY).")


def _save_to_file(email: Email) -> None:
    outbox = Path(current_app.instance_path) / "outbox"
    outbox.mkdir(parents=True, exist_ok=True)
    name = time.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(3) + ".txt"
    (outbox / name).write_text(
        f"To: {email.to}\nSubject: {email.subject}\n\n{email.text}\n", encoding="utf-8"
    )


def _send_with_resend(email: Email) -> None:
    key = os.getenv("RESEND_API_KEY", "").strip()
    sender = email.sender if email.sender is not None else os.getenv("MAIL_FROM", "").strip()
    if not key or not sender:
        raise MailNotReady("RESEND_API_KEY and MAIL_FROM must both be set.")
    payload = {"from": sender, "to": [email.to], "subject": email.subject, "text": email.text}
    reply_to = email.reply_to if email.reply_to is not None else os.getenv("MAIL_REPLY_TO", "").strip()
    if reply_to:
        payload["reply_to"] = reply_to
    headers = {"Authorization": f"Bearer {key}"}
    if email.idempotency_key:
        headers["Idempotency-Key"] = email.idempotency_key

    problem = "no answer"
    for attempt in range(len(RETRY_WAITS) + 1):
        if attempt:
            time.sleep(RETRY_WAITS[attempt - 1])  # back off a little before trying again
        try:
            res = requests.post(RESEND_URL, json=payload, headers=headers, timeout=TIMEOUT)
        except requests.RequestException as exc:
            problem = type(exc).__name__
            continue
        if res.status_code == 429 or res.status_code >= 500:
            problem = f"HTTP {res.status_code}"
            continue  # busy or rate limited: worth another try
        if res.ok:
            return
        # 4xx = something wrong with the request; trying again won't help.
        # Only the status code is logged: never the key or the email body.
        raise MailError(f"Resend refused the email (HTTP {res.status_code}).")
    log.warning("Resend failed after %d tries (%s)", len(RETRY_WAITS) + 1, problem)
    raise MailError(f"Couldn't reach Resend ({problem}).")
