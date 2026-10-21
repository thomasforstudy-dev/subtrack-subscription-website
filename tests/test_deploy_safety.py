"""Simulate deployment failures; never invoke Task Scheduler or the live updater."""

import pytest

from deploy.health import install_readiness, wait_ready
from deploy.update import UpdateFailure, perform_update


class Clock:
    def __init__(self):
        self.now = 0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


@pytest.mark.parametrize("value", [{}, {"status": "ready", "revision": "old"},
                                 {"status": "unavailable", "revision": "new"}, None])
def test_readiness_rejects_stale_or_failed_health(value):
    clock = Clock()
    assert not wait_ready("new", timeout=1, fetch=lambda *args: value,
                          clock=clock, sleep=clock.sleep)
    assert clock.now == 1


def test_readiness_recovers_from_network_error():
    clock = Clock()
    calls = []

    def fetch(*args):
        calls.append(args)
        if len(calls) == 1:
            raise OSError("offline")
        return {"status": "ready", "revision": "new"}

    assert wait_ready("new", timeout=1, fetch=fetch, clock=clock, sleep=clock.sleep)
    assert len(calls) == 2


@pytest.mark.parametrize("url", ["https://example.com/", "http://192.168.1.1/", "http://user@127.0.0.1/"])
def test_readiness_rejects_external_addresses(url):
    with pytest.raises(ValueError):
        wait_ready("new", url=url)


@pytest.mark.parametrize("timeout", [0, -1, 61])
def test_readiness_deadline_is_bounded(timeout):
    with pytest.raises(ValueError):
        wait_ready("new", timeout=timeout)


def test_readiness_checks_database_and_redacts_failures(app, monkeypatch):
    from app import db
    monkeypatch.setattr("deploy.health.subprocess.check_output", lambda *args, **kwargs: b"new")
    install_readiness(app)
    client = app.test_client()
    healthy = client.get("/__subtrack__/ready")
    assert healthy.json == {"status": "ready", "revision": "new"}
    assert healthy.headers["Cache-Control"] == "no-store"

    def fail(*args, **kwargs):
        raise RuntimeError("private DSN password must not appear")

    monkeypatch.setattr(db.session, "execute", fail)
    unhealthy = client.get("/__subtrack__/ready")
    assert unhealthy.status_code == 503
    assert unhealthy.json == {"status": "unavailable", "revision": "new"}
    assert "private" not in unhealthy.text and "password" not in unhealthy.text


class FakeServer:
    def __init__(self, failure=None, branch="main", dirty=""):
        self.failure = failure
        self.branch = branch
        self.dirty = dirty
        self.events = []
        self.lines = []
        self.revisions = 0
        self.failed = False

    def event(self, name):
        self.events.append(name)
        if name == self.failure and not self.failed:
            self.failed = True
            raise UpdateFailure("private password hidden")

    def run(self, args, **kwargs):
        name = " ".join(args[:4])
        self.event(name)
        if args[1:3] == ["branch", "--show-current"]:
            return self.branch
        if args[1] == "status":
            return self.dirty
        if args[1:3] == ["rev-parse", "HEAD"]:
            self.revisions += 1
            return "old" if self.revisions == 1 else "new"
        return ""

    def control(self, action):
        self.event(action)

    def ready(self, revision):
        self.event("ready:" + revision)
        return True

    def backup(self):
        self.event("backup")

    def update(self):
        return perform_update(self.run, self.control, self.ready, self.backup, "python", self.lines.append)


@pytest.mark.parametrize("failure,step", [
    ("git branch --show-current", "Check live branch"),
    ("git status --porcelain", "Check for uncommitted files"),
    ("git rev-parse HEAD", "Record current revision"),
    ("check", "Check server task and process ownership"),
    ("git fetch origin", "Fetch latest main"),
    ("git merge --ff-only origin/main", "Fast-forward to latest main"),
    ("python -m pip install", "Install application dependencies"),
    ("python -m pytest -q", "Run application tests"),
    ("stop", "Stop current server"),
    ("backup", "Back up instance files (SQLite database and private uploads)"),
    ("python -m flask --app", "Check database schema"),
    ("start", "Start updated server"),
    ("ready:new", "Verify updated server database and revision health"),
])
def test_each_deployment_failure_returns_failure_without_success(failure, step):
    server = FakeServer(failure)
    assert server.update() == 1
    assert f"Update FAILED at step: {step} (UpdateFailure). No update success is claimed." in server.lines
    assert not any("Update verified" in line for line in server.lines)
    assert not any("password" in line for line in server.lines)
    if failure == "python -m flask --app":
        assert server.events.index("git switch --detach old") < server.events.index("start")
    if failure in {"python -m pip install", "python -m pytest -q"}:
        assert "stop" not in server.events and "start" not in server.events


def test_failed_health_returns_failure_even_when_rollback_healthy():
    server = FakeServer()
    server.ready = lambda revision: revision == "old"
    assert server.update() == 1
    assert "git switch --detach old" in server.events
    assert not any("Update verified" in line for line in server.lines)
    assert any("Update FAILED at step: Verify updated server database and revision health" in line
               for line in server.lines)


