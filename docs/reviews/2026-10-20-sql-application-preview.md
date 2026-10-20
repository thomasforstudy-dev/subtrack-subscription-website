# SQL Server application preview — 20 October 2026

## Open and identify the application

Open **http://127.0.0.1:8773/bills/** on this laptop. The yellow development
banner names **SQL Server**, **SubTrack_CodexPreview_20261020**, provider **mssql**
and the running application revision. This is a separate Waitress process on
loopback, with separate session cookies and private uploads. The live site on
8000 and the existing SQLite preview on 8772 are not its database or process.

Generated account credentials are in the owner-only, Git-ignored local file
`instance/sql-preview-access.json` in this worktree. Use `sql_review_a` and
`sql_review_b`; do not share this file or the stable local session secret.
Open it locally in the editor; passwords are deliberately absent from this report.

The actual connection is SQL Server Express 17.0.1000.7 on
`localhost\SQLEXPRESS`, ODBC Driver 18, Windows integrated authentication.
No service was changed. The preview never reads the live `.env`; connection
failure is fatal, with no SQLite fallback. Health identity is available locally
at `/__sql_preview__/health` and queries `DB_NAME()` on each request.

Mail stays in memory, AI is fake, reminder CLI/schedulers are disabled, link
preview fetching is disabled and external connections/navigation are blocked.
All accounts, documents, bills and subscriptions are synthetic. Do not use a
real invoice or real account in this preview.

## Click checklist

1. Open the URL, confirm the database banner, then sign in as `sql_review_a`.
2. Open Subscriptions / Gói đăng ký. Add USD 0.10 and USD 0.20 subscriptions
   with 31 January 2028 renewal dates. Their USD total increases by **0.30**.
   Add EUR 12.34: EUR stays separate. Search and move to page 2.
3. Open Bills / Hóa đơn → manual entry. Enter a shop, USD, and an item with
   quantity 3 and unit price 3.33. Save, edit the note, archive, filter Archived,
   and restore. The line amount is **9.99**. An oversized line must be rejected
   without changing the previous saved bill.
4. Upload a generated PNG or small generated PDF. Open the private file from
   its bill. A corrupt image, encrypted PDF or PDF over five pages must fail.
5. Search/filter bills; try JSON, CSV and Markdown exports. Subscription page
   exports cover the visible page (as labelled); bill exports are account scoped.
   Open Calendar / Lịch and download the ICS file.
6. Note an edit/file URL, log out using the account menu, and sign in as
   `sql_review_b`. A's subscriptions, links, bills, files and exports must not
   appear. Opening A's private edit/file URL must return 404.
7. Sign in as A, restart only this preview using the commands below, reload,
   and confirm the saved bill, file, link and subscriptions remain.

Registration, weak-password rejection and missing-CSRF rejection are also
covered by the real HTTP checks. Browser password policy and server validation
both apply. GET logout is refused; logout requires a CSRF-protected POST.

## Start, status and stop only this preview

In PowerShell, from `C:\Users\buith\Projects\subtrack-sql-preview`:

```powershell
.\scripts\sql-preview-control.ps1 status
.\scripts\sql-preview-control.ps1 start
.\scripts\sql-preview-control.ps1 stop
```

For a restart: `stop`, then `start`. The controller validates the command line,
PID, health identity and port, and refuses unrelated processes. It does not
change Windows services or scheduled tasks. Logs are
`instance/sql-preview.log` and `instance/sql-preview-error.log`.

`init` creates only the fixed synthetic database if absent, preserves existing
accounts/records and reruns migrations with before/after record hashes. It does
not reset passwords, clear tables, drop databases or delete files.

## Integration and evidence

The live checkout was clean main **766d7296f7d2aab72f544aad0b13221aea4f5264**.
Our branch `codex/sql-application-preview` started there and incorporated Claude's
reviewed true merge **25d2ecd795690df0aba332f7ea681b7fb5e2b0ef**, which retains
both current main and **6918df8** history. It adds the parser subprocess deadline
and SQL Server unique-constraint introspection fallback without discarding
shell v3, static mtime cache versions, bills validation or voice changes.

At exact **25d2ecd**, Python **3.14.8**: **388 passed, 0 failed, 0 skipped**
in 138.06 seconds. `CI=true` made installed Node voice JavaScript checks mandatory.
These pytest application fixtures use SQLite/mocks: they are not SQL evidence.
The final exact-commit acceptance results are recorded separately in the local
`instance/sql-acceptance.md` and machine-readable evidence files.

Actual SQL evidence:

- Numbered migrations **01–06** applied initially, then **twice more** after
  seeding; every synthetic table's rows/counts/hash remained identical across
  the two reruns. See `sql-preview-migrations.json`.
- Six real HTTP groups passed: registration/login/logout/password/CSRF;
  subscription dates/Decimal/currencies/isolation; links/isolation; bill CRUD,
  archive/restore, line amount and rejected-edit rollback; valid/invalid uploads
  and private downloads; search/filter/paging/JSON/CSV/Markdown/calendar/ICS.
  Requests used real authenticated sessions and CSRF tokens, not Flask's test
  client. See `sql-web-results.json`.
