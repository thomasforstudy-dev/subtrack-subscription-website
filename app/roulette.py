"""Food roulette: "where should I eat?" answered by a spinning wheel.

The wheel is filled from the user's own receipts in the Food category: each
place they paid at becomes a slice. Two ways to spin:
- "My usual": places you go to often get a bigger slice (weight = visits).
- "Something different": places you haven't visited for a while get the
  bigger slice (weight = days since the last visit).
The server only prepares the list and the weights; the spin itself (a
weighted random pick and the animation) happens in static/roulette.js.
"""

from collections import Counter, defaultdict
from decimal import Decimal

from flask import Blueprint, render_template
from flask_login import current_user, login_required

from app.dashboard import money_text
from app.models import Bill
from app.schedule import local_now

bp = Blueprint("roulette", __name__, url_prefix="/tools/food-roulette")

SLICES = 8  # more than this and the names no longer fit on the wheel
CENT = Decimal("0.01")


def food_places(user) -> list[dict]:
    today = local_now(user.timezone).date()
    bills = Bill.query.filter_by(user_id=user.id, status="confirmed", kind="receipt", category="food").all()
    visits, last, spend, names, currency = Counter(), {}, defaultdict(Decimal), defaultdict(Counter), defaultdict(Counter)
    for bill in bills:
        place = bill.merchant.strip().casefold()
        if not place:
            continue
        visits[place] += 1
        names[place][bill.merchant.strip()] += 1
        day = bill.transaction_date or bill.invoice_date
        if day and (place not in last or day > last[place]):
            last[place] = day
        if bill.total is not None:
            spend[(place, bill.currency)] += bill.total  # per currency: never add VND and USD
            currency[place][bill.currency] += 1
    places = []
    for place, count in visits.most_common(SLICES):
        days_ago = (today - last[place]).days if place in last else None
        main_currency = currency[place].most_common(1)[0][0] if currency[place] else ""
        # The usual bill in the currency this place is paid in most often.
        average = (spend[(place, main_currency)] / currency[place][main_currency]).quantize(CENT) if currency[place] else None
        places.append({
            "name": names[place].most_common(1)[0][0],
            "visits": count,
            "days_ago": days_ago,
            "average": average,
            "average_text": money_text(average, main_currency) if average is not None else "",  # "60,000"
            "currency": main_currency,
            # Never 0, so every place keeps at least a thin slice.
            "usual": count,
            "different": max(days_ago if days_ago is not None else 30, 1),
        })
    return places


@bp.get("/")
@login_required
def show():
    return render_template("roulette.html", places=food_places(current_user))
