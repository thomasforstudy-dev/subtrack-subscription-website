"""Look up a web page's title, so a pasted link gets a real name automatically.

Example: https://stitch.withgoogle.com/  ->  "Stitch - Design with AI"

Safety: the server visits the link itself, so a user could try to make it open
addresses inside your home network (your router, SQL Server, other PCs, the
cloud "metadata" address 169.254.169.254).
- Only http/https, only ports 80/443, at most 3 redirects, each one checked.
- The name is looked up ONCE, every address must be public, and we connect to
  exactly that address. (If we checked, then let the library look the name up
  again, a tricky DNS server could answer "public" the first time and
  "192.168.1.1" the second: "DNS rebinding".)
- Short time limits and a size limit. The page is only read as text: its
  JavaScript never runs.
"""

import ipaddress
import re
import socket
import time
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import certifi  # comes with requests
import urllib3  # comes with requests

ALLOWED_PORTS = {80, 443}
MAX_REDIRECTS = 3
MAX_BYTES = 300_000          # read at most ~300 KB of the page
TOTAL_SECONDS = 6            # give up after this long
TIMEOUT = urllib3.Timeout(connect=3, read=4)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SubTrackLinkPreview/1.0)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en;q=0.9,vi;q=0.8",
}


def fetch_preview(url: str) -> dict:
    """Return {"title", "site_name", "description", "icon"} for a page, or {} if we can't."""
    deadline = time.monotonic() + TOTAL_SECONDS
    for _ in range(MAX_REDIRECTS + 1):
        resp = _open(url)
        if resp is None:
            return {}
        try:
            # Follow redirects ourselves, so every hop gets the safety check.
            location = resp.headers.get("Location")
            if resp.status in (301, 302, 303, 307, 308) and location:
                url = urljoin(url, location)
                continue
            if resp.status != 200:
                return {}
            content_type = resp.headers.get("Content-Type", "").lower()
            if "html" not in content_type:
                return {}

            body = b""
            for chunk in resp.stream(16_384):
                body += chunk
                if len(body) >= MAX_BYTES or time.monotonic() > deadline:
                    break
            charset = re.search(r"charset=([\w-]+)", content_type)
            return parse_html(_decode(body, charset.group(1) if charset else None), base_url=url)
        except (urllib3.exceptions.HTTPError, OSError):
            return {}
        finally:
            resp.release_conn()
    return {}


def _open(url: str):
    """Start a GET to a *checked* public address. Returns the response, or None."""
    try:
        parsed = urlparse(url)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        return None
    host = parsed.hostname
    if parsed.scheme not in ("http", "https") or not host or port not in ALLOWED_PORTS:
        return None
    address = public_address(host, port)
    if address is None:
        return None

    # Connect to the address we checked, but tell the website (Host header)
    # and the HTTPS certificate check which name we really want.
    name = f"[{host}]" if ":" in host else host
    default_port = 443 if parsed.scheme == "https" else 80
    host_header = name if port == default_port else f"{name}:{port}"
    if parsed.scheme == "https":
        pool = urllib3.HTTPSConnectionPool(
            address, port, timeout=TIMEOUT, retries=False, maxsize=1,
            cert_reqs="CERT_REQUIRED", ca_certs=certifi.where(),
            server_hostname=host, assert_hostname=host,
        )
    else:
        pool = urllib3.HTTPConnectionPool(address, port, timeout=TIMEOUT, retries=False, maxsize=1)
    path = (parsed.path or "/") + (f"?{parsed.query}" if parsed.query else "")
    try:
        return pool.urlopen(
            "GET", path, headers={**HEADERS, "Host": host_header},
            redirect=False, retries=False, preload_content=False,
        )
    except (urllib3.exceptions.HTTPError, OSError):
        return None


def parse_html(html: str, base_url: str = "") -> dict:
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
        "icon": icon_url(base_url, parser.icon) if base_url else "",
    }
    return {k: v for k, v in result.items() if v}


def icon_url(page_url: str, href: str = "") -> str:
    """The site's own icon: from <link rel="icon">, or /favicon.ico as a fallback.

    It is always on the saved site itself: we never ask a third-party icon
    service, which would tell that service every link our users save.
    """
    page = urlparse(page_url)
    if page.scheme not in ("http", "https") or not page.netloc:
        return ""
    url = urljoin(page_url, href) if href else f"{page.scheme}://{page.netloc}/favicon.ico"
    if urlparse(url).scheme not in ("http", "https") or len(url) > 2048:
        return f"{page.scheme}://{page.netloc}/favicon.ico"
    return url


def public_address(host: str, port: int) -> str | None:
    """Look the name up once. Return an address to connect to, or None if ANY
    address it points to is private (home network, this PC, cloud metadata...)."""
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError, OSError):
        return None
    addresses = []
    for info in infos:
        address = info[4][0].split("%")[0]  # drop IPv6 zone like "%eth0"
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            return None
        if not ip.is_global or ip.is_multicast:
            return None
        addresses.append(address)
    return addresses[0] if addresses else None


def host_is_public(host: str, port: int) -> bool:
    """True only if every address the name points to is on the public internet."""
    return public_address(host, port) is not None


class _MetaParser(HTMLParser):
    WANTED = {"og:title", "twitter:title", "og:site_name", "og:description", "description"}
    ICON_RELS = {"icon", "shortcut icon", "apple-touch-icon"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.icon = ""
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
        elif tag == "link" and not self.icon:
            attr = {k.lower(): (v or "") for k, v in attrs}
            if attr.get("rel", "").lower().strip() in self.ICON_RELS and attr.get("href"):
                self.icon = attr["href"].strip()

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
