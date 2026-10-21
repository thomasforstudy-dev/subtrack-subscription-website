# Proposed updater: named failure steps — 21 Oct 2026

## Scope

Owner requested a review of Codex's proposed updater and a clear message naming
the failed step. This branch, `codex/deploy-step-errors`, starts at current main
`d9713de12c2172b355ce3dac355c20b4e4299a30`. It brings only the proposed updater,
its readiness registration and its simulated tests from `166085c`, then adds
named update/recovery failures. It does not bring the SQL preview tools or replace
the running preview's checkout. Main and the live updater are unchanged.
The latest main request (`b2400ba`) is merged into this branch; both sides of
the PROGRESS log were preserved.

## Finding and repair

The proposal reported only `Update FAILED (UpdateFailure)`. Command output was
intentionally hidden to avoid printing credentials, but this also hid whether
fetch, tests, backup, schema or startup failed.

Each operation now announces a fixed, readable step. The error repeats the last
step and the exception type, without raw exceptions, command output, environment
values, tokens or connection strings. Examples:

```text
Update step: Check database schema
Update FAILED at step: Check database schema (UpdateFailure). No update success is claimed.
Recovery step: Restore previous revision
```

```text
Update FAILED at step: Start updated server (UpdateFailure). No update success is claimed.
Recovery NOT verified at step: Start previous server (UpdateFailure). Manual review required.
```

The original failure stays visible even if recovery fails too. A failed update
still exits with code 1, including when recovery succeeds. A bounded health
failure is separately named `Verify updated server database and revision health`.
Missing Python, an inaccessible project folder and helper preparation also have
named failures. Progress messages contain only labels controlled by this code.

### Update steps

1. Check live branch.
2. Check for uncommitted files.
3. Record current revision.
4. Check server task and process ownership.
5. Fetch latest main.
6. Fast-forward to latest main.
7. Record new revision.
8. Install application dependencies.
9. Run application tests.
10. Stop current server.
11. Back up instance files (SQLite database and private uploads).
12. Check database schema.
13. Start updated server.
14. Verify updated server database and revision health.

Recovery labels separately identify stopping the server, restoring the previous
revision, restoring dependencies, starting the previous server and checking its
database/revision health. Temporary helper cleanup cannot hide the original error.

## Verification and limits

`tests/test_deploy_safety.py` injects failures at every update and recovery step,
including false readiness, command timeout and helper preparation. Assertions
cover the exact failed step, exit status 1, absence of success text and exclusion
of synthetic private diagnostics. Batch preflight is checked as source text;
the real live batch file is not executed.

Local exact-commit full-suite results are saved in the ignored
`instance/deploy-step-test-results.json` and `instance/deploy-step-tests.xml`.
These tests use SQLite and injected server operations. They do not establish
production SQL behavior or actual SYSTEM Task Scheduler startup/rollback.

**Review status: suitable for owner review, not approved for live replacement.**
Actual elevated/SYSTEM startup remains unverified. Startup no longer invokes
Git: revision capture reads repository metadata as described below.
An older release without the readiness endpoint cannot be called verified
recovery. Recovery restores code/dependencies, not database schema, and leaves
detached HEAD for manual review. SQL Server requires its own separately verified
database backup plus private uploads; the instance backup is not a SQL backup.

No live updater, service, scheduler, database migration, real email, external AI
or model training was run by this review. No merge or deployment is authorized
by a passing test result.

## Claude's two blockers — repaired on the review branch

1. **SYSTEM ownership:** removed `git rev-parse` from readiness registration.
   Revision capture reads `.git/HEAD`, loose refs or `packed-refs`, including a
   linked worktree's `.git` pointer and shared `commondir`. Detached HEAD works
   too. Invalid, missing or inaccessible metadata cannot prevent normal pages
   starting. The readiness response is instead 503 with an unknown revision;
   the updater still cannot claim a verified update. The revision is captured
   once, so a running old worker cannot claim newly pulled code.
2. **Public tunnel:** readiness refuses **any presence** of `CF-Connecting-IP`,
   including an empty header and a header claiming loopback. The refusal is an
   empty 404 with `Cache-Control: no-store`, before a database query or revision
   disclosure. Non-loopback requests are refused too. Direct IPv4/IPv6 loopback
   requests retain the database/revision checks. No service, tunnel or global
   Git configuration changes are needed for either repair.

Focused checks: **72 passed**, including 32 new cases for both blockers, plus the
40 deployment checks. Git subprocesses are forbidden by a regression probe.
Fixtures cover normal/packed/detached/worktree metadata, lookup failure while
login still works, fixed startup revision, direct loopback and tunneled GET/HEAD
refusal. These are automated local tests; actual SYSTEM startup and requests
through the production Cloudflare tunnel have not been executed by this review.
