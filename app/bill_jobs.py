"""Reading uploaded bills: jobs that turn a file into a draft for the owner to check.

1. request: the owner presses "Read this bill" (a POST with CSRF). One job per
   file: asking twice gives the same job back.
2. claim: a worker takes a queued job with a conditional UPDATE and a claim
   token (the same idea as reminders.py). Only one worker can win it. A worker
   that crashed leaves "running"; after STALE_AFTER another run takes it again.
3. read: the file's own text (doc_text.py, in a time-limited child process);
   pages without text go to OCR (ocr.py) if OCR is set up.
4. find fields (extract_fields.py) and check them, then save the page text, the
   draft and "succeeded" in ONE transaction that only commits while we still
   hold the claim. So a job can never make two drafts, even if two workers race.

Nothing here creates a confirmed bill: the owner accepts a draft (bill_review.py).
Jobs run only when `flask process-documents` runs. No scheduler starts it.
"""

import json
import secrets
from datetime import timedelta

import click
from flask.cli import with_appcontext
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError

from app import db
from app.doc_text import TextError, read_text_bounded
from app.doc_text import page as text_page
from app.documents import UploadError, file_path
from app.extract_fields import EXTRACTOR, ExtractionError, check_extraction, extract
from app.models import BillDraft, BillDraftRevision, DocumentJob, DocumentPage, utcnow
from app.ocr import OcrUnavailable, ocr_adapter

MAX_ATTEMPTS = 3
STALE_AFTER = timedelta(minutes=10)  # a "running" job older than this: its worker died
BATCH = 10

# Problems that may go away by themselves: try again later (at most MAX_ATTEMPTS).
RETRY_LATER = {"ocr-offline", "ocr-busy", "timeout", "reader-crashed"}
# What each error code means, for the job page (no internal details).
MESSAGES = {
    "ocr-not-set-up": "Photos and scanned pages need OCR, and OCR isn't switched on yet. Type the bill in, or try again later.",
    "ocr-offline": "The OCR computer didn't answer. We'll try again a few times; you can also type the bill in.",
    "ocr-busy": "The OCR computer is busy. We'll try again a few times.",
    "ocr-bad-reply": "The OCR computer sent something we couldn't use. Type the bill in, or try again later.",
    "timeout": "Reading this file took too long.",
    "reader-crashed": "Reading this file failed unexpectedly.",
    "bad-document": "This file couldn't be read. Type the bill in instead.",
    "too-big": "This Word file is too big to read.",
    "bad-extraction": "The reader's answer couldn't be trusted, so nothing was filled in. Type the bill in.",
    "file-missing": "The uploaded file is missing on the server.",
    "gave-up": "Reading kept failing, so we stopped trying.",
}


# ---------- 1. request ----------------------------------------------------------

def request_reading(user, document) -> tuple[DocumentJob, bool]:
    """The job for this file, made now if there isn't one. Returns (job, made_now)."""
    job = DocumentJob.query.filter_by(user_id=user.id, document_id=document.id).first()
    if job:
        return job, False
    job = DocumentJob(user_id=user.id, document_id=document.id, status="queued", next_try_at=utcnow())
    db.session.add(job)
    try:
        db.session.commit()
    except IntegrityError:  # the same request twice at the same moment: use the other one
        db.session.rollback()
        return DocumentJob.query.filter_by(user_id=user.id, document_id=document.id).one(), False
    return job, True


def retry(job: DocumentJob) -> bool:
    """The owner asks again after a failure. Only a failed job can be retried."""
    won = DocumentJob.query.filter_by(id=job.id, status="failed").update(
        {"status": "queued", "attempts": 0, "next_try_at": utcnow(), "error_code": "",
         "claim_token": None, "finished_at": None},
        synchronize_session=False,
    )
    db.session.commit()
    return won == 1


# ---------- 2. claim ------------------------------------------------------------

def waiting(now) -> list[DocumentJob]:
    return (
        DocumentJob.query.filter(or_(
            and_(DocumentJob.status == "queued", DocumentJob.next_try_at <= now),
            and_(DocumentJob.status == "running", DocumentJob.claimed_at < now - STALE_AFTER),
        ))
        .order_by(DocumentJob.id).limit(BATCH).all()
    )


def claim(job: DocumentJob, now) -> str | None:
    """Take the job for this run. Returns our claim token, or None if someone else has it."""
    if job.attempts >= MAX_ATTEMPTS:
        # A job whose worker died MAX_ATTEMPTS times: stop instead of looping forever.
        DocumentJob.query.filter_by(id=job.id, status=job.status, attempts=job.attempts).update(
            {"status": "failed", "error_code": "gave-up", "claim_token": None, "finished_at": now},
            synchronize_session=False)
        db.session.commit()
        return None
    token = secrets.token_hex(8)
    still_same = and_(
        DocumentJob.id == job.id,
        DocumentJob.status == job.status,
        DocumentJob.attempts == job.attempts,
        DocumentJob.claim_token.is_(None) if job.claim_token is None else DocumentJob.claim_token == job.claim_token,
    )
    won = DocumentJob.query.filter(still_same).update(
        {"status": "running", "claim_token": token, "claimed_at": now, "attempts": job.attempts + 1},
        synchronize_session=False,
    )
    db.session.commit()
    return token if won == 1 else None


