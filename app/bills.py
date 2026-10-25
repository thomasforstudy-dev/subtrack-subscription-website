"""Bills: receipts and credit card bills, typed in or from an uploaded file.

The flow today (no AI yet): upload a photo/PDF/Word file -> it's checked and
stored privately -> the user types the bill in next to it -> saved.
Later the OCR job will fill a draft first, and the user still checks it.

Every query filters by the logged-in user. Nothing here deletes data:
bills are archived, files are kept.
"""

import csv
import io
import json
import re
from datetime import date, time
from decimal import Decimal, InvalidOperation
from zoneinfo import available_timezones

from flask import Blueprint, Response, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

from app import db
from app.cards import card_rows
from app.documents import IMAGES, MIME_TYPES, UploadError, clean_name, file_path, inspect_bounded as inspect, read_upload, save_file
from app.models import Bill, BillDraft, BillLine, Document, DocumentJob
from app.schedule import local_now
from app.validation import escape_like

bp = Blueprint("bills", __name__, url_prefix="/bills")

PER_PAGE = 20
MAX_LINES = 30
BLANK_LINES = 3  # empty rows the form shows for new items
ZONES = available_timezones()
TEXT_LIMITS = {"merchant": 200, "branch": 200, "address": 500, "invoice_number": 64, "notes": 2000}
DATE_FIELDS = ("invoice_date", "transaction_date", "statement_start", "statement_end", "due_date")
MONEY_FIELDS = ("subtotal", "tax", "total")
FORM_FIELDS = ("kind", "category", "currency", "timezone", "transaction_time", "card_last4",
               *TEXT_LIMITS, *DATE_FIELDS, *MONEY_FIELDS)


def user_today() -> date:
    return local_now(current_user.timezone).date()


def own_bill_or_404(bill_id: int) -> Bill:
    return Bill.query.filter_by(id=bill_id, user_id=current_user.id).first_or_404()


def own_document_or_404(document_id: int) -> Document:
    return Document.query.filter_by(id=document_id, user_id=current_user.id).first_or_404()


# ---------- list ----------------------------------------------------------------

@bp.route("/")
@login_required
def list_bills():
    status = request.args.get("status", "confirmed")
    status = status if status in Bill.STATUSES else "confirmed"
    kind = request.args.get("kind", "")
    category = request.args.get("category", "")
    q = (request.args.get("q") or "").strip()[:100]

    query = Bill.query.filter_by(user_id=current_user.id, status=status)
    if kind in Bill.KINDS:
        query = query.filter_by(kind=kind)
    if category in Bill.CATEGORIES:
        query = query.filter_by(category=category)
    if q:
        like = f"%{escape_like(q)}%"
        query = query.filter(or_(
            Bill.merchant.ilike(like, escape="\\"), Bill.invoice_number.ilike(like, escape="\\"),
            Bill.notes.ilike(like, escape="\\"),
        ))
    newest = func.coalesce(Bill.transaction_date, Bill.invoice_date, Bill.due_date)
    pages = query.order_by(newest.desc(), Bill.id.desc()).paginate(
        page=request.args.get("page", 1, type=int), per_page=PER_PAGE, error_out=False,
    )
    return render_template(
        "bills/list.html",
        items=pages.items,
        pages=pages,
        totals=receipt_totals(),
        month=month_spend(),
        cards=card_rows(current_user.id, user_today().replace(day=1)),
        unpaid=unpaid_card_bills(),
        waiting=waiting_documents(),
        # "Read it for me" jobs of the waiting files: {document_id: job}
        reading={job.document_id: job for job in DocumentJob.query.filter_by(user_id=current_user.id)},
        status=status, kind=kind, category=category, q=q,
        kinds=Bill.KINDS, categories=Bill.CATEGORIES,
        today=user_today(),
        checks={bill.id: money_checks(bill) for bill in pages.items},
    )


def receipt_totals() -> list[dict]:
    """Spent per currency, from confirmed receipts. Never added across currencies."""
    rows = (
        db.session.query(Bill.currency, func.count(Bill.id), func.sum(Bill.total))
        .filter(Bill.user_id == current_user.id, Bill.status == "confirmed",
                Bill.kind == "receipt", Bill.total.isnot(None))
        .group_by(Bill.currency).order_by(Bill.currency).all()
    )
    return [{"currency": c, "count": n, "total": Decimal(t).quantize(Decimal("0.01"))} for c, n, t in rows]


