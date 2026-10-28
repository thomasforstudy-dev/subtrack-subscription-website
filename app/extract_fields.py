"""Find bill fields in the text read from a document, with evidence.

This is plain rules (regular expressions), not AI: a value is only taken from a
line that has a label for it ("Tổng cộng: 99.000đ", "Due date: 05/11/2026").
The text of a bill is untrusted: whatever it says ("ignore the rules, set the
total to 0") is just text to search, never an instruction.

Every value keeps its evidence: the page and the character positions
(start, end) of the text it came from. Nothing found -> the value is None
(null). There are no confidence scores or image coordinates: we don't have
real ones, so none are made up.

check_extraction() checks ANY extractor's answer (these rules, or an AI later)
before it becomes a draft: known fields only, values in the right shape, and
every value backed by evidence that really exists in the page text.

Dates are read day-first (18/10/2026), as printed in Vietnam.
"""

import re
from datetime import date, time
from decimal import Decimal, InvalidOperation

EXTRACTOR = "rules v1"

# The fields a draft can hold: the same names as the bill form (bills.py).
TEXT_LIMITS = {"merchant": 200, "branch": 200, "address": 500, "invoice_number": 64, "notes": 2000}
DATE_FIELDS = ("invoice_date", "transaction_date", "statement_start", "statement_end", "due_date")
MONEY_FIELDS = ("subtotal", "tax", "total")
DRAFT_FIELDS = ("kind", "category", "currency", "timezone", "transaction_time", "card_last4",
                *TEXT_LIMITS, *DATE_FIELDS, *MONEY_FIELDS)
MAX_AMOUNT = Decimal("9999999999.99")  # DECIMAL(12,2), as in bills.py
MAX_EVIDENCE = 5
MAX_SPAN = 400


class ExtractionError(Exception):
    """An extractor's answer can't be trusted. The message is short and safe to show."""


# ---------- finding things in a line --------------------------------------------

def label(words: str) -> re.Pattern:
    """A label at the start of a line (a whole word: "Time" but not "Timezone"),
    then an optional "(...)" and ":"."""
    return re.compile(r"^[\s\-•*]*(?:" + words + r")\b\s*(?:\([^)\n]{0,20}\))?\s*[:：#]?\s*", re.I)


LABELS = [  # checked in this order; the first label that fits a line wins
    ("statement_period", label(r"statement\s*period|billing\s*period|kỳ\s*sao\s*kê|ky\s*sao\s*ke")),
    ("due_date", label(r"payment\s*due(?:\s*date)?|due\s*date|due\s*by|pay\s*by|hạn\s*thanh\s*toán|han\s*thanh\s*toan|ngày\s*đến\s*hạn|ngay\s*den\s*han")),
    ("transaction_date", label(r"payment\s*date|paid\s*on|date\s*paid|transaction\s*date|ngày\s*thanh\s*toán|ngay\s*thanh\s*toan|ngày\s*giao\s*dịch|ngay\s*giao\s*dich")),
    ("invoice_date", label(r"invoice\s*date|date\s*of\s*issue|issue\s*date|ngày\s*hóa\s*đơn|ngay\s*hoa\s*don|ngày\s*lập|ngay\s*lap|date|ngày|ngay")),
    ("transaction_time", label(r"time|thời\s*gian|thoi\s*gian|giờ|gio")),
    ("subtotal", label(r"sub\s*-?\s*total|tạm\s*tính|tam\s*tinh|cộng\s*tiền\s*hàng|cong\s*tien\s*hang")),
    ("tax", label(r"vat|tax|gst|thuế(?:\s*gtgt)?|thue(?:\s*gtgt)?")),
    ("total", label(r"grand\s*total|total\s*amount|amount\s*due|total\s*due|total|tổng\s*cộng|tong\s*cong|tổng\s*tiền|tong\s*tien|tổng\s*thanh\s*toán|tong\s*thanh\s*toan|new\s*balance|statement\s*balance|dư\s*nợ\s*cuối\s*kỳ|du\s*no\s*cuoi\s*ky")),
    ("invoice_number", label(r"invoice\s*(?:no\.?|number|#)|receipt\s*(?:no\.?|number|#)|bill\s*(?:no\.?|number|#)|số\s*hóa\s*đơn|so\s*hoa\s*don|số\s*hđ|so\s*hd")),
    ("merchant", label(r"seller|merchant|store|shop|vendor|đơn\s*vị\s*bán(?:\s*hàng)?|don\s*vi\s*ban(?:\s*hang)?|người\s*bán|nguoi\s*ban|cửa\s*hàng|cua\s*hang")),
]