@pytest.mark.parametrize("branch,dirty,step", [
    ("codex/preview", "", "Check live branch"),
    ("main", "?? new-file", "Check for uncommitted files"),
])
def test_preflight_preserves_work(branch, dirty, step):
    server = FakeServer(branch=branch, dirty=dirty)
    assert server.update() == 1
    assert not any(event in server.events for event in ["stop", "start", "backup", "git fetch origin"])
    assert any("Update FAILED at step: " + step in line for line in server.lines)


def test_recovery_failure_is_explicit():
    server = FakeServer("backup")
    original = server.run

    def run(args, **kwargs):
        if args[1] == "switch":
            raise UpdateFailure("Recovery failed")
        return original(args, **kwargs)

    server.run = run
    assert server.update() == 1
    assert any("Recovery NOT verified" in line for line in server.lines)
    assert any("Recovery NOT verified at step: Restore previous revision" in line for line in server.lines)


@pytest.mark.parametrize("step", [
    "Stop server before recovery", "Restore previous revision", "Restore previous dependencies",
    "Start previous server", "Verify previous server database and revision health",
])
def test_each_recovery_failure_names_its_own_step_and_preserves_original(step):
    server = FakeServer("backup")
    original_run, original_control, original_ready = server.run, server.control, server.ready

    def fail():
        raise RuntimeError("SECRET synthetic DSN must never appear")

    def control(action):
        if server.failed and ((action == "stop" and step == "Stop server before recovery")
                              or (action == "start" and step == "Start previous server")):
            fail()
        return original_control(action)

    def run(args, **kwargs):
        if server.failed and ((args[1] == "switch" and step == "Restore previous revision")
                              or (args[1:3] == ["-m", "pip"] and step == "Restore previous dependencies")):
            fail()
        return original_run(args, **kwargs)

    def ready(revision):
        if revision == "old" and step == "Verify previous server database and revision health":
            return False
        return original_ready(revision)

    server.run, server.control, server.ready = run, control, ready
    assert server.update() == 1
    assert any("Update FAILED at step: Back up instance files" in line for line in server.lines)
    assert any("Recovery NOT verified at step: " + step in line for line in server.lines)
    assert not any("SECRET" in line or "DSN" in line or "Update verified" in line for line in server.lines)


def test_new_revision_read_failure_names_step():
    server = FakeServer()
    original = server.run

    def run(args, **kwargs):
        if args[1:3] == ["rev-parse", "HEAD"] and server.revisions == 1:
            raise OSError("private diagnostic")
        return original(args, **kwargs)

    server.run = run
    assert server.update() == 1
    assert any("Update FAILED at step: Record new revision (OSError)" in line for line in server.lines)
    assert not any("private diagnostic" in line for line in server.lines)


@pytest.mark.parametrize("failed_step", ["Create temporary updater folder", "Copy server-control helper"])
def test_helper_preparation_failure_names_step_without_driver_output(monkeypatch, capsys, failed_step):
    from deploy import update

    def fail(*args, **kwargs):
        raise OSError("SECRET preparation details")

    if failed_step == "Create temporary updater folder":
        monkeypatch.setattr(update.tempfile, "TemporaryDirectory", fail)
    else:
        monkeypatch.setattr(update.Path, "write_bytes", fail)
    assert update.main() == 1
    output = capsys.readouterr().out
    assert "Update FAILED at step: " + failed_step + " (OSError)" in output
    assert "SECRET" not in output


def test_command_timeout_output_never_reaches_failure_message(monkeypatch):
    from deploy import update
    import subprocess

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(["private connection string"], 600, output="SECRET output")

    monkeypatch.setattr(update.subprocess, "run", timeout)
    server = FakeServer()
    server.run = update.command
    assert server.update() == 1
    assert any("Update FAILED at step: Check live branch (TimeoutExpired)" in line for line in server.lines)
    assert not any("SECRET" in line or "private" in line for line in server.lines)


def test_batch_preflight_names_the_failed_step():
    from pathlib import Path

    wrapper = (Path(__file__).resolve().parents[1] / "deploy" / "update_server.bat").read_text()
    assert 'cd /d "%~dp0.." || (' in wrapper
    assert "Update FAILED at step: Open project folder." in wrapper
    assert "Update FAILED at step: Locate Python virtual environment." in wrapper
    assert "endlocal & exit /b %RESULT%" in wrapper


def test_success_requires_schema_start_and_exact_revision_health():
    server = FakeServer()
    assert server.update() == 0
    assert server.events.index("backup") < server.events.index("python -m flask --app")
    assert server.events.index("python -m flask --app") < server.events.index("start")
    assert server.events[-1] == "ready:new"
    assert server.lines[-1] == "Update verified on revision new"
    assert len([line for line in server.lines if line.startswith("Update step:")]) == 14
    assert not any("FAILED" in line or "Recovery step:" in line for line in server.lines)
