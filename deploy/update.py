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
    try:
        if run(["git", "branch", "--show-current"], capture=True) != "main":
            raise UpdateFailure("Run only from the live main checkout.")
        if run(["git", "status", "--porcelain"], capture=True):
            raise UpdateFailure("Checkout has uncommitted files; preserve them first.")
        old = run(["git", "rev-parse", "HEAD"], capture=True)
        control("check")
        run(["git", "fetch", "origin"])
        changed = True
        run(["git", "merge", "--ff-only", "origin/main"])
        new = run(["git", "rev-parse", "HEAD"], capture=True)
        run([python, "-m", "pip", "install", "-q", "-r", "requirements.txt"])
        run([python, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--basetemp",
             str(Path(tempfile.gettempdir()) / ("subtrack-tests-" + uuid.uuid4().hex))])
        stop_attempted = True
        control("stop")
        stopped = True
        backup()
        run([python, "-m", "flask", "--app", "app", "check-db"])
        control("start")
        if not ready(new):
            raise UpdateFailure("New application did not pass bounded database/revision readiness.")
        emit("Update verified on revision " + new[:12])
        return 0
    except Exception as error:
        emit("Update FAILED (" + type(error).__name__ + "). No update success is claimed.")
        # Do not print subprocess/driver exceptions: they may contain credentials.
        if not changed or not old:
            return 1
        try:
            if stop_attempted:
                control("stop")
                stopped = True
            run(["git", "switch", "--detach", old])
            run([python, "-m", "pip", "install", "-q", "-r", "requirements.txt"])
            if stopped:
                control("start")
                if not ready(old):
                    raise UpdateFailure("Recovery readiness was not confirmed.")
            emit("Previous code restored; review detached HEAD before another update.")
        except Exception as recovery_error:
            emit("Recovery NOT verified (" + type(recovery_error).__name__ + "). Manual review required.")
        return 1


def main():
    python = str(ROOT / ".venv" / "Scripts" / "python.exe")
    os.environ["CI"] = "true"
    # Keep this helper available if recovery checks out an older revision.
    with tempfile.TemporaryDirectory(prefix="subtrack-update-") as temporary:
        helper = Path(temporary) / "server_control.ps1"
        helper.write_bytes((ROOT / "deploy" / "server_control.ps1").read_bytes())

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


if __name__ == "__main__":
    sys.exit(main())