def month_spend() -> dict | None:
    """This month's receipts in the user's main currency, split by category.

    The main currency is the one with the most receipts this month; the
    others are listed apart (never added together)."""
    start = user_today().replace(day=1)
    day = func.coalesce(Bill.transaction_date, Bill.invoice_date)
    rows = (
        db.session.query(Bill.currency, Bill.category, func.count(Bill.id), func.sum(Bill.total))
        .filter(Bill.user_id == current_user.id, Bill.status == "confirmed", Bill.kind == "receipt",
                Bill.total.isnot(None), day >= start)
        .group_by(Bill.currency, Bill.category).all()
    )
    if not rows:
        return None
    by_currency = {}
    for currency, category, count, total in rows:
        entry = by_currency.setdefault(currency, {"count": 0, "total": Decimal(0), "categories": []})
        entry["count"] += count
        entry["total"] += Decimal(total)
        entry["categories"].append((category, Decimal(total)))
    main = max(by_currency, key=lambda c: (by_currency[c]["count"], by_currency[c]["total"]))
    entry = by_currency[main]
    biggest = max(amount for _, amount in entry["categories"]) or Decimal(1)
    return {
        "currency": main,
        "count": entry["count"],
        "total": entry["total"].quantize(Decimal("0.01")),
        # (category, amount, bar width in %), biggest first
        "categories": [(cat, amount.quantize(Decimal("0.01")), int(amount / biggest * 100))
                       for cat, amount in sorted(entry["categories"], key=lambda row: -row[1])],
        "others": [(c, by_currency[c]["total"].quantize(Decimal("0.01"))) for c in sorted(by_currency) if c != main],
    }


def unpaid_card_bills() -> list[Bill]:
    return (
        Bill.query.filter_by(user_id=current_user.id, status="confirmed", kind="card_bill", paid_at=None)
        .order_by(Bill.due_date, Bill.id).all()
    )


def waiting_documents() -> list[Document]:
    """Uploaded files that no bill uses yet: "type this one in"."""
    used = db.session.query(Bill.document_id).filter(
        Bill.user_id == current_user.id, Bill.document_id.isnot(None)
    )
    return (
        Document.query.filter_by(user_id=current_user.id)
        .filter(Document.id.notin_(used)).order_by(Document.created_at.desc()).all()
    )


# ---------- add / edit -----------------------------------------------------------

@bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    document = attached_document(request.values.get("document_id"))
    if request.method == "POST":
        values, lines, error = read_form(request.form)
        if error:
            flash(error)
            return render_form(None, document, request.form)
        bill = Bill(user_id=current_user.id, source="upload" if document else "manual",
                    document_id=document.id if document else None)
        apply(bill, values, lines)
        db.session.add(bill)
        db.session.commit()
        flash_saved(bill, "Bill saved.")
        return redirect(url_for("bills.list_bills"))
    return render_form(None, document, {})


@bp.route("/<int:bill_id>/edit", methods=["GET", "POST"])
@login_required
def edit(bill_id: int):
    bill = own_bill_or_404(bill_id)
    if request.method == "POST":
        values, lines, error = read_form(request.form, bill)
        if error:
            flash(error)
            return render_form(bill, bill.document, request.form)
        apply(bill, values, lines)
        db.session.commit()
        flash_saved(bill, "Bill updated.")
        return redirect(url_for("bills.list_bills"))
    return render_form(bill, bill.document, {})


def flash_saved(bill: Bill, message: str) -> None:
    flash(message)
    for problem in money_checks(bill):
        flash("Please check: " + problem)


def attached_document(raw_id) -> Document | None:
    """The uploaded file this bill is typed from, only if it's the user's own."""
    if not raw_id:
        return None
    if not str(raw_id).isdigit():
        return None
    return own_document_or_404(int(raw_id))


def render_form(bill, document, form):
    form = dict(form)
    # Never show a typed full card number back on the page.
    if "card_last4" in form and not re.fullmatch(r"\d{4}", str(form["card_last4"]).strip()):
        form["card_last4"] = ""
    sent_rows = submitted_rows(form)
    if sent_rows:
        # The form had an item table: show exactly what was typed, every row of it.
        saved_lines, rows = [], sent_rows
    else:
        saved_lines = [
            {"description": line.description, "quantity": quantity_text(line.quantity), "unit_price": line.unit_price}
            for line in (bill.lines if bill else [])
        ]
        rows = len(saved_lines) + BLANK_LINES
    return render_template(
        "bills/form.html", item=bill, form=form, document=document,
        lines=saved_lines, rows=min(max(rows, BLANK_LINES), MAX_LINES),
        kinds=Bill.KINDS, categories=Bill.CATEGORIES, max_lines=MAX_LINES,
    )