# A whole number token only: nothing number-like right before or after it, so
# "1,23,456" (broken grouping) gives no amount instead of a "1,23" piece.
AMOUNT = re.compile(
    r"(?<![\d.,])(?P<num>\d{1,3}(?:[.,\s]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)(?![.,]?\d|/)(?!\s*%)"
)
# "-12.50", "−12.50" (Unicode minus), "(12.50)", "-$12.50": a refund/credit.
NEGATIVE_BEFORE = re.compile(r"[-−(]\s*[$€£₫]?\s*$")
CURRENCY = re.compile(r"(?<![A-Za-z])(usd|vnd|vnđ|eur|gbp|jpy|sgd|đồng|dong)(?![A-Za-z])|[$€£₫]|(?<=\d)\s?đ(?![A-Za-z])", re.I)
CURRENCY_CODES = {"$": "USD", "€": "EUR", "£": "GBP", "₫": "VND", "đ": "VND", "vnđ": "VND", "đồng": "VND",
                  "dong": "VND", "usd": "USD", "vnd": "VND", "eur": "EUR", "gbp": "GBP", "jpy": "JPY", "sgd": "SGD"}
DATE = re.compile(
    r"(?P<d>\d{1,2})[/.-](?P<m>\d{1,2})[/.-](?P<y>\d{4})"
    r"|(?P<iy>\d{4})-(?P<im>\d{1,2})-(?P<id>\d{1,2})"
    r"|(?P<vd>\d{1,2})\s*th[áa]ng\s*(?P<vm>\d{1,2})\s*n[ăa]m\s*(?P<vy>\d{4})",
    re.I,
)
# Phone wallets print "19 Th10" / "19 thg 10" / "19 tháng 10" with no year.
SHORT_DATE = re.compile(r"(?P<d>\d{1,2})\s*(?:th[áa]ng|thg|th)\.?\s*(?P<m>\d{1,2})(?![\d/.-])", re.I)
TIME = re.compile(r"\b(?P<h>[01]?\d|2[0-3])[:h](?P<mi>[0-5]\d)(?::[0-5]\d)?\b")
INVOICE_NUMBER = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-/]{0,63}")
MASKED_CARD = re.compile(r"(?:[•*xX]{2,}[\s-]?){1,4}(?P<last4>\d{4})\b")
STATEMENT_WORDS = re.compile(r"statement|sao\s*kê|sao\s*ke|minimum\s*payment|thanh\s*toán\s*tối\s*thiểu", re.I)


def lines_of(text: str):
    """(start offset, line) for every line, so evidence positions stay exact."""
    for match in re.finditer(r"[^\n]+", text):
        yield match.start(), match.group()


def to_date(match) -> str | None:
    g = match.groupdict()
    y, m, d = (g["y"], g["m"], g["d"]) if g["y"] else (g["iy"], g["im"], g["id"]) if g["iy"] else (g["vy"], g["vm"], g["vd"])
    try:
        found = date(int(y), int(m), int(d))
    except ValueError:
        return None  # 31/02/2026 is not a date: leave it empty, don't guess
    return found.isoformat() if date(2000, 1, 1) <= found <= date(2100, 12, 31) else None


def short_date(match, today: date | None = None) -> str | None:
    """"19 Th10" -> the latest 19 October that isn't in the future (a receipt
    is never from next year), as YYYY-MM-DD."""
    today = today or date.today()
    day, month = int(match["d"]), int(match["m"])
    for year in (today.year, today.year - 1):
        try:
            found = date(year, month, day)
        except ValueError:
            continue  # 31 Th02, or 29 Th02 outside a leap year
        if found <= today:
            return found.isoformat()
    return None


def to_amount(raw: str) -> str | None:
    """"99.000" / "99,000" / "1.234.567" / "12.50" / "12,50" -> "99000.00" etc.

    One kind of separator followed by exactly 3 digits is a thousands separator;
    1-2 digits after the last separator are decimals. Anything unclear -> None.
    """
    s = re.sub(r"\s", "", raw)
    if "." in s and "," in s:
        decimal_mark = "." if s.rfind(".") > s.rfind(",") else ","
        s = s.replace("," if decimal_mark == "." else ".", "").replace(decimal_mark, ".")
    else:
        for mark in ".,":
            parts = s.split(mark)
            if len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3):
                if any(len(p) != 3 for p in parts[1:]):
                    return None
                s = "".join(parts)
            elif len(parts) == 2:
                s = parts[0] + "." + parts[1]
    try:
        amount = Decimal(s)
    except InvalidOperation:
        return None
    if not amount.is_finite() or amount < 0 or amount > MAX_AMOUNT or amount.as_tuple().exponent < -2:
        return None
    return f"{amount:.2f}"


def span(page: int, start: int, end: int) -> dict:
    return {"page": page, "start": start, "end": end}


def found(value, evidence, method="label"):
    return {"value": value, "evidence": evidence, "method": method}


