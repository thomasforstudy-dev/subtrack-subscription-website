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
    hosts_seen: list[str] = []

    def do_GET(self):
        _Site.hosts_seen.append(self.headers.get("Host", ""))
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
        elif self.path == "/huge":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<title>Big</title>" + b"x" * 2_000_000)
        elif self.path == "/with-icon":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b'<title>Icon page</title><link rel="icon" href="/img/i.png">')
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
    _Site.hosts_seen = []
    # Pretend our local test server is a public website on an allowed port.
    # "public.test" is a made-up name that only this fake lookup knows.
    monkeypatch.setattr(link_preview, "ALLOWED_PORTS", {port})
    monkeypatch.setattr(
        link_preview, "public_address",
        lambda host, p: "127.0.0.1" if host in ("127.0.0.1", "public.test") else None,
    )
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


def test_fetch_real_page(site):
    assert fetch_preview(site + "/page") == {
        "title": "Trang chủ – Xin chào",
        "icon": site + "/favicon.ico",  # no <link rel=icon>: the site's own /favicon.ico
    }


def test_icon_from_the_page(site):
    assert fetch_preview(site + "/with-icon")["icon"] == site + "/img/i.png"


def test_follows_safe_redirects_only(site):
    assert fetch_preview(site + "/redirect-home")["title"] == "Trang chủ – Xin chào"
    assert fetch_preview(site + "/redirect-private") == {}


def test_ignores_non_html(site):
    assert fetch_preview(site + "/file.pdf") == {}


def test_reads_only_the_start_of_huge_pages(site):
    assert fetch_preview(site + "/huge")["title"] == "Big"


def test_connects_to_the_checked_address_not_a_new_lookup(site):
    """DNS rebinding: we connect to the address we checked, and only send the
    name in the Host header. "public.test" doesn't exist in real DNS, so this
    only works if the name is never looked up a second time."""
    port = site.rsplit(":", 1)[1]
    assert fetch_preview(f"http://public.test:{port}/page")["title"] == "Trang chủ – Xin chào"
    assert _Site.hosts_seen[-1] == f"public.test:{port}"


def test_name_with_any_private_address_is_refused(monkeypatch):
    def fake_lookup(host, port, proto):
        # One public and one private answer: refuse, the private one could be used.
        return [(None, None, None, "", ("93.184.216.34", port)), (None, None, None, "", ("10.0.0.7", port))]

    monkeypatch.setattr(link_preview.socket, "getaddrinfo", fake_lookup)
    assert link_preview.public_address("tricky.example", 443) is None


def test_icon_url_rules():
    assert link_preview.icon_url("https://a.example/x/y", "") == "https://a.example/favicon.ico"
    assert link_preview.icon_url("https://a.example/x/", "icon.svg") == "https://a.example/x/icon.svg"
    assert link_preview.icon_url("https://a.example/", "javascript:alert(1)") == "https://a.example/favicon.ico"
