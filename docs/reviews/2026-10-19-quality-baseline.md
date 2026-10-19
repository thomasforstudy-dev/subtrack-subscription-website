# Codex quality baseline — 19 October 2026

## Scope and baseline

This is the first execution handoff for `Promt/03-PROMPT-CODEX.md`: review,
isolated tests, and CI preparation. The other workstreams in that document
remain a backlog; this report does not mark them complete.

- Repository: `thomasforstudy-dev/subtrack-subscription-website`.
- GitHub `main`: `af6395143b010f03a840347bccc2e674c84cb554`.
- GitHub branch inventory: only `main`; open pull requests: none.
- GitHub Actions runs for that exact SHA: none returned by the API.
- Local starting commit: `e7a02a4`, the existing skill-library/test-discovery commit.
- Execution branch: `codex/quality-baseline`, based on that local commit.
- Reviewed `AGENTS.md`, `docs/PROGRESS.md`, `DESIGN.md`, app/test/schema source,
  and existing deployment scripts. Backend and UI source match the published
  baseline; local-only IDE directories are outside this handoff.
- The real host may have additional work. GitHub and this checkout cannot
  establish the state of uncommitted files, secrets, services, or data there.

## Handoff status

| Item | Status | Evidence | Next action / AI |
|---|---|---|---|
| Published source / branch review | Source reviewed | GitHub baseline above; findings below | Claude: backend fixes; Antigravity: associated form text/UI |
| SQLite integration and existing tests | Tests run: 68 passed, 4 expected failures | Python 3.14.8 on Windows; command below | Codex: retain coverage as features land |
| Known security/input regressions | Needs fixes | Four strict `xfail` contracts in `tests/test_review_findings.py` | Claude: fix, then remove the relevant marker |
| CI | Prepared; hosted run unverified | `.github/workflows/tests.yml`: Python 3.14, Windows/Ubuntu, pytest, dependency check | Owner/Claude: publish branch and inspect both jobs |
| SQL Server | Source reviewed; runtime unverified | `database/01_schema.sql`, config URL tests only | Claude/Codex: verify on a separate test DB/snapshot |
| Reminder delivery / retry / scheduling | Not implemented in reviewed source | `ReminderLog` model exists; no sender or reminder job | Claude: sender/retry contract; Codex: tests/task after that |
| Calendar / ICS | Not implemented | No calendar routes in reviewed app | Codex next feature after backend coordination |
| Upload / bill review / OCR / Phi | Not implemented | No upload, bill, extraction or inference routes | Claude: contract; Codex: fake-service tests; training stays on hold |
| PWA / extension | Not implemented | No manifest/service worker/extension API | Claude: scoped token API; Codex: extension after contract |
| Windows startup / backups | Startup scripts reviewed; runtime and restore unverified | Existing `deploy/` tasks use SYSTEM; no backup/restore verification | Codex: test-host identity and backup plan; avoid duplicate tasks |
| Dataset preparation | Not implemented | No reviewed dataset/export pipeline in this checkout | Agree schemas/consent/split rules before export |

## Findings for Claude

All source locations below refer to the reviewed app baseline, which this
handoff leaves unchanged. P1 means fix before relying on the public service's
security; P2 means an important correctness or product-contract issue.

| ID | Priority / location | Reproduction and impact | Specific fix / owner |
|---|---|---|---|
| R1 | P1 — `app/auth.py:27` | On a fresh database, the first public registration becomes administrator and can open `/admin/users`. This is reproduced by `test_public_signup_does_not_grant_admin`; it does not establish who is admin in production. | Claude: remove admin assignment from public signup; use an explicit owner bootstrap command/configuration with a deliberate identity. Keep existing admins intact. |
| R2 | P1 — `app/subscriptions.py:24`, `app/links.py:53`, `app/auth.py:41` | A session-authenticated subscription POST without a CSRF token is accepted. Mutation routes have no token validation. The regression test demonstrates server acceptance; browser cookie behavior is not simulated. | Claude: add server CSRF validation for all session mutations and make logout POST; coordinate hidden tokens with Antigravity and update test form helpers. |
| R3 | P1 — `app/__init__.py:32` | Static review: when `SECRET_KEY` is absent, the app starts with a public default. Someone who knows that key can construct signed session data. The production environment was not read, so its configuration is unverified. | Claude: require a strong explicit secret for public startup, with a separate explicit test/development configuration. Owner: rotate if the default was used publicly; do not disclose the value. |
| R4 | P1 — `app/link_preview.py:35`, `:38`, `:99` | Static review: the safety check resolves the hostname, then `requests.get` resolves that hostname again. A domain changing from a public to a private answer between those steps can bypass the intended address check. Existing tests cover private literals and redirects, not this race. | Claude: bind each connection to a validated address while preserving HTTPS hostname verification/SNI and Host; validate each redirect. Add a fake DNS/transport regression without contacting private services. |
| R5 | P2 — `app/subscriptions.py:77` | Posting `next_renewal_at=2026-02-30` raises `ValueError` (a server error outside testing). The invalid-date contract reproduces it. | Claude: validate date and amount inputs, show a friendly form error, and leave the existing row unchanged. Add invalid-edit and non-finite amount coverage with the fix. |
| R6 | P2 — `app/auth.py:42`, `:53`, `app/models.py:20` | Registration accepts `password123`; the handoff requires uppercase, digit and special character validation at the server. Username is also absent from model/form handling. The password gap is reproduced by a strict expected-failure test. | Claude: implement the agreed new-signup fields/policy with an additive SQL migration. Preserve password login for old accounts and OAuth access. Antigravity: render the matching fields and errors. |
| R7 | P2 — `app/subby.py:30`, `app/static/subby.js:40`, `app/templates/landing.html:196` | Source promises reminder emails, but the reviewed source has no sender or scheduled reminder job. The unique log constraint proves neither delivery nor crash recovery. | Claude: correct Subby's capability facts until reminders are verified; Antigravity: align static answers/landing copy. Then prove timezone, retry, concurrency and no-payment assumptions with fake mail tests. |
| R8 | P2 — `app/links.py:101` | Static review: pinning a link redirects to unvalidated `request.referrer`. A request supplying an external Referer is redirected off-site. | Claude: redirect to the local links page, or validate a relative/same-origin return target. Add a forged-Referer regression. |

