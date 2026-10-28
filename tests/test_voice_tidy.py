"""Subby's mic: tidying Vietnamese transcripts (static/voice-tidy.js) and
the detailed Vietnamese instructions Gemini gets for recordings."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app import ai_providers

ROOT = Path(__file__).resolve().parent.parent
TIDY_JS = ROOT / "app" / "static" / "voice-tidy.js"

# (language, what the browser heard, what goes in the question box)
CASES = [
    ("vi", "ừm netflix của tôi bao giờ gia hạn", "Netflix của tôi bao giờ gia hạn?"),
    ("vi", "thêm gói nét phích 260 nghìn một tháng", "Thêm gói Netflix 260.000 một tháng."),
    ("vi", "thêm spotify 1 triệu rưỡi một năm", "Thêm Spotify 1.500.000 một năm."),
    ("vi", "gói du túp premium giá 1 triệu 2", "Gói YouTube Premium giá 1.200.000."),
    ("vi", "chát gi pi ti 1 triệu 2 tháng", "ChatGPT 1.000.000 2 tháng."),  # "for 2 months", not 1.200.000
    ("vi", "tôi trả 10 đô cho icloud", "Tôi trả 10 USD cho iCloud."),
    ("vi", "sống ở đô thị", "Sống ở đô thị."),  # "đô thị" is a city, not dollars
    ("vi", "ờ tại sao gu gồ oan bị trừ 45k", "Tại sao Google One bị trừ 45.000?"),
    ("vi", "tháng này tôi tiêu bao nhiêu", "Tháng này tôi tiêu bao nhiêu?"),
    ("vi", "gói này hết hạn chưa", "Gói này hết hạn chưa?"),
    ("vi", "tôi chưa bao giờ dùng canva", "Tôi chưa bao giờ dùng Canva."),  # "never": not a question
    ("vi", "nhắc tôi trước 3 ngày", "Nhắc tôi trước 3 ngày."),
    ("vi", "Tháng này tôi tiêu bao nhiêu?", "Tháng này tôi tiêu bao nhiêu?"),  # already tidy: unchanged
    ("vi", "các gói của tôi", "Các gói của tôi."),  # decomposed marks -> NFC
    ("en", "when does netflix renew", "When does Netflix renew?"),
    ("en", "add youtube for 260k", "Add YouTube for 260k."),  # money rules are Vietnamese only
]


def run_node(script: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed")
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(out.stdout)


def test_tidy_fixes_vietnamese_transcripts():
    script = f"""
      const V = require({json.dumps(str(TIDY_JS))});
      const cases = {json.dumps(CASES, ensure_ascii=False)};
      console.log(JSON.stringify(cases.map(([lang, heard]) => {{
        const once = V.tidy(heard, lang);
        return [once, V.tidy(once, lang)];
      }})));
    """
    results = run_node(script)
    for (lang, heard, expected), (once, twice) in zip(CASES, results):
        assert once == expected, heard
        assert twice == once, f"tidying twice changed {heard!r}"  # subby.js may tidy twice


def test_android_repeats_are_joined_once():
    script = f"""
      const V = require({json.dumps(str(TIDY_JS))});
      console.log(JSON.stringify([
        V.joinSegments(["thêm", "thêm netflix", "thêm netflix 260 nghìn"]),
        V.joinSegments(["thêm netflix", " 260 nghìn một tháng"]),
      ]));
    """
    assert run_node(script) == ["thêm netflix 260 nghìn", "thêm netflix 260 nghìn một tháng"]


def test_gemini_gets_detailed_vietnamese_rules(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    sent = {}

    class Reply:
        status_code, ok = 200, True

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "Netflix bao giờ gia hạn?"}]}}]}

    def post(url, headers, json, timeout):
        sent.update(json)
        return Reply()

    monkeypatch.setattr(ai_providers.requests, "post", post)
    assert ai_providers.transcribe(b"OggS", "audio/ogg") == "Netflix bao giờ gia hạn?"
    rules = sent["contents"][0]["parts"][1]["text"]
    assert "tone mark" in rules and "260.000" in rules and "Netflix" in rules
    ai_providers.transcribe(b"OggS", "audio/ogg", "en")
    assert "260.000" not in sent["contents"][0]["parts"][1]["text"]


def test_mic_language_switch_is_on_the_page(client):
    page = client.get("/").get_data(as_text=True)
    assert "data-voice-lang" in page
    assert page.index("voice-tidy.js") < page.index("subby.js")  # tidy must load first
