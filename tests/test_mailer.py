"""The Resend adapter. Resend is faked: these tests never send real email."""

import pytest
import requests

from app import mailer
from app.mailer import Email, MailError, MailNotReady


class FakeResponse:
    def __init__(self, status):
        self.status_code = status
        self.ok = 200 <= status < 300


@pytest.fixture()
def resend_on(monkeypatch):
    monkeypatch.setenv("MAIL_BACKEND", "resend")
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    monkeypatch.setenv("MAIL_FROM", "SubTrack <hi@example.com>")
    monkeypatch.setattr(mailer.time, "sleep", lambda seconds: None)  # no real waiting


def fake_resend(monkeypatch, answers):
    calls = []

    def post(url, json, headers, timeout):
        calls.append({"json": json, "headers": headers, "timeout": timeout})
        answer = answers[len(calls) - 1]
        if isinstance(answer, Exception):
            raise answer
        return FakeResponse(answer)

    monkeypatch.setattr(mailer.requests, "post", post)
    return calls


def test_sends_with_key_in_header_and_idempotency_key(resend_on, monkeypatch):
    calls = fake_resend(monkeypatch, [200])
    mailer.send_email(Email("you@example.com", "Hi", "Body", idempotency_key="abc"))
    assert calls[0]["headers"]["Authorization"] == "Bearer re_test_key"
    assert calls[0]["headers"]["Idempotency-Key"] == "abc"
    assert calls[0]["json"]["to"] == ["you@example.com"]
    assert calls[0]["timeout"] == mailer.TIMEOUT


def test_busy_or_offline_resend_is_tried_again(resend_on, monkeypatch):
    calls = fake_resend(monkeypatch, [503, requests.ConnectionError("down"), 200])
    mailer.send_email(Email("you@example.com", "Hi", "Body"))
    assert len(calls) == 3


def test_gives_up_after_three_tries(resend_on, monkeypatch):
    calls = fake_resend(monkeypatch, [429, 500, 502])
    with pytest.raises(MailError) as err:
        mailer.send_email(Email("you@example.com", "Hi", "Body"))
    assert len(calls) == 3
    assert "re_test_key" not in str(err.value)  # never leak the key


def test_bad_request_is_not_retried(resend_on, monkeypatch):
    calls = fake_resend(monkeypatch, [422, 200])
    with pytest.raises(MailError):
        mailer.send_email(Email("you@example.com", "Hi", "Body"))
    assert len(calls) == 1


def test_default_backend_never_emails_real_people(monkeypatch):
    monkeypatch.delenv("MAIL_BACKEND", raising=False)
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    assert mailer.backend() == "file"
    monkeypatch.setenv("APP_ENV", "production")
    assert mailer.backend() == "none"
    with pytest.raises(MailNotReady):
        mailer.send_email(Email("you@example.com", "Hi", "Body"))


def test_file_backend_writes_to_instance_outbox(app, monkeypatch, tmp_path):
    monkeypatch.setenv("MAIL_BACKEND", "file")
    app.instance_path = str(tmp_path)
    with app.app_context():
        mailer.send_email(Email("you@example.com", "Hello", "The body"))
    files = list((tmp_path / "outbox").glob("*.txt"))
    assert len(files) == 1
    assert "Subject: Hello" in files[0].read_text(encoding="utf-8")