ITEM_FIELD = re.compile(r"item_(name|qty|price)_(\d{1,2})")


def submitted_rows(form) -> int:
    """The highest item row number the form sent (item_name_5 -> 5), at most MAX_LINES."""
    numbers = [int(m.group(2)) for key in form if (m := ITEM_FIELD.fullmatch(key))]
    return min(max(numbers, default=0), MAX_LINES)


@bp.route("/<int:bill_id>/paid", methods=["POST"])
@login_required
def mark_paid(bill_id: int):
    bill = own_bill_or_404(bill_id)
    bill.paid_at = user_today() if request.form.get("paid", "1") == "1" else None
    db.session.commit()
    flash("Marked as paid." if bill.paid_at else "Marked as not paid.")
    return redirect(url_for("bills.list_bills"))


@bp.route("/<int:bill_id>/archive", methods=["POST"])
@login_required
def archive(bill_id: int):
    own_bill_or_404(bill_id).status = "archived"
    db.session.commit()
    flash("Archived.")
    return redirect(url_for("bills.list_bills"))


@bp.route("/<int:bill_id>/restore", methods=["POST"])
@login_required
def restore(bill_id: int):
    own_bill_or_404(bill_id).status = "confirmed"
    db.session.commit()
    flash("Restored.")
    return redirect(url_for("bills.list_bills", status="archived"))


# ---------- checking the form ---------------------------------------------------

def raw_values(form, bill: Bill | None) -> dict:
    """Like subscriptions: a field that isn't in the form keeps its saved value;
    a field that is there but empty is cleared on purpose."""
    saved = {field: "" for field in FORM_FIELDS}
    saved.update(kind="receipt", category="other")
    if bill is not None:
        for field in FORM_FIELDS:
            value = getattr(bill, field)
            if isinstance(value, time):
                value = value.strftime("%H:%M")
            saved[field] = "" if value is None else str(value)
    return {field: form[field] if field in form else saved[field] for field in FORM_FIELDS}


def read_form(form, bill: Bill | None = None) -> tuple[dict, list | None, str | None]:
    """Check every field. Returns (values, lines, None) or ({}, None, a friendly error).
    lines is None when the form sent no item rows at all (editing keeps the saved ones)."""
    raw = raw_values(form, bill)
    values = {}

    values["kind"] = raw["kind"] or "receipt"
    if values["kind"] not in Bill.KINDS:
        return {}, None, "Pick receipt or card bill."
    values["category"] = raw["category"] or "other"
    if values["category"] not in Bill.CATEGORIES:
        return {}, None, "Pick a category from the list."

    for field, limit in TEXT_LIMITS.items():
        values[field] = (raw[field] or "").strip()
        if len(values[field]) > limit:
            return {}, None, f"{label(field)} can be up to {limit} characters."
    if not values["merchant"]:
        what = "card or bank" if values["kind"] == "card_bill" else "shop"
        return {}, None, f"Please type the {what} name."

    values["currency"] = (raw["currency"] or "").strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", values["currency"]):
        return {}, None, "Use a 3-letter currency code, like USD, EUR or VND."

    for field in DATE_FIELDS:
        text = (raw[field] or "").strip()
        values[field] = None
        if text:
            try:
                values[field] = date.fromisoformat(text)
            except ValueError:
                return {}, None, f"{label(field)}: please pick a date."
            if not date(2000, 1, 1) <= values[field] <= date(2100, 12, 31):
                return {}, None, f"{label(field)} looks wrong. Please check the year."

    text = (raw["transaction_time"] or "").strip()
    values["transaction_time"] = None  # empty = the bill shows no time (never 00:00)
    if text:
        try:
            values["transaction_time"] = time.fromisoformat(text).replace(second=0, microsecond=0, tzinfo=None)
        except ValueError:
            return {}, None, "Time: please use hours and minutes, like 14:30."

    values["timezone"] = (raw["timezone"] or "").strip()
    if values["timezone"] and values["timezone"] not in ZONES:
        return {}, None, "Pick a time zone from the list, like Asia/Ho_Chi_Minh."

    for field in MONEY_FIELDS:
        values[field], error = read_money(raw[field], values["currency"], label(field))
        if error:
            return {}, None, error

    digits = re.sub(r"[\s-]", "", raw["card_last4"] or "")
    if digits and not re.fullmatch(r"\d{4}", digits):
        return {}, None, "Card: type only the last 4 digits. Never the full card number."
    values["card_last4"] = digits

    if values["kind"] == "card_bill" and values["due_date"] is None:
        return {}, None, "Please pick the payment due date of the card bill."
    start, end = values["statement_start"], values["statement_end"]
    if start and end and end < start:
        return {}, None, "The statement can't end before it starts."

    lines, error = read_lines(form, values["currency"])
    if error:
        return {}, None, error
    return values, lines, None


