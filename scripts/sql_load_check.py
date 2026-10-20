"""Bounded 1/5/10-user HTTP workload, on the dedicated synthetic SQL preview only."""

import ctypes
import json
import math
import os
import secrets
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pyodbc
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.sql_preview import DATABASE, INSTANCE, access_details, dsn
from scripts.sql_web_checks import Client, exports, health, require


def cpu_sample():
    from ctypes import wintypes
    idle, kernel, user = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
    if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
        raise RuntimeError("Cannot monitor host CPU; refusing load")
    number = lambda value: (value.dwHighDateTime << 32) | value.dwLowDateTime
    return number(idle), number(kernel) + number(user)


def percentile(values, fraction):
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)] if values else None


def live_probe(session):
    started = time.perf_counter()
    response = session.get("http://127.0.0.1:8000/login", timeout=3)
    return response.status_code, time.perf_counter() - started


def run_stage(users, seconds=20):
    require(os.name == "nt", "This laptop workload requires Windows resource monitoring")
    require(0 < seconds <= 300 and users in (1, 5, 10), "Invalid bounded stage")
    identity = health()
    require(not identity["dirty"], "Commit the preview code before recording load measurements")
    marker = "load_" + secrets.token_hex(5) + "_" + str(users)
    records, samples, errors, intended = [], [], [], []
    lock = threading.Lock()
    stop = threading.Event()
    live = requests.Session(); live.trust_env = False
    baseline = [live_probe(live) for _ in range(3)]
    require(all(code == 200 for code, _ in baseline), "Live site is not healthy before load; refusing test")
    live_limit = max(1.0, max(seconds for _, seconds in baseline) * 5)

    def record(method, path, status, elapsed):
        with lock:
            records.append({"method": method, "path": path.split("?")[0], "status": status, "ms": elapsed})

    clients = [Client(account).login() for account in access_details()["accounts"][2:2 + users]]
    for client in clients:
        client.record = record
    started = time.perf_counter()
    deadline = started + seconds

    def monitor():
        previous = cpu_sample()
        pressure_hits = 0
        live_hits = 0
        with pyodbc.connect(dsn(), autocommit=True) as conn:
            conn.timeout = 3
            while not stop.wait(0.5):
                now = cpu_sample()
                cpu = 100 * (1 - (now[0] - previous[0]) / max(1, now[1] - previous[1]))
                previous = now
                blocked, longest = conn.execute(
                    "SELECT COUNT(*),COALESCE(MAX(wait_time),0) FROM sys.dm_exec_requests "
                    "WHERE database_id=DB_ID(?) AND session_id<>@@SPID AND blocking_session_id>0", DATABASE).fetchone()
                low_memory = conn.execute(
                    "SELECT process_physical_memory_low,process_virtual_memory_low FROM sys.dm_os_process_memory").fetchone()
                code, latency = live_probe(live)
                samples.append({"elapsed_seconds": round(time.perf_counter() - started, 2),
                                "host_cpu_percent": round(cpu, 2), "blocked_sql_requests": blocked,
                                "longest_observed_wait_ms": longest, "sql_memory_pressure": bool(any(low_memory)),
                                "live_status": code, "live_latency_ms": round(latency * 1000, 2)})
                pressure_hits = pressure_hits + 1 if cpu >= 85 else 0
                live_hits = live_hits + 1 if code != 200 or latency > live_limit else 0
                if pressure_hits >= 10 or any(low_memory) or live_hits >= 3:
                    errors.append("Stopped: sustained CPU/SQL memory pressure or degraded live response")
                    stop.set()
                    break

    def worker(index, client):
        try:
            for number in range(100):
                if stop.is_set() or time.perf_counter() >= deadline:
                    break
                if number in (0, 10):
                    name = f"{marker}_{index}_{number}"
                    if number == 0:
                        response = client.post("/bills/new", {"merchant": name, "currency": "USD", "total": "1.23",
                            "item_name_1": "Synthetic load item", "item_qty_1": "1", "item_price_1": "1.23"})
                        kind = "bill"
                    else:
                        response = client.post("/subscriptions/new", {"name": name, "amount": "0.11", "currency": "USD",
                            "cycle": "monthly", "next_renewal_at": "2028-01-31", "lead_days": "7"})
                        kind = "subscription"
                    with lock:
                        intended.append({"user": client.account["username"], "name": name, "kind": kind,
                                         "http_status": response.status_code})
                    require(response.status_code == 302, "Controlled write failed")
                else:
                    paths = ["/dashboard.json", "/subscriptions/", "/bills/", "/links/", "/calendar/", "/bills/export.json"]
                    require(client.get(paths[number % len(paths)]).status_code == 200, "Representative read failed")
                stop.wait(0.2)
        except Exception as error:
            with lock:
                errors.append(type(error).__name__ + ": " + str(error))
            stop.set()

    monitor_error = []

    def safe_monitor():
        try:
            monitor()
        except Exception as error:
            monitor_error.append(type(error).__name__)
            stop.set()  # never continue without resource/live-site monitoring

    thread = threading.Thread(target=safe_monitor, daemon=True)
    thread.start()
    with ThreadPoolExecutor(max_workers=users) as pool:
        list(pool.map(lambda pair: worker(*pair), enumerate(clients)))
    duration = time.perf_counter() - started
    stop.set(); thread.join(timeout=5)
    require(not thread.is_alive(), "Monitor did not terminate")
    failed_writes = []
    for client in clients:
        client.record = None
        bills = exports(client)
        for write in (item for item in intended if item["user"] == client.account["username"]):
            if write["kind"] == "bill":
                matches = [row for row in bills if row["merchant_name"] == write["name"]]
                saved = len(matches) == 1 and matches[0]["total"] == "1.23" and matches[0]["line_items"][0]["amount"] == "1.23"
            else:
                page = client.get("/subscriptions/?q=" + write["name"])
                saved = write["name"] in page.text and "0.11 USD" in page.text
            if write["http_status"] != 302 or not saved:
                failed_writes.append(write)
    timings = [row["ms"] for row in records]
    result = {"identity": identity, "users": users, "maximum_seconds": seconds, "actual_seconds": round(duration, 2),
              "maximum_requests_per_user": 100, "think_seconds": 0.2, "request_count": len(records),
              "p50_ms": round(percentile(timings, 0.5), 2), "p95_ms": round(percentile(timings, 0.95), 2),
              "max_ms": round(max(timings), 2), "http_errors": [row for row in records if row["status"] not in (200, 302)],
              "errors": errors + monitor_error, "attempted_writes": len(intended), "failed_writes": failed_writes,
              "all_saved_data_verified": not failed_writes, "sample_interval_seconds": 0.5,
              "maximum_observed_blocked_requests": max((s["blocked_sql_requests"] for s in samples), default=0),
              "maximum_observed_sql_wait_ms": max((s["longest_observed_wait_ms"] for s in samples), default=0),
              "live_baseline_ms": [round(t * 1000, 2) for _, t in baseline], "live_stop_threshold_ms": live_limit * 1000,
              "stop_rules": "CPU >=85% for ten consecutive samples, SQL low-memory flag, or three degraded live probes",
              "samples": samples, "interpretation": "Measured synthetic workload; not a proposed target or production capacity guarantee"}
    (INSTANCE / f"sql-load-{users}.json").write_text(json.dumps(result, indent=2))
    print(json.dumps({key: result[key] for key in ["users", "request_count", "actual_seconds", "p50_ms", "p95_ms", "max_ms", "attempted_writes", "failed_writes", "errors", "maximum_observed_blocked_requests"]}))
    require(not result["errors"] and not result["http_errors"] and not failed_writes, "Stage failed or stopped; inspect recorded result")
    return result


if __name__ == "__main__":
    results = [run_stage(users) for users in (1, 5, 10)]
    (INSTANCE / "sql-load-results.json").write_text(json.dumps(results, indent=2))