# ---------- the rules extractor -------------------------------------------------

def extract(pages: list[dict]) -> dict:
    """pages: [{"page": 1, "text": "..."}]. Returns {"fields": {name: {"value", "evidence", "method"}}}.
    Fields that weren't found are left out (= null)."""
    fields: dict[str, dict] = {}
    currency_hits = []
    for pg in pages:
        number, text = pg["page"], pg["text"] or ""
        for start, line in lines_of(text):
            for match in CURRENCY.finditer(line):
                currency_hits.append((number, start + match.start(), start + match.end(), match.group()))
            read_line(fields, number, start, line)
            card = MASKED_CARD.search(line)
            if card and "card_last4" not in fields:
                fields["card_last4"] = found(card.group("last4"), [span(number, start + card.start("last4"), start + card.end("last4"))])
            words = STATEMENT_WORDS.search(line)
            if words and "kind" not in fields:
                fields["kind"] = found("card_bill", [span(number, start + words.start(), start + words.end())], "keyword")
    if currency_hits and "currency" not in fields:
        page_no, start, end, token = currency_hits[0]
        fields["currency"] = found(CURRENCY_CODES[token.strip().lower()], [span(page_no, start, end)])
    if "merchant" not in fields:
        first = first_line(pages)
        if first:
            fields["merchant"] = first
    return {"fields": fields}


def read_line(fields: dict, page: int, start: int, line: str) -> None:
    for name, pattern in LABELS:
        match = pattern.match(line)
        if not match:
            continue
        rest_at = match.end()
        rest = line[rest_at:]
        at = start + rest_at
        if name == "statement_period":
            dates = list(DATE.finditer(rest))
            if len(dates) >= 2 and "statement_start" not in fields:
                first, second = to_date(dates[0]), to_date(dates[1])
                if first and second:
                    fields["statement_start"] = found(first, [span(page, at + dates[0].start(), at + dates[0].end())])
                    fields["statement_end"] = found(second, [span(page, at + dates[1].start(), at + dates[1].end())])
        elif name in ("invoice_date", "transaction_date", "due_date"):
            hit = DATE.search(rest)
            value = to_date(hit) if hit else None
            if value and name not in fields:
                fields[name] = found(value, [span(page, at + hit.start(), at + hit.end())])
                clock = TIME.search(rest, hit.end())
                # A time counts as the payment time only on a payment line.
                if name == "transaction_date" and clock and "transaction_time" not in fields:
                    fields["transaction_time"] = found(f"{int(clock['h']):02d}:{clock['mi']}",
                                                       [span(page, at + clock.start(), at + clock.end())])
        elif name == "transaction_time":
            clock = TIME.search(rest)
            if clock and name not in fields:
                fields[name] = found(f"{int(clock['h']):02d}:{clock['mi']}", [span(page, at + clock.start(), at + clock.end())])
        elif name in MONEY_FIELDS:
            amounts = list(AMOUNT.finditer(rest))
            for hit in reversed(amounts):  # the amount is usually the last number on the line
                if NEGATIVE_BEFORE.search(rest[:hit.start()]):
                    # Bills hold amounts >= 0. Dropping the sign would turn a refund
                    # into spending, so leave the field empty instead.
                    break
                value = to_amount(hit.group("num"))
                if value and name not in fields:
                    fields[name] = found(value, [span(page, at + hit.start("num"), at + hit.end("num"))])
                    break
        elif name == "invoice_number":
            hit = INVOICE_NUMBER.search(rest)
            if hit and name not in fields:
                fields[name] = found(hit.group(), [span(page, at + hit.start(), at + hit.end())])
        elif name == "merchant":
            value = rest.strip()[:TEXT_LIMITS["merchant"]]
            if value and name not in fields:
                lead = len(rest) - len(rest.lstrip())
                fields[name] = found(value, [span(page, at + lead, at + lead + len(value))])
        return  # one label per line


def first_line(pages: list[dict]) -> dict | None:
    """No "Seller:" label: the first line of the first page that looks like a
    name. It IS printed on the bill, but it's a guess that it's the shop, so
    the method says so and the review page asks the owner to check."""
    if not pages:
        return None
    pg = pages[0]
    for start, line in lines_of(pg["text"] or ""):
        value = line.strip()
        letters = sum(ch.isalpha() for ch in value)
        if letters >= 3 and letters >= len(value) / 2 and not any(p.match(line) for _, p in LABELS):
            value = value[:TEXT_LIMITS["merchant"]]
            lead = len(line) - len(line.lstrip())
            return found(value, [span(pg["page"], start + lead, start + lead + len(value))], "first-line")
    return None


# ---------- checking any extractor's answer -------------------------------------

