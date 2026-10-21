"""Minimal server readiness and bounded loopback-only deployment verification."""

import argparse
import json
import re
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, build_opener

READY_URL = "http://127.0.0.1:8000/__subtrack__/ready"


def read_revision(project_root):
    """Read Git metadata without invoking Git or requiring safe.directory."""
    try:
        git_dir = Path(project_root) / ".git"
        if git_dir.is_file():
            pointer = git_dir.read_text(encoding="utf-8").strip()
            if not pointer.startswith("gitdir: "):
                return None
            git_dir = (git_dir.parent / pointer[8:]).resolve()
        common_dir = git_dir
        common_file = git_dir / "commondir"
        if common_file.is_file():
            common_dir = (git_dir / common_file.read_text(encoding="utf-8").strip()).resolve()
        value = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
        # HEAD may be detached, or refer to a loose/packed branch. Linked
        # worktrees keep HEAD separately and share branch refs via commondir.
        for _ in range(5):
            if re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", value):
                return value.lower()
            if not value.startswith("ref: "):
                return None
            ref = value[5:]
            if (not ref.startswith("refs/") or "\\" in ref or ":" in ref
                    or any(part in {"", ".", ".."} for part in ref.split("/"))):
                return None
            for base in dict.fromkeys([git_dir, common_dir]):
                loose = base / ref
                if loose.is_file():
                    value = loose.read_text(encoding="utf-8").strip()
                    break
            else:
                for line in (common_dir / "packed-refs").read_text(encoding="utf-8").splitlines():
                    if line.startswith(("#", "^")):
                        continue
                    fields = line.split()
                    if len(fields) == 2 and fields[1] == ref:
                        value = fields[0]
                        break
                else:
                    return None
        return None
    except (OSError, ValueError, UnicodeError):
        return None


def install_readiness(app):
    # Capture at startup: an old worker cannot claim to serve a newly pulled commit.
    # Metadata failure must not prevent ordinary pages from starting. Unknown
    # revisions remain unavailable to the updater, rather than claiming success.
    try:
        revision = read_revision(Path(__file__).resolve().parents[1])
    except Exception:
        revision = None
    from flask import jsonify, request
    from sqlalchemy import text
    from app import db

    @app.get("/__subtrack__/ready")
    def readiness():
        # cloudflared connects from loopback too. Header presence, even empty,
        # marks a tunneled request; checking remote_addr alone is insufficient.
        if "CF-Connecting-IP" in request.headers or request.remote_addr not in {"127.0.0.1", "::1"}:
            response = app.response_class(status=404)
            response.headers["Cache-Control"] = "no-store"
            return response
        if revision is None:
            response = jsonify(status="unavailable", revision=None)
            response.headers["Cache-Control"] = "no-store"
            return response, 503
        try:
            db.session.execute(text("SELECT 1"))
            response = jsonify(status="ready", revision=revision)
            response.headers["Cache-Control"] = "no-store"
            return response
        except Exception:
            db.session.rollback()
            # No database name, login, connection string or driver error is public.
            response = jsonify(status="unavailable", revision=revision)
            response.headers["Cache-Control"] = "no-store"
            return response, 503


def fetch_health(url, timeout):
    with build_opener(ProxyHandler({})).open(url, timeout=timeout) as response:
        if response.status != 200:
            return {}
        return json.loads(response.read(4096))


def wait_ready(expected_revision, url=READY_URL, timeout=30, fetch=fetch_health,
               clock=time.monotonic, sleep=time.sleep):
    address = urlsplit(url)
    if address.scheme != "http" or address.hostname not in {"127.0.0.1", "localhost", "::1"} or address.username:
        raise ValueError("Readiness verification must stay on loopback HTTP")
    if not 0 < timeout <= 60:
        raise ValueError("Readiness deadline must be between 0 and 60 seconds")
    deadline = clock() + timeout
    while clock() < deadline:
        try:
            result = fetch(url, min(2, max(0.1, deadline - clock())))
            if isinstance(result, dict) and result.get("status") == "ready" and result.get("revision") == expected_revision:
                return True
        except Exception:
            pass
        sleep(min(0.25, max(0, deadline - clock())))
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--url", default=READY_URL)
    args = parser.parse_args()
    if not wait_ready(args.revision, args.url, args.timeout):
        print("Readiness failed: expected application revision and database connection were not confirmed.")
        raise SystemExit(1)
    print("Readiness verified for revision " + args.revision[:12])


if __name__ == "__main__":
    main()