# Money columns are DECIMAL(12,2): the biggest value SQL Server can store.
MAX_BILL_AMOUNT = Decimal("9999999999.99")
# Currencies with no cents (ISO 4217 "minor unit" 0): 45000.50 VND can't exist.
WHOLE_NUMBER_CURRENCIES = {
    "BIF", "CLP", "DJF", "GNF", "ISK", "JPY", "KMF", "KRW",
    "PYG", "RWF", "UGX", "VND", "VUV", "XAF", "XOF", "XPF",
}


def read_money(raw, currency: str, what: str) -> tuple[Decimal | None, str | None]:
    """An optional amount on a bill. Empty = not on the bill (None)."""
    text = (raw or "").strip()
    if not text:
        return None, None
    try:
        amount = Decimal(text)
    except InvalidOperation:
        amount = None
    if amount is None or not amount.is_finite() or amount < 0 or amount.as_tuple().exponent < -2:
        return None, f"{what}: type a number like 9.99 (dot for decimals, at most 2)."
    if amount > MAX_BILL_AMOUNT:
        return None, f"{what} is too big (at most {MAX_BILL_AMOUNT:,})."
    if currency in WHOLE_NUMBER_CURRENCIES and amount != amount.to_integral_value():
        return None, f"{what}: {currency} has no decimals, so type a whole number."
    return amount.quantize(Decimal("0.01")), None


def read_lines(form, currency: str) -> tuple[list | None, str | None]:
    """item_name_1 / item_qty_1 / item_price_1, item_name_2 ... Rows without a name are skipped.

    Returns None when the form had no item table at all (editing then keeps the
    saved items). The `item_rows` hidden field says "the table was there", so
    removing every row really removes the items.
    """
    if "item_rows" not in form and not submitted_rows(form):
        return None, None
    lines = []
    for n in range(1, MAX_LINES + 1):
        name = (form.get(f"item_name_{n}") or "").strip()
        if not name:
            continue
        if len(name) > 300:
            return None, f"Item {n}: the name can be up to 300 characters."
        qty_text = (form.get(f"item_qty_{n}") or "").strip()
        quantity = parse_quantity(qty_text) if qty_text else None
        if qty_text and quantity is None:
            return None, f"Item {n}: the quantity must be a number above 0, like 2 or 1.5."
        price, error = read_money(form.get(f"item_price_{n}"), currency, f"Item {n} price")
        if error:
            return None, error
        amount = None
        if price is not None:
            amount = (price * (quantity or 1)).quantize(Decimal("0.01"))
            if amount > MAX_BILL_AMOUNT:  # 9999999 x 99999999.99 doesn't fit DECIMAL(12,2)
                return None, f"Item {n}: quantity × price is too big (at most {MAX_BILL_AMOUNT:,})."
        lines.append({"description": name, "quantity": quantity, "unit_price": price, "amount": amount})
    return lines, None


def money_checks(bill: Bill) -> list[str]:
    """Numbers on the bill that don't add up. Shown so the user can look again;
    the typed values are never changed. Discounts, tips or service charges can
    explain a difference, so this is a "please check", not an error."""
    problems = []
    amounts = [line.amount for line in bill.lines]
    lines_sum = sum(amounts, Decimal(0)) if amounts and None not in amounts else None
    sub, tax, total = bill.subtotal, bill.tax, bill.total
    if sub is not None and tax is not None and total is not None and sub + tax != total:
        problems.append(f"Subtotal {sub} + tax {tax} = {sub + tax}, but the total says {total}.")
    if lines_sum is not None and sub is not None and lines_sum != sub:
        problems.append(f"The items add up to {lines_sum}, but the subtotal says {sub}.")
    if lines_sum is not None and sub is None and total is not None:
        if lines_sum != total and (tax is None or lines_sum + tax != total):
            problems.append(f"The items add up to {lines_sum}, but the total says {total}.")
    return problems


