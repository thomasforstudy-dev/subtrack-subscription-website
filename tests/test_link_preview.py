import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app import link_preview
from app.link_preview import fetch_preview, host_is_public, parse_html


def test_parse_prefers_og_title():
    html = """<html><head><title>  Plain
      title </title><meta property="og:title" content="Nice &amp; Short">
      <meta name="description" content="What it does."></head></html>"""
    assert parse_html(html) == {"title": "Nice & Short", "description": "What it does."}


def test_parse_falls_back_to_title_tag_and_handles_junk():
    assert parse_html("<title>Only title</title>") == {"title": "Only title"}
    assert parse_html("<<<not html") == {}


@pytest.mark.parametrize(
    "host", ["127.0.0.1", "localhost", "10.0.0.5", "192.168.1.1", "169.254.169.254", "::1", "0.0.0.0"]
)
def test_private_addresses_are_blocked(host):
    assert host_is_public(host, 80) is False


def test_public_address_allowed():
    assert host_is_public("8.8.8.8", 443) is True


def test_unsafe_urls_are_never_fetched():
    for url in ["http://127.0.0.1/", "http://192.168.1.1/admin", "http://example.com:1433/", "ftp://example.com"]:
        assert fetch_preview(url) == {}


class _Site(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/redirect-home":
            self.send_response(302)
            self.send_header("Location", "/page")
            self.end_headers()
        elif self.path == "/redirect-private":
            self.send_response(302)
            self.send_header("Location", "http://192.168.1.1/")
            self.end_headers()
        elif self.path == "/file.pdf":
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.end_headers()
            self.wfile.write(b"%PDF")
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("<title>Trang chủ – Xin chào</title>".encode())

    def log_message(self, *args):
        pass


@pytest.fixture()
def site(monkeypatch):
    server = HTTPServer(("127.0.0.1", 0), _Site)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    # Pretend our local test server is a public website on an allowed port.
    monkeypatch.setattr(link_preview, "ALLOWED_PORTS", {port})
    monkeypatch.setattr(link_preview, "host_is_public", lambda host, p: host == "127.0.0.1")
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


def test_fetch_real_page(site):
    assert fetch_preview(site + "/page") == {"title": "Trang chủ – Xin chào"}


def test_follows_safe_redirects_only(site):
    assert fetch_preview(site + "/redirect-home") == {"title": "Trang chủ – Xin chào"}
    assert fetch_preview(site + "/redirect-private") == {}


def test_ignores_non_html(site):
    assert fetch_preview(site + "/file.pdf") == {}
