"""Minimal server readiness and bounded loopback-only deployment verification."""

import argparse
import json
import subprocess
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, build_opener

READY_URL = "http://127.0.0.1:8000/__subtrack__/ready"


def install_readiness(app):
    # Capture at startup: an old worker cannot claim to serve a newly pulled commit.
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"],
                                       cwd=Path(__file__).resolve().parents[1], timeout=5).decode().strip()
    from flask import jsonify
    from sqlalchemy import text
    from app import db

    @app.get("/__subtrack__/ready")
    def readiness():
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