def parse_quantity(text: str) -> Decimal | None:
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    if not value.is_finite() or value <= 0 or value > 9999999 or value.as_tuple().exponent < -3:
        return None
    return value


def label(field: str) -> str:
    return field.replace("_", " ").capitalize()


def apply(bill: Bill, values: dict, lines: list | None) -> None:
    for field, value in values.items():
        setattr(bill, field, value)
    if bill.status is None:
        bill.status = "confirmed"
    if lines is not None:  # None = the form had no item rows: keep the saved ones
        bill.lines = [BillLine(position=i, **line) for i, line in enumerate(lines, start=1)]


# ---------- upload and download ------------------------------------------------

@bp.route("/upload", methods=["POST"])
@login_required
def upload():
    file = request.files.get("file")
    if file is None or not file.filename:
        flash("Please choose a file first.")
        return redirect(url_for("bills.list_bills"))
    try:
        data = read_upload(file.stream)
        facts = inspect(data)
    except UploadError as problem:
        flash(str(problem))
        return redirect(url_for("bills.list_bills"))

    # The same file again: use the one already saved (no second copy).
    existing = Document.query.filter_by(user_id=current_user.id, sha256=facts["sha256"]).first()
    if existing:
        flash("You already uploaded this file.")
        return redirect_for_document(existing)

    stored = save_file(data, facts["kind"])
    document = Document(user_id=current_user.id, original_name=clean_name(file.filename),
                        stored_name=stored, **facts)
    db.session.add(document)
    try:
        db.session.commit()
    except IntegrityError:  # the same file sent twice at the same moment
        db.session.rollback()
        file_path(stored).unlink(missing_ok=True)  # our own copy that was never recorded
        existing = Document.query.filter_by(user_id=current_user.id, sha256=facts["sha256"]).first_or_404()
        return redirect_for_document(existing)
    flash("File saved. Now type in the bill details next to it.")
    return redirect(url_for("bills.create", document_id=document.id))


def redirect_for_document(document: Document):
    bill = Bill.query.filter_by(user_id=current_user.id, document_id=document.id).first()
    if bill:
        return redirect(url_for("bills.edit", bill_id=bill.id))
    return redirect(url_for("bills.create", document_id=document.id))


@bp.route("/files/<int:document_id>")
@login_required
def download(document_id: int):
    """Only the owner can open a file. Photos can be shown on the page
    (?view=1); PDFs and Word files are always downloaded, never opened inline."""
    document = own_document_or_404(document_id)
    try:
        path = file_path(document.stored_name)
    except UploadError:
        return "File not found.", 404
    if not path.is_file():
        return "File not found.", 404
    inline = request.args.get("view") == "1" and document.kind in IMAGES
    response = send_file(path, mimetype=MIME_TYPES[document.kind], as_attachment=not inline,
                         download_name=document.original_name, max_age=0)
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "default-src 'none'; img-src 'self'; sandbox"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


# ---------- export (JSON / CSV / Markdown) -------------------------------------

def money(value) -> str | None:
    return None if value is None else str(value)


def quantity_text(value) -> str | None:
    """2.000 -> "2", 1.500 -> "1.5" (the database keeps 3 decimals)."""
    return None if value is None else format(value.normalize(), "f")


def bill_json(bill: Bill, evidence: dict | None = None) -> dict:
    """The standard bill format (docs/CONTRACT.md). Money is a string, dates are
    ISO, and anything not on the bill is null, never guessed.
    evidence: for a bill made from a checked draft, {field: [page/text spans]}."""
    when = None
    if bill.transaction_date:
        when = bill.transaction_date.isoformat()
        if bill.transaction_time:  # no time on the bill -> just the date, no fake 00:00
            when += "T" + bill.transaction_time.strftime("%H:%M")
    return {
        "id": bill.id,
        "document_id": bill.document_id,
        "kind": bill.kind,
        "invoice_number": bill.invoice_number or None,
        "invoice_date": bill.invoice_date.isoformat() if bill.invoice_date else None,
        "transaction_datetime": when,
        "timezone": bill.timezone or None,
        "merchant_name": bill.merchant,
        "merchant_branch": bill.branch or None,
        "merchant_address": bill.address or None,
        "currency": bill.currency,
        "subtotal": money(bill.subtotal),
        "tax": money(bill.tax),
        "total": money(bill.total),
        "line_items": [
            {"description": line.description, "quantity": quantity_text(line.quantity),
             "unit_price": money(line.unit_price), "amount": money(line.amount)}
            for line in bill.lines
        ],
        "category": bill.category,
        "card_last4": bill.card_last4 or None,
        "statement_start": bill.statement_start.isoformat() if bill.statement_start else None,
        "statement_end": bill.statement_end.isoformat() if bill.statement_end else None,
        "due_date": bill.due_date.isoformat() if bill.due_date else None,
        "paid_at": bill.paid_at.isoformat() if bill.paid_at else None,
        "notes": bill.notes or None,
        "source": bill.source,  # "manual" = typed by the user, "upload" = typed from a file
        "review_status": "confirmed",  # only bills the user saved are exported
        # Typed by a person: no evidence, so none is made up (null). Made from a
        # checked draft: where in the document each kept value was found.
        "evidence": evidence or None,
        "checks": money_checks(bill),  # numbers that don't add up, for a second look
    }


