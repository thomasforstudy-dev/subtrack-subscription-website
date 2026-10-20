"""OCR: reading the text in photos and scanned PDF pages.

OCR_PROVIDER in .env picks the reader:
  (empty) / none -> no OCR. Photos and scans can't be read automatically; the
                    job says "OCR isn't available" and the owner types the bill in.
  got            -> GOT-OCR 2.0 running on the owner's own PC as a small private
                    web service (OCR_BASE_URL, with OCR_API_KEY as a shared secret).
                    It turns the file's pages into text. Nothing is downloaded or
                    started from here, and the address is never public.

FakeOcr exists for the tests only: it returns text the test gives it. It can't
be chosen in .env, so the live site can never "read" a bill it didn't read.
"""

import os
from dataclasses import dataclass

import requests

TIMEOUT = 90  # seconds: a 5-page scan on a 6 GB GPU
MAX_CHARS = 20_000  # per page, the same limit as doc_text.py


class OcrUnavailable(Exception):
    """OCR can't run right now. .code is short and safe to store:
    not-set-up, offline, busy, bad-reply or http-NNN."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass
class OcrPage:
    number: int
    text: str
    truncated: bool = False


@dataclass
class OcrResult:
    engine: str  # model name + revision, saved next to the text
    pages: list[OcrPage]


class OcrAdapter:
    name = "base"

    def read(self, data: bytes, kind: str, pages: list[int]) -> OcrResult:
        """Read these pages (1 = first) of the file. Raises OcrUnavailable."""
        raise NotImplementedError


class GotOcr(OcrAdapter):
    name = "got-ocr"

    def __init__(self):
        self.base_url = os.getenv("OCR_BASE_URL", "").strip().rstrip("/")
        self.key = os.getenv("OCR_API_KEY", "").strip()

    def read(self, data, kind, pages):
        if not self.base_url or not self.key:
            raise OcrUnavailable("not-set-up")
        try:
            res = requests.post(
                f"{self.base_url}/v1/ocr",
                headers={"Authorization": f"Bearer {self.key}"},
                files={"file": ("bill", data)},
                data={"kind": kind, "pages": ",".join(str(p) for p in pages)},
                timeout=TIMEOUT,
            )
        except requests.RequestException:
            raise OcrUnavailable("offline") from None  # the PC is off or asleep
        if res.status_code in (429, 503):
            raise OcrUnavailable("busy")
        if not res.ok:
            raise OcrUnavailable(f"http-{res.status_code}")
        try:
            answer = res.json()
        except ValueError:
            raise OcrUnavailable("bad-reply") from None
        return check_reply(answer, pages)


def check_reply(answer: object, asked: list[int]) -> OcrResult:
    """Accept only {"model": str, "revision": str, "pages": [{"page": n, "text": str,
    "truncated": bool}]} for pages we asked about. Anything else is "bad-reply"."""
    if not isinstance(answer, dict):
        raise OcrUnavailable("bad-reply")
    model, revision, pages = answer.get("model"), answer.get("revision"), answer.get("pages")
    if not isinstance(model, str) or not isinstance(revision, str) or not isinstance(pages, list):
        raise OcrUnavailable("bad-reply")
    result = []
    for item in pages:
        if not isinstance(item, dict):
            raise OcrUnavailable("bad-reply")
        number, text, cut = item.get("page"), item.get("text"), item.get("truncated", False)
        if (isinstance(number, bool) or not isinstance(number, int) or number not in asked
                or not isinstance(text, str) or not isinstance(cut, bool)):
            raise OcrUnavailable("bad-reply")
        result.append(OcrPage(number, text[:MAX_CHARS], cut or len(text) > MAX_CHARS))
    if len({p.number for p in result}) != len(result):
        raise OcrUnavailable("bad-reply")  # the same page twice
    return OcrResult(f"{model[:40]} {revision[:30]}".strip(), result)


class FakeOcr(OcrAdapter):
    """For tests: returns the given text, or raises the given problem."""

    name = "fake-ocr"

    def __init__(self, pages: dict[int, str] | None = None, problem: str | None = None):
        self.pages = pages or {}
        self.problem = problem
        self.calls = 0

    def read(self, data, kind, pages):
        self.calls += 1
        if self.problem:
            raise OcrUnavailable(self.problem)
        return OcrResult("fake-ocr test", [OcrPage(n, self.pages.get(n, "")) for n in pages])


def ocr_adapter() -> OcrAdapter | None:
    """The configured reader, or None when there is no OCR."""
    chosen = os.getenv("OCR_PROVIDER", "").strip().lower()
    return GotOcr() if chosen == "got" else None
