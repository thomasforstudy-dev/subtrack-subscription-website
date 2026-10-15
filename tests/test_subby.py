"""Subby's brain. Gemini is faked: these tests never call the real API."""

import pytest

from app import subby


class FakeGemini:
    status_code = 200

    def __init__(self, text):
        self.text = text
        self.sent = None

    def __call__(self, url, headers, json, timeout):
        self.sent = {"url": url, "headers": headers, "json": json}
        return self

    def raise_for_status(self):
        pass

    def json(self):
        return {"candidates": [{"content": {"parts": [{"text": self.text}]}}]}


@pytest.fixture(autouse=True)
def fresh_limits(monkeypatch):
    subby._asked.clear()
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)


def ask(client, question="How do reminders work?", **extra):
    return client.post("/subby/ask", json={"question": question, **extra})


def test_answers_from_gemini(client, monkeypatch):
    fake = FakeGemini("We email you before it renews.")
    monkeypatch.setattr(subby.requests, "post", fake)
    res = ask(client, fun=False, history=[{"role": "bot", "text": "Hi!"}])
    assert res.get_json() == {"answer": "We email you before it renews.", "handoff": False}
    # The key goes in a header (never in the page), and history is passed on.
    assert fake.sent["headers"] == {"x-goog-api-key": "test-key"}
    assert fake.sent["json"]["contents"][0]["role"] == "model"
    assert "friendly, calm and plain" in fake.sent["json"]["system_instruction"]["parts"][0]["text"]


def test_handoff_marker_is_removed(client, monkeypatch):
    monkeypatch.setattr(subby.requests, "post", FakeGemini("Let me get the human. [HANDOFF]"))
    data = ask(client, "Can I get a refund?").get_json()
    assert data == {"answer": "Let me get the human.", "handoff": True}


def test_no_key_means_browser_uses_its_own_answers(client, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY")
    res = ask(client)
    assert res.status_code == 503
    assert res.get_json()["answer"] is None


def test_gemini_failure_is_handled(client, monkeypatch):
    def broken(*args, **kwargs):
        raise subby.requests.ConnectionError("down")

    monkeypatch.setattr(subby.requests, "post", broken)
    assert ask(client).status_code == 502


def test_only_json_is_accepted(client):
    res = client.post("/subby/ask", data={"question": "hi"})
    assert res.status_code == 400


def test_long_questions_are_cut(client, monkeypatch):
    fake = FakeGemini("ok")
    monkeypatch.setattr(subby.requests, "post", fake)
    ask(client, "x" * 5000)
    sent = fake.sent["json"]["contents"][-1]["parts"][0]["text"]
    assert len(sent) == subby.MAX_QUESTION


def test_too_many_questions_are_slowed_down(client, monkeypatch):
    monkeypatch.setattr(subby.requests, "post", FakeGemini("ok"))
    for _ in range(subby.LIMIT_PER_HOUR):
        assert ask(client).status_code == 200
    assert ask(client).status_code == 429


def test_busy_model_falls_back_to_next(client, monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "busy-model,backup-model")
    tried = []

    class Busy(FakeGemini):
        status_code = 503

    def fake_post(url, headers, json, timeout):
        tried.append(url.split("/models/")[1].split(":")[0])
        return Busy("") if "busy" in url else FakeGemini("From the backup.")(url, headers, json, timeout)

    monkeypatch.setattr(subby.requests, "post", fake_post)
    assert ask(client).get_json()["answer"] == "From the backup."
    assert tried == ["busy-model", "backup-model"]

