# Current AllOutFree main: SQL Server validation and updater review

## Source and branch isolation

Main at task start: **4e086799ccd2d34e03ba6efb8fdbc3dbc7ba21d1** (AllOutFree v3,
mascot and the fixes for the earlier R1–R5 review).

The requested **codex/sql-application-preview** branch was pushed unchanged at
**adac36453da3067af6c43f04635b0a4a56880ed6**. No credentials, private invoices,
uploads or database files were included.

For current-main checks, Codex created a separate worktree/branch:
`subtrack-sql-current-main` / **codex/sql-current-main-validation**. Merge
**e318dab47043be9c23d34cd9c71d626c897a82e9** combines current main and the SQL
preview tools. The only conflict was PROGRESS.md; both sides were retained and
checked against both original files. No conflict markers remain. Current main's
dashboard, AllOutFree styling, mascot, static cache versioning and bill repairs
were preserved.

**Nothing was merged into main or deployed by this task.** The live checkout,
Windows services and existing previews were not controlled by these checks.

## SQL connection and preview

- Existing `localhost\SQLEXPRESS`, Windows integrated authentication, ODBC 18.
- Explicit provider **mssql**, actual `DB_NAME()` checked before queries.
- New dedicated synthetic database **SubTrack_CodexMainPreview_20261020**.
- Separate loopback preview: **http://127.0.0.1:8774/dashboard**.
- Migrations **01–07** applied initially, then twice more with exact before/after
  synthetic record hashes. No source database was dropped, truncated or cleared.
- New owner-only login files and private uploads stay in this worktree's ignored
  instance folder. Exact dashboard login-file location is recorded in the local
  `instance/sql-dashboard-results.json`. No password is printed or committed.
- Fake AI, memory mail, no reminder/document-processing CLI, no OCR service and
  no external network writes. SQL connection failure cannot fall back to SQLite.

The original SQL preview remains at 8773 in its original worktree/database;
SQLite preview 8772 and the live service on 8000 are separate. Fixed names/port
in this validation branch deliberately identify the new preview, not the old one.
The new preview also uses distinct session/remember cookie names: browser cookies
are shared across ports on a host, so another port alone would not preserve the
older preview's login. HTTP checks verify the new session cookie is actually issued.

## Confirmed bug and isolated repair

The first **actual SQL Server** overview checks exposed a month-window bug in
main's `app/dashboard.py`: Spent this month had a lower date bound but no upper
bound. The synthetic current-month receipts were 0.10 + 0.20 USD. Future-month
receipts (13.37, 3.33 and 999 USD) incorrectly made the tile **1016.00 USD**.

All four clock/boundary cases reproduced it. This is a logical query-bound bug,
not a SQL Server driver failure. Baseline evidence is retained locally in
`instance/sql-dashboard-main-before-fix.json`.

The repair on the validation branch adds:

```python
func.coalesce(Bill.transaction_date, Bill.invoice_date) < month_start(today, 1)
```

The existing lower bound is retained. A regression was added to
`tests/test_dashboard_v3.py`. No template, CSS or other shared backend file was
changed. Codex reserved this narrow backend repair in project coordination
memory before editing it. **The repair is not yet on live main.**

## Verification

Focused local suite: **47 passed**, Python 3.14.8, including dashboard, mascot,
preview safety and simulated deployment failure tests.

Actual SQL checks (`scripts/validate_sqlserver.py --dashboard-only`):

- Real-date overview plus January month-end, leap day and UTC+14 year rollover.
  Fixed clocks are explicit fixtures; SQL queries execute against SQL Server.
- COALESCE returns a Python date; money remains Decimal. Transaction date takes
  priority, invoice date is the fallback, and missing dates are excluded.
- Exact 0.10 + 0.20 = **0.30**; future and prior months excluded from current
  spending. Other currencies, archived bills, card statements and other users
  do not enter receipt spending.
- Six chart months, first/last boundaries, skipped renewal history, monthly/yearly
  projections, chart percentages, active counts and account-scoped activity.
- Real authenticated HTTP: dashboard HTML/chart and dashboard JSON return 200.
- Real HTTP guest/authenticated missing pages return 404 with the lost mascot
  and correct return link. Another user's subscription gets the same friendly
  404 without disclosing the record; missing .json job URLs retain the plain 404.
- Existing six real HTTP workflow groups also passed: authentication/password/
  CSRF, subscriptions/Decimal/currencies, links, bills/rollback/archive/restore,
  valid/invalid uploads/private downloads and search/export/calendar isolation.

Final exact-commit full-suite, SQL and restart results are in the ignored local
`instance/current-main-sql-acceptance.md` / JSON evidence. SQLite pytest results
and actual SQL results are reported separately. No new load test was requested
or run; the earlier 10-user SQL memory signal remains unresolved. Real OCR,
microphone services, production startup and production migration are unverified.

## Review the updater BEFORE any main merge

The batch file becomes a small checked wrapper:

```bat
@echo off
setlocal
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
    echo The virtual environment is missing. Run run_local.bat once first.
    exit /b 1
)
".venv\Scripts\python.exe" -m deploy.update
set "RESULT=%ERRORLEVEL%"
endlocal & exit /b %RESULT%
```

The actual file also has two operator reminder comments. The deployment flow is
in **deploy/update.py**, **deploy/server_control.ps1**, **deploy/health.py** and
the minimal readiness registration in **serve.py**.

| Existing updater | Proposed updater |
|---|---|
| Schema failure can reach restart and success text | Failed schema/start/health returns nonzero; no verified-success message |
| Stops whatever holds loopback port 8000 | Validates the task's checkout, Python and serve argument; refuses unknown processes |
| Task startup success assumed | Bounded health requires a real DB query and the revision captured at worker startup |
| Recovery commands unchecked | Recovery checked; failed recovery explicit; even successful rollback exits with update failure |
| Minute-resolution backup name can be reused | New unique instance backup folder; prior backups preserved |
| Tracked changes checked | Non-ignored untracked work also prevents updating |

Full patch: local **instance/update-server-before-main.patch**. The original
pushed branch can be compared at
[main...codex/sql-application-preview](https://github.com/thomasforstudy-dev/subtrack-subscription-website/compare/main...codex/sql-application-preview).
The current-main validation branch includes the isolated dashboard fix as well.

**This is source-level and simulated failure-path verification.** The actual
updater, SYSTEM task startup (including Git revision capture in that account),
rollback of a real running release and production SQL migration were not run.
An older release without the readiness route cannot be labelled verified
recovery. Recovery uses detached HEAD and needs review before returning to main.
SQL updates still require a separately verified SQL backup plus matching private
uploads. The wrapper does not migrate production SQL automatically.

## Start/status/stop only the NEW preview

PowerShell from `C:\Users\buith\Projects\subtrack-sql-current-main`:

```powershell
.\scripts\sql-preview-control.ps1 status
.\scripts\sql-preview-control.ps1 start
.\scripts\sql-preview-control.ps1 stop
```

Restart = stop, then start. Controller PID/health checks apply only to 8774 in
this worktree. Use generated dashboard account A to see synthetic chart data;
account B verifies isolation. The development banner names SQL/database/revision.

## Deferred extension

The extension token API has not landed in the inspected main. Keep its existing
Requests entry until that dependency is ready. Then implement the agreed
`2026-10-20-codex-extension-token-response.md` contract using **AllOutFree** and
`app/static/icon-192.png`. No extension tokens, browser install, real messages,
model downloads or training were performed. GOT-OCR and Phi-3.5-mini remain on hold.
