"""Exercise real HTTP forms on the dedicated SQL preview; no Flask test client."""

import io
import json
import re
import secrets
import sys
from decimal import Decimal
from html import unescape
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.sql_preview import DATABASE, INSTANCE, PORT, access_details

BASE = f"http://127.0.0.1:{PORT}"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


class Client:
    def __init__(self, account=None, record=None):
        self.account = account
        self.session = requests.Session()
        self.session.trust_env = False
        self.token = None
        self.record = record

    def request(self, method, path, **kwargs):
        import time
        require(path.startswith("/") and not path.startswith("//"), "Only relative preview paths allowed")
        start = time.perf_counter()
        try:
            result = self.session.request(method, BASE + path, timeout=15, allow_redirects=False, **kwargs)
            if self.record:
                self.record(method, path, result.status_code, (time.perf_counter() - start) * 1000)
            return result
        except Exception:
            if self.record:
                self.record(method, path, 0, (time.perf_counter() - start) * 1000)
            raise

    def get(self, path):
        return self.request("GET", path)

    def csrf(self, path="/login"):
        page = self.get(path)
        require(page.status_code == 200, "Cannot read CSRF form: " + path)
        match = re.search(r'name="csrf-token" content="([^"]+)"', page.text)
        if not match:
            match = re.search(r'name="csrf_token" value="([^"]+)"', page.text)
        require(match is not None, "Real HTML did not supply a CSRF token")
        self.token = unescape(match[1])
        return self.token

    def post(self, path, data=None, csrf=True, **kwargs):
        values = dict(data or {})
        if csrf:
            if not self.token:
                self.csrf()
            values["csrf_token"] = self.token
        return self.request("POST", path, data=values, **kwargs)

    def login(self):
        self.csrf()
        result = self.post("/login", {"identifier": self.account["username"], "password": self.account["password"]})
        require(result.status_code == 302, "Synthetic account login failed")
        self.csrf("/subscriptions/")  # login intentionally rotates the session
        return self


def health():
    response = Client().get("/__sql_preview__/health")
    require(response.status_code == 200, "SQL health failed")
    result = response.json()
    require(result["provider"] == "mssql" and result["database"] == DATABASE, "Wrong preview/database")
    return result


def exports(client):
    response = client.get("/bills/export.json")
    require(response.status_code == 200, "Bill JSON export failed")
    return response.json()


def follow_flash(client, response, text):
    require(response.status_code == 302, "Expected upload/form redirect")
    page = client.get(response.headers["Location"])
    require(text in page.text, "Expected validation message: " + text)


def synthetic_png(marker):
    """Keep repeated acceptance runs distinct without changing old documents."""
    from PIL import Image, PngImagePlugin
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("Synthetic acceptance run", marker)
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(buffer, "PNG", pnginfo=metadata)
    return buffer.getvalue()


