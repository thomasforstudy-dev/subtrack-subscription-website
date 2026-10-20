"""Pages for reading uploaded bills: start a job, see its status, check the draft.

A draft is never a bill. The owner looks at each field next to the text it
came from, corrects what's wrong and presses Accept; only then a Bill is made.
Every change is kept as a revision, so what the document said, what the reader
found and what the owner changed stay separate.

Every query filters by the logged-in user. Contract: docs/CONTRACT.md -> Reading bills.
"""

import json

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.bill_jobs import MESSAGES, request_reading, retry
from app.bills import apply, own_document_or_404, read_form
from app.extract_fields import DRAFT_FIELDS, TEXT_LIMITS
from app.models import Bill, BillDraft, BillDraftRevision, DocumentJob, DocumentPage

bp = Blueprint("bill_review", __name__, url_prefix="/bills")

MAX_VALUE = max(TEXT_LIMITS.values())
LABELS = {
    "kind": "Kind", "category": "Category", "currency": "Currency", "timezone": "Time zone",
    "transaction_time": "Payment time", "card_last4": "Card (last 4 digits)", "merchant": "Shop / card or bank",
    "branch": "Branch", "address": "Address", "invoice_number": "Invoice number", "notes": "Notes",
    "invoice_date": "Invoice date (printed on the bill)", "transaction_date": "Paid on",
    "statement_start": "Statement from", "statement_end": "Statement to", "due_date": "Card payment due",
    "subtotal": "Subtotal", "tax": "Tax", "total": "Total",
}


def own_job_or_404(job_id: int) -> DocumentJob:
    return DocumentJob.query.filter_by(id=job_id, user_id=current_user.id).first_or_404()


def own_draft_or_404(draft_id: int) -> BillDraft:
    return BillDraft.query.filter_by(id=draft_id, user_id=current_user.id).first_or_404()


def draft_of(job: DocumentJob) -> BillDraft | None:
    return BillDraft.query.filter_by(job_id=job.id, user_id=current_user.id).first()


# ---------- jobs ------------------------------------------------------------------

@bp.route("/files/<int:document_id>/read", methods=["POST"])
@login_required
def read_document(document_id: int):
    """The explicit "Read this bill for me" button. Nothing is read without it."""
    document = own_document_or_404(document_id)
    job, made_now = request_reading(current_user, document)
    flash("Queued: we'll read this file and prepare a draft for you to check." if made_now
          else "This file is already being read (or was read).")
    return redirect(url_for("bill_review.job_page", job_id=job.id))


@bp.route("/jobs/<int:job_id>")
@login_required
def job_page(job_id: int):
    job = own_job_or_404(job_id)
    return render_template("bills/job.html", job=job, draft=draft_of(job),
                           message=MESSAGES.get(job.error_code, ""))


@bp.route("/jobs/<int:job_id>.json")
@login_required
def job_json(job_id: int):
    """For the page to check progress without reloading."""
    job = own_job_or_404(job_id)
    draft = draft_of(job)
    return jsonify(
        status=job.status, attempts=job.attempts, error_code=job.error_code or None,
        message=MESSAGES.get(job.error_code) or None,
        draft_url=url_for("bill_review.draft_page", draft_id=draft.id) if draft else None,
    )


@bp.route("/jobs/<int:job_id>/retry", methods=["POST"])
@login_required
def retry_job(job_id: int):
    job = own_job_or_404(job_id)
    flash("Queued again." if retry(job) else "Only a job that failed can be tried again.")
    return redirect(url_for("bill_review.job_page", job_id=job.id))


# ---------- drafts --------------------------------------------------------------

@bp.route("/drafts/<int:draft_id>", methods=["GET", "POST"])
@login_required
def draft_page(draft_id: int):
    draft = own_draft_or_404(draft_id)
    if request.method == "POST":
        if draft.status != "draft":
            flash("This draft is closed: it was already accepted or put aside.")
            return redirect(url_for("bill_review.draft_page", draft_id=draft.id))
        if request.form.get("revision") != str(draft.revision):
            flash("This draft changed in another tab. Here is the newest version; please check it again.")
            return redirect(url_for("bill_review.draft_page", draft_id=draft.id))
        if request.form.get("action") == "accept":
            return accept(draft)
        return save(draft)
    return show(draft)