- Restarting only this test preview preserved the saved bill, document bytes,
  link and subscriptions. See `sql-persistence-results.json`.

## Measured load and its limits

First acceptance at exact **2620459a1862115c4057f4dbf7b5392ae9d134e0**:

| Concurrent users | Requests | Duration | p50 ms | p95 ms | Max ms | Writes |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 91 | 20.09 s | 12.04 | 22.85 | 100.06 | 2 |
| 5 | 453 | 20.11 s | 12.51 | 31.87 | 58.19 | 10 |
| 10, completed retry | 890 | 20.21 s | 14.11 | 49.81 | 89.14 | 20 |

All completed stages had **zero HTTP errors, failed writes and observed blocked
SQL requests**. Every controlled write was read back through the application.
This is a short synthetic workload, not a production capacity guarantee or a
proposed latency target. Setup/logins and post-stage verification are excluded
from the measured request count. Reads rotate dashboard, subscriptions, bills,
links, calendar and bill exports. Each user writes one bill and one subscription.
There is 0.2-second think time and a cap of 100 requests/user and 20 seconds/stage.

**Do not omit the interrupted run:** the first 10-user stage stopped at 12.34 s
after 551 requests because SQL Server signalled low-memory pressure. It had zero
HTTP errors/failed writes/observed blocking; all 20 writes survived. The live site
still returned 200 throughout. Five subsequent clear SQL memory samples preceded
the same-rate successful retry; no safety threshold was relaxed. Original
evidence remains in `sql-load-10-stopped.json` and `sql-load-retry-preflight.json`.

Monitoring every 0.5 s stops on a SQL low-memory flag, overall CPU >=85% for ten
consecutive samples, monitoring failure, or three degraded live public login
probes (> max(1 s, 5x baseline), or non-200). Sampling cannot prove that no brief
blocking occurred between samples. A final acceptance rerun, if completed, is
separately identified in `sql-acceptance.md`; the interrupted run stays disclosed.

## Deployment lane — prepared, not deployed

Codex owns `deploy/`, its helpers/tests and minimal `serve.py` readiness wiring.
Claude's reviewed merge supplied backend approval; Claude's active bill-reading
jobs/model/OCR files were not edited here. Coordination is recorded in shared
project memory. Claude's newer jobs slice is outside this tested revision.

`update_server.bat` now returns the checked Python updater's exit code. The
updater refuses non-main/dirty checkouts and foreign scheduled tasks/processes,
checks every package/test/backup/schema/start result, and requires bounded
loopback health for the **exact revision captured when that worker started**
plus a real database query. Schema failure cannot reach new-version success.
Failed startup/readiness triggers recovery; even a successful rollback returns
failure. Recovery failure is explicit. Unknown port owners are never killed.
Instance copies use new unique backup folders. The Cloudflare task is untouched.

Failure paths are simulated in tests; **the actual updater, SYSTEM task startup,
production SQL migrations and hosted deployment were not run**. Older releases
without the readiness route cannot be reported as verified recovery. A recovered
checkout uses detached HEAD and needs review before returning to main.

### Backup/restore drill

`scripts/sql_restore_check.py` made a new native SQL **COPY_ONLY, CHECKSUM** backup
of the synthetic preview, verified it, and restored into the new isolated
**SubTrack_CodexRestore_20261020** target with new physical files and no REPLACE.
It refuses an existing restore target or backup path. All table records matched;
`DBCC CHECKDB` passed; private uploads matched stored SHA-256 hashes. Restored
owner A could download the generated file; B received 404. Source records were
unchanged before/after. Existing backups and source files remain intact.

`instance/sql-restore-results.json` records the SQL backup path, upload copy,
table/file hashes and integrity results. Retain both the database backup **and**
its matching upload copy/manifest. The retained restore DB prevents a careless
rerun from overwriting evidence. This validates the synthetic recovery procedure;
it does not certify a production backup or off-device disaster recovery. SQL
production updates still require a separately verified SQL backup plus matching
private uploads before an authorised release. No SQL migration is automatic here.

## Remaining limitations

- Repeating the original web harness reused identical PNG bytes; the app's correct
  duplicate-file redirect differed from the harness expectation. Generated files
  now include a unique run marker, preserving prior files and checking fresh uploads.
- A restricted runner attempt at 1b50dc6 had 415 passes and five local HTTP link
  preview failures. It is not a passing acceptance result; see the final local
  report for the authorised loopback rerun and actual results.
- Investigate the intermittent SQL low-memory signal before larger/longer load.
- No production release or hosted CI result is claimed for this new branch.
- Real email, cloud AI, OAuth, scheduler delivery, microphones/speech services
  and outside integrations are intentionally not exercised. Voice JS checks are
  real Node checks, not proof of the laptop microphone's recognition quality.
- GOT-OCR and Phi-3.5-mini downloads/training remain on hold.
- Login details, databases, uploads, generated backups and local instance
  evidence are excluded from Git. Only source and synthetic-safe documentation
  belong in a shared commit.
