"""Real SQL Server month-window/dashboard/404 checks on the fixed synthetic preview."""

import calendar
import json
import secrets
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.sql_preview import DATABASE, INSTANCE, build_app, restrict_file

SOURCE_MAIN = "4e086799ccd2d34e03ba6efb8fdbc3dbc7ba21d1"


def next_month(day, billing_day):
    year, month = (day.year + 1, 1) if day.month == 12 else (day.year, day.month + 1)
    return date(year, month, min(billing_day, calendar.monthrange(year, month)[1]))


def check_case(app, instant, marker, label):
    from app import dashboard, db
    from app.links import url_fingerprint
    from app.models import Bill, Link, Renewal, Subscription, User, utcnow

    today = instant.astimezone(ZoneInfo("Pacific/Kiritimati")).date()
    first = date(today.year, today.month, 1)
    after = next_month(first, 1)
    months = [dashboard.month_start(today, n) for n in range(-3, 3)]
    end = next_month(months[-1], 1)
    accounts = [{"username": f"dash_{marker}_{label}_{n}", "password": secrets.token_urlsafe(18) + "Aa1!"}
                for n in range(2)]
    errors = []

    def check(condition, message):
        if not condition:
            errors.append(message)

    with app.app_context():
        owners = []
        for account in accounts:
            user = User(username=account["username"], email=account["username"] + "@example.com",
                        timezone="Pacific/Kiritimati", email_verified_at=utcnow(), reminders_enabled=False)
            user.set_password(account["password"])
            db.session.add(user)
            owners.append(user)
        db.session.flush()
        a, b = owners
        last = date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
        specifications = [("monthly", "10.01", "USD", today + timedelta(days=2)),
                          ("monthly", "0.10", "USD", last),
                          ("yearly", "120.00", "USD", today + timedelta(days=4)),
                          ("monthly", "7.00", "EUR", today + timedelta(days=3))]
        plans = []
        for index, (cycle, amount, currency, due) in enumerate(specifications):
            plan = Subscription(user_id=a.id, name=f"{marker}_{label}_owner_plan_{index}",
                                amount=Decimal(amount), currency=currency, cycle=cycle,
                                next_renewal_at=due, billing_day=due.day, lead_days="7", remind_days=7)
            db.session.add(plan)
            plans.append(plan)
        db.session.add(Subscription(user_id=b.id, name=marker + "_OTHER_SECRET_PLAN", amount=Decimal("9999"),
            currency="USD", cycle="monthly", next_renewal_at=today, billing_day=today.day, lead_days="7"))
        db.session.add(Subscription(user_id=a.id, name=marker + "_archived_plan", amount=Decimal("8888"),
            currency="USD", cycle="monthly", next_renewal_at=today, billing_day=today.day,
            status="archived", lead_days="7"))
        db.session.flush()
        expected_renewals = {m: Decimal(0) for m in months}
        for cycle, amount, currency, due in specifications:
            if currency != "USD":
                continue
            day = due
            while day < end:
                if day >= months[0]:
                    expected_renewals[day.replace(day=1)] += Decimal(amount)
                day = next_month(day, due.day) if cycle == "monthly" else date(day.year + 1, day.month, day.day)
        db.session.add(Renewal(user_id=a.id, subscription_id=plans[0].id, due_date=months[2],
                              amount=Decimal("12.34"), currency="USD", status="paid"))
        expected_renewals[months[2]] += Decimal("12.34")
        db.session.add(Renewal(user_id=a.id, subscription_id=plans[0].id, due_date=months[1],
                              amount=Decimal("999"), currency="USD", status="skipped"))

        # The two current-month receipts prove Decimal addition and invoice fallback.
        # A transaction date takes precedence over an invoice date when both exist.
        bill_specs = [("decimal_a", "0.10", first, None, "USD", "confirmed", "receipt"),
                      ("invoice_fallback", "0.20", None, first + timedelta(days=1), "USD", "confirmed", "receipt"),
                      ("date_precedence", "7.00", first - timedelta(days=1), first, "USD", "confirmed", "receipt"),
                      ("first_chart_day", "1.11", months[0], None, "USD", "confirmed", "receipt"),
                      ("before_chart", "999", months[0] - timedelta(days=1), None, "USD", "confirmed", "receipt"),
                      ("next_month", "13.37", after, None, "USD", "confirmed", "receipt"),
                      ("last_chart_day", "3.33", end - timedelta(days=1), None, "USD", "confirmed", "receipt"),
                      ("after_chart", "999", end, None, "USD", "confirmed", "receipt"),
                      ("other_currency", "999", first, None, "EUR", "confirmed", "receipt"),
                      ("archived", "999", first, None, "USD", "archived", "receipt"),
                      ("unpaid_card", "100", first, None, "USD", "confirmed", "card_bill"),
                      ("no_date", "5", None, None, "USD", "confirmed", "receipt")]
        expected_spent = {m: Decimal(0) for m in months}
        for name, total, transaction, invoice, currency, status, kind in bill_specs:
            db.session.add(Bill(user_id=a.id, merchant=f"{marker}_{label}_{name}", total=Decimal(total),
                                currency=currency, transaction_date=transaction, invoice_date=invoice,
                                status=status, kind=kind))
            bill_day = transaction or invoice
            if currency == "USD" and status == "confirmed" and kind == "receipt" and bill_day and months[0] <= bill_day < end:
                expected_spent[bill_day.replace(day=1)] += Decimal(total)
        db.session.add(Bill(user_id=b.id, merchant=marker + "_OTHER_SECRET_SHOP", total=Decimal("9999"),
                            currency="USD", transaction_date=first))
        link = "https://example.invalid/" + marker + label
        db.session.add(Link(user_id=a.id, title=marker + " owned link", url=link, url_hash=url_fingerprint(link)))
        db.session.commit()
        owner_id, other_id, sub_id = a.id, b.id, plans[0].id

    real_now = dashboard.local_now
    with app.test_request_context(), patch("app.dashboard.local_now", lambda zone: real_now(zone, instant)):
        a = db.session.get(User, owner_id)
        data = dashboard.overview(a)
        bars = {bar["month"]: bar for bar in data["bars"]}
        check(data["today"] == today, "Local day/time zone mismatch")
        check(data["currency"] == "USD" and data["active_count"] == 4, "Currency/active-account isolation failed")
        check(data["main_total"]["monthly"] == Decimal("20.11"), "Projected Decimal total mismatch")
        check(data["other_totals"][0]["monthly"] == Decimal("7.00"), "Currencies were mixed")
        check(data["spent_month"] == Decimal("0.30"),
              f"Spent this month is {data['spent_month']}; expected 0.30 (future months must be excluded)")
        check(data["unpaid_cards"] == 1 and data["links_count"] == 1, "Owner-scoped count mismatch")
        check(list(bars) == months, "Six-month/year/leap window mismatch")
        top = max([*expected_renewals.values(), *expected_spent.values()])
        for month in months:
            check(bars[month]["spent"] == expected_spent[month], f"Receipt/date/coalesce boundary mismatch at {month}")
            check(bars[month]["renewals"] == expected_renewals[month], f"Renewal projection/history mismatch at {month}")
            check(bars[month]["spent_pct"] == int(expected_spent[month] * 100 / top), "Spent chart percentage mismatch")
        when = db.func.coalesce(Bill.transaction_date, Bill.invoice_date)
        raw = db.session.query(when, Bill.total).filter(Bill.user_id == owner_id, Bill.total == Decimal("0.10")).one()
        check(type(raw[0]) is date and isinstance(raw[1], Decimal), "SQL driver did not preserve Date/Decimal types")
        check(all("OTHER_SECRET" not in item["title"] for item in data["activity"]), "Activity leaked another account")
        spent_month = str(data["spent_month"])
    return {"label": label, "instant_utc": instant.isoformat(), "local_day": str(today),
            "coalesce_type": "date", "money_type": "Decimal", "spent_month": spent_month,
            "expected_spent_month": "0.30", "bars": 6, "failures": errors}, accounts, sub_id


