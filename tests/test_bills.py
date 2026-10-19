"""Bills: typing in receipts / card bills, private uploads, exports."""

import io
import json
import zipfile
from decimal import Decimal
from pathlib import Path

import pytest

from app import db, documents
from app.models import Bill, Document

from .conftest import sign_up

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200
RECEIPT = {
    "kind": "receipt", "merchant": "Highlands Coffee", "branch": "Takashimaya",
    "currency": "vnd", "transaction_date": "2026-10-18", "transaction_time": "",
    "subtotal": "90000", "tax": "9000", "total": "99000", "category": "food",
    "item_name_1": "Phin sữa đá", "item_qty_1": "2", "item_price_1": "45000",
    "item_name_2": "", "item_qty_2": "", "item_price_2": "",
}


def pdf(pages: int, extra: bytes = b"") -> bytes:
    body = b"".join(b"%d 0 obj << /Type /Page /Parent 1 0 R >> endobj\n" % n for n in range(pages))
    return b"%PDF-1.4\n1 0 obj << /Type /Pages >> endobj\n" + body + extra + b"%%EOF"


def docx(files: dict | None = None) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in (files or {"word/document.xml": b"<w:document/>"}).items():
            archive.writestr(name, content)
    return out.getvalue()


def upload(client, data: bytes, name="bill.png", **kwargs):
    return client.post("/bills/upload", data={"file": (io.BytesIO(data), name)},
                       content_type="multipart/form-data", **kwargs)


def only_bill(app) -> Bill:
    with app.app_context():
        bill = Bill.query.one()
        bill.lines  # load before the session closes
        return bill


# ---------- typing a bill in ---------------------------------------------------

def test_receipt_is_saved_with_lines_and_no_made_up_time(user, app):
    assert user.post("/bills/new", data=RECEIPT).status_code == 302
    bill = only_bill(app)
    assert (bill.merchant, bill.currency, bill.total) == ("Highlands Coffee", "VND", Decimal("99000.00"))
    assert bill.transaction_time is None  # the bill had no time: not 00:00
    assert [(line.description, line.amount) for line in bill.lines] == [("Phin sữa đá", Decimal("90000.00"))]
    assert bill.source == "manual"


@pytest.mark.parametrize("changes,message", [
    ({"merchant": ""}, "shop name"),
    ({"currency": "dollars"}, "3-letter"),
    ({"total": "9.999"}, "Total"),
    ({"total": "-5"}, "Total"),
    ({"transaction_time": "25:99"}, "Time"),
    ({"timezone": "Mars/Base"}, "time zone"),
    ({"item_qty_1": "0"}, "quantity"),
    ({"kind": "card_bill"}, "due date"),
    ({"kind": "card_bill", "due_date": "2026-11-05", "statement_start": "2026-10-31", "statement_end": "2026-10-01"}, "end before"),
])
def test_bad_values_are_friendly_errors(user, app, changes, message):
    page = user.post("/bills/new", data={**RECEIPT, **changes}).get_data(as_text=True)
    assert message in page
    with app.app_context():
        assert Bill.query.count() == 0


def test_full_card_number_is_refused_and_not_shown_back(user, app):
    card = {**RECEIPT, "kind": "card_bill", "merchant": "VPBank", "due_date": "2026-11-05",
            "card_last4": "4111 1111 1111 1111"}
    page = user.post("/bills/new", data=card).get_data(as_text=True)
    assert "last 4 digits" in page
    assert "4111 1111" not in page
    with app.app_context():
        assert Bill.query.count() == 0
    user.post("/bills/new", data={**card, "card_last4": "1111"})
    assert only_bill(app).card_last4 == "1111"


def test_card_bill_paid_and_unpaid(user, app):
    user.post("/bills/new", data={**RECEIPT, "kind": "card_bill", "merchant": "VPBank", "due_date": "2026-11-05"})
    bill_id = only_bill(app).id
    assert "Card bills to pay" in user.get("/bills/").get_data(as_text=True)
    user.post(f"/bills/{bill_id}/paid", data={"paid": "1"})
    assert only_bill(app).paid_at is not None
    user.post(f"/bills/{bill_id}/paid", data={"paid": "0"})
    assert only_bill(app).paid_at is None


