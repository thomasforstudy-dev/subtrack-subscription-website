"""A small, SAFE load test for AllOutFree — run it against a LOCAL copy only.

It fires many concurrent GET requests at a few public pages of a server you
started yourself on 127.0.0.1, for a short time, and reports how fast it answered
and whether anything failed. It is for checking your own site's limits on your
own machine; it is NOT a tool for attacking a live site.

Guard rails (on purpose):
  - Refuses any host that is not localhost / 127.0.0.1 / ::1.
  - Capped: at most 60 seconds, 100 workers.
  - Read-only: only GET requests to public pages (no login, no forms, no POST).

Usage (after `python -m flask run` or run_local.bat in another terminal):
  python tools/loadtest.py --url http://127.0.0.1:5000 --seconds 20 --workers 40

What to look at in the report:
  - "ok %" should stay high; a flood should give tidy 200s or 429s, never 500s.
  - "429" means the rate limiter kicked in (good: it's protecting the server).
  - requests/second and the p95 time show how much a single process handles.
Put Cloudflare (your tunnel) in front for real traffic: it absorbs floods before
they reach this one Python process.
"""

import argparse
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from urllib.parse import urlparse

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
PATHS = ["/", "/login", "/register", "/guide", "/static/style.css", "/favicon.ico"]


def check_local(base: str) -> str:
    host = (urlparse(base).hostname or "").lower()
    if host not in LOCAL_HOSTS:
        sys.exit(f"Refusing to load-test {host!r}: this tool only runs against localhost. "
                 "Test on a copy you started yourself, never a live site.")
    return base.rstrip("/")


def worker(base, paths, stop_at, codes, times, lock):
    i = 0
    while time.monotonic() < stop_at:
        path = paths[i % len(paths)]
        i += 1
        start = time.monotonic()
        try:
            with urllib.request.urlopen(base + path, timeout=10) as res:
                status = res.status
                res.read(2048)  # read a little, then move on
        except urllib.error.HTTPError as exc:
            status = exc.code  # 429, 404, 500... all counted
        except Exception:
            status = 0  # connection refused / timeout
        dt = (time.monotonic() - start) * 1000
        with lock:
            codes[status] += 1
            times.append(dt)


def main():
    ap = argparse.ArgumentParser(description="Local-only load test for AllOutFree.")
    ap.add_argument("--url", default="http://127.0.0.1:5000")
    ap.add_argument("--seconds", type=int, default=20)
    ap.add_argument("--workers", type=int, default=40)
    args = ap.parse_args()

    base = check_local(args.url)
    seconds = max(1, min(args.seconds, 60))
    workers = max(1, min(args.workers, 100))

    print(f"Load test: {base}  ·  {workers} workers  ·  {seconds}s  ·  GET only")
    codes, times, lock = Counter(), [], threading.Lock()
    stop_at = time.monotonic() + seconds
    threads = [threading.Thread(target=worker, args=(base, PATHS, stop_at, codes, times, lock)) for _ in range(workers)]
    t0 = time.monotonic()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.monotonic() - t0

    total = sum(codes.values())
    ok = sum(n for code, n in codes.items() if 200 <= code < 400)
    print(f"\nrequests: {total}  ·  {total / elapsed:.0f}/s  ·  ok: {100 * ok / total:.1f}%" if total else "no requests")
    for code, n in sorted(codes.items()):
        label = {0: "connection failed", 429: "rate-limited (good)", 500: "server error (bad)"}.get(code, "")
        print(f"  {code or 'ERR':>5}: {n:>6}  {label}")
    if times:
        times.sort()
        p95 = times[int(len(times) * 0.95) - 1]
        print(f"latency ms: median {statistics.median(times):.0f}  ·  p95 {p95:.0f}  ·  max {max(times):.0f}")
    if codes.get(500):
        print("\n⚠ 500s appeared under load — worth a look. Tidy 200/404/429 is what you want.")


if __name__ == "__main__":
    main()