def website_checks(accounts, sub_id, marker):
    from scripts.sql_web_checks import Client, health, require
    identity = health()
    a, b = [Client(account).login() for account in accounts]
    page = a.get("/dashboard")
    require(page.status_code == 200 and "AllOutFree" in page.text and "bar-col" in page.text,
            "Actual SQL-backed dashboard HTML/chart failed")
    require("OTHER_SECRET" not in page.text, "Dashboard HTML leaked another account")
    require(a.get("/dashboard.json").status_code == 200, "Dashboard JSON failed")
    guest = Client()
    for client, path, back in [(guest, "/sql-missing-" + marker, "Back to the home page"),
                               (a, "/sql-missing-" + marker, "Back to the dashboard"),
                               (b, f"/subscriptions/{sub_id}/edit", "Back to the dashboard")]:
        response = client.get(path)
        require(response.status_code == 404 and "mascot-lost" in response.text and back in response.text,
                "Friendly missing/private-item 404 failed on SQL")
        # The signed-in user's own username contains the run marker in the header.
        require(marker + "_web_owner_plan" not in response.text and "OTHER_SECRET" not in response.text,
                "404 disclosed another account's record")
    response = b.get("/bills/jobs/2000000000.json")
    require(response.status_code == 404 and "mascot" not in response.text, "JSON-address plain 404 changed")
    return {"identity": identity, "dashboard_html_chart_json": "passed",
            "guest_authenticated_private_item_404": "passed", "json_address_plain_404": "passed"}


def main():
    from sqlalchemy import text
    app = build_app()
    from app import db
    with app.app_context():
        provider = db.engine.dialect.name
        actual = db.session.execute(text("SELECT DB_NAME()")).scalar_one()
        if provider != "mssql" or actual != DATABASE:
            raise RuntimeError("Wrong SQL validation target")
    marker = secrets.token_hex(4)
    instants = [("web", datetime.now(timezone.utc)),
                ("jan", datetime(2026, 1, 30, 12, 30, tzinfo=timezone.utc)),
                ("leap", datetime(2028, 2, 29, 5, tzinfo=timezone.utc)),
                ("year", datetime(2026, 12, 31, 11, 30, tzinfo=timezone.utc))]
    cases, accounts, first_sub = [], None, None
    for label, instant in instants:
        case, pair, sub_id = check_case(app, instant, marker, label)
        cases.append(case)
        if label == "web":
            accounts, first_sub = pair, sub_id
    access = INSTANCE / ("sql-dashboard-logins-" + marker + ".json")
    access.touch(exist_ok=False)
    restrict_file(access)
    access.write_text(json.dumps({"database": DATABASE, "accounts": accounts}, indent=2), encoding="utf-8")
    report = {"provider": provider, "database": actual, "source_main": SOURCE_MAIN,
              "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip(),
              "dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT).strip()),
              "scope": "Actual SQL Server queries; fixed clocks for boundary cases, not SQLite",
              "cases": cases, "owner_login_file": str(access), "owner_subscription_id": first_sub}
    if "--sql-only" not in sys.argv:
        report["website"] = website_checks(accounts, first_sub, marker)
    report["failures"] = [failure for case in cases for failure in case["failures"]]
    (INSTANCE / "sql-dashboard-results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"provider": provider, "database": actual, "boundary_cases": len(cases),
                      "failures": report["failures"], "website": "not run" if "--sql-only" in sys.argv else "passed"}))
    if report["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
