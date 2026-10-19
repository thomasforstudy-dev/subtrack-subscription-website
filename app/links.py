"""Pinned links: save useful websites, tag them, search them."""

import re
from urllib.parse import urlparse

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from app import db
from app.link_preview import fetch_preview
from app.models import Link
from app.validation import escape_like

bp =Blueprint("links", __name__, url_prefix="/links")

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
    return redirect(request.referrer or url_for("links.list_links"))


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
    link.url = url
    link.title = (request.form.get("title") or "").strip()[:200]
    link.tags = normalize_tags(request.form.get("tags") or "")
    link.notes = (request.form.get("notes") or "").strip()
    if not link.title:
        # No title typed: look up the page's real name (falls back to the domain).
        found = fetch_preview(url)
        link.title = found.get("title") or urlparse(url).netloc
        if not link.notes and found.get("description"):
            link.notes = found["description"]
    if "is_pinned" in request.form or request.form.get("form") == "full":
        link.is_pinned = request.form.get("is_pinned") == "on"
    return None


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
    parsed = urlparse(url)
    # Only allow real web links. This blocks things like "javascript:" links,
    # which could run code when clicked.
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return "", "That doesn't look like a web link (it should start with http:// or https://)."
    if len(url) > 2048:
        return "", "That link is too long (max 2048 characters)."
    return url, None


def normalize_tags(raw: str) -> str:
    tags: list[str] = []
    for part in raw.split(","):
        tag = part.strip().lower()[:30]
        if tag and tag not in tags:
            tags.append(tag)
    return ", ".join(tags[:MAX_TAGS])[:200]