The four expected failures are R1, R2, R5 and R6. They are **unresolved bugs**,
not successful security checks. `strict=True` makes an unexpected pass fail CI,
so the owner of a fix must remove the corresponding marker after reviewing it.
Other exception types are not suppressed by these markers. Static findings R3,
R4, R7 and R8 still need targeted remediation tests.

## What the tests establish

- Signup, logout, password login, create/edit/archive subscription, persisted
  decimal amount and a valid leap-day renewal date.
- Anonymous access rejection across private routes; a second user cannot list,
  read, edit or archive the first user's subscription, or access the admin page.
- Private saved-link titles, notes and tag chips remain scoped to their owner;
  unauthorized edit requests leave the row unchanged. Existing link tests also
  exercise add/search/tag/pin/delete and preview behavior.
- Jinja escapes script-shaped subscription and link titles.
- SQLite enforces the unique reminder-log tuple while allowing another renewal
  date/channel. No email was sent; retry/concurrency is not established.
- SQL Server URL precedence, credential delimiter escaping, and Windows identity
  settings are tested as strings. No SQL Server connection/migration is made.

`tests/conftest.py` disables dotenv **before app imports**, replaces database and
session settings for the test process, clears configured provider credentials,
and permits only loopback IP socket connections during tests. Existing fake
Gemini/OAuth tests keep their mocks. This prevents accidental real provider
connections through the application paths exercised by the suite. It is a test
safeguard, not a sandbox for executing unreviewed code. The pinned
`python-dotenv==1.1.1` does not implement `PYTHON_DOTENV_DISABLED`, so a pytest
configuration hook patches its loader before collection and restores it at
session exit. A synthetic environment-file test verifies the app's loader
cannot populate environment values; a socket test verifies the external block.

## Validation and CI

Windows validation, with the existing local virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -ra --tb=short --strict-markers --basetemp=instance/pytest-codex-quality-03 --junitxml=instance/codex-quality-results.xml
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Result: **68 passed, 4 xfailed**; no broken dependencies; no whitespace errors.
Use a fresh, disposable `instance/pytest-*` path when repeating the command:
pytest clears its chosen base temporary directory. `instance/` is Git-ignored.

The initial sandbox run could not create pytest's default temporary directories
or connect to the local preview test server. The completed run used an isolated
project temporary folder with loopback access. This is an environment limit,
not evidence of a deployed application regression.

CI uses normal `push`/`pull_request` events, read-only repository permission,
disabled persisted checkout credentials, and no deployment or secret inputs.
It runs `pip check` and the full application suite on Windows and Ubuntu with
Python 3.14. It uses the documented
[checkout](https://github.com/actions/checkout) and
[setup-python](https://github.com/actions/setup-python) actions. The Ubuntu job
and clean dependency installation have **not** been executed locally, and there
is no hosted CI result for this new commit until it is published.

## Team handoff and next work

Claude should take R1–R6 and R8 in the backend lane, coordinating form/token
changes with Antigravity. R7 requires both backend capability facts and UI copy.
No direct message, issue, review comment, or pull request was posted to another
tool or GitHub; this file is the shared handoff.

Codex's next implementation can be Calendar URL/ICS once the renewal-date and
timezone contract is settled. Extension work depends on Claude's scoped token
API. Reminder scheduling depends on a real idempotent sender command. A separate
SQL Server test database is required before claiming SQL Server validation.
The automation remains review-only; no duplicate schedule is created. No host
service, real calendar, email, production DB, DNS or inference setup is changed.

For transfer to the other device, use the local patch package under
`instance/codex-handoff/`. It contains the pre-existing unpushed skill-library
commit first and this quality commit second, so it can be applied in order on
the recorded GitHub baseline. Review both patches before applying with `git am`.