def test_edit_keeps_what_the_form_did_not_send(user, app):
    user.post("/bills/new", data=RECEIPT)
    bill_id = only_bill(app).id
    # A simpler form: only a few fields and no item rows.
    user.post(f"/bills/{bill_id}/edit", data={"merchant": "Highlands", "currency": "VND"})
    bill = only_bill(app)
    assert bill.merchant == "Highlands" and bill.branch == "Takashimaya"
    assert bill.total == Decimal("99000.00") and len(bill.lines) == 1
    # Sent but empty = cleared on purpose.
    user.post(f"/bills/{bill_id}/edit", data={**RECEIPT, "branch": "", "item_name_1": ""})
    bill = only_bill(app)
    assert bill.branch == "" and bill.lines == []


def test_archive_and_restore_never_delete(user, app):
    user.post("/bills/new", data=RECEIPT)
    bill_id = only_bill(app).id
    user.post(f"/bills/{bill_id}/archive")
    assert only_bill(app).status == "archived"
    assert "Highlands" not in user.get("/bills/").get_data(as_text=True)
    user.post(f"/bills/{bill_id}/restore")
    assert only_bill(app).status == "confirmed"


def test_totals_are_per_currency(user, app):
    user.post("/bills/new", data=RECEIPT)
    user.post("/bills/new", data={**RECEIPT, "merchant": "Gucci", "currency": "USD", "total": "1200.50"})
    page = user.get("/bills/").get_data(as_text=True)
    assert "99000.00 VND" in page and "1200.50 USD" in page


def test_search_and_filters(user, app):
    user.post("/bills/new", data=RECEIPT)
    user.post("/bills/new", data={**RECEIPT, "merchant": "Qwerty Streaming", "category": "streaming"})
    page = user.get("/bills/?category=streaming").get_data(as_text=True)
    assert "Qwerty Streaming" in page and "Highlands" not in page
    page = user.get("/bills/?q=highl").get_data(as_text=True)
    assert "Highlands" in page and "Qwerty Streaming" not in page


# ---------- uploads ------------------------------------------------------------

def test_upload_is_stored_privately_under_a_random_name(user, app):
    res = upload(user, PNG, name="../../static/evil.png")
    assert res.status_code == 302 and "/bills/new?document_id=" in res.headers["Location"]
    with app.app_context():
        doc = Document.query.one()
        assert doc.original_name == "evil.png" and doc.kind == "png" and doc.page_count == 1
        stored = Path(app.instance_path) / "uploads" / doc.stored_name
    assert stored.read_bytes() == PNG
    assert "static" not in str(stored.relative_to(app.instance_path))
    # Typing the bill in from it links the two.
    user.post("/bills/new", data={**RECEIPT, "document_id": str(doc.id)})
    bill = only_bill(app)
    assert bill.document_id == doc.id and bill.source == "upload"


def test_same_file_twice_is_kept_once(user, app):
    upload(user, PNG)
    res = upload(user, PNG, name="again.png")
    assert "/bills/new?document_id=" in res.headers["Location"]
    with app.app_context():
        assert Document.query.count() == 1


@pytest.mark.parametrize("data,name,message", [
    (b"just text pretending", "bill.pdf", "Please upload a PNG"),
    (b"MZ\x90\x00 an exe", "bill.png", "Please upload a PNG"),
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 50, "old.doc", ".doc files"),
    (pdf(6), "long.pdf", "6 pages"),
    (pdf(1, b"/Encrypt 5 0 R"), "locked.pdf", "password"),
    (docx({"hello.txt": b"not word"}), "fake.docx", "Please upload a PNG"),
    (docx({"word/document.xml": b"\x00" * 3_000_000}), "bomb.docx", "too big once opened"),
    (b"PK\x03\x04 broken zip", "broken.docx", "damaged"),
    (b"", "empty.png", "That file is empty"),
])
def test_bad_files_are_refused(user, app, data, name, message):
    res = upload(user, data, name=name)
    assert res.status_code == 302
    assert message in user.get("/bills/").get_data(as_text=True)
    with app.app_context():
        assert Document.query.count() == 0


def test_good_pdf_and_docx_are_accepted(user, app):
    upload(user, pdf(2), name="statement.pdf")
    upload(user, docx(), name="invoice.docx")
    with app.app_context():
        assert sorted((d.kind, d.page_count) for d in Document.query) == [("docx", None), ("pdf", 2)]


def test_file_over_10_mb_is_refused(user, app, monkeypatch):
    monkeypatch.setattr(documents, "MAX_BYTES", 1000)
    upload(user, PNG + b"\x00" * 1000)
    assert "bigger than 10 MB" in user.get("/bills/").get_data(as_text=True)
    # Far too big: refused before it is even read.
    res = upload(user, PNG + b"\x00" * (12 * 1024 * 1024))
    assert res.status_code == 302
    with app.app_context():
        assert Document.query.count() == 0


