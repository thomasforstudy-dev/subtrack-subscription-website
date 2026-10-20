"""Dashboard: what's renewing soon and roughly what it costs, per currency.

Two different kinds of money, never mixed:
- projected: what active subscriptions *should* cost per month/year.
- expected charges: renewal dates that have passed. Not proven payments:
  they stay "expected" until the user marks them paid or skipped.
Totals are never added across currencies (no exchange rates).
"""

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from flask import Blueprint, jsonify, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from app import db
from app.bills import WHOLE_NUMBER_CURRENCIES
from app.models import Bill, Link, Renewal, Subscription
from app.schedule import local_now, monthly_equivalent, next_renewal

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


CHART_MONTHS_BEFORE, CHART_MONTHS_AFTER = 3, 2  # 6 bars: 3 past months, this one, 2 ahead


def main_currency(active: list[Subscription]) -> str | None:
    """The currency most active plans use: the dashboard's big numbers and chart
    use it, so amounts in different currencies are never added together."""
    counts = defaultdict(int)
    for sub in active:
        counts[sub.currency] += 1
    return min(counts, key=lambda c: (-counts[c], c)) if counts else None


def month_start(day: date, shift: int = 0) -> date:
    index = day.year * 12 + day.month - 1 + shift
    return date(index // 12, index % 12 + 1, 1)


def chart(user, active: list[Subscription], currency: str, today: date) -> list[dict]:
    """Per month, in `currency`: renewals (passed ones from history, coming ones
    from each plan's schedule) and spending from confirmed receipts."""
    months = [month_start(today, shift) for shift in range(-CHART_MONTHS_BEFORE, CHART_MONTHS_AFTER + 1)]
    first, after = months[0], month_start(months[-1], 1)
    renewals = defaultdict(Decimal)
    for row in Renewal.query.filter_by(user_id=user.id, currency=currency) \
            .filter(Renewal.due_date >= first, Renewal.due_date < after, Renewal.status != "skipped"):
        renewals[month_start(row.due_date)] += row.amount
    for sub in active:  # coming renewals: step through each plan's own dates
        if sub.currency != currency:
            continue
        day = sub.next_renewal_at
        while day < after:
            if day >= first:
                renewals[month_start(day)] += sub.amount
            day = next_renewal(day, sub.cycle, sub.billing_day)
    spent = defaultdict(Decimal)
    when = func.coalesce(Bill.transaction_date, Bill.invoice_date)
    for bill_day, total in db.session.query(when, Bill.total).filter(
            Bill.user_id == user.id, Bill.status == "confirmed", Bill.kind == "receipt",
            Bill.currency == currency, Bill.total.isnot(None), when >= first, when < after):
        spent[month_start(bill_day)] += total
    top = max([*renewals.values(), *spent.values(), Decimal(0)])
    return [
        {"month": m, "renewals": renewals[m], "spent": spent[m], "this_month": m == month_start(today),
         "renewals_pct": int(renewals[m] * 100 / top) if top else 0,
         "spent_pct": int(spent[m] * 100 / top) if top else 0}
        for m in months
    ]


def activity(user, today: date, limit: int = 8) -> list[dict]:
    """The newest things that happened: bills saved, renewal dates passed, plans added."""
    items = []
    for bill in Bill.query.filter_by(user_id=user.id, status="confirmed").order_by(Bill.created_at.desc()).limit(limit):
        items.append({"when": bill.transaction_date or bill.invoice_date or bill.created_at.date(),
                      "title": bill.merchant, "kind": "card_bill" if bill.kind == "card_bill" else "receipt",
                      "amount": bill.total, "currency": bill.currency,
                      "status": ("paid" if bill.paid_at else "unpaid") if bill.kind == "card_bill" else "saved",
                      "url": url_for("bills.edit", bill_id=bill.id)})
    names = {s.id: s.name for s in Subscription.query.filter_by(user_id=user.id)}
    for row in Renewal.query.filter_by(user_id=user.id).filter(Renewal.due_date <= today) \
            .order_by(Renewal.due_date.desc()).limit(limit):
        items.append({"when": row.due_date, "title": names.get(row.subscription_id, "—"), "kind": "renewal",
                      "amount": row.amount, "currency": row.currency, "status": row.status,
                      "url": url_for("subscriptions.edit", item_id=row.subscription_id)})
    for sub in Subscription.query.filter_by(user_id=user.id).order_by(Subscription.created_at.desc()).limit(limit):
        items.append({"when": sub.created_at.date(), "title": sub.name, "kind": "new_plan",
                      "amount": sub.amount, "currency": sub.currency, "status": sub.status,
                      "url": url_for("subscriptions.edit", item_id=sub.id)})
    return sorted(items, key=lambda item: item["when"], reverse=True)[:limit]


def overview(user) -> dict:
    """Everything the dashboard shows, from the user's own data only."""
    data = summary(user)
    today = data["today"]
    hour = local_now(user.timezone).hour
    active = active_subscriptions(user)
    currency = main_currency(active)
    soon = [s for s in data["upcoming"] if s.next_renewal_at < today + timedelta(days=7)]
    data.update(
        greeting="morning" if hour < 12 else "afternoon" if hour < 18 else "evening",
        currency=currency,
        main_total=next((row for row in data["totals"] if row["currency"] == currency), None),
        other_totals=[row for row in data["totals"] if row["currency"] != currency],
        week=soon,
        week_total=sum((s.amount for s in soon if s.currency == currency), Decimal(0)),
        active_count=len(active),
        unpaid_cards=Bill.query.filter_by(user_id=user.id, status="confirmed", kind="card_bill", paid_at=None).count(),
        links_count=Link.query.filter_by(user_id=user.id).count(),
        spent_month=sum((total for (total,) in db.session.query(Bill.total).filter(
            Bill.user_id == user.id, Bill.status == "confirmed", Bill.kind == "receipt", Bill.currency == currency,
            Bill.total.isnot(None), func.coalesce(Bill.transaction_date, Bill.invoice_date) >= month_start(today),
            func.coalesce(Bill.transaction_date, Bill.invoice_date) < month_start(today, 1))),
            Decimal(0)),
        bars=chart(user, active, currency, today) if currency else [],
        activity=activity(user, today),
    )
    return data


@bp.app_template_filter("money")
def money_text(amount, currency: str | None = None) -> str:
    """398000 VND -> "398,000"; 20 USD -> "20.00" (no cents for currencies without them)."""
    if amount is None:
        return "—"
    return f"{amount:,.0f}" if currency in WHOLE_NUMBER_CURRENCIES else f"{amount:,.2f}"


@bp.route("/dashboard")
@login_required
def show():
    data = overview(current_user)
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
