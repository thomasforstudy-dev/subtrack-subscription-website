"""The only things Subby may look up or prepare in someone's account.

How it works (simple on purpose, the same for Gemini and Phi):
1. The model reads the question. If it needs the user's own data, it replies
   with one line:  [TOOL] {"name": "list_upcoming_renewals", "args": {"days": 30}}
2. The server checks that line: the name must be in TOOLS, every argument must
   be known and valid. Anything else is refused and nothing runs.
3. The server runs the tool for the LOGGED-IN user (current_user, from the
   session). The model can't pick the user: a "user_id" argument is refused.
4. The server writes the answer itself from the results. The results never go
   back to the model, so private data doesn't leave the server and text inside
   saved links or notes can't give the model new orders (prompt injection).

No tool writes to the database. create_reminder_draft only fills in the
normal "Add subscription" form; the user checks it and presses Save.
"""

import json
from datetime import date, timedelta
from decimal import Decimal
from urllib.parse import urlencode

from flask import url_for
from sqlalchemy import or_

from app.models import Link, Renewal, Subscription
from app.schedule import local_now
from app.validation import escape_like

TOOL_MARK = "[TOOL]"
MAX_ROWS = 10  # never return a whole table


class ToolError(Exception):
    """The model asked for something not allowed. The message is safe to show."""


# ---------- checking arguments --------------------------------------------------

def whole_number(value, low: int, high: int, label: str) -> int:
    # bool is a kind of int in Python, so refuse it on purpose.
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ToolError(f"{label} must be a whole number from {low} to {high}.")
    return value


