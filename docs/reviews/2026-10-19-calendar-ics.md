# Calendar/ICS handoff — 19 October 2026

Branch: `codex/calendar-ics`, based on integrated core `f2fb8ad` from
`codex/integration-validation`. Both Claude and Antigravity histories remain
ancestors. No merge to main, deployment, Google event creation or training.

Implemented: a Calendar link from the subscription list; an account-wide active
subscription review list; individual Google Calendar template/review links;
private single-event and all-active-subscription ICS downloads. No API key,
OAuth consent, paid model or external API request is used by these routes.

The export is a **snapshot of next expected renewal dates**. It does not claim
payment, create recurring events, synchronize later changes or revoke events
already imported elsewhere. Choose notifications in the receiving calendar.
Repeated manual imports can create duplicates depending on that calendar client.
The stable UID helps identify the same subscription but is not a sync guarantee.

## Evidence and boundaries

- Fourteen focused tests passed: login/other-user gates, archived/empty cases,
  all 25 rows across pages, stable UID after edits, leap-day/exclusive end,
  IANA zones across DST boundaries, minimal private-field export, safe response
  headers, CRLF injection, escaped punctuation and 75-octet UTF-8 folding.
- Targeted SQL Server check passed against the existing synthetic
  `SubTrack_CodexTest_20261019_Clean`: index, owner review and ICS response (one
  synthetic event). `instance/sql-calendar-validation.json` records the result.
- Full combined Python 3.14.8 / Windows / SQLite suite: **306 passed**, no xfails
  (`instance/calendar-test-results.xml`). Hosted CI for the exact published
  Calendar commit is checked separately in the final handoff. Real Google import/save and other calendar client behavior
  remain unverified; no real event was created to test this feature.
- All calendar responses prohibit caching and referrers. Exports omit notes,
  prices, email addresses, management URLs and credentials. Only title/date/zone
  enter the Google template URL after the user chooses that link. No broad login
  cookie or bearer token is embedded in any URL.

Sources used for the format/date semantics:
[RFC 5545](https://www.rfc-editor.org/rfc/rfc5545.html) (content-line folding,
TEXT escaping, all-day DATE and non-inclusive DTEND), and
[Google's manual import instructions](https://support.google.com/calendar/answer/37118?hl=en).
The tests verify generated content; they do not substitute for testing each
calendar client's importer.

## Team/owner actions

- Antigravity: polish the two working calendar templates while preserving the
  review step, date/timezone text, owner-only URLs and export limitations.
- Claude: consume the integrated core, especially additive migration 05 and
  reminder snapshot/SQL BIT fixes, before stacking new backend work. The latest
  published Claude revision at inventory remains `776f400`; no real bills/upload
  branch has arrived to validate. Own-account Subby backend tests are included.
- Owner: review the published branches/CI and local synthetic preview. Keep
  production database configuration and scheduler activation as a separate step.
  Both GOT-OCR and Phi-3.5-mini training remain on hold. Extension tokens and
  Gmail consent remain prerequisites for their later workstreams.
