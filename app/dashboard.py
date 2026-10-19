"""Dashboard: what's renewing soon and roughly what it costs, per currency.

Two different kinds of money, never mixed:
- projected: what active subscriptions *should* cost per month/year.
- expected charges: renewal dates that have passed. Not proven payments:
  they stay "expected" until the user marks them paid or skipped.
Totals are never added across currencies (no exchange rates).
"""

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from flask import Blueprint, jsonify, render_template
from flask_login import current_user, login_required

from app.models import Renewal, Subscription
from app.schedule import local_now, monthly_equivalent

bp = Blueprint("dashboard", __name__)

UPCOMING_DAYS = 30
HISTORY_DAYS = 60
CENT = Decimal("0.01")


def active_subscriptions(user) -> list[Subscription]:
    return (
        Subscription.query.filter_by(user_id=user.id, status="active")
        .order_by(Subscription.next_renewal_at, Subscription.id)
        .all()
    )


def projected_totals(active: list[Subscription]) -> list[dict]:
    """One row per currency over ALL active subscriptions of the account
    (never just the page of the list that is showing)."""
    projected = defaultdict(lambda: {"count": 0, "monthly": Decimal(0)})
    for sub in active:
        projected[sub.currency]["count"] += 1
        projected[sub.currency]["monthly"] += monthly_equivalent(sub.amount, sub.cycle)
    return [
        {
            "currency": currency,
            "count": row["count"],
            "monthly": row["monthly"].quantize(CENT),
            "yearly": (row["monthly"] * 12).quantize(CENT),
        }
        for currency, row in sorted(projected.items())
    ]


def summary(user) -> dict:
    today = local_now(user.timezone).date()
    active = active_subscriptions(user)
    totals = projected_totals(active)
    upcoming = [s for s in active if s.next_renewal_at <= today + timedelta(days=UPCOMING_DAYS)]
    expected = (
        Renewal.query.filter_by(user_id=user.id)
        .filter(Renewal.due_date >= today - timedelta(days=HISTORY_DAYS))
        .order_by(Renewal.due_date.desc())
        .all()
    )
    return {"today": today, "totals": totals, "upcoming": upcoming, "expected": expected}


@bp.route("/dashboard")
@login_required
def show():
    data = summary(current_user)
    names = {s.id: s.name for s in Subscription.query.filter_by(user_id=current_user.id)}
    return render_template("dashboard.html", names=names, **data)


@bp.route("/dashboard.json")
@login_required
def as_json():
    """Same data for the extension / calendar (docs/CONTRACT.md).
    Money is a string like "9.99" so no decimals are lost; dates are ISO."""
    data = summary(current_user)
    return jsonify(
        today=data["today"].isoformat(),
        projected=[
            {**row, "monthly": str(row["monthly"]), "yearly": str(row["yearly"])}
            for row in data["totals"]
        ],
        upcoming=[
            {
                "id": s.id,
                "name": s.name,
                "amount": str(s.amount),
                "currency": s.currency,
                "cycle": s.cycle,
                "next_renewal_at": s.next_renewal_at.isoformat(),
                "days_left": (s.next_renewal_at - data["today"]).days,
                "manage_url": s.manage_url or None,
            }
            for s in data["upcoming"]
        ],
    )