def fail(job_id: int, token: str, code: str, attempts: int, now) -> str:
    """Record a failure (only while we hold the claim). Temporary problems go back
    to "queued" with a growing wait, until MAX_ATTEMPTS."""
    db.session.rollback()  # drop anything half-saved by this run
    again = code in RETRY_LATER and attempts < MAX_ATTEMPTS
    values = {"error_code": code, "claim_token": None}
    if again:
        values.update(status="queued", next_try_at=now + timedelta(minutes=5 * 2 ** (attempts - 1)))
    else:
        values.update(status="failed", finished_at=now)
    DocumentJob.query.filter_by(id=job_id, claim_token=token).update(values, synchronize_session=False)
    db.session.commit()
    return "retry" if again else "failed"


# ---------- 3 + 4. read the file and make the draft ---------------------------

def run_job(job: DocumentJob, token: str, now, ocr=None) -> str:
    """Do one claimed job. Returns "succeeded", "retry", "failed" or "lost"."""
    document = job.document
    try:
        data = file_path(document.stored_name).read_bytes()
    except (UploadError, OSError):
        return fail(job.id, token, "file-missing", job.attempts, now)

    pages = [{"page": p.page_number, "text": p.text}
             for p in DocumentPage.query.filter_by(document_id=document.id).order_by(DocumentPage.page_number)]
    new_pages = []
    if not pages:  # read the file (a retry reuses what an earlier run already saved)
        try:
            read = read_text_bounded(data, document.kind)
            new_pages, pages = read_pages(read, data, document.kind, ocr)
        except TextError as problem:
            return fail(job.id, token, problem.code, job.attempts, now)
        except OcrUnavailable as problem:
            return fail(job.id, token, "ocr-" + problem.code if not problem.code.startswith("http") else "ocr-bad-reply",
                        job.attempts, now)

    try:
        fields = check_extraction(extract(pages), pages)
    except ExtractionError:
        return fail(job.id, token, "bad-extraction", job.attempts, now)

    try:
        for p in new_pages:
            db.session.add(DocumentPage(document_id=document.id, user_id=job.user_id, page_number=p["page"],
                                        text=p["text"], source=p["source"], engine=p.get("engine", ""),
                                        truncated=p.get("truncated", False)))
        save_draft(job, fields, pages, now)
        won = DocumentJob.query.filter_by(id=job.id, claim_token=token).update(
            {"status": "succeeded", "claim_token": None, "finished_at": now, "error_code": ""},
            synchronize_session=False,
        )
        if won != 1:
            db.session.rollback()  # another worker took over: keep its result, not ours
            return "lost"
        db.session.commit()
    except IntegrityError:  # another worker already saved this job's draft or pages
        db.session.rollback()
        return "lost"
    return "succeeded"


def read_pages(read: list[dict], data: bytes, kind: str, ocr) -> tuple[list[dict], list[dict]]:
    """Use the file's own text where there is some; OCR the pages without text.

    Returns (pages to save, pages to search). If some pages have text and OCR is
    off, the readable pages are used and the rest stay unread (the draft says so).
    Raises OcrUnavailable when nothing at all could be read.
    """
    source = "docx" if kind == "docx" else "pdf-text"
    saved = [{**p, "source": source} for p in read if not p["needs_ocr"]]
    missing = [p["page"] for p in read if p["needs_ocr"]]
    if missing:
        reader = ocr if ocr is not None else ocr_adapter()
        try:
            if reader is None:
                raise OcrUnavailable("not-set-up")
            result = reader.read(data, kind, missing)
            for p in result.pages:
                # The same clean-up as text read from files: card numbers masked to the
                # last 4 digits, same line endings. Done BEFORE searching and saving, so
                # evidence positions point into the masked text and no full number is kept.
                clean = text_page(p.number, p.text)
                saved.append({"page": p.number, "text": clean["text"], "truncated": p.truncated or clean["truncated"],
                              "source": "ocr", "engine": result.engine})
        except OcrUnavailable:
            if not saved:
                raise
    saved.sort(key=lambda p: p["page"])
    return saved, [{"page": p["page"], "text": p["text"]} for p in saved]


def save_draft(job: DocumentJob, fields: dict, pages: list[dict], now) -> None:
    read_numbers = {p["page"] for p in pages}
    unread = [n for n in range(1, (job.document.page_count or 1) + 1) if n not in read_numbers]
    values = {name: {"value": item["value"], "origin": "document" if item["value"] is not None else "empty",
                     "method": item["method"], "evidence": item["evidence"]}
              for name, item in fields.items()}
    extracted = {"extractor": EXTRACTOR, "unread_pages": unread, "fields": values}
    draft = BillDraft(user_id=job.user_id, document_id=job.document_id, job_id=job.id, status="draft",
                      extractor=EXTRACTOR, extracted_json=json.dumps(extracted, ensure_ascii=False),
                      values_json=json.dumps(values, ensure_ascii=False), revision=1)
    db.session.add(draft)
    db.session.flush()  # gives the draft its id for the first history entry
    db.session.add(BillDraftRevision(draft_id=draft.id, user_id=job.user_id, number=1, action="extracted",
                                     changed=", ".join(n for n, v in values.items() if v["value"] is not None)[:400],
                                     values_json=draft.values_json, created_at=now))


# ---------- running jobs ------------------------------------------------------

def process_due(now=None, ocr=None) -> dict:
    now = now or utcnow()
    counts = {"succeeded": 0, "retry": 0, "failed": 0, "lost": 0}
    for job in waiting(now):
        token = claim(job, now)
        if token is None:
            counts["lost"] += 1
            continue
        db.session.refresh(job)
        counts[run_job(job, token, now, ocr)] += 1
    return counts


@click.command("process-documents")
@with_appcontext
def process_documents_command():
    """Read the bills people asked to read (queued jobs). Safe to run twice at once."""
    counts = process_due()
    click.echo(", ".join(f"{name}: {count}" for name, count in counts.items()))
