"""After a bill is read: file it by itself when that is safe.

auto_file() runs inside the reading job's own transaction (bill_jobs.run_job),
so the draft, the bill and the plan are saved together or not at all.

- The draft becomes a real bill only when the shop, the total and a date were
  found in the document AND the values pass the same checks as the bill form
  (bills.read_form). Otherwise the draft waits for the owner, as before.
- Never twice: if a bill with the same shop, total and date is already saved
  (typed in by hand, or the same receipt photographed again), nothing is added.
- A repeating payment (Gemini's "plan" suggestion, e.g. Netflix monthly)
  becomes a plan with its next renewal date, checked by the plan form's own
  rules. The normal reminders (reminders.py) then email the owner before it
  renews, at the time and on the days set in their Settings. Only when the
  owner has no plan with that name yet.

The owner can still edit or archive what was filed; nothing is ever deleted.
"""

from sqlalchemy import func

from app import db
from app.bills import apply as apply_bill
from app.bills import read_form as read_bill_form
from app.models import Bill, BillDraftRevision, Subscription, User
from app.schedule import local_now, next_renewal, passed_renewals
from app.subscriptions import apply as apply_plan
from app.subscriptions import read_form as read_plan_form


def main_currency(user_id: int) -> str | None:
    """The currency of the owner's newest saved bill: used only when the
    document shows an amount but no currency sign (common on Vietnamese receipts)."""
    newest = Bill.query.filter_by(user_id=user_id, status="confirmed").order_by(Bill.id.desc()).first()
    return newest.currency if newest else None


def already_saved(user_id: int, values: dict, day) -> bool:
    return Bill.query.filter(
        Bill.user_id == user_id, Bill.status == "confirmed",
        func.lower(Bill.merchant) == values["merchant"].lower(), Bill.total == values["total"],
        func.coalesce(Bill.transaction_date, Bill.invoice_date, Bill.due_date) == day,
    ).first() is not None


def auto_file(job, draft, values: dict, suggested: dict, now) -> dict:
    """Try to save the draft as a bill (and its plan). Returns what was made:
    {"bill": Bill | None, "plan": Subscription | None}."""
    made = {"bill": None, "plan": None}
    form = {name: (item["value"] or "") for name, item in values.items()}
    form["category"] = suggested.get("category") or "other"
    form["timezone"] = ""
    if not form.get("currency") and form.get("total"):
        form["currency"] = main_currency(job.user_id) or ""
    if not (form.get("merchant") and form.get("total")
            and (form.get("transaction_date") or form.get("invoice_date") or form.get("due_date"))):
        return made

    checked, lines, error = read_bill_form(form)
    if error:
        return made  # the owner checks the draft, as before
    day = checked["transaction_date"] or checked["invoice_date"] or checked["due_date"]
    if already_saved(job.user_id, checked, day):
        return made

    bill = Bill(user_id=job.user_id, source="upload", document_id=job.document_id)
    apply_bill(bill, checked, lines)
    db.session.add(bill)
    db.session.flush()  # gives the bill its id
    draft.status, draft.bill_id, draft.revision = "accepted", bill.id, draft.revision + 1
    db.session.add(BillDraftRevision(draft_id=draft.id, user_id=job.user_id, number=draft.revision,
                                     action="auto-saved", changed="", values_json=draft.values_json,
                                     created_at=now))
    made["bill"] = bill
    made["plan"] = plan_from(bill, suggested.get("plan"), day)
    return made


def plan_from(bill: Bill, plan: dict | None, paid_on) -> Subscription | None:
    """A plan for a repeating payment, renewing one cycle after this payment
    (rolled forward to today or later, so no reminder is about the past)."""
    if not plan or bill.kind != "receipt":
        return None
    name, cycle = plan["service"], plan["cycle"]
    exists = Subscription.query.filter(Subscription.user_id == bill.user_id,
                                       func.lower(Subscription.name) == name.lower()).first()
    if exists:
        return None
    user = db.session.get(User, bill.user_id)
    today = local_now(user.timezone if user else None).date()
    _, renews = passed_renewals(next_renewal(paid_on, cycle), cycle, paid_on.day, today)
    values, error = read_plan_form({
        "name": name, "amount": str(bill.total), "currency": bill.currency, "cycle": cycle,
        "next_renewal_at": renews.isoformat(), "notes": f"Added from an uploaded bill ({bill.merchant[:100]}).",
    })
    if error:
        return None
    item = Subscription(user_id=bill.user_id)
    apply_plan(item, values)
    item.billing_day = paid_on.day  # paid on the 31st: renews on the 31st (or the month's last day)
    db.session.add(item)
    return item
