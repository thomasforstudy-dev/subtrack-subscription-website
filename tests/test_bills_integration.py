"""Real navigation and rendered controls must match the bills backend."""

from html.parser import HTMLParser

import pytest

from app import db
from app.models import Bill
from tests.html_helpers import Page
from tests.test_bills import RECEIPT


class Links(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.targets = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and attrs.get("data-nav-target") == "bills":
            self.targets.append(attrs.get("href"))


def test_bills_navigation_and_real_exports(user):
    for path in ("/dashboard", "/subscriptions/", "/bills/"):
        assert Links(user.get(path).get_data(as_text=True)).targets == ["/bills/"]
    page = user.get("/bills/").get_data(as_text=True)
    for suffix in ("json", "csv", "md"):
        assert f'/bills/export.{suffix}' in page


@pytest.mark.parametrize("count", [5, 30])
@pytest.mark.parametrize("error", ["total", "product"])
def test_every_rendered_control_survives_rejected_edit(user, app, count, error):
    user.post("/bills/new", data=RECEIPT)
    with app.app_context():
        bill_id = Bill.query.one().id
    original = Page(user.get(f"/bills/{bill_id}/edit").get_data(as_text=True)).form_with("merchant")["fields"]
    values = {**original, "currency": "USD", "merchant": "Keep rejected merchant"}
    for number in range(1, count + 1):
        values.update({f"item_name_{number}": f"Retain row {number}",
                       f"item_qty_{number}": "1", f"item_price_{number}": "3.25"})
    if error == "total":
        values["total"] = "NaN"
    else:
        values["item_qty_1"], values["item_price_1"] = "9999999", "99999999.99"
    response = user.post(f"/bills/{bill_id}/edit", data=values, csrf=False)
    assert response.status_code == 200
    fields = Page(response.get_data(as_text=True)).form_with("merchant")["fields"]
    assert fields["item_rows"] == "1" and fields["csrf_token"]
    for number in range(1, count + 1):
        for kind in ("name", "qty", "price"):
            key = f"item_{kind}_{number}"
            assert fields[key] == values[key]
    with app.app_context():
        assert Bill.query.one().merchant == RECEIPT["merchant"]


def test_bill_mutations_reject_missing_csrf(user, app):
    assert user.post("/bills/new", data=RECEIPT, csrf=False).status_code == 400
    user.post("/bills/new", data=RECEIPT)
    with app.app_context():
        bill_id = Bill.query.one().id
    for action in ("edit", "paid", "archive", "restore"):
        assert user.post(f"/bills/{bill_id}/{action}", data=RECEIPT, csrf=False).status_code == 400
