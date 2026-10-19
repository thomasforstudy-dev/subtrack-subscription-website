"""Choosing Subby's model, and what happens when Phi (the laptop) is offline."""

import pytest
import requests

from app import ai_providers
from app.ai_providers import FakeProvider, PhiProvider, ProviderUnavailable, Turn


class Reply:
    def __init__(self, status, data):
        self.status_code = status
        self.ok = status < 400
        self.data = data

    def json(self):
        return self.data


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ["SUBBY_PROVIDER", "SUBBY_FALLBACK", "PHI_BASE_URL", "PHI_API_KEY", "PHI_MODEL", "GEMINI_MODEL"]:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")


def phi_on(monkeypatch):
    monkeypatch.setenv("SUBBY_PROVIDER", "phi")
    monkeypatch.setenv("PHI_BASE_URL", "http://phi-laptop.internal:8080/")
    monkeypatch.setenv("PHI_API_KEY", "shared-secret")


def test_phi_speaks_the_openai_style_chat_api(monkeypatch):
    phi_on(monkeypatch)
    sent = {}

    def post(url, json, headers, timeout):
        sent.update(url=url, json=json, headers=headers)
        return Reply(200, {"choices": [{"message": {"content": " Hello from Phi. "}}]})

    monkeypatch.setattr(ai_providers.requests, "post", post)
    answer = PhiProvider().chat("Rules", [Turn("assistant", "Hi!")], "What is SubTrack?", 0.3)
    assert answer == "Hello from Phi."
    assert sent["url"] == "http://phi-laptop.internal:8080/v1/chat/completions"
    assert sent["headers"] == {"Authorization": "Bearer shared-secret"}
    assert sent["json"]["model"] == "phi-3.5-mini-instruct"
    assert [m["role"] for m in sent["json"]["messages"]] == ["system", "assistant", "user"]


def test_phi_not_set_up(monkeypatch):
    monkeypatch.setenv("SUBBY_PROVIDER", "phi")
    with pytest.raises(ProviderUnavailable, match="not-set-up"):
        PhiProvider().chat("Rules", [], "Hi", 0.3)


def offline(*args, **kwargs):
    raise requests.ConnectionError("laptop is asleep")


def test_offline_phi_does_not_silently_use_the_cloud(client, monkeypatch):
    phi_on(monkeypatch)
    calls = []

    def post(url, **kwargs):
        calls.append(url)
        return offline()

    monkeypatch.setattr(ai_providers.requests, "post", post)
    res = client.post("/subby/ask", json={"question": "hi"})
    assert res.status_code == 502
    assert res.get_json() == {"answer": None, "reason": "model-offline", "provider": "phi"}
    assert all("googleapis" not in url for url in calls)  # nothing went to Gemini


def test_fallback_only_when_the_owner_allows_it_and_it_is_disclosed(client, monkeypatch):
    phi_on(monkeypatch)
    monkeypatch.setenv("SUBBY_FALLBACK", "gemini")

    def post(url, **kwargs):
        if "phi-laptop" in url:
            return offline()
        return Reply(200, {"candidates": [{"content": {"parts": [{"text": "From Gemini."}]}}]})

    monkeypatch.setattr(ai_providers.requests, "post", post)
    data = client.post("/subby/ask", json={"question": "hi"}).get_json()
    assert data["answer"] == "From Gemini."
    assert data["provider"] == "gemini" and data["fallback"] is True


def test_fake_provider_is_labelled(client, monkeypatch):
    monkeypatch.setenv("SUBBY_PROVIDER", "fake")
    data = client.post("/subby/ask", json={"question": "hi"}).get_json()
    assert data["provider"] == "fake"
    assert data["answer"].startswith("[fake model]")


def test_unknown_provider_means_not_set_up(client, monkeypatch):
    monkeypatch.setenv("SUBBY_PROVIDER", "gpt-9")
    res = client.post("/subby/ask", json={"question": "hi"})
    assert res.status_code == 503
    assert res.get_json()["reason"] == "not-set-up"


def test_extraction_never_guesses():
    assert FakeProvider().extract("Gucci Takashimaya total 100", ["merchant_branch", "total"]) == {
        "merchant_branch": None, "total": None,
    }


def test_providers_say_whether_text_leaves_our_machines():
    assert ai_providers.GeminiProvider.is_cloud is True
    assert ai_providers.PhiProvider.is_cloud is False
