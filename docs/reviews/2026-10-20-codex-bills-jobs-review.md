# Codex review: Claude bill-reading jobs

## Scope and starting point

Reviewed **claude/bills-jobs**, exact head
**d5d0ac7f3866ea394503ea7ec69e4cfec8f65a03** against
**25d2ecd795690df0aba332f7ea681b7fb5e2b0ef**.

The base is confirmed by Git ancestry. It is the true merge with parents
**766d7296f7d2aab72f544aad0b13221aea4f5264** (then-current main) and
**6918df8d9f5a40597d0bdf35d51b379eae66bbd6** (Codex bills/voice). Claude's
two commits after it are **46fabe1** and **d5d0ac7**. The shell/cache/voice
history is retained. Twenty files changed in this slice.

Review used a separate `codex/bills-jobs-review` worktree. No application
source, Claude checkout, live checkout, preview, service or database was changed.
Main already pointed at d5d0ac7 when inspected; this review performed no merge
or deployment. SQL preview branch adac364 remains separate.

## Verdict

**Changes requested: five unresolved findings.** Existing automated tests are
green, but do not cover these cases. Claude owns the backend repairs; Codex can
verify them afterward. All five are introduced by **46fabe1**, absent from the
25d2ecd base, and remain present at d5d0ac7.

### R1 — P1: OCR page text bypasses card-number masking

Location: `app/bill_jobs.py:198–200` (`read_pages`).

The PDF/DOCX reader masks long card numbers, but OCR text goes directly into
DocumentPage and the draft's visible page text. A synthetic photo with mocked
OCR text containing a full card number retained that number in both the database
and the review HTML. Real GOT-OCR was not called.

Impact: enabling OCR can retain payment card numbers beyond the promised last
four digits. This is a privacy blocker for the OCR path.

Fix: apply the common, length-preserving card mask and newline normalization to
every OCR page before extraction, persistence and evidence offsets are computed.
Keep only the final four digits. Verify spaced, dashed and continuous numbers,
and confirm evidence positions still point into the stored masked text. Assert
the full number is absent from pages, draft/revision JSON, HTML and exports.

### R2 — P1: saving a draft persists a full card number in card_last4

Location: `app/bill_review.py:131` (`changes_from`), plus draft rendering.

The generic draft save allows up to MAX_VALUE characters for every field and
does not validate card_last4. Submit `action=save`, `revision=1`, and a synthetic
16-digit value in card_last4: both values_json and the following review page
contain the full number. Accept validation occurs too late to protect a saved
draft. Rejected-accept rendering also needs the same redaction boundary.

Impact: an ordinary typing mistake can persist sensitive card data even with OCR
disabled. The manual bill form already avoids echoing an invalid full number.

Fix: validate this field as empty or exactly four digits before saving any draft
or revision. Refuse the invalid value without storing or echoing it; do not
silently convert the owner's input into a different value. Add HTML maxlength
and pattern as assistance, with server validation authoritative. Test Save and
rejected Accept, draft history, HTML and exports.

### R3 — P2: exported evidence becomes false after editing an accepted bill

Location: `app/bills.py:549–552` (`accepted_evidence`).

Accept a synthetic draft with total 99000.00, then use the ordinary bill editor
to change total to 100000. The JSON export reports total 100000.00 while still
attaching the original document span `99.000` as evidence for that total.
Evidence is read from the accepted draft without comparing the current Bill.

Impact: JSON/CSV exports claim document support for a value the owner changed.

Fix: compare normalized current bill fields against accepted document-origin
values and omit evidence for changed fields, or maintain an explicit bill-edit
provenance revision. Preserve original extraction/history. Verify changed money,
dates, merchant and card fields lose current-value evidence; unchanged fields
retain valid evidence. Exercise JSON and CSV, and keep account isolation.

### R4 — P2: a negative total is extracted as a positive amount

Location: `app/extract_fields.py:62–64,191–196` (AMOUNT/read_line).

`Total: -12.50 USD` becomes total `12.50`, with evidence `12.50`: the number
matcher starts after the minus sign. The to_amount check never sees that sign.

Impact: a credit/refund can become a positive-spend draft. Acceptance is manual,
but the proposed amount is materially wrong.

Fix: match the complete signed monetary token. Since current bills reject
negative amounts, leave this field empty/unsupported rather than stripping its
sign. Also test parentheses, Unicode minus and malformed grouping to prevent
extracting a valid-looking fragment from an unsupported amount. Positive values
and existing exact Decimal cases must continue to work.

### R5 — P2: the evidence validator accepts a value its evidence contradicts

Location: `app/extract_fields.py:250–254` (`check_extraction`).

With page text `Total: 99.00 USD`, an extractor answer of total `1.00` and a
valid span covering `99.00` is accepted. Positions and value shape are checked,
but the value is never compared with the cited text.

Impact: the advertised guard for any extractor can bless an invented financial
value using an unrelated valid span. Current rules are local; no remote model
was used to reproduce this. It must be corrected before relying on this boundary
for additional extraction adapters.

Fix: validate field-specific normalization against the cited text: amount/date
normalization, currency mapping, last-four digits and text values. Explicitly
define permissible keyword transformations (such as statement -> card_bill).
Reject contradictions rather than merely requiring a span. Test matching
normalized values and deliberately mismatched values for each field family.

## Verification evidence

### GitHub Actions — actual hosted results for d5d0ac7

[Branch workflow run 39361240514](https://github.com/thomasforstudy-dev/subtrack-subscription-website/actions/runs/39361240514)
was already running when inspected and finished successfully during this review.
It was not a newly dispatched run by Codex.

| Job | Python | Result | Test duration |
|---|---|---|---|
| Ubuntu | 3.14.8 | 453 passed, 0 failed, 0 skipped | 104.26 s |
| Windows | 3.14.8 | 453 passed, 0 failed, 0 skipped | 445.28 s |

Pinned dependency checks passed. CI=true makes the real Node voice-handler
regression mandatory, and it ran within the suite. Microphone recognition and
real OCR were not exercised. These workflows use **SQLite/mocks, not SQL Server**.

### Focused review reproductions — actual local results

Python 3.14.8, synthetic SQLite fixtures and FakeOcr only: **five defect-confirming
probes completed in 4.31 s**. Their assertions describe the current wrong
behavior, so their passing is evidence of defects, not five passing regressions
for the desired behavior. The local ignored files are
`instance/review_probe.py`, `instance/review-probe.log` and its XML report.
No real invoices, real card details or SQL database were used.

Claude's separate SQL validation report was not rerun here. The earlier SQL
preview load-memory stop remains unresolved and is not changed by green hosted
SQLite CI.

## Source audit and handoff

The 20 changed files contain source, synthetic tests, migrations and documentation.
No runtime .env, database/backup files, uploads or private invoices were present;
credential-pattern inspection found none. This is a source review, not a claim
that every historical repository commit has been audited.

The token response is in
`docs/proposals/2026-10-20-codex-extension-token-response.md`. No tokens were
implemented or created. No production migration, deploy, scheduler, model
download or training was performed. GOT-OCR and Phi-3.5-mini remain on hold.