def test_upload_needs_the_csrf_token(user):
    res = user.post("/bills/upload", data={"file": (io.BytesIO(PNG), "a.png")},
                    content_type="multipart/form-data", csrf=False)
    assert res.status_code == 400


def test_download_headers(user, app):
    upload(user, PNG)
    upload(user, pdf(1), name="b.pdf")
    with app.app_context():
        png_id, pdf_id = (d.id for d in Document.query.order_by(Document.id))
    shown = user.get(f"/bills/files/{png_id}?view=1")
    assert shown.data == PNG and "attachment" not in shown.headers.get("Content-Disposition", "")
    assert shown.headers["X-Content-Type-Options"] == "nosniff"
    assert "no-store" in shown.headers["Cache-Control"]
    # A PDF is never opened inside our site, even if asked.
    assert "attachment" in user.get(f"/bills/files/{pdf_id}?view=1").headers["Content-Disposition"]


def test_tampered_stored_name_cant_escape_the_folder(user, app):
    upload(user, PNG)
    with app.app_context():
        doc = Document.query.one()
        doc.stored_name = "../../app/__init__.py"
        db.session.commit()
        doc_id = doc.id
    assert user.get(f"/bills/files/{doc_id}").status_code == 404


# ---------- nobody sees anyone else's bills -----------------------------------

def test_other_users_cant_touch_my_bills_or_files(client, app):
    sign_up(client, "owner@example.com")
    client.post("/bills/new", data=RECEIPT)
    upload(client, PNG)
    with app.app_context():
        bill_id, doc_id = Bill.query.one().id, Document.query.one().id
    client.post("/logout")
    sign_up(client, "other@example.com")
    for path in [f"/bills/{bill_id}/edit", f"/bills/files/{doc_id}", f"/bills/new?document_id={doc_id}"]:
        assert client.get(path).status_code == 404, path
    for path in [f"/bills/{bill_id}/edit", f"/bills/{bill_id}/archive", f"/bills/{bill_id}/paid"]:
        assert client.post(path, data=RECEIPT).status_code == 404, path
    # Attaching someone else's file to my new bill is refused too.
    assert client.post("/bills/new", data={**RECEIPT, "document_id": str(doc_id)}).status_code == 404
    page = client.get("/bills/").get_data(as_text=True)
    assert "Highlands" not in page and "bill.png" not in page
    assert json.loads(client.get("/bills/export.json").data) == []
    with app.app_context():
        assert Bill.query.one().status == "confirmed"


# ---------- exports ------------------------------------------------------------

def test_json_export_is_the_standard_format(user):
    user.post("/bills/new", data=RECEIPT)
    [row] = json.loads(user.get("/bills/export.json").data)
    assert row["merchant_name"] == "Highlands Coffee" and row["merchant_branch"] == "Takashimaya"
    assert row["merchant_address"] is None and row["invoice_number"] is None  # not on the bill -> null
    assert row["transaction_datetime"] == "2026-10-18"  # date only, no fake time
    assert row["total"] == "99000.00" and isinstance(row["total"], str)
    assert row["line_items"][0] == {"description": "Phin sữa đá", "quantity": "2",
                                    "unit_price": "45000.00", "amount": "90000.00"}
    assert row["review_status"] == "confirmed"


def test_time_is_exported_when_the_bill_has_one(user):
    user.post("/bills/new", data={**RECEIPT, "transaction_time": "14:30", "timezone": "Asia/Ho_Chi_Minh"})
    [row] = json.loads(user.get("/bills/export.json").data)
    assert row["transaction_datetime"] == "2026-10-18T14:30" and row["timezone"] == "Asia/Ho_Chi_Minh"


def test_csv_export_is_safe_for_spreadsheets(user):
    user.post("/bills/new", data={**RECEIPT, "merchant": "=HYPERLINK(\"http://evil\")"})
    text = user.get("/bills/export.csv").get_data(as_text=True)
    assert "'=HYPERLINK" in text
    assert "merchant_name" in text.splitlines()[0]


def test_markdown_export_escapes_table_breaks(user):
    user.post("/bills/new", data={**RECEIPT, "item_name_1": "a | b"})
    text = user.get("/bills/export.md").get_data(as_text=True)
    assert "a \\| b" in text and "# SubTrack bills" in text


def test_unknown_export_format(user):
    assert user.get("/bills/export.exe").status_code == 404


def test_bills_pages_need_login(client):
    for path in ["/bills/", "/bills/new", "/bills/export.json"]:
        assert client.get(path).status_code == 302