def accepted_evidence(user_id: int, bills: dict[int, Bill]) -> dict[int, dict]:
    """{bill_id: {field: [evidence]}} for bills made from accepted drafts.

    A field keeps its evidence only while the bill's CURRENT value is still the one
    the document showed. Edit the total in the bill editor afterwards, and the
    total loses its document evidence (the draft and its history stay as they were).
    """
    found = {}
    for draft in BillDraft.query.filter_by(user_id=user_id, status="accepted"):
        bill = bills.get(draft.bill_id)
        if bill is None:
            continue
        values = json.loads(draft.values_json)
        found[bill.id] = {name: v["evidence"] for name, v in values.items()
                          if v["origin"] == "document" and v["evidence"] and current_text(bill, name) == v["value"]}
    return found


def current_text(bill: Bill, name: str) -> str | None:
    """A bill field written the way drafts write it ("99000.00", "2026-10-18", "14:30")."""
    value = getattr(bill, name, None)
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, time):
        return value.strftime("%H:%M")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def export_rows() -> list[dict]:
    bills = Bill.query.filter_by(user_id=current_user.id, status="confirmed").order_by(Bill.id).all()
    evidence = accepted_evidence(current_user.id, {bill.id: bill for bill in bills})
    return [bill_json(bill, evidence.get(bill.id)) for bill in bills]


def safe_cell(value) -> str:
    """Spreadsheet apps run cells starting with = + - @ as formulas: make them plain text."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


@bp.route("/export.<fmt>")
@login_required
def export(fmt: str):
    rows = export_rows()
    if fmt == "json":
        body, kind = json.dumps(rows, ensure_ascii=False, indent=2), "application/json"
    elif fmt == "csv":
        out = io.StringIO()
        columns = list(rows[0] if rows else bill_json(Bill()))  # headers even with no bills
        writer = csv.writer(out)
        writer.writerow(columns)
        for row in rows:
            cells = [json.dumps(row[c], ensure_ascii=False) if isinstance(row[c], (list, dict)) else row[c]
                     for c in columns]
            writer.writerow([safe_cell(cell) for cell in cells])
        body, kind = "﻿" + out.getvalue(), "text/csv"  # ﻿: Excel then reads Vietnamese correctly
    elif fmt == "md":
        body, kind = markdown(rows), "text/markdown"
    else:
        return "Unknown format.", 404
    response = Response(body, content_type=f"{kind}; charset=utf-8")
    response.headers["Content-Disposition"] = f'attachment; filename="alloutfree-bills.{fmt}"'
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def md_text(value) -> str:
    """Markdown table cells: no line breaks, and | can't start a new column."""
    return "" if value is None else str(value).replace("\n", " ").replace("|", "\\|")


def markdown(rows: list[dict]) -> str:
    parts = ["# AllOutFree bills", ""]
    for row in rows:
        parts.append(f"## {md_text(row['merchant_name'])} — {md_text(row['transaction_datetime'] or row['invoice_date'] or row['due_date'] or 'no date')}")
        parts.append("")
        for key in ("kind", "invoice_number", "currency", "subtotal", "tax", "total", "category", "due_date", "paid_at"):
            if row[key] is not None:
                parts.append(f"- {key}: {md_text(row[key])}")
        if row["line_items"]:
            parts += ["", "| Item | Qty | Unit price | Amount |", "|---|---|---|---|"]
            for line in row["line_items"]:
                parts.append("| " + " | ".join(md_text(line[k]) for k in ("description", "quantity", "unit_price", "amount")) + " |")
        parts.append("")
    return "\n".join(parts)
