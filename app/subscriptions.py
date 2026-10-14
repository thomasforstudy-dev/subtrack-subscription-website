from datetime import date, datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.models import Subscription

bp = Blueprint("subscriptions", __name__, url_prefix="/subscriptions")


@bp.route("/")
@login_required
def list_subscriptions():
    items = (
        Subscription.query.filter_by(user_id=current_user.id, status="active")
        .order_by(Subscription.next_renewal_at)
        .all()
    )
    today = date.today()
    return render_template("subscriptions/list.html", items=items, today=today)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "POST":
        item = _subscription_from_form()
        item.user_id = current_user.id
        db.session.add(item)
        db.session.commit()
        flash("Subscription saved.")
        return redirect(url_for("subscriptions.list_subscriptions"))
    return render_template("subscriptions/form.html", item=None)


@bp.route("/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def edit(item_id: int):
    item = Subscription.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    if request.method == "POST":
        _fill_subscription(item)
        db.session.commit()
        flash("Subscription updated.")
        return redirect(url_for("subscriptions.list_subscriptions"))
    return render_template("subscriptions/form.html", item=item)


@bp.route("/<int:item_id>/archive", methods=["POST"])
@login_required
def archive(item_id: int):
    item = Subscription.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    item.status = "archived"
    db.session.commit()
    flash("Archived.")
    return redirect(url_for("subscriptions.list_subscriptions"))


def _subscription_from_form() -> Subscription:
    item = Subscription()
    _fill_subscription(item)
    return item


def _fill_subscription(item: Subscription) -> None:
    item.name = (request.form.get("name") or "").strip()[:120] or "Untitled"
    amount = request.form.get("amount") or "0"
    try:
        item.amount = max(0, min(round(float(amount), 2), 99_999_999.99))
    except ValueError:
        item.amount = 0
    item.currency = (request.form.get("currency") or "USD").strip().upper()[:8]
    cycle = request.form.get("cycle") or "monthly"
    item.cycle = cycle if cycle in Subscription.CYCLES else "monthly"
    raw_date = request.form.get("next_renewal_at")
    item.next_renewal_at = (
        datetime.strptime(raw_date, "%Y-%m-%d").date() if raw_date else date.today()
    )
    try:
        remind_days = int(request.form.get("remind_days") or 7)
    except ValueError:
        remind_days = 7
    item.remind_days = max(0, min(remind_days, 365))
    item.notes = request.form.get("notes") or ""
    item.status = "active"
