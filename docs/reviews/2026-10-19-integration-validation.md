# Integrated runtime validation — 19 October 2026

Integration branch: `codex/integration-validation`. Merge parents retain Claude's
`776f400` (`claude/subby-tools`, including `d4bff6e` runtime repairs) and
Antigravity's `f5bd396` (`antigravity/ui-ux`, including `d74d2ac`). The original
shared checkout and its uncommitted dashboard/settings edits are preserved.

## Verified execution

| Check | Evidence | Result |
|---|---|---|
| Python 3.14.8 / Windows / SQLite union suite | `pytest -q --strict-markers`, `instance/integration-test-results.xml` | **292 passed**, no xfails |
| Original four review failures | `tests/test_review_findings.py` | Ordinary passing regressions; missing-CSRF test explicitly uses `csrf=False` |
| UI form/error/search/settings contracts | `tests/test_ui_contracts.py`; table-scoped assertions in `tests/test_subscriptions.py` | Passed; rendered forms retain lead times/management URL, rejected values remain, search reaches rows after page 1 |
| Separate SQLite worker processes | `tests/test_reminder_processes.py` | One winner for simultaneous claims; crash after fake provider acceptance recovers with identical payload |
| Calendar date rules / DST | `tests/test_schedule.py`, `tests/test_reminders.py` | Month ends/leap years retained; spring skipped hour and autumn repeated hour do not duplicate a reminder |
| Dependencies | `python -m pip check` | No broken requirements |
| SQL Server runtime | `scripts/validate_sqlserver.py --resume`; `instance/sqlserver-validation.json` | Migrations + targeted CRUD/transactions/workers passed; details below |
| Earlier hosted CI | Runs `39234397635` (`5a8ec43`) and `39242196173` (`d74d2ac`) | Both completed successfully; these are older revisions |
| Exact integrated-core hosted CI | Run `39276880151`, commit `f2fb8ad` | Windows and Ubuntu jobs completed successfully |
| Browser preview | `scripts/preview.py`, loopback port 8770 | Search, unchanged edit, settings persistence, Subby tools/draft and 390px dashboard checked; screenshots in ignored `instance/browser-evidence/` |

The first union run passed 281 tests. New form/process/DST/dialect checks bring
the suite to 292. The first sandbox run failed because a disposable temporary
folder's parent was absent; that environment setup was corrected before the
reported completed runs. No failing test was weakened to hide an application
defect, and no valuable suite was discarded.

## Integration decisions and repairs

- Reviewed route names, CSRF fields, auth fields, lead-day/manage URL controls,
  pagination, settings persistence and model fallback metadata before resolving
  UI conflicts using the repaired UI implementations. Kept both work logs.
- Combined Claude's username-aware CSRF client/memory-mail setup with Codex's
  dotenv-before-import protection, provider credential clearing, non-loopback
  TCP block and database teardown. The pinned dotenv 1.1.1 needs the loader hook.
- Converted the four old xfails only after verifying the fixed backend. Logout
  lifecycle tests now use the real POST contract. Table sorting tests examine
  actual subscription rows instead of unrelated overview/demo text.
- Found and fixed a new crash/retry defect: email text changed the next day while
  its idempotency key stayed the same. `Reminder.payload_json`, additive
  `05_reminder_payload.sql` and the SQLite upgrader persist the message BEFORE
  delivery, including sender/reply-to. Retried messages remain byte-equivalent
  even if name, account display name, site URL or sender configuration changes.
  A changed recipient causes the old reminder to be skipped. No real email is
  sent in validation. Provider idempotency has a finite retention period, so this
  does not claim exactly-once delivery beyond a provider's retention window.
- Found and fixed a SQL Server-only planning error: `.is_(True)` compiled to
  `users.reminders_enabled IS 1`. Equality to SQLAlchemy `true()` compiles to
  valid `= 1`. A regression compiles the real planning query for SQL Server.
- Reconciled the arriving Subby account-tool response: safe text/list/link
  rendering and a local "Check and save" draft link. Tool answers are excluded
  from subsequent model history, preventing automatic account-data disclosure.
  Preview tool selection is deterministic and visibly labelled fake; it does
  not establish real Phi inference or model training.
- Browser validation found an additional UI contract mismatch: summary JavaScript
  read `data-summary-url` and `data.totals`, but the template/API provide
  `data-dashboard-json` and `projected`. Aligned the script and rendered account
  totals on the server as well, so a 25-plan USD 250 account remains visible
  before JavaScript loads and on filtered pages. The strengthened UI contract
  tests pass (4 tests); browser search reaches the 25th plan from page 1.

## SQL Server evidence and safety boundary

Read-only discovery found `MSSQL$SQLEXPRESS` installed but stopped, SQLCMD, and
ODBC Drivers 17/18. The owner explicitly approved starting the existing service.
A narrow elevated helper started it; no other service, scheduler or app database
configuration was changed. Windows-integrated access reports SQL Server
`17.0.1000.7` and sysadmin membership, and test-database creation succeeded.

The shared checkout's effective configuration currently has no DB_SERVER or
DATABASE_URL setting and defaults to **SQLite**. This is a configuration result,
not proof about an independently running deployment's process environment.
No matching `SubTrack*` scheduled tasks were returned by read-only inspection.

Only these NEW synthetic databases were created and selected:

- `SubTrack_CodexTest_20261019_Clean`
- `SubTrack_CodexTest_20261019_Legacy`

The runner removes only the scripts' hardcoded database-creation/USE wrapper
from the in-memory test input, selects an allowlisted synthetic database, rejects
remaining database switches/destructive SQL, and executes the original table,
constraint, index and view definitions. Source migration files are unchanged
apart from the new additive 05 script. It runs 01–05 twice, checks constraints
and indexes, and preserves legacy users/admin flags/subscriptions/links and
backfilled username/lead-day/billing-day values. Then it exercises application
CRUD, genuine CSRF rejection, another user's access rejection, rollback,
archive/restore, settings, two competing worker processes and crash-after-send
recovery using a local fake idempotent mail provider. This is targeted SQL Server
coverage, not a claim that all 292 SQLite tests ran on SQL Server.

The first SQL attempt exposed the Boolean syntax bug after successful migration
and CRUD checks. Resuming only these test databases after the fix completed the
worker gates. Test databases are retained for inspection; nothing was dropped,
truncated or copied from production. The production `SubTrack` database was not
selected, migrated or read. SQLEXPRESS remains running as approved.

## Preview, ownership and next work

`scripts/preview.py` uses only synthetic SQLite data, memory-only mail and a
labelled fake provider. It binds `127.0.0.1:8770`, disables dotenv reads, and shows
backend/database/provider/revision mode in the page banner. Generated disposable
login details are stored only in Git-ignored `instance/preview-access.json`.
No real invoice, customer record or API key belongs in this preview.

The shared folder lacks the reviewer's `probe-routes.py`; equivalent endpoint
regressions for malformed URLs/model JSON, safe pin redirects and field retention
are preserved in `tests/test_review_repairs.py` and run in the union suite.

Calendar links/ICS will be implemented on a separate branch after core browser
validation: see `codex/calendar-ics` and its calendar handoff. Extension work still waits for scoped tokens; Gmail waits for consent
and project decisions. Bills/upload remains a labelled UI demo until its real
backend slice arrives. GOT-OCR and Phi-3.5-mini training remains paused. No merge
to main, deployment, production scheduler activation or real recipient send.