def check_website():
    identity = health()
    details = access_details()
    a, b = [Client(account).login() for account in details["accounts"][:2]]
    marker = "web_" + secrets.token_hex(5)
    checks = []

    # Real registration, password validation, logout and no-token boundaries.
    visitor = Client()
    require(visitor.post("/register", {"username": marker}, csrf=False).status_code == 400, "Registration CSRF bypass")
    bad = visitor.post("/register", {"username": marker, "email": marker + "@example.com", "password": "weak", "confirm": "weak"})
    require(bad.status_code == 200, "Weak password was accepted")
    new_account = {"username": marker, "email": marker + "@example.com", "password": secrets.token_urlsafe(18) + "Aa1!"}
    require(visitor.post("/register", {**new_account, "confirm": new_account["password"]}).status_code == 302, "Registration failed")
    visitor.csrf("/subscriptions/")
    require(visitor.get("/logout").status_code == 405, "GET logout accepted")
    require(visitor.post("/logout", csrf=False).status_code == 400, "Logout CSRF bypass")
    require(visitor.post("/logout").status_code == 302, "Logout failed")
    require(visitor.get("/bills/").status_code == 302, "Logout left account data accessible")
    visitor.account = new_account
    visitor.login()
    checks.append("registration/password/logout/CSRF via real HTTP")

    initial = {row["currency"]: Decimal(row["monthly"]) for row in a.get("/dashboard.json").json()["projected"]}
    sub = {"name": marker + " plan", "amount": "0.10", "currency": "usd", "cycle": "monthly",
           "next_renewal_at": "2028-01-31", "lead_days": "14,7,3"}
    require(a.post("/subscriptions/new", sub, csrf=False).status_code == 400, "Subscription CSRF bypass")
    for amount, currency in [("0.10", "USD"), ("0.20", "USD"), ("12.34", "EUR")]:
        require(a.post("/subscriptions/new", {**sub, "name": marker + currency + amount, "amount": amount, "currency": currency}).status_code == 302, "Valid subscription failed")
    invalid = a.post("/subscriptions/new", {**sub, "next_renewal_at": "2028-02-30"})
    require(invalid.status_code == 200, "Invalid subscription date accepted")
    totals = {row["currency"]: Decimal(row["monthly"]) for row in a.get("/dashboard.json").json()["projected"]}
    require(totals["USD"] == initial["USD"] + Decimal("0.30"), "USD Decimal total mismatch")
    require(totals["EUR"] == initial.get("EUR", Decimal(0)) + Decimal("12.34"), "EUR mixed into USD")
    subs_page = a.get("/subscriptions/?q=" + marker)
    require("2028-01-31" in subs_page.text and marker not in b.get("/subscriptions/").text, "Subscription date/ownership failed")
    sub_id = int(re.search(r'/subscriptions/(\d+)/edit', subs_page.text)[1])
    require(b.get(f"/subscriptions/{sub_id}/edit").status_code == 404, "Other account opened subscription")
    require(b.post(f"/subscriptions/{sub_id}/archive").status_code == 404, "Other account changed subscription")
    checks.append("subscription dates/currencies/exact Decimal totals/isolation")

    link = {"url": "https://example.invalid/" + marker, "title": marker + " link", "tags": "synthetic"}
    require(a.post("/links/new", link).status_code == 302, "Link create failed")
    links = a.get("/links/?q=" + marker)
    link_id = int(re.search(r'/links/(\d+)/edit', links.text)[1])
    require(b.get(f"/links/{link_id}/edit").status_code == 404, "Other account opened link")
    require(b.post(f"/links/{link_id}/pin").status_code == 404, "Other account pinned link")
    require(marker not in b.get("/links/").text, "Link leaked")
    checks.append("saved link create/search/ownership; external fetch disabled")

    bill = {"merchant": marker + " receipt", "currency": "USD", "total": "9.99", "category": "food",
            "item_rows": "1", "item_name_1": "Synthetic item", "item_qty_1": "3", "item_price_1": "3.33"}
    require(a.post("/bills/new", bill).status_code == 302, "Bill create failed")
    row = next(row for row in exports(a) if row["merchant_name"] == bill["merchant"])
    bill_id = row["id"]
    require(row["line_items"][0]["amount"] == "9.99", "Line Decimal multiplication mismatch")
    require(a.post(f"/bills/{bill_id}/edit", {"notes": "SQL HTTP edit"}).status_code == 302, "Bill edit failed")
    bad = a.post(f"/bills/{bill_id}/edit", {**bill, "merchant": "Must not save", "item_qty_1": "9999999", "item_price_1": "99999999.99", "item_name_30": "Keep row thirty"})
    require(bad.status_code == 200 and "Keep row thirty" in bad.text, "Rejected bill edit lost later row")
    current = next(row for row in exports(a) if row["id"] == bill_id)
    require(current["merchant_name"] == bill["merchant"] and current["notes"] == "SQL HTTP edit", "Rejected edit persisted")
    for action in ["edit", "archive", "restore", "paid"]:
        require(b.post(f"/bills/{bill_id}/{action}", bill).status_code == 404, "Bill ownership failed")
        require(a.post(f"/bills/{bill_id}/{action}", bill, csrf=False).status_code == 400, "Bill CSRF failed")
    require(a.post(f"/bills/{bill_id}/archive").status_code == 302, "Archive failed")
    require(all(row["id"] != bill_id for row in exports(a)), "Archived bill still exported")
    require(a.post(f"/bills/{bill_id}/restore").status_code == 302, "Restore failed")
    require(any(row["id"] == bill_id for row in exports(a)), "Restored bill missing")
    checks.append("bill create/edit/lines/overflow rollback/archive/restore/CSRF/ownership")

    from pypdf import PdfWriter
    png = synthetic_png(marker)
    upload = a.post("/bills/upload", files={"file": ("synthetic.png", png, "image/png")})
    require(upload.status_code == 302, "Valid image upload failed")
    doc_id = int(parse_qs(urlsplit(upload.headers["Location"]).query)["document_id"][0])
    file = a.get(f"/bills/files/{doc_id}")
    require(file.content == png and "no-store" in file.headers["Cache-Control"], "Private file download mismatch")
    require(b.get(f"/bills/files/{doc_id}").status_code == 404, "File leaked across accounts")
    require(b.post("/bills/new", {**bill, "document_id": doc_id}).status_code == 404, "Other account attached file")
    require(a.post("/bills/new", {**bill, "merchant": marker + " file bill", "document_id": doc_id}).status_code == 302, "Owner file association failed")
    invalid_files = [(b"\x89PNG\r\n\x1a\ninvalid", "corrupt.png", "damaged"),
                     ((ROOT / "tests/fixtures/synthetic-six-page-compressed.pdf").read_bytes(), "six.pdf", "6 pages")]
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.encrypt("synthetic-only")
    output = io.BytesIO(); writer.write(output)
    invalid_files.append((output.getvalue(), "encrypted.pdf", "password"))
    for content, name, message in invalid_files:
        follow_flash(a, a.post("/bills/upload", files={"file": (name, content)}), message)
    require(a.post("/bills/upload", files={"file": ("csrf.png", png)}, csrf=False).status_code == 400, "Upload CSRF bypass")
    checks.append("decoded PNG/corrupt/compressed six-page/encrypted uploads/private download/file ownership")

    for suffix in ["json", "csv", "md"]:
        own = a.get("/bills/export." + suffix)
        other = b.get("/bills/export." + suffix)
        require(own.status_code == 200 and bill["merchant"] in own.text, "Bill export failed")
        require(marker not in other.text, "Export leaked another account")
    require(marker in a.get("/bills/?q=" + marker + "&category=food").text, "Bill search/filter failed")
    require("Page 2 of" in a.get("/bills/?page=2").text, "Bill pagination failed")
    require("Page 2 of" in a.get("/subscriptions/?page=2").text, "Subscription pagination failed")
    calendar = a.get("/calendar/renewals.ics")
    require(calendar.status_code == 200 and b"BEGIN:VEVENT\r\n" in calendar.content, "ICS export failed")
    require(b"SQL HTTP edit" not in calendar.content and "no-store" in calendar.headers["Cache-Control"], "ICS privacy failed")
    require(a.get("/calendar/").status_code == 200, "Calendar index failed")
    checks.append("search/filter/pagination/JSON/CSV/Markdown/Calendar/ICS/export ownership")
    state = {"marker": marker, "bill_id": bill_id, "document_id": doc_id, "link_id": link_id, "sub_id": sub_id}
    (INSTANCE / "sql-web-persistence.json").write_text(json.dumps(state, indent=2))
    result = {"identity": identity, "checks": checks, "passed_groups": len(checks), "failures": 0,
              "transport": "real loopback HTTP + real SQL Server", "synthetic_marker": marker}
    (INSTANCE / "sql-web-results.json").write_text(json.dumps(result, indent=2))
    print(json.dumps({"passed_groups": len(checks), "failures": 0, "provider": identity["provider"], "database": identity["database"]}))


def check_persistence():
    identity = health()
    state = json.loads((INSTANCE / "sql-web-persistence.json").read_text())
    a = Client(access_details()["accounts"][0]).login()
    require(any(row["id"] == state["bill_id"] for row in exports(a)), "Bill lost after preview restart")
    require(a.get(f"/bills/files/{state['document_id']}").status_code == 200, "File lost after restart")
    require(state["marker"] in a.get(f"/links/?q={state['marker']}").text, "Link lost after restart")
    require(state["marker"] in a.get(f"/subscriptions/?q={state['marker']}").text, "Subscription lost after restart")
    result = {"provider": identity["provider"], "database": identity["database"], "revision": identity["revision"],
              "preview_restart_persistence": "passed", "bill_file_link_subscription": "preserved"}
    (INSTANCE / "sql-persistence-results.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result))


if __name__ == "__main__":
    check_persistence() if "--persistence" in sys.argv else check_website()
