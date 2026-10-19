"""Renewal date rules: month ends, leap years, time zones."""

from datetime import date, datetime, timezone
from decimal import Decimal

from app.schedule import local_now, monthly_equivalent, next_renewal, passed_renewals


def test_monthly_on_the_31st_uses_the_last_day_then_goes_back():
    d = date(2027, 1, 31)
    d = next_renewal(d, "monthly", 31)
    assert d == date(2027, 2, 28)
    d = next_renewal(d, "monthly", 31)
    assert d == date(2027, 3, 31)  # doesn't drift to the 28th
    assert next_renewal(date(2027, 4, 30), "monthly", 31) == date(2027, 5, 31)


def test_leap_year_february():
    assert next_renewal(date(2028, 1, 31), "monthly", 31) == date(2028, 2, 29)
    assert next_renewal(date(2028, 2, 29), "yearly", 29) == date(2029, 2, 28)
    # Four years later it is back on the 29th.
    d = date(2028, 2, 29)
    for _ in range(4):
        d = next_renewal(d, "yearly", 29)
    assert d == date(2032, 2, 29)


def test_december_rolls_into_next_year():
    assert next_renewal(date(2026, 12, 15), "monthly", 15) == date(2027, 1, 15)


def test_weekly():
    assert next_renewal(date(2026, 12, 29), "weekly") == date(2027, 1, 5)


def test_passed_renewals_keep_history():
    passed, upcoming = passed_renewals(date(2028, 1, 31), "monthly", 31, today=date(2028, 3, 15))
    assert passed == [date(2028, 1, 31), date(2028, 2, 29)]
    assert upcoming == date(2028, 3, 31)


def test_renewal_today_is_not_passed():
    passed, upcoming = passed_renewals(date(2026, 11, 1), "monthly", 1, today=date(2026, 11, 1))
    assert passed == [] and upcoming == date(2026, 11, 1)


def test_monthly_equivalent_uses_decimal():
    assert monthly_equivalent(Decimal("120.00"), "yearly") == Decimal("10")
    assert monthly_equivalent(Decimal("12"), "weekly") == Decimal("52")
    assert monthly_equivalent(Decimal("0.10"), "monthly") + Decimal("0.20") == Decimal("0.30")


def test_local_date_depends_on_time_zone():
    late_utc = datetime(2026, 10, 31, 20, 0, tzinfo=timezone.utc)
    assert local_now("UTC", late_utc).date() == date(2026, 10, 31)
    assert local_now("Asia/Ho_Chi_Minh", late_utc).date() == date(2026, 11, 1)  # UTC+7
    assert local_now("America/Los_Angeles", late_utc).date() == date(2026, 10, 31)
    assert local_now("Not/AZone", late_utc).date() == date(2026, 10, 31)  # falls back to UTC


def test_dst_skipped_hour_and_repeated_hour_are_explicit():
    spring = [local_now("America/New_York", datetime(2026, 3, 8, hour, 30)) for hour in (6, 7)]
    assert [value.hour for value in spring] == [1, 3]  # no 02:30 local time that day
    autumn = [local_now("America/New_York", datetime(2026, 11, 1, hour, 30)) for hour in (5, 6)]
    assert [value.hour for value in autumn] == [1, 1]
    assert [value.fold for value in autumn] == [0, 1]
