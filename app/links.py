"""Pinned links: save useful websites, tag them, search them."""

import hashlib
import ipaddress
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlsplit

import click
from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from app import db
from app.link_preview import fetch_preview, icon_url
from app.models import Link
from app.security import safe_next_url
from app.validation import escape_like

# cli_group=None: the command is "flask fill-link-fingerprints".
bp = Blueprint("links", __name__, url_prefix="/links", cli_group=None)

MAX_TAGS = 10


@bp.route("/")
@login_required
def list_links():
    q = (request.args.get("q") or "").strip()
    tag = (request.args.get("tag") or "").strip().lower()

    query = Link.query.filter_by(user_id=current_user.id)
    if q:
        like = f"%{escape_like(q)}%"
        query = query.filter(
            or_(
                Link.title.ilike(like, escape="\\"),
                Link.url.ilike(like, escape="\\"),
                Link.tags.ilike(like, escape="\\"),
                Link.notes.ilike(like, escape="\\"),
            )
        )
    items = query.order_by(Link.is_pinned.desc(), Link.created_at.desc()).all()
    if tag:
        items = [link for link in items if tag in link.tag_list]

    all_tags = sorted(
        {
            t
            for (tags,) in db.session.query(Link.tags).filter_by(user_id=current_user.id)
            for t in (tags or "").split(", ")
            if t
        }
    )
    return render_template(
        "links/list.html", items=items, q=q, tag=tag, all_tags=all_tags
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "POST":
        link = Link(user_id=current_user.id)
        error = _fill_link(link)
        if error:
            flash(error)
            return render_template("links/form.html", item=None, form=request.form)
        db.session.add(link)
        db.session.commit()
        flash("Link saved.")
        return redirect(url_for("links.list_links"))
    return render_template("links/form.html", item=None, form={})


@bp.route("/<int:link_id>/edit", methods=["GET", "POST"])
@login_required
def edit(link_id: int):
    link = _own_link_or_404(link_id)
    if request.method == "POST":
        error = _fill_link(link)
        if error:
            flash(error)
            db.session.rollback()
            return render_template("links/form.html", item=link, form=request.form)
        db.session.commit()
        flash("Link updated.")
        return redirect(url_for("links.list_links"))
    return render_template("links/form.html", item=link, form={})


@bp.route("/preview", methods=["POST"])
@login_required
def preview():
    """Called by the page when a link is pasted, to fill in the title box."""
    url, error = normalize_url(request.form.get("url") or "")
    if error:
        return jsonify({})
    return jsonify(fetch_preview(url))


@bp.route("/<int:link_id>/pin", methods=["POST"])
@login_required
def toggle_pin(link_id: int):
    link = _own_link_or_404(link_id)
    link.is_pinned = not link.is_pinned
    db.session.commit()
    return redirect(back_to_links())


def back_to_links() -> str:
    """Go back to the list the user was on (keeping ?q= / ?tag=), but never to
    another website: the Referer header can be faked, so only its path is
    used, and only when it is our own links page."""
    wanted = safe_next_url(request.form.get("next"))
    if wanted is None and request.referrer:
        try:
            ref = urlparse(request.referrer)
        except ValueError:
            ref = None
        if ref is not None and ref.netloc == request.host:
            wanted = safe_next_url(ref.path + (f"?{ref.query}" if ref.query else ""))
    list_path = url_for("links.list_links")
    if wanted and wanted.split("?")[0] == list_path:
        return wanted
    return list_path


@bp.route("/<int:link_id>/delete", methods=["POST"])
@login_required
def delete(link_id: int):
    link = _own_link_or_404(link_id)
    db.session.delete(link)
    db.session.commit()
    flash("Link deleted.")
    return redirect(url_for("links.list_links"))


def _own_link_or_404(link_id: int) -> Link:
    # Filtering by user_id means nobody can open someone else's link by guessing an id.
    return Link.query.filter_by(id=link_id, user_id=current_user.id).first_or_404()


def _fill_link(link: Link) -> str | None:
    """Copy form fields onto the link. Returns an error message, or None if OK."""
    url, error = normalize_url(request.form.get("url") or "")
    if error:
        return error
    fingerprint = url_fingerprint(url)
    same = Link.query.filter(
        Link.user_id == current_user.id, Link.url_hash == fingerprint, Link.id != (link.id or 0)
    ).first()
    if same:
        return f"You already saved this link as “{same.title}”. Search for it, or edit that one."

    link.url = url
    link.url_hash = fingerprint
    link.title = (request.form.get("title") or "").strip()[:200]
    link.tags = normalize_tags(request.form.get("tags") or "")
    link.notes = (request.form.get("notes") or "").strip()
    found = {}
    if not link.title:
        # No title typed: look up the page's real name (falls back to the domain).
        found = fetch_preview(url)
        link.title = found.get("title") or urlparse(url).netloc
        if not link.notes and found.get("description"):
            link.notes = found["description"]
    link.favicon_url = found.get("icon") or icon_url(url)
    if "is_pinned" in request.form or request.form.get("form") == "full":
        link.is_pinned = request.form.get("is_pinned") == "on"
    return None


# Query parts that only say where a click came from, not which page it is.
TRACKING_PREFIXES = ("utm_", "fbclid", "gclid", "mc_eid", "igshid", "ref_src")


def url_fingerprint(url: str) -> str:
    """The same page written differently gets the same fingerprint:
    http/https, "www.", a trailing "/", "#section" and tracking tags are ignored.
    "https://www.Example.com/a/?utm_source=x#top" == "http://example.com/a"."""
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        # A broken address saved before links were checked: still give it a
        # stable fingerprint instead of crashing the page or the start-up.
        return hashlib.sha256(url.strip().lower().encode()).hexdigest()
    host = (parts.hostname or "").lower().removeprefix("www.")
    if port and port not in (80, 443):
        host += f":{port}"
    query = sorted(
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith(TRACKING_PREFIXES)
    )
    key = host + parts.path.rstrip("/") + ("?" + urlencode(query) if query else "")
    return hashlib.sha256(key.encode()).hexdigest()


@bp.cli.command("fill-link-fingerprints")
def fill_link_fingerprints_command():
    """For SQL Server after 04_links.sql: give older links a fingerprint and icon."""
    click.echo(f"Updated {fill_missing_fingerprints()} links.")


def fill_missing_fingerprints() -> int:
    """Links saved before fingerprints existed get one (run at start-up / by command)."""
    links = Link.query.filter(Link.url_hash.is_(None)).limit(5000).all()
    for link in links:
        link.url_hash = url_fingerprint(link.url)
        link.favicon_url = link.favicon_url or icon_url(link.url)
    db.session.commit()
    return len(links)


def normalize_url(raw: str) -> tuple[str, str | None]:
    url = raw.strip()
    if not url:
        return "", "Please paste a link."
    # "mailto:", "javascript:", "file:" ... -> not a website. ("site.com:8080" is fine.)
    has_other_scheme = re.match(r"^[a-z][a-z0-9+.-]*:(?!\d)", url, re.IGNORECASE)
    if has_other_scheme and not re.match(r"^https?://", url, re.IGNORECASE):
        return "", "That doesn't look like a web link (it should start with http:// or https://)."
    if "://" not in url:
        url = "https://" + url
    if len(url) > 2048:
        return "", "That link is too long (max 2048 characters)."
    if any(ch.isspace() or ord(ch) < 32 for ch in url):
        return "", "A web link can't contain spaces. Please check it."
    try:
        parsed = urlparse(url)
        parsed.port  # raises ValueError for "site.com:abc" or a port above 65535
    except ValueError:
        # Also "https://[broken" (a half-written IPv6 address).
        return "", "That link has a mistake in it. Please check the address and port number."
    # Only allow real web links. This blocks things like "javascript:" links,
    # which could run code when clicked.
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return "", "That doesn't look like a web link (it should start with http:// or https://)."
    if is_private_host(parsed.hostname):
        return "", "Links to private or local addresses (like 127.0.0.1 or your router) can't be saved."
    return url, None


def is_private_host(host: str) -> bool:
    """True for localhost names and IP addresses that aren't on the public
    internet (127.0.0.1, 10.x, 192.168.x, 169.254.x, ::1 ...). Names like
    example.com are checked again by link_preview before the server fetches them."""
    host = host.strip("[]").rstrip(".").lower()
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        return True
    try:
        return not ipaddress.ip_address(host).is_global
    except ValueError:
        return False  # a normal name, not an IP address


def normalize_tags(raw: str) -> str:
    tags: list[str] = []
    for part in raw.split(","):
        tag = part.strip().lower()[:30]
        if tag and tag not in tags:
            tags.append(tag)
    return ", ".join(tags[:MAX_TAGS])[:200]