def show(draft: BillDraft, typed=None):
    extracted = json.loads(draft.extracted_json)
    pages = DocumentPage.query.filter_by(document_id=draft.document_id, user_id=current_user.id) \
        .order_by(DocumentPage.page_number).all()
    revisions = BillDraftRevision.query.filter_by(draft_id=draft.id, user_id=current_user.id) \
        .order_by(BillDraftRevision.number).all()
    return render_template(
        "bills/draft.html", draft=draft, values=json.loads(draft.values_json),
        found=extracted["fields"], unread_pages=extracted.get("unread_pages", []),
        pages=pages, revisions=revisions, fields=DRAFT_FIELDS, labels=LABELS, typed=typed or {},
        bill=db.session.get(Bill, draft.bill_id) if draft.bill_id else None,
    )


def changes_from(form, values: dict) -> tuple[dict, list[str]]:
    """The draft values after the owner's form. A changed field is now "you"
    (no document evidence); an unchanged one keeps where it came from."""
    new, changed = {}, []
    for name in DRAFT_FIELDS:
        old = values[name]
        if name not in form:
            new[name] = old
            continue
        typed = (form.get(name) or "").strip()[:MAX_VALUE]
        # The Kind list always sends something; "receipt" is its default, not a change.
        untouched_default = name == "kind" and typed == "receipt" and old["value"] is None
        if typed == (old["value"] or "") or untouched_default:
            new[name] = old
            continue
        changed.append(name)
        new[name] = {"value": typed or None, "origin": "you" if typed else "empty", "method": "", "evidence": []}
    return new, changed


def next_revision(draft: BillDraft, values: dict, changed: list[str], action: str, **extra) -> bool:
    """Save new values only if nobody saved in between (revision number check)."""
    won = BillDraft.query.filter_by(id=draft.id, user_id=current_user.id, status="draft", revision=draft.revision) \
        .update({"values_json": json.dumps(values, ensure_ascii=False), "revision": draft.revision + 1, **extra},
                synchronize_session=False)
    if won != 1:
        return False
    db.session.add(BillDraftRevision(draft_id=draft.id, user_id=current_user.id, number=draft.revision + 1,
                                     action=action, changed=", ".join(changed)[:400],
                                     values_json=json.dumps(values, ensure_ascii=False)))
    return True


def save(draft: BillDraft):
    values, changed = changes_from(request.form, json.loads(draft.values_json))
    if not changed:
        flash("Nothing changed.")
        return redirect(url_for("bill_review.draft_page", draft_id=draft.id))
    if not next_revision(draft, values, changed, "edited"):
        db.session.rollback()
        flash("This draft changed in another tab. Here is the newest version.")
        return redirect(url_for("bill_review.draft_page", draft_id=draft.id))
    db.session.commit()
    flash("Draft saved: " + ", ".join(LABELS[n] for n in changed) + ".")
    return redirect(url_for("bill_review.draft_page", draft_id=draft.id))


def accept(draft: BillDraft):
    """Make the real bill from the checked values: the same checks as the normal
    bill form. A rejected form changes nothing (no bill, draft as it was)."""
    values, changed = changes_from(request.form, json.loads(draft.values_json))
    checked, lines, error = read_form({name: (v["value"] or "") for name, v in values.items()})
    if error:
        flash(error)
        return show(draft, typed=request.form)
    bill = Bill(user_id=current_user.id, source="upload", document_id=draft.document_id)
    apply(bill, checked, lines)
    db.session.add(bill)
    db.session.flush()  # gives the bill its id
    if not next_revision(draft, values, changed, "accepted", status="accepted", bill_id=bill.id):
        db.session.rollback()  # accepted twice (double click, two tabs): keep only the first bill
        flash("This draft was already accepted or changed in another tab.")
        return redirect(url_for("bill_review.draft_page", draft_id=draft.id))
    db.session.commit()
    flash("Bill saved from your checked draft.")
    return redirect(url_for("bills.edit", bill_id=bill.id))


@bp.route("/drafts/<int:draft_id>/discard", methods=["POST"])
@login_required
def discard(draft_id: int):
    """Put a draft aside (it is kept, not deleted). The bill can still be typed in."""
    draft = own_draft_or_404(draft_id)
    won = BillDraft.query.filter_by(id=draft.id, user_id=current_user.id, status="draft") \
        .update({"status": "discarded"}, synchronize_session=False)
    db.session.commit()
    flash("Draft put aside. You can type the bill in yourself." if won else "This draft is already closed.")
    return redirect(url_for("bills.create", document_id=draft.document_id))