def short_text(value, high: int, label: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= high:
        raise ToolError(f"{label} must be text of 1 to {high} characters.")
    return value.strip()


REQUIRED = object()  # marks an argument that has no default


def check_args(args: dict, schema: dict) -> dict:
    """schema = {"days": (checker, default or REQUIRED)}. Unknown keys are refused."""
    unknown = set(args) - set(schema)
    if unknown:
        raise ToolError("I can't use these settings: " + ", ".join(sorted(unknown)))
    clean = {}
    for key, (checker, default) in schema.items():
        if key in args:
            clean[key] = checker(args[key])
        elif default is REQUIRED:
            raise ToolError(f"I need the {key.replace('_', ' ')}.")
        elif default is not None:
            clean[key] = default
    return clean


# ---------- the tools -----------------------------------------------------------

def list_upcoming_renewals(user, days: int) -> dict:
    today = local_now(user.timezone).date()
    rows = (
        Subscription.query.filter_by(user_id=user.id, status="active")
        .filter(Subscription.next_renewal_at <= today + timedelta(days=days))
        .order_by(Subscription.next_renewal_at, Subscription.id)
        .limit(MAX_ROWS)
        .all()
    )
    items = [
        {
            "name": s.name, "amount": str(s.amount), "currency": s.currency,
            "next_renewal_at": s.next_renewal_at.isoformat(),
            "days_left": (s.next_renewal_at - today).days,
        }
        for s in rows
    ]
    if not items:
        answer = f"Nothing renews in the next {days} days."
    else:
        lines = [f"- {i['name']}: {i['amount']} {i['currency']} on {i['next_renewal_at']}" for i in items]
        answer = f"Renewing in the next {days} days:\n" + "\n".join(lines)
    return {"answer": answer, "data": {"days": days, "items": items}}


def search_saved_links(user, query: str) -> dict:
    like = f"%{escape_like(query)}%"
    rows = (
        Link.query.filter_by(user_id=user.id)
        .filter(or_(
            Link.title.ilike(like, escape="\\"), Link.url.ilike(like, escape="\\"),
            Link.tags.ilike(like, escape="\\"), Link.notes.ilike(like, escape="\\"),
        ))
        .order_by(Link.is_pinned.desc(), Link.created_at.desc())
        .limit(MAX_ROWS)
        .all()
    )
    items = [{"title": link.title, "url": link.url} for link in rows]
    if not items:
        answer = f"I couldn't find a saved link matching \u201c{query}\u201d."
    else:
        answer = f"Saved links matching \u201c{query}\u201d:\n" + "\n".join(f"- {i['title']}" for i in items)
    return {"answer": answer, "data": {"query": query, "items": items}}


def summarize_transactions(user, days: int) -> dict:
    """Renewal charges of the last `days` days, per currency and status.

    These are renewal dates that passed (from the reminder job), not bank
    transactions: "expected" means not confirmed as paid yet.
    """
    today = local_now(user.timezone).date()
    rows = (
        Renewal.query.filter_by(user_id=user.id)
        .filter(Renewal.due_date > today - timedelta(days=days), Renewal.due_date <= today)
        .all()
    )
    totals: dict[tuple[str, str], Decimal] = {}
    for r in rows:
        key = (r.currency, r.status)
        totals[key] = totals.get(key, Decimal(0)) + r.amount
    items = [
        {"currency": currency, "status": status, "total": str(total)}
        for (currency, status), total in sorted(totals.items())
    ]
    if not items:
        answer = f"No renewal charges in the last {days} days."
    else:
        lines = [f"- {i['total']} {i['currency']} {i['status']}" for i in items]
        answer = (
            f"Renewal charges in the last {days} days (\u201cexpected\u201d = not marked paid yet):\n"
            + "\n".join(lines)
        )
    return {"answer": answer, "data": {"days": days, "items": items}}


def create_reminder_draft(user, **draft) -> dict:
    """Fill in the Add subscription form. Nothing is saved until the user presses Save
    there, and that form checks every field again."""
    confirm_url = url_for("subscriptions.create") + "?" + urlencode(draft)
    return {
        "answer": f"I filled in a reminder for \u201c{draft['name']}\u201d. Please check it and press Save.",
        "data": {"draft": draft},
        "confirm_url": confirm_url,
    }


def iso_date(value) -> str:
    try:
        day = date.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        day = None
    if day is None or not date(2000, 1, 1) <= day <= date(2100, 12, 31):
        raise ToolError("The date must look like 2026-11-30.")
    return day.isoformat()


def one_of(choices):
    def check(value):
        if value not in choices:
            raise ToolError("Pick one of: " + ", ".join(choices))
        return value
    return check


def money(value) -> str:
    # Only digits and one dot; the form itself checks the range and decimals.
    text = value if isinstance(value, str) else ""
    if not text or len(text) > 12 or text.count(".") > 1 or not text.replace(".", "").isdigit():
        raise ToolError("The price must look like 9.99.")
    return text


def currency(value) -> str:
    if not isinstance(value, str) or len(value) != 3 or not value.isalpha() or not value.isascii():
        raise ToolError("Use a 3-letter currency code, like USD.")
    return value.upper()


# The allowlist: name -> (function, argument rules). Nothing else can run.
TOOLS = {
    "list_upcoming_renewals": (
        list_upcoming_renewals,
        {"days": (lambda v: whole_number(v, 1, 90, "days"), 30)},
    ),
    "search_saved_links": (
        search_saved_links,
        {"query": (lambda v: short_text(v, 100, "query"), REQUIRED)},
    ),
    "summarize_transactions": (
        summarize_transactions,
        {"days": (lambda v: whole_number(v, 1, 366, "days"), 30)},
    ),
    "create_reminder_draft": (
        create_reminder_draft,
        {
            "name": (lambda v: short_text(v, 120, "name"), REQUIRED),
            "amount": (money, None),
            "currency": (currency, None),
            "cycle": (one_of(Subscription.CYCLES), None),
            "next_renewal_at": (iso_date, None),
        },
    ),
}

TOOL_HELP = f"""
Tools: the user is logged in. If the question needs THEIR OWN data, reply with
exactly one line and nothing else:
{TOOL_MARK} {{"name": "<tool>", "args": {{...}}}}
- list_upcoming_renewals  args: days (1-90, default 30)
- search_saved_links      args: query (text, required)
- summarize_transactions  args: days (1-366, default 30) - renewal charges, paid or expected
- create_reminder_draft   args: name (required), amount ("9.99"), currency ("USD"),
                          cycle (weekly/monthly/yearly), next_renewal_at ("YYYY-MM-DD")
Use only these tools and only these args. Never invent data; if no tool fits, answer normally."""


# ---------- reading the model's reply ------------------------------------------

def find_tool_call(text: str) -> dict | None:
    """Return {"name", "args"} if the model asked for a tool, None if it just answered.

    Raises ToolError if it tried to call a tool but the line is broken.
    """
    if TOOL_MARK not in text:
        return None
    rest = text.split(TOOL_MARK, 1)[1].strip().strip("`").strip()
    try:
        call, _ = json.JSONDecoder().raw_decode(rest)
    except ValueError:
        raise ToolError("I got muddled preparing that.") from None
    if not isinstance(call, dict) or not isinstance(call.get("name"), str):
        raise ToolError("I got muddled preparing that.")
    args = call.get("args", {})
    if not isinstance(args, dict):
        raise ToolError("I got muddled preparing that.")
    return {"name": call["name"], "args": args}


def run_tool(user, call: dict) -> dict:
    """Check the call against the allowlist and run it for `user` only."""
    if call["name"] not in TOOLS:
        raise ToolError("That's not something I'm allowed to do.")
    function, schema = TOOLS[call["name"]]
    return function(user, **check_args(call["args"], schema))
