"""Readiness under restricted accounts and requests forwarded by Cloudflare."""

from pathlib import Path
import subprocess

import pytest

from deploy.health import install_readiness, read_revision

REVISION = "a" * 40
NEXT_REVISION = "b" * 40


def put(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_revision_reads_normal_loose_ref_without_git(tmp_path, monkeypatch):
    def no_git(*args, **kwargs):
        raise AssertionError("Git must never run during readiness registration")

    monkeypatch.setattr(subprocess, "run", no_git)
    monkeypatch.setattr(subprocess, "check_output", no_git)
    put(tmp_path / ".git/HEAD", "ref: refs/heads/main\n")
    put(tmp_path / ".git/refs/heads/main", REVISION + "\n")
    assert read_revision(tmp_path) == REVISION


@pytest.mark.parametrize("revision", [REVISION, "c" * 64])
def test_revision_reads_detached_head(tmp_path, revision):
    put(tmp_path / ".git/HEAD", revision + "\n")
    assert read_revision(tmp_path) == revision


def test_revision_reads_packed_ref_exactly(tmp_path):
    put(tmp_path / ".git/HEAD", "ref: refs/heads/main\n")
    put(tmp_path / ".git/packed-refs", "# pack-refs with: peeled\n"
        + NEXT_REVISION + " refs/heads/main-other\n^" + NEXT_REVISION + "\n"
        + REVISION + " refs/heads/main\n")
    assert read_revision(tmp_path) == REVISION


@pytest.mark.parametrize("packed", [False, True])
@pytest.mark.parametrize("absolute_pointer", [False, True])
def test_revision_reads_worktree_head_and_common_refs(tmp_path, packed, absolute_pointer):
    root = tmp_path / "checkout"
    common = tmp_path / "shared.git"
    git_dir = common / "worktrees/review"
    pointer = str(git_dir) if absolute_pointer else "../shared.git/worktrees/review"
    put(root / ".git", "gitdir: " + pointer + "\n")
    put(git_dir / "commondir", "../..\n")
    put(git_dir / "HEAD", "ref: refs/heads/codex/review\n")
    if packed:
        put(common / "packed-refs", REVISION + " refs/heads/codex/review\n")
    else:
        put(common / "refs/heads/codex/review", REVISION + "\n")
    assert read_revision(root) == REVISION


@pytest.mark.parametrize("head", ["not-a-revision", "ref: refs/heads/missing",
    "ref: refs/../../outside", "ref: refs/heads/../outside", "ref: C:/private", "ref: refs\\heads\\main"])
def test_missing_or_invalid_revision_is_unknown(tmp_path, head):
    put(tmp_path / ".git/HEAD", head)
    assert read_revision(tmp_path) is None


def test_missing_repository_or_bad_git_pointer_is_unknown(tmp_path):
    assert read_revision(tmp_path) is None
    put(tmp_path / ".git", "not a git directory pointer")
    assert read_revision(tmp_path) is None


def test_unreadable_git_metadata_is_unknown(tmp_path, monkeypatch):
    put(tmp_path / ".git/HEAD", REVISION)
    original = Path.read_text

    def read(path, *args, **kwargs):
        if path.name == "HEAD":
            raise PermissionError("synthetic private path")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)
    assert read_revision(tmp_path) is None


def test_symbolic_ref_cycle_is_unknown(tmp_path):
    put(tmp_path / ".git/HEAD", "ref: refs/heads/main")
    put(tmp_path / ".git/refs/heads/main", "ref: refs/heads/main")
    assert read_revision(tmp_path) is None


def test_startup_reads_actual_checkout_without_invoking_git(app, monkeypatch):
    def no_git(*args, **kwargs):
        pytest.fail("Readiness startup must not run Git under SYSTEM")

    monkeypatch.setattr(subprocess, "run", no_git)
    monkeypatch.setattr(subprocess, "check_output", no_git)
    install_readiness(app)
    response = app.test_client().get("/__subtrack__/ready")
    assert response.status_code == 200
    assert response.json["revision"] == read_revision(Path(__file__).resolve().parents[1])


@pytest.mark.parametrize("raises", [False, True])
def test_lookup_failure_does_not_stop_site_but_cannot_pass_readiness(app, monkeypatch, raises):
    def unknown(root):
        if raises:
            raise PermissionError("SECRET lookup details")
        return None

    monkeypatch.setattr("deploy.health.read_revision", unknown)
    install_readiness(app)
    client = app.test_client()
    assert client.get("/login").status_code == 200
    response = client.get("/__subtrack__/ready")
    assert response.status_code == 503
    assert response.json == {"status": "unavailable", "revision": None}
    assert response.headers["Cache-Control"] == "no-store"
    assert "SECRET" not in response.text


@pytest.mark.parametrize("method", ["GET", "HEAD"])
@pytest.mark.parametrize("header,value", [("CF-Connecting-IP", "198.51.100.5"),
                                          ("cf-connecting-ip", ""),
                                          ("Cf-Connecting-Ip", "127.0.0.1")])
def test_cloudflare_from_loopback_is_refused_before_database(app, monkeypatch, method, header, value):
    from app import db

    monkeypatch.setattr("deploy.health.read_revision", lambda root: REVISION)
    install_readiness(app)

    def no_database(*args, **kwargs):
        pytest.fail("Tunneled requests must not perform the database health query")

    monkeypatch.setattr(db.session, "execute", no_database)
    response = app.test_client().open("/__subtrack__/ready", method=method,
                                    headers={header: value}, environ_overrides={"REMOTE_ADDR": "127.0.0.1"})
    assert response.status_code == 404
    assert response.data == b""
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("remote", ["192.0.2.5", "", "::ffff:192.0.2.5"])
def test_non_loopback_without_cloudflare_header_is_refused(app, monkeypatch, remote):
    monkeypatch.setattr("deploy.health.read_revision", lambda root: REVISION)
    install_readiness(app)
    response = app.test_client().get("/__subtrack__/ready", environ_overrides={"REMOTE_ADDR": remote})
    assert response.status_code == 404
    assert response.data == b""


@pytest.mark.parametrize("remote", ["127.0.0.1", "::1"])
def test_direct_loopback_database_health_succeeds(app, monkeypatch, remote):
    monkeypatch.setattr("deploy.health.read_revision", lambda root: REVISION)
    install_readiness(app)
    response = app.test_client().get("/__subtrack__/ready", environ_overrides={"REMOTE_ADDR": remote})
    assert response.status_code == 200
    assert response.json == {"status": "ready", "revision": REVISION}


def test_running_worker_keeps_startup_revision_when_checkout_moves(app, tmp_path, monkeypatch):
    head = tmp_path / ".git/HEAD"
    put(head, REVISION)
    monkeypatch.setattr("deploy.health.read_revision", lambda root: read_revision(tmp_path))
    install_readiness(app)
    put(head, NEXT_REVISION)
    response = app.test_client().get("/__subtrack__/ready")
    assert response.status_code == 200
    assert response.json["revision"] == REVISION