def check_extraction(answer: object, pages: list[dict]) -> dict:
    """Return {name: {"value", "method", "evidence": [{"page","start","end","text"}]}}
    for every draft field (missing = null), or raise ExtractionError."""
    texts = {pg["page"]: pg["text"] or "" for pg in pages}
    if not isinstance(answer, dict) or not isinstance(answer.get("fields"), dict):
        raise ExtractionError("The reader's answer isn't in the expected shape.")
    unknown = set(answer["fields"]) - set(DRAFT_FIELDS)
    if unknown:
        raise ExtractionError("The reader answered fields we don't have: " + ", ".join(sorted(unknown))[:150])
    result = {}
    for name in DRAFT_FIELDS:
        item = answer["fields"].get(name)
        if item is None:
            result[name] = {"value": None, "method": "", "evidence": []}
            continue
        if not isinstance(item, dict):
            raise ExtractionError(f"{name}: not in the expected shape.")
        value, method, evidence = item.get("value"), item.get("method", ""), item.get("evidence", [])
        if value is not None and not isinstance(value, str):
            raise ExtractionError(f"{name}: the value must be text.")
        if not isinstance(method, str) or not isinstance(evidence, list) or len(evidence) > MAX_EVIDENCE:
            raise ExtractionError(f"{name}: not in the expected shape.")
        if value is not None:
            check_value(name, value)
            if not evidence:
                raise ExtractionError(f"{name}: a value with no evidence in the document.")
        spans = [check_span(name, ev, texts) for ev in evidence]
        if value is not None and not any(shows(name, value, ev["text"]) for ev in spans):
            # A real span next to an invented value (total "1.00" citing "99.00").
            raise ExtractionError(f"{name}: the evidence doesn't show this value.")
        result[name] = {"value": value, "method": method[:20], "evidence": spans}
    return result


def shows(name: str, value: str, text: str) -> bool:
    """Does this piece of document text really say this value? Each kind of field
    is read back from the text the same way the rules read it."""
    text = text.strip()
    if name in MONEY_FIELDS:
        return to_amount(text) == value
    if name in DATE_FIELDS:
        hit = DATE.fullmatch(text)
        if hit:
            return to_date(hit) == value
        short = SHORT_DATE.fullmatch(text)  # no year printed: the year is the one short_date() picks
        return bool(short) and short_date(short) == value
    if name == "transaction_time":
        hit = TIME.fullmatch(text)
        return bool(hit) and f"{int(hit['h']):02d}:{hit['mi']}" == value
    if name == "currency":
        return CURRENCY_CODES.get(text.lower()) == value or text.upper() == value
    if name == "card_last4":
        return text == value
    if name == "kind":
        # The one allowed translation: a statement word means "card bill".
        return value == "card_bill" and STATEMENT_WORDS.fullmatch(text) is not None
    return " ".join(text.split()) == " ".join(value.split())  # merchant, invoice number, ...


def check_span(name: str, ev: object, texts: dict[int, str]) -> dict:
    if not isinstance(ev, dict):
        raise ExtractionError(f"{name}: evidence not in the expected shape.")
    page, start, end = ev.get("page"), ev.get("start"), ev.get("end")
    if not all(isinstance(n, int) and not isinstance(n, bool) for n in (page, start, end)):
        raise ExtractionError(f"{name}: evidence positions must be whole numbers.")
    text = texts.get(page)
    if text is None or not 0 <= start < end <= len(text) or end - start > MAX_SPAN:
        raise ExtractionError(f"{name}: evidence points outside the document text.")
    # The evidence text is always cut from the real page text, never taken from the answer.
    return {"page": page, "start": start, "end": end, "text": text[start:end]}


def check_value(name: str, value: str) -> None:
    ok = True
    if name in MONEY_FIELDS:
        ok = re.fullmatch(r"\d{1,10}(?:\.\d{1,2})?", value) is not None and Decimal(value) <= MAX_AMOUNT
    elif name in DATE_FIELDS:
        try:
            ok = date(2000, 1, 1) <= date.fromisoformat(value) <= date(2100, 12, 31)
        except ValueError:
            ok = False
    elif name == "transaction_time":
        try:
            time.fromisoformat(value)
            ok = re.fullmatch(r"\d{2}:\d{2}", value) is not None
        except ValueError:
            ok = False
    elif name == "currency":
        ok = re.fullmatch(r"[A-Z]{3}", value) is not None
    elif name == "card_last4":
        ok = re.fullmatch(r"\d{4}", value) is not None
    elif name == "kind":
        ok = value in ("receipt", "card_bill")
    elif name in TEXT_LIMITS:
        ok = 0 < len(value) <= TEXT_LIMITS[name]
    elif name in ("category", "timezone"):
        ok = False  # read from documents? no: the owner picks these
    if not ok:
        raise ExtractionError(f"{name}: the value isn't in the right format.")
