"""Checked update/recovery flow. Never run during preview validation."""

import os
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

from deploy.health import wait_ready

ROOT = Path(__file__).resolve().parents[1]


class UpdateFailure(Exception):
    pass


def command(args, *, capture=False, timeout=600):
    # Driver/git diagnostics can include connection details. Only explicitly
    # requested, successful Git metadata is returned to the caller.
    result = subprocess.run(args, cwd=ROOT, timeout=timeout, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode:
        raise UpdateFailure("Command failed: " + str(args[0]))
    return result.stdout.strip() if capture else ""


def perform_update(run, control, ready, backup, python, emit=print):
    """Dependencies make every failure path testable without touching a server."""
    old = None
    changed = False
    stopped = False
    stop_attempted = False
    step = "Check live branch"

    def update_step(label, action, *args, **kwargs):
        nonlocal step
        step = label
        emit("Update step: " + label)
        return action(*args, **kwargs)

    try:
        if update_step("Check live branch", run, ["git", "branch", "--show-current"], capture=True) != "main":
            raise UpdateFailure("Run only from the live main checkout.")
        if update_step("Check for uncommitted files", run, ["git", "status", "--porcelain"], capture=True):
            raise UpdateFailure("Checkout has uncommitted files; preserve them first.")
        old = update_step("Record current revision", run, ["git", "rev-parse", "HEAD"], capture=True)
        update_step("Check server task and process ownership", control, "check")
        update_step("Fetch latest main", run, ["git", "fetch", "origin"])
        changed = True
        update_step("Fast-forward to latest main", run, ["git", "merge", "--ff-only", "origin/main"])
        new = update_step("Record new revision", run, ["git", "rev-parse", "HEAD"], capture=True)
        update_step("Install application dependencies", run,
                    [python, "-m", "pip", "install", "-q", "-r", "requirements.txt"])
        update_step("Run application tests", run,
                    [python, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--basetemp",
                     str(Path(tempfile.gettempdir()) / ("subtrack-tests-" + uuid.uuid4().hex))])
        stop_attempted = True
        update_step("Stop current server", control, "stop")
        stopped = True
        update_step("Back up instance files (SQLite database and private uploads)", backup)
        update_step("Check database schema", run, [python, "-m", "flask", "--app", "app", "check-db"])
        update_step("Start updated server", control, "start")
        if not update_step("Verify updated server database and revision health", ready, new):
            raise UpdateFailure("New application did not pass bounded database/revision readiness.")
        emit("Update verified on revision " + new[:12])
        return 0
    except Exception as error:
        emit("Update FAILED at step: " + step + " (" + type(error).__name__
             + "). No update success is claimed.")
        # Do not print subprocess/driver exceptions: they may contain credentials.
        if not changed or not old:
            return 1

        recovery_step = "Restore previous revision"

        def recover(label, action, *args):
            nonlocal recovery_step
            recovery_step = label
            emit("Recovery step: " + label)
            return action(*args)

        try:
            if stop_attempted:
                recover("Stop server before recovery", control, "stop")
                stopped = True
            recover("Restore previous revision", run, ["git", "switch", "--detach", old])
            recover("Restore previous dependencies", run,
                    [python, "-m", "pip", "install", "-q", "-r", "requirements.txt"])
            if stopped:
                recover("Start previous server", control, "start")
                if not recover("Verify previous server database and revision health", ready, old):
                    raise UpdateFailure("Recovery readiness was not confirmed.")
            emit("Previous code restored; review detached HEAD before another update.")
        except Exception as recovery_error:
            emit("Recovery NOT verified at step: " + recovery_step + " ("
                 + type(recovery_error).__name__ + "). Manual review required.")
        return 1


def main():
    python = str(ROOT / ".venv" / "Scripts" / "python.exe")
    os.environ["CI"] = "true"
    # Keep this helper available if recovery checks out an older revision.
    temporary = None
    step = "Create temporary updater folder"
    try:
        temporary = tempfile.TemporaryDirectory(prefix="subtrack-update-")
        step = "Copy server-control helper"
        helper = Path(temporary.name) / "server_control.ps1"
        helper.write_bytes((ROOT / "deploy" / "server_control.ps1").read_bytes())
    except Exception as error:
        print("Update FAILED at step: " + step + " (" + type(error).__name__
              + "). No update success is claimed.")
        if temporary is not None:
            try:
                temporary.cleanup()
            except OSError:
                print("Warning: temporary updater helper cleanup failed; remove it manually later.")
        return 1

    try:
        def control(action):
            command(["powershell.exe", "-NoProfile", "-File", str(helper), action,
                     "-ProjectRoot", str(ROOT)], timeout=30)

        def backup():
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8]
            target = Path.home() / "SubTrack-backups" / stamp
            target.mkdir(parents=True, exist_ok=False)
            result = subprocess.run(["robocopy", str(ROOT / "instance"), str(target),
                                     "/E", "/NFL", "/NDL", "/NJH", "/NJS"], timeout=300)
            if result.returncode >= 8:
                raise UpdateFailure("Private upload/instance backup failed.")
            print("New instance backup saved: " + str(target))

        return perform_update(command, control, wait_ready, backup, python)
    finally:
        # Cleanup is not a deployment step; its failure must not mask the real one.
        try:
            temporary.cleanup()
        except OSError:
            print("Warning: temporary updater helper cleanup failed; remove it manually later.")


if __name__ == "__main__":
    sys.exit(main())
