# Bills and voice integration gate — 20 October 2026

Branch: `codex/bills-voice-validation`. Read the commit containing this report for
the exact revision; local evidence lives in ignored `instance/` files. The shared
Antigravity and Claude checkouts were preserved. Real merges retain bills `970e8c0`,
voice `1e14b4d`, Claude repairs `78dffc3`, styled bills `6e21daf`, and final UI/voice handoff `ac378e8` histories.

## Repaired review findings

All six findings were P2 issues in the reviewed input branches, before these
integration repairs. No strict expected failures remain in this suite.

| Finding | Original problem / reproduction | Repair and verification | Responsible lane |
|---|---|---|---|
| B1 | Header-only PNG/PDF accepted; compressed six-page PDF bypassed regex page count in `970e8c0`. Invalid or huge decoded files could reach later processing. | Claude added real Pillow decoding, 12000-side/30MP limits, no animation, pypdf page/encryption checks, corrupt/truncated fixtures. Codex isolates parsing in a child with an 8-second timeout and tests actual termination. Valid PNG/JPEG/WEBP/five-page PDF accepted; compressed six-page/encrypted/corrupt/oversize files rejected. | Claude parser; Codex process boundary and verification |
| B2 | Quantity 9999999 × price 99999999.99 exceeded DECIMAL(12,2) in `970e8c0`; SQLite concealed the mismatch. | Claude validates direct and multiplied amounts against 9999999999.99. SQL Server stores the exact maximum and rejects an over-limit edit before SQL; old bill/lines survive. | Claude validation; Codex SQL proof |
| B3 | After invalid total, new form rendered only three rows, losing rows 4–30 in `970e8c0`. | Backend counts submitted indices; merged styled form keeps `item_rows`. Codex adds accessible Add/Remove and verifies actual controls for all fields at 5/30 rows, including rejected edits and reused row numbers. Browser retained rows 5 and 30 on error and saved a corrected receipt. | Claude backend; Antigravity styling; Codex integration |
| V1 | Voice Send preferred stale `heardTranscript` over the edited input in `1e14b4d`. | Reviewed input is authoritative; cancel/close aborts and invalidates callbacks; normal stop preserves final results. Actual shipped JS handlers run under speech mocks: edit/send/stop/end/cancel/late callbacks/Escape/permission refusal/unsupported/duplicate click. Keyboard review is retained when switching modes. | Antigravity voice; Codex integration repair and regression |
| I1 | UI branch linked Bills to `/dashboard#bills`; it predated actual bills routes. | Styled UI now links to `/bills/`, real forms/filters/pager/exports. Mismatch warnings survive the merge. OCR remains explicitly unavailable/demo. Existing Subby transaction tool is accurately labelled renewal charges, not confirmed bills; no new bill-summary tool claimed. | Antigravity UI; Codex contract verification |
| I2 | Existing core health check omitted migration-06 tables/columns/indexes. | Read-only readiness checks all three tables and their columns, file uniqueness and bill lookup indexes. SQLite upgrade adds matching lookup indexes. SQLAlchemy MSSQL lacks unique-constraint reflection; unique indexes cover that dialect. Six readiness regressions cover incomplete schemas and that difference. | Codex |

## Verified locally

- Python **3.14.8**, Windows, full suite: **381 passed**, no xfails/skips in the
  recorded run; `instance/bills-voice-results.xml`. Includes genuine missing-CSRF
  requests, no-dotenv/offline providers/external-socket guard and actual separate
  reminder processes (overlap claim and crash-after-provider-acceptance recovery).
- Pinned dependency consistency: `pip check` passed. This is dependency
  consistency, not a claim that a vulnerability advisory audit was performed.
  Pillow 12.3.0 and pypdf 6.21.1 are pinned for structural file validation.
- SQL Server **17.0.1000.7**, Windows authentication, only:
  `SubTrack_CodexBills_20261019_Clean` and
  `SubTrack_CodexBills_20261019_Legacy`. Scripts 01–06 ran twice on both;
  legacy user/admin/subscription/link rows survived. SQL bill CRUD/edit/rollback,
  ownership, CSRF, Decimal bounds, file association/download and exports passed.
  Separate SQL reminder worker claim/crash retry passed; **zero real emails**.
  `instance/sql-bills-migrations.json`, `sql-bills-application.json`,
  `sql-bills-recheck.json`. Test databases retained for inspection.
- Browser: generated synthetic account login, real bills navigation, 20/5 paging,
  account-wide receipt totals, 30-row cap/removal/reuse, error recovery, successful
  manual save. Browser JSON download contained all 26 synthetic bills while the
  list is paginated; Decimal strings and unknown date/time stayed unknown.
- `scripts/preview-control.ps1` starts/stops only the task-owned hidden loopback
  preview; it rejects mismatching saved PIDs. Preview banner identifies SQLite,
  memory mail, fake AI, unavailable OCR and revision (plus local changes if dirty).

Hosted Windows/Ubuntu results must be read from the checks on the **exact pushed
commit**, not inherited 292/306/346/364 results or queued runs. Final handoff
records the exact run and job results after publication.

## Data audit and boundaries

Outgoing tracked files are checked for high-confidence credentials, private keys,
`.env`, database/backup files and private invoices. The single PDF fixture is
six blank synthetic pages, independently read with pypdf; it is not an invoice.
Preview login, uploads, databases, exports and screenshots stay under ignored
`instance/` or local downloads. Existing Git author identity remains ordinary
repository metadata; this is not a claim that history has no author names/emails.

The primary checkout's `.env` still selects **SQLite fallback**. That is a local
configuration check, not proof of the running public service's database. No
production database was selected or migrated. No main merge/deploy, scheduler
activation, real message, Google event creation, public preview or training.

## Preview and remaining work

URL: **http://127.0.0.1:8772/bills/**. This device only; another device's localhost
refers to itself. From this isolated checkout in PowerShell:

```powershell
.\scripts\preview-control.ps1 start
.\scripts\preview-control.ps1 status
.\scripts\preview-control.ps1 stop
```

Synthetic access: ignored `instance/preview-access.json`. Do not upload real bills
to the fixture. Tests require Node on PATH for the mocked JS callbacks; no npm
packages or application build step are used.

Priorities after this gate:

1. Claude durable OCR worker/adapters, per-field evidence/revision review and DOCX
   text extraction are prerequisites for the next OCR verification slice. Current
   validation is file acceptance, not OCR. Child timeout and byte/pixel limits do
   not constitute a formal operating-system memory sandbox.
2. Antigravity/owner real Vietnamese/English microphone/TTS/browser matrix and PWA
   install checks. Source currently has no service-worker caching implementation;
   install/offline capability is unverified. Never cache private responses.
3. Owner chooses primary host/actual SQL configuration, then least privilege,
   encrypted DB+private-upload backups and an actual isolated restore drill.
   Preparation is in `deploy/RELEASE-GATE.md`; restoration is not yet verified.
4. Reminder test recipient and scheduler activation need separate owner approval.
   Scoped/revocable token APIs must arrive before extension implementation.

GOT-OCR and Phi-3.5-mini training remain on hold. Real OCR/Phi inference, mail
delivery, Google import and production behavior remain unverified.
