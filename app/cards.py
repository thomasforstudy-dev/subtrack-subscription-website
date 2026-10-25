"""The card holder on the Bills page: the user's credit and debit cards.

Only the first 6 digits and the last 4 are stored (see models.Card). The
card's network (Visa, Mastercard...) is worked out from the first digits,
and each card shows how much was spent with it this month, by matching the
last 4 digits saved on bills.

Every query filters by the logged-in user. Removing a card hides it
(removed_at) and keeps the row.
"""

import re
from collections import defaultdict
from decimal import Decimal

from flask import Blueprint, flash, redirect, request, url_for
from flask_login import current_user, login_required

from app import db
from app.models import Bill, Card, utcnow

bp = Blueprint("cards", __name__, url_prefix="/cards")

MAX_CARDS = 12
SIX_DIGITS = re.compile(r"^\d{6}$")
FOUR_DIGITS = re.compile(r"^\d{4}$")


def network_for(first6: str) -> str:
    """The card network from the first digits (the public IIN ranges)."""
    two, four = int(first6[:2]), int(first6[:4])
    if first6.startswith("9704"):
        return "napas"  # Vietnam's domestic network
    if first6.startswith("4"):
        return "visa"
    if 51 <= two <= 55 or 2221 <= four <= 2720:
        return "mastercard"
    if two in (34, 37):
        return "amex"
    if 3528 <= four <= 3589:
        return "jcb"
    if first6.startswith("62"):
        return "unionpay"
    return "card"


def masked_number(card: Card) -> str:
    """'4111 11•• •••• 1234': the digits we know, dots for the ones we never store."""
    return f"{card.first6[:4]} {card.first6[4:]}•• •••• {card.last4}"


def active_cards(user_id: int) -> list[Card]:
    return Card.query.filter_by(user_id=user_id, removed_at=None).order_by(Card.created_at, Card.id).all()


def card_rows(user_id: int, month_start, month_end) -> list[dict]:
    """Each card with how many bills used it and what it spent this month (per currency).

    Only receipts count as spending: a card statement repeats the same
    purchases, so adding it too would count them twice."""
    cards = active_cards(user_id)
    if not cards:
        return []
    last4s = {card.last4 for card in cards}
    bills = Bill.query.filter(
        Bill.user_id == user_id, Bill.status == "confirmed", Bill.card_last4.in_(last4s),
    ).all()
    count = defaultdict(int)
    month = defaultdict(lambda: defaultdict(Decimal))
    for bill in bills:
        count[bill.card_last4] += 1
        day = bill.transaction_date or bill.invoice_date
        if bill.kind == "receipt" and bill.total is not None and day and month_start <= day < month_end:
            month[bill.card_last4][bill.currency] += bill.total
    return [
        {
            "card": card,
            "network": network_for(card.first6),
            "number": masked_number(card),
            "bills": count[card.last4],
            "month": sorted(month[card.last4].items()),
        }
        for card in cards
    ]


@bp.post("/")
@login_required
def add():
    name = (request.form.get("name") or "").strip()[:60]
    first6 = re.sub(r"\s", "", request.form.get("first6") or "")
    last4 = re.sub(r"\s", "", request.form.get("last4") or "")
    kind = request.form.get("kind", "credit")
    color = request.form.get("color", "violet")

    if not SIX_DIGITS.match(first6) or not FOUR_DIGITS.match(last4):
        flash("Type the first 6 and the last 4 digits of the card, numbers only.", "error")
    elif len(active_cards(current_user.id)) >= MAX_CARDS:
        flash(f"The card holder fits {MAX_CARDS} cards. Remove one first.", "error")
    else:
        card = Card(
            user_id=current_user.id,
            name=name or network_for(first6).title() + " ··" + last4,
            kind=kind if kind in Card.KINDS else "credit",
            first6=first6,
            last4=last4,
            color=color if color in Card.COLORS else "violet",
        )
        db.session.add(card)
        db.session.commit()
        flash("Card added to your card holder.", "success")
    return redirect(url_for("bills.list_bills") + "#cards")


@bp.post("/<int:card_id>/remove")
@login_required
def remove(card_id: int):
    card = Card.query.filter_by(id=card_id, user_id=current_user.id, removed_at=None).first_or_404()
    card.removed_at = utcnow()
    db.session.commit()
    flash("Card removed from your card holder.", "success")
    return redirect(url_for("bills.list_bills") + "#cards")
