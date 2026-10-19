"""Renewal dates: plain date math, no database. Easy to test.

Rules
- weekly:  every 7 days.
- monthly: the same day each month. If that month is shorter, use its last
  day (a plan started on the 31st renews on 28/29 Feb, 30 Apr, then 31 May).
  `billing_day` remembers the real day (31), so short months don't make the
  date drift earlier forever.
- yearly:  the same date each year; 29 Feb renews on 28 Feb in other years
  and goes back to 29 Feb in leap years.

These dates are *expected* renewals. Reaching one doesn't mean a payment
happened: real charges come from bills/transactions the user confirms.
"""

import calendar
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

CYCLES = ("weekly", "monthly", "yearly")


def _clamp_day(year: int, month: int, day: int) -> date:
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last))


def next_renewal(current: date, cycle: str, billing_day: int | None = None) -> date:
    """The renewal after `current`."""
    if cycle == "weekly":
        return current + timedelta(days=7)
    day = billing_day or current.day
    if cycle == "monthly":
        year, month = (current.year + 1, 1) if current.month == 12 else (current.year, current.month + 1)
        return _clamp_day(year, month, day)
    if cycle == "yearly":
        return _clamp_day(current.year + 1, current.month, day)
    raise ValueError(f"Unknown cycle: {cycle}")


def passed_renewals(current: date, cycle: str, billing_day: int | None, today: date) -> tuple[list[date], date]:
    """Renewal dates before `today`, and the first one on or after it.

    Example: monthly on the 31st, current 31 Jan, today 15 Mar
    -> passed [31 Jan, 29 Feb], next 31 Mar.
    """
    passed = []
    while current < today:
        passed.append(current)
        current = next_renewal(current, cycle, billing_day)
    return passed, current


def monthly_equivalent(amount, cycle: str):
    """Roughly what a plan costs per month, for projections (Decimal in, Decimal out)."""
    from decimal import Decimal

    amount = Decimal(amount)
    if cycle == "weekly":
        return amount * 52 / 12
    if cycle == "yearly":
        return amount / 12
    return amount


def user_zone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def local_now(zone_name: str | None, now_utc: datetime | None = None) -> datetime:
    """The time right now where the user lives."""
    now_utc = now_utc or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    return now_utc.astimezone(user_zone(zone_name))
