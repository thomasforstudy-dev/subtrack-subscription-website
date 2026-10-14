"""Look up a web page's title, so a pasted link gets a real name automatically.

Example: https://stitch.withgoogle.com/  ->  "Stitch - Design with AI"

Safety: the server visits the link itself, so a user could try to make it open
addresses inside your home network (your router, SQL Server, other PCs).
We only ever visit public internet addresses, on the normal web ports, with a
short time limit and a size limit.
"""

import ipaddress
import re
import socket
import time
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import requests

ALLOWED_PORTS = {80, 443}
MAX_REDIRECTS = 3
MAX_BYTES = 300_000          # read at most ~300 KB of the page
TOTAL_SECONDS = 6            # give up after this long
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SubTrackLinkPreview/1.0)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en;q=0.9,vi;q=0.8",
}


def fetch_preview(url: str) -> dict:
    """Return {"title", "site_name", "description"} for a page, or {} if we can't."""
    deadline = time.monotonic() + TOTAL_SECONDS
    for _ in range(MAX_REDIRECTS + 1):
        if not _is_safe_url(url):
            return {}
        try:
            resp = requests.get(
                url, headers=HEADERS, timeout=(3, 4), allow_redirects=False, stream=True
            )
        except requests.RequestException:
            return {}

        with resp:
            # Follow redirects ourselves, so every hop gets the safety check.
            if resp.is_redirect and resp.headers.get("Location"):
                url = urljoin(url, resp.headers["Location"])
                continue
            if resp.status_code != 200:
                return {}
            content_type = resp.headers.get("Content-Type", "").lower()
            if "html" not in content_type:
                return {}

            body = b""
            for chunk in resp.iter_content(16_384):
                body += chunk
                if len(body) >= MAX_BYTES or time.monotonic() > deadline:
                    break

            encoding = resp.encoding if "charset=" in content_type else None
            return parse_html(_decode(body, encoding))
    return {}


def parse_html(html: str) -> dict:
    parser = _MetaParser()
    try:
        parser.feed(html)
    except Exception:  # noqa: BLE001 - broken HTML shouldn't break saving a link
        pass
    meta = parser.meta
    title = meta.get("og:title") or meta.get("twitter:title") or parser.title
    description = meta.get("og:description") or meta.get("description") or ""
    result = {
        "title": _clean(title, 200),
        "site_name": _clean(meta.get("og:site_name", ""), 100),
        "description": _clean(description, 300),
    }
    return {k: v for k, v in result.items() if v}


def _is_safe_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    if port not in ALLOWED_PORTS:
        return False
    return host_is_public(parsed.hostname, port)


def host_is_public(host: str, port: int) -> bool:
    """True only if every address the name points to is on the public internet."""
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError):
        return False
    if not infos:
        return False
    for info in infos:
        address = info[4][0].split("%")[0]  # drop IPv6 zone like "%eth0"
        ip = ipaddress.ip_address(address)
        if not ip.is_global or ip.is_multicast:
            return False
    return True


class _MetaParser(HTMLParser):
    WANTED = {"og:title", "twitter:title", "og:site_name", "og:description", "description"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.meta: dict[str, str] = {}
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            attr = {k.lower(): (v or "") for k, v in attrs}
            key = (attr.get("property") or attr.get("name") or "").lower()
            if key in self.WANTED and attr.get("content"):
                self.meta.setdefault(key, attr["content"])

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title and len(self.title) < 1000:
            self.title += data


def _decode(body: bytes, encoding: str | None) -> str:
    if not encoding:
        found = re.search(rb'<meta[^>]+charset=["\']?([\w-]+)', body[:4096], re.I)
        encoding = found.group(1).decode("ascii") if found else "utf-8"
    try:
        return body.decode(encoding, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


def _clean(text: str, limit: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
