"""Subscription pages: list (search, filter, sort, pages), add, edit, archive, restore."""

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from app import db
from app.links import normalize_url
from app.models import Renewal, Subscription
from app.schedule import local_now
from app.validation import escape_like

bp = Blueprint("subscriptions", __name__, url_prefix="/subscriptions")

PER_PAGE = 20
MAX_AMOUNT = Decimal("99999999.99")
MAX_LEADS = 3
SORTS = {
    "renewal": (Subscription.next_renewal_at, Subscription.id),
    "name": (Subscription.name, Subscription.id),
    "amount": (Subscription.amount.desc(), Subscription.id),
}
STATUSES = ("active", "archived", "all")


def user_today() -> date:
    """Today's date where the user lives (their time zone from Settings)."""
    return local_now(current_user.timezone).date()


@bp.route("/")
@login_required
def list_subscriptions():
    status = request.args.get("status", "active")
    status = status if status in STATUSES else "active"
    sort = request.args.get("sort", "renewal")
    sort = sort if sort in SORTS else "renewal"
    q = (request.args.get("q") or "").strip()[:100]

    query = Subscription.query.filter_by(user_id=current_user.id)
    if status != "all":
        query = query.filter_by(status=status)
    if q:
        like = f"%{escape_like(q)}%"
        query = query.filter(
            or_(Subscription.name.ilike(like, escape="\\"), Subscription.notes.ilike(like, escape="\\"))
        )
    pages = query.order_by(*SORTS[sort]).paginate(
        page=request.args.get("page", 1, type=int),
        per_page=PER_PAGE,
        error_out=False,
    )
    return render_template(
        "subscriptions/list.html",
        items=pages.items,
        pages=pages,
        status=status,
        sort=sort,
        q=q,
        today=user_today(),
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "POST":
        values, error = read_form(request.form)
        if error:
            flash(error)
            return render_template("subscriptions/form.html", item=None, form=request.form)
        item = Subscription(user_id=current_user.id)
        apply(item, values)
        db.session.add(item)
        db.session.commit()
        flash("Subscription saved.")
        return redirect(url_for("subscriptions.list_subscriptions"))
    return render_template("subscriptions/form.html", item=None, form={})


@bp.route("/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def edit(item_id: int):
    item = own_or_404(item_id)
    if request.method == "POST":
        values, error = read_form(request.form)
        if error:
            flash(error)
            return render_template("subscriptions/form.html", item=item, form=request.form)
        apply(item, values)
        db.session.commit()
        flash("Subscription updated.")
        return redirect(url_for("subscriptions.list_subscriptions"))
    return render_template("subscriptions/form.html", item=item, form={})


@bp.route("/<int:item_id>/archive", methods=["POST"])
@login_required
def archive(item_id: int):
    own_or_404(item_id).status = "archived"
    db.session.commit()
    flash("Archived. Reminders for it have stopped.")
    return redirect(url_for("subscriptions.list_subscriptions"))


@bp.route("/<int:item_id>/restore", methods=["POST"])
@login_required
def restore(item_id: int):
    own_or_404(item_id).status = "active"
    db.session.commit()
    flash("Restored.")
    return redirect(url_for("subscriptions.list_subscriptions", status="archived"))


@bp.route("/renewals/<int:renewal_id>", methods=["POST"])
@login_required
def mark_renewal(renewal_id: int):
    """Say whether an expected renewal was really paid (or skipped)."""
    renewal = Renewal.query.filter_by(id=renewal_id, user_id=current_user.id).first_or_404()
    status = request.form.get("status", "")
    if status not in Renewal.STATUSES:
        abort(400)
    renewal.status = status
    db.session.commit()
    return redirect(url_for("dashboard.show"))


def own_or_404(item_id: int) -> Subscription:
    # Filtering by user_id means nobody can open someone else's subscription by guessing an id.
    return Subscription.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()


def read_form(form) -> tuple[dict, str | None]:
    """Check every field. Returns (clean values, None) or ({}, a friendly error)."""
    name = (form.get("name") or "").strip()
    if not 1 <= len(name) <= 120:
        return {}, "Please give it a name (up to 120 characters)."

    amount = parse_amount(form.get("amount") or "0")
    if amount is None:
        return {}, "Please type the price as a number like 9.99 (dot for decimals, at most 2 decimals)."

    currency = (form.get("currency") or "USD").strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", currency):
        return {}, "Use a 3-letter currency code, like USD, EUR or VND."

    cycle = form.get("cycle") or "monthly"
    if cycle not in Subscription.CYCLES:
        return {}, "Pick weekly, monthly or yearly."

    try:
        renewal = date.fromisoformat(form.get("next_renewal_at") or "")
    except ValueError:
        return {}, "Please pick the next renewal date."
    if not date(2000, 1, 1) <= renewal <= date(2100, 12, 31):
        return {}, "That renewal date looks wrong. Please check the year."

    # "lead_days" is the new field ("14, 7, 3"); old forms send one "remind_days".
    leads = parse_leads(form.get("lead_days") or form.get("remind_days") or "7")
    if leads is None:
        return {}, f"Remind me: up to {MAX_LEADS} numbers of days from 0 to 365, like 14, 7, 3."

    manage_url = ""
    if (form.get("manage_url") or "").strip():
        manage_url, error = normalize_url(form["manage_url"])
        if error:
            return {}, "Manage link: " + error

    notes = (form.get("notes") or "").strip()
    if len(notes) > 2000:
        return {}, "Notes can be up to 2000 characters."

    return {
        "name": name, "amount": amount, "currency": currency, "cycle": cycle,
        "next_renewal_at": renewal, "leads": leads, "manage_url": manage_url, "notes": notes,
    }, None


def parse_amount(raw: str) -> Decimal | None:
    """Money is a Decimal, never a float (0.1 + 0.2 must be exactly 0.3)."""
    try:
        amount = Decimal(raw.strip())
    except InvalidOperation:
        return None
    if not amount.is_finite() or amount < 0 or amount > MAX_AMOUNT:
        return None
    if amount.as_tuple().exponent < -2:  # 9.999 has 3 decimals
        return None
    return amount.quantize(Decimal("0.01"))


def parse_leads(raw: str) -> list[int] | None:
    """"14, 7,3" -> [14, 7, 3]. None if anything is wrong."""
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not 1 <= len(parts) <= MAX_LEADS or not all(p.isdigit() for p in parts):
        return None
    days = sorted({int(p) for p in parts}, reverse=True)
    return days if all(0 <= d <= 365 for d in days) else None


def apply(item: Subscription, values: dict) -> None:
    if item.next_renewal_at != values["next_renewal_at"] or item.billing_day is None:
        item.billing_day = values["next_renewal_at"].day  # remember the real billing day
    item.name = values["name"]
    item.amount = values["amount"]
    item.currency = values["currency"]
    item.cycle = values["cycle"]
    item.next_renewal_at = values["next_renewal_at"]
    item.lead_days = ",".join(str(d) for d in values["leads"])
    item.remind_days = values["leads"][0]  # the biggest, for older pages and SQL views
    item.manage_url = values["manage_url"]
    item.notes = values["notes"]
    if item.status is None:
        item.status = "active"
