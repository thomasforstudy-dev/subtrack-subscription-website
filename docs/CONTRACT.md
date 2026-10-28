# SubTrack — route, form and JSON contract

What the backend promises the UI lane (Antigravity) and the extension/calendar
lane (Codex). **Field `name=`s and routes here must not change without updating
this file and keeping the old name working.** Owner of this file: backend lane.

Last change: 2026-10-19 — Claude — accounts (section A); subscriptions, dashboard, settings, reminders (section B); link icons + duplicates (section C); runtime review repairs (edit semantics, totals scope, `/settings.json`, broken URLs, pin redirect, model errors).

## Rules for every form

| Rule | Detail |
|---|---|
| CSRF | Every `method="post"` form must contain `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`. Without it the server answers **400**. |
| JavaScript `fetch` POSTs | Send header `X-CSRF-Token` with the value of `<meta name="csrf-token">` (in `base.html`). |
| Exempt | `POST /subby/ask` only (JSON-only, touches no account data). |
| Errors | Shown with `flash()`; the page re-renders with the typed values kept (never the passwords). |
| `next` | Login keeps `?next=/some/page` in the URL. A form with no `action` posts back to the same URL, so it is kept automatically. Only same-site paths are followed. |

## Accounts

### Sign up — `GET/POST /register` (template `auth/register.html`)

| Field | Required | Rule (server checks; the UI may hint with the same rule) |
|---|---|---|
| `username` | yes | 3–30 characters: `a-z`, `0-9`, `_`. Upper case is turned into lower case. HTML hint: `pattern="[A-Za-z0-9_]{3,30}"` |
| `email` | yes | A normal email address, max 255 characters. Stored in lower case. |
| `password` | yes | **12–128 characters, at least one upper-case letter, one number and one special character** (anything that isn't a letter or number). HTML hint: `minlength="12" maxlength="128"` |
| `confirm` | yes | Must equal `password`. |

Success: logs in, sends a "confirm your email" link, redirects to `/subscriptions/`.

### Log in — `GET/POST /login` (template `auth/login.html`)

| Field | Required | Note |
|---|---|---|
| `identifier` | yes | Email **or** username. The old field name `email` still works. |
| `password` | yes | |

After 5 wrong tries for the same account from the same address in 15 minutes
(or 30 from one address), the page answers **429** with a "wait 15 minutes" message.

### Log out — `POST /logout`

Now **POST only** (a plain link answers 405). Use a small form:
`<form method="post" action="{{ url_for('auth.logout') }}">` + `csrf_token` + a button.

### Confirm email

| Route | Fields | Template |
|---|---|---|
| `GET /verify-email/<token>` | — | `auth/verify.html` (gets `valid: bool`) shows a "Confirm my email" button |
| `POST /verify-email/<token>` | `csrf_token` | — (redirects) |
| `POST /verify-email/code` (logged in, since 21 Oct) | `csrf_token`, `code` (6 digits, spaces ok), `next` (a path on this site) | — (redirects to `next`) |
| `POST /verify-email/resend` (logged in) | `csrf_token` | — (redirects back) |

The link is valid for 24 hours and works once. Clicking only *opens* the page;
the button press confirms, so email scanners that open links can't use it up.

The same email also holds a **6-digit code** (subject "123456 is your AllOutFree code"),
typed into the yellow banner in `base.html` (`autocomplete="one-time-code"`). It works once,
for 30 minutes, only for the address it was sent to; each new email cancels the older code;
5 wrong codes cancel it. Codes are a separate table (`email_codes`), so a code is never a link.

### Forgot / reset password

| Route | Fields | Template |
|---|---|---|
| `GET/POST /forgot-password` | `email` | `auth/forgot.html` |
| `GET/POST /reset-password/<token>` | `password`, `confirm` (same rules as sign up) | `auth/reset.html` |

`/forgot-password` always shows the same message whether or not the account
exists. Reset links last 30 minutes, work once, and changing the password logs
the account out everywhere else.

### Values templates can use

| Name | Type | Meaning |
|---|---|---|
| `csrf_token()` | function | The token for the hidden field / meta tag |
| `current_user.username` | str | Shown in the top bar |
| `current_user.email_verified` | bool | `False` → show the "please confirm your email" banner with the resend button |
| `current_user.is_admin` | bool | Unchanged |

## Subscriptions

### Add / edit — `GET/POST /subscriptions/new`, `GET/POST /subscriptions/<id>/edit` (template `subscriptions/form.html`)

| Field | Required | Rule |
|---|---|---|
| `name` | yes | 1–120 characters |
| `amount` | no (0) | Decimal, dot for decimals, max 2 decimals, 0 – 99,999,999.99 |
| `currency` | no (USD) | 3 letters (`USD`, `EUR`, `VND`); stored upper case |
| `cycle` | yes | `weekly`, `monthly`, `yearly` |
| `next_renewal_at` | yes | `YYYY-MM-DD`, year 2000–2100 |
| `lead_days` | no (7) | Up to 3 numbers 0–365, comma separated: `14, 7, 3`. Old field `remind_days` (one number) still works. |
| `manage_url` | no | http/https link to manage or cancel; shown with `rel="noopener noreferrer nofollow"` |
| `notes` | no | Up to 2000 characters |

On an error the template gets `form` (what was typed) as well as `item`.
**Render every field from `form` first** (`form.get('notes', item.notes)`), so
nothing the user typed disappears when another field is wrong.

**Editing — omitted vs. cleared (since 19 Oct repair):**

| What the form sends | Result |
|---|---|
| Field not in the form at all | Saved value is **kept** (a simpler form can't wipe it) |
| Field present but empty (`manage_url=`, `notes=`) | Deliberately **cleared** |
| `lead_days` empty | Back to the default `7` |
| Only `remind_days` (old forms), same number as the saved biggest lead | `lead_days` **kept** (e.g. `14,7,3`) |
| Only `remind_days`, a different number | `lead_days` becomes just that number |

The UI edit form should still send `lead_days` and `manage_url` so people can change them.

### List — `GET /subscriptions/` (template `subscriptions/list.html`)

Query string: `q` (searches name + notes), `status` = `active` (default) / `archived` / `all`,
`sort` = `renewal` (default) / `name` / `amount`, `page` (20 per page).
Template gets `items`, `pages` (Flask-SQLAlchemy pagination: `page`, `pages`,
`total`, `has_prev`, `prev_num`, `has_next`, `next_num`), `q`, `status`, `sort`,
`today` (user's local date) and `totals`.

| Scope | Meaning |
|---|---|
| `items` | **Only this page** (20), after search / filter / sort. Never add these up for totals. |
| `pages.total` | How many subscriptions match the current search / filter (all pages). |
| `totals` | **Whole account**, all active subscriptions, one row per currency: `{currency, count, monthly, yearly}` (Decimal). The same on every page and every search. Use this for any "you spend…" numbers. Same data as `/dashboard.json` → `projected`. |
| Search | Done by the server over the whole account (`?q=`). A browser-side filter only sees the 20 rows on screen, so the search box must submit `q` (GET). Keep `q`, `status`, `sort` in pager links. |
| Export | There is no export of subscriptions yet. Don't show an export button for them. (Bills export comes with the bills feature.) |

| Route | Fields |
|---|---|
| `POST /subscriptions/<id>/archive` | `csrf_token` |
| `POST /subscriptions/<id>/restore` | `csrf_token` |
| `POST /subscriptions/renewals/<renewal_id>` | `csrf_token`, `status` = `paid` / `skipped` / `expected` |

## Dashboard — `GET /dashboard` (template `dashboard.html`)

Template gets `today`, `totals` (list of `{currency, count, monthly, yearly}` —
one row per currency, never added together), `upcoming` (active subscriptions
renewing in the next 30 days), `expected` (passed renewal dates in the last 60
days, status `expected` / `paid` / `skipped`), `names` (subscription id → name).

"Projected" = what subscriptions *should* cost. "Expected charges" = dates that
passed; **not** proof of payment. "Actual spending" will come from confirmed bills.

### `GET /dashboard.json` (logged in; for the extension / calendar)

```json
{
  "today": "2026-10-19",
  "projected": [{"currency": "USD", "count": 2, "monthly": "20.00", "yearly": "240.00"}],
  "upcoming": [{"id": 3, "name": "Netflix", "amount": "9.99", "currency": "USD",
                "cycle": "monthly", "next_renewal_at": "2026-10-24", "days_left": 5,
                "manage_url": "https://netflix.com/cancel"}]
}
```

Money is a **string** (no float rounding), dates are ISO `YYYY-MM-DD`, missing
values are `null`. For now it uses the login cookie; the extension will get
API tokens later (backend lane).

## Settings — `GET/POST /settings` (template `settings.html`)

| Field | Rule |
|---|---|
| `timezone` | An IANA name like `Asia/Ho_Chi_Minh` (template gets `zones`, the full list) |
| `reminders_enabled` | checkbox `on` = reminders on; missing = off |
| `reminder_hour` | 0–23, the user's local time |
| `channels` | repeated checkbox; only `email` exists now (template gets `channels`) |

Settings are stored **on the server** in the user's account; the reminder job
reads them there. A settings panel elsewhere in the UI must load them from
`GET /settings.json` and save them with a normal `POST /settings` (same fields +
`csrf_token`). Settings kept only in the browser (localStorage) are display
preferences and never change when reminders are sent.

`GET /settings.json` (logged in):

```json
{"timezone": "Asia/Ho_Chi_Minh", "reminders_enabled": true, "reminder_hour": 9,
 "channels": ["email"], "available_channels": ["email"]}
```

## Reminder job (PC setup lane)

```
.venv\Scripts\python -m flask --app app send-reminders          (send what is due)
.venv\Scripts\python -m flask --app app send-reminders --dry-run (plan only)
```

Safe to run every 15–60 minutes and twice at once. Prints counts. Exits with an
error if email isn't set up (rows stay waiting). Only confirmed emails get reminders.

Since integration validation, the first attempted email is persisted before
sending (`database/05_reminder_payload.sql`). Crash retries reuse its complete
payload and idempotency key, including sender/reply-to. A recipient change skips
the saved message. SQL Server reminder planning uses a portable BIT comparison.

## Pinned links

Routes and field names are unchanged (`url`, `title`, `tags`, `notes`, `is_pinned`, `form`).

| New | Detail |
|---|---|
| `link.favicon_url` | The site's **own** icon (from its `<link rel="icon">`, else `https://<site>/favicon.ico`). Show it with `<img src="{{ link.favicon_url }}" alt="" width="16" height="16" loading="lazy" referrerpolicy="no-referrer">` and a letter fallback when it fails. Never use a third-party favicon service (it would learn every saved link). Note: showing it lets the saved site see the viewer's IP, like opening the link. |
| Duplicates | Saving the same page twice (ignoring http/https, `www.`, trailing `/`, `#...`, `utm_*` and similar) is refused with a flash: "You already saved this link as “…”." |
| `POST /links/preview` | JSON now may include `"icon"` next to `"title"`, `"site_name"`, `"description"`. Send `X-CSRF-Token`. A broken address returns `{}` (200). |
| Broken addresses | Bad port (`site:abc`, `site:99999`), half-written IPv6 (`https://[oops`), spaces or no host → the form is shown again with a flash; the saved link is unchanged. Never a 500. Same rule for a subscription's `manage_url`. |
| `POST /links/<id>/pin` | Optional `next` field (e.g. `/links/?q=school`). After pinning, the server goes back to that links page, or to `/links/`. It never follows an outside Referer. |

External links keep `target="_blank" rel="noopener noreferrer"`. Never `|safe` on titles or notes.

## Subby — `POST /subby/ask` (JSON, no CSRF token needed)

Request: `{"question": "...", "fun": true, "history": [{"role": "user"|"bot", "text": "..."}]}`

| Status | Body | Page should |
|---|---|---|
| 200 | `{"answer", "handoff": bool, "provider": "gemini"/"phi"/"fake", "fallback": bool}` | Show the answer. **If `fallback` is true, add a small note: "answered by a cloud model".** |
| 429 | `{"answer": "...slow down...", "handoff": false}` | Show it |
| 502 | `{"answer": null, "reason": "model-offline"/"model-failed"/"empty", "provider"}` | Use the built-in answers |
| 503 | `{"answer": null, "reason": "not-set-up"}` | Use the built-in answers |

Model metadata: `provider` says which model answered. `fallback: true` means the
chosen model was offline and the owner allowed a cloud fallback: the page **must**
show that (showing the provider name alone is not enough). Reasons:
`model-offline` = the model couldn't be reached or timed out; `model-failed` = it
answered something unusable (null/wrong shape/not JSON) or another error;
`empty` = it answered nothing. A wrong `SUBBY_FALLBACK` setting is ignored (no
fallback), never a 500 and never a silent cloud call.

### Subby's mic — `POST /subby/listen?lang=vi|en` (since 28 Oct)

Body: the recording itself (`audio/webm`, `audio/ogg`, `audio/mp4`, `audio/wav` or
`audio/mpeg`, at most 2 MB), with the `X-CSRF-Token` header. Only used where the browser
can't recognise speech (Firefox). `lang` is the mic's language switch
(`[data-voice-lang]` in `_subby.html`); missing or anything else means `vi`. Reply:
`{"text": "..."}`; 400 not audio, 413 too long, 429 too many, 503 Gemini unavailable.
The page runs every transcript (browser or Gemini) through `static/voice-tidy.js`
before it goes in the question box.

### Account tools (logged-in users, since 19 Oct)

When a logged-in user asks about their own account, the 200 reply has extra keys.
The answer text is written by the server (English), not by the model.

| `tool` | `data` | Extra |
|---|---|---|
| `list_upcoming_renewals` | `{"days", "items": [{"name", "amount", "currency", "next_renewal_at", "days_left"}]}` | |
| `search_saved_links` | `{"query", "items": [{"title", "url"}]}` | Show `url` as a link with `rel="noopener noreferrer"`; titles as plain text |
| `summarize_transactions` | `{"days", "items": [{"currency", "status": "paid"/"expected"/"skipped", "total"}]}` | Renewal charges, not bank data. Never add across currencies |
| `create_reminder_draft` | `{"draft": {"name", "amount"?, "currency"?, "cycle"?, "next_renewal_at"?}}` | `confirm_url` → `/subscriptions/new?...`. **Show a "Check and save" button** that opens it. Nothing is saved until the user presses Save on that form |
| `null` | — | The model asked for something not allowed, or the visitor isn't logged in: just show `answer` |

Money is a string, dates are ISO, at most 10 items. Keys missing = a normal answer.
`GET /subscriptions/new` accepts `name`, `amount`, `currency`, `cycle`,
`next_renewal_at` in the address to fill the form; other keys are ignored.

## Calendar (manual links and ICS, Codex integration)

| Route | Contract |
|---|---|
| `GET /calendar/` | Logged-in account's active subscriptions, across all pages |
| `GET /calendar/renewals.ics` | Private attachment: next renewal of every active subscription |
| `GET /calendar/subscriptions/<id>` | Owner-only review page with Google template link and single-event download |
| `GET /calendar/subscriptions/<id>.ics` | Owner-only active subscription; archived/other user's IDs return 404 |

Dates are **all-day DATE values**, with an exclusive next-day end. There is no
automatic recurrence, calendar sync, feed, OAuth or external write. The user's
validated IANA zone is displayed and included in calendar metadata/Google URL;
the renewal date is never converted into a UTC midnight. Downloads use stable
pseudonymous UIDs, CRLF, UTF-8 octet folding and escaped text. No amount, notes,
email, management link or login credential is exported. The Google link opens
only after the user chooses it; it shares title/date/zone and still requires
Save in Google. The review page explains this. The UI lane can restyle
`calendar/index.html` and `calendar/review.html`, preserving these routes and
the privacy/date explanations. No reusable public feed token is implemented.

## Bills (since 19 Oct, D slice 1: typed in + upload, no OCR yet)

Plain templates `bills/list.html` and `bills/form.html` for the UI lane to style
(and to connect the demo in `subscriptions/_bills_section.html`). Every POST needs `csrf_token`.

| Route | What |
|---|---|
| `GET /bills/` | List. Query: `q` (shop / invoice number / notes), `kind`, `category`, `status` (`confirmed` / `archived`), `page`. Template gets `items`, `pages`, `totals` (per currency, receipts only, Decimal), `unpaid` (card bills not paid, by due date), `waiting` (uploaded files not typed in yet), `kinds`, `categories`, `today` |
| `GET/POST /bills/new` | Add. Optional `document_id` (query on GET, hidden field on POST) = typed from that uploaded file |
| `GET/POST /bills/<id>/edit` | Edit. A field **not sent** keeps its saved value; sent but empty = cleared. No `item_name_*` fields at all = items kept |
| `POST /bills/<id>/paid` | `paid=1` (paid today) or `paid=0` |
| `POST /bills/<id>/archive`, `/restore` | Nothing is ever deleted |
| `POST /bills/upload` | `multipart/form-data`, field **`file`**. PNG/JPG/WEBP/PDF/DOCX by content (not name), then really opened: photos fully decoded (≤ 12000 px a side, ≤ 30 MP, not animated), PDFs read by pypdf (1–5 pages, counted even when compressed). ≤ 10 MB. Refused with a flash: damaged/cut-off files, old `.doc`, password-protected PDF/DOCX, zip bombs. Same file again = the saved one. Redirects to `/bills/new?document_id=…` (or that bill's edit page) with a flash |
| `GET /bills/files/<id>` | The owner's file only. Always a download, except photos with `?view=1` (for `<img>` next to the form). PDFs/DOCX are never shown inline |
| `GET /bills/export.json` / `.csv` / `.md` | Saved (confirmed) bills. CSV is safe to open in Excel (formula cells are made plain text) |

Form fields (names match the demo where it had them):

| Field | Rule |
|---|---|
| `kind` | `receipt` (default) or `card_bill` |
| `merchant` | Required, ≤ 200 (shop, or card/bank name) |
| `branch`, `address`, `invoice_number` | Optional, ≤ 200 / 500 / 64. Only what the bill shows |
| `invoice_date`, `transaction_date` | Optional `YYYY-MM-DD` |
| `transaction_time` | Optional `HH:MM`. **Empty = the bill has no time** (never shown as 00:00) |
| `timezone` | Optional IANA name (`Asia/Ho_Chi_Minh`) |
| `currency` | Required, 3 letters |
| `subtotal`, `tax`, `total` | Optional Decimal 0 – 9,999,999,999.99 (fits DECIMAL(12,2)), dot for decimals, max 2 decimals. **Whole numbers only** for currencies without cents (VND, JPY, KRW, …) |
| `category` | `software`, `streaming`, `education`, `utilities`, `shopping`, `food`, `travel`, `other` |
| `card_last4` | Optional, exactly 4 digits. A full card number is refused **and not shown back** |
| `statement_start`, `statement_end`, `due_date` | Dates. `due_date` required for `card_bill`; end ≥ start |
| `item_name_N`, `item_qty_N`, `item_price_N` | N = 1–30. Rows without a name are skipped. Qty > 0, ≤ 3 decimals; price like the totals; amount = qty × price must be ≤ 9,999,999,999.99 |
| `item_rows` | Hidden, `1`: "this form has the item table". Send it so that removing every row really removes the items. Without it and without any `item_name_N`, editing keeps the saved items |
| `notes` | ≤ 2000 |

Export JSON (one object per bill): `id, document_id, kind, invoice_number, invoice_date,
transaction_datetime ("2026-10-18" or "2026-10-18T14:30"), timezone, merchant_name,
merchant_branch, merchant_address, currency, subtotal, tax, total,
line_items [{description, quantity, unit_price, amount}], category, card_last4,
statement_start, statement_end, due_date, paid_at, notes, source ("manual"/"upload"),
review_status ("confirmed")`. Money and quantities are strings, dates ISO, anything not on
the bill is `null`. `evidence` is `null` for typed-in bills (nothing is made up); per-field source page/text arrives with the OCR slice. `checks` lists numbers that don't add up (subtotal + tax ≠ total, items ≠ subtotal/total): shown for a second look, the typed values are **never changed**.

**Item rows after an error (review B3):** the form is re-rendered with every row number
the POST contained (up to 30), with the typed values. UI add/remove controls: add = a new
row with the next free N (≤ 30); remove = empty that row's name (or drop its inputs) and
keep sending `item_rows=1`. Row numbers don't need to be continuous.

Integration validation: the actual form offers keyboard-accessible Add/Remove controls
through row 30. Image/PDF/DOCX inspection runs in a separate parser process with an
8-second deadline; timeout rejects the upload before storing a document or file.
Images are decoded with side/pixel limits and PDFs require a readable 1–5-page tree.
Mocked browser speech uses the reviewed input as the submitted question, retains
final results after normal Stop, and aborts/invalidates cancelled or closed sessions.
The browser may use an external speech service; real microphone/TTS remains unverified.

**Receipt vs card bill:** a `receipt` is one purchase (what was bought, when). A `card_bill`
is a bank/card statement (statement window, due date, paid or not). Totals on `/bills/`
count receipts only, so a card bill and the purchases on it are never counted twice.

## Reading bills (since 20 Oct: jobs, drafts with evidence, review)

Nothing is read until the owner presses the button, and nothing becomes a bill until the
owner accepts a draft. Plain templates `bills/job.html`, `bills/draft.html` for the UI lane
to style. **New routes only; no existing route or field name changed.** Every POST needs
`csrf_token`; every route is the owner's only (someone else → 404).

| Route | What |
|---|---|
| `POST /bills/files/<document_id>/read` | "Read it for me". One job per file: pressing it again returns the same job. Redirects to the job page |
| `GET /bills/jobs/<job_id>` | Job page: status, honest message, Try again (when failed), link to the draft, "type it in yourself" |
| `GET /bills/jobs/<job_id>.json` | `{status, attempts, error_code, message, draft_url, bill_url, plan_url}` for polling (null when absent; `bill_url`/`plan_url` = what the AI reader filed by itself) |
| `POST /bills/jobs/<job_id>/retry` | Only a `failed` job goes back to `queued` |
| `GET /bills/drafts/<draft_id>` | Review page (template gets `draft`, `values`, `found`, `unread_pages`, `pages`, `revisions`, `fields`, `labels`, `typed`, `bill`) |
| `POST /bills/drafts/<draft_id>` | Fields with the bill form's names (`merchant`, `total`, `invoice_date`, …) + hidden `revision` + `action=save` (new revision) or `action=accept` (same checks as `/bills/new`; makes one Bill, then redirects to its edit page). A stale `revision` (other tab) is refused, nothing saved |
| `POST /bills/drafts/<draft_id>/discard` | Draft kept as `discarded`; redirects to `/bills/new?document_id=…` |

`/bills/` template also gets `reading` = `{document_id: job}` (the list shows "Read it for me"
or "Reading status" next to each waiting file).

**AI reader (since 28 Oct, `OCR_PROVIDER=gemini`).** `/bills/` also gets `ai_reading` (bool);
when true the upload card must say files go to Google's Gemini (`[data-ai-reading]`).
`POST /bills/upload` then queues the reading itself and redirects to the job page (not
`/bills/new`). Jobs run in the background straight away; the job page refreshes itself while
`queued`/`running` and gets `filed` = `{bill, plan}`: a complete, valid draft becomes a Bill by
itself (draft `accepted`, revision action `auto-saved`) and a subscription bill adds a plan
(only if no plan has that name). Anything unclear stays a draft, as before. With the AI off,
nothing here changes.

**Job status**: `queued` → `running` → `succeeded` | `failed`. `error_code` (message for each in
`app/bill_jobs.py` → `MESSAGES`): `ocr-not-set-up`, `ocr-offline`, `ocr-busy`, `ocr-bad-reply`,
`timeout`, `reader-crashed`, `bad-document`, `too-big`, `bad-extraction`, `file-missing`, `gave-up`.
Temporary ones (`ocr-offline`, `ocr-busy`, `timeout`, `reader-crashed`) go back to `queued` with
5, then 10 minutes' wait, at most 3 tries. Jobs start in the background when a file is queued
or retried, and when the owner opens `/bills/` or a job page while a retry is due;
`flask process-documents` still runs them by hand.

**Draft values** (`values`, one entry per field name of the bill form):
`{"value": "99000.00" | null, "origin": "document" | "you" | "empty", "method": "label" |
"first-line" | "keyword" | "", "evidence": [{"page": 1, "start": 87, "end": 93, "text": "99.000"}]}`.
`found` is the same shape for what the reader found (never changed). `method: "first-line"`
= the merchant is the bill's first line (a guess: ask the owner to check). Evidence = page +
character positions in the stored page text; there are no image coordinates or confidence
scores (we don't have real ones). Show document text as text (never `|safe`).

**Dates stay apart**: `invoice_date` = printed on the bill (label "Invoice date / Ngày …" or a
generic "Date / Ngày"), `transaction_date`/`transaction_time` = only from a payment label
("Paid on / Ngày thanh toán"), `due_date` = card payment due ("Due date / Hạn thanh toán").
Category and time zone are never read from the bill: the owner picks them.

**Export**: a bill made from an accepted draft has `"source": "upload"` and `evidence` =
`{field: [spans]}` for the values that still came from the document; typed-in bills keep
`"evidence": null`. A field loses its evidence as soon as the bill's current value differs
from what the document showed (for example after editing the total in `/bills/<id>/edit`).

**Card numbers** (Codex review R1/R2): text from files *and* OCR is masked to the last 4
digits before it is searched, saved or shown. In a draft, `card_last4` must be empty or
exactly 4 digits on both Save and Accept; anything else is refused, not stored, not shown
back (`maxlength="4"` on the input is only a helper).

**Amounts** (R4): bills hold amounts ≥ 0, so a refund/credit (`-12.50`, `−12.50`, `(12.50)`)
or a broken number (`1,23,456`) leaves the field empty instead of losing its sign.
**Evidence must show the value** (R5): every value is read back from its cited text
(amount, date, time, currency symbol, last 4 digits, exact text); a contradiction makes the
job fail with `bad-extraction`. The one allowed translation: a statement word → `card_bill`.

**OCR**: `.env` `OCR_PROVIDER` empty = none (photos/scans fail with `ocr-not-set-up`; PDFs and
Word files with text still work); `got` = GOT-OCR on the owner's PC at `OCR_BASE_URL` with
`OCR_API_KEY`. Its reply must be `{"model", "revision", "pages": [{"page", "text", "truncated"}]}`.

## Extension API tokens (since 20 Oct; contract agreed with Codex)

Code: `app/api_tokens.py` (owner pages + checks), `app/api.py` (API). Agreed in
`docs/proposals/2026-10-20-codex-extension-token-response.md`.

### Owner pages (login cookie + CSRF, template `api_tokens.html`)

| Route | Form fields | What |
|---|---|---|
| `GET /settings/tokens` | | List: name, prefix (`st_xxxxx…`), scopes, created, last used, expires, state (`active` / `expired` / `revoked`). Linked from `/settings` (`#extension-tokens`). |
| `POST /settings/tokens` | `name` (1–60), `days` (1–365, default 90), `scopes` (checkboxes; V1 only `renewals:read`) | Creates a token and shows its secret **once** in the answer (`new_secret` in the template; never in a flash, never again). Bad form → 400; already 5 active → 409. |
| `POST /settings/tokens/<id>/revoke` | | Revoke now (owner only, else 404). Kept in the list; repeating is harmless. |

Both pages send `Cache-Control: no-store`. At most **5 active tokens**; revoked and expired
ones don't count. A **password reset revokes every token**.

### The API (token only; the login cookie is never used)

Header `Authorization: Bearer st_<43 characters>`, exactly that shape, one credential. A token
in the address, a form or a cookie is never read. Every request re-checks owner, scope,
expiry and revocation. Answers are JSON with `Cache-Control: no-store`.

| Route | Scope | Answer |
|---|---|---|
| `GET /api/v1/renewals?days=7` (`days` 1–31, default 7) | `renewals:read` | `{"today": "2026-10-21", "timezone": "Asia/Ho_Chi_Minh", "days": 7, "count": 2, "items": [{"id", "name", "amount": "260000.00", "currency": "VND", "next_renewal_at": "2026-10-23", "days_left": 2}]}` |
| `GET /api/v1/me` | any | `{"username", "timezone", "scopes": ["renewals:read"], "expires_at": "2027-01-18T07:12:09Z"}` |

- **Window**: the owner's active plans with `today <= next_renewal_at < today + days`, where
  `today` is the owner's local date. A saved date in the past is moved to its next real date
  for the answer (read-only). Sorted by date, then name, then id; **no limit**, so a badge
  from `count` never undercounts. Amounts are Decimal strings; currencies are never added.
  No `manage_url` in V1: open the website for that.
- **Errors**: `401 {"error": "missing-token" | "bad-token" | "expired" | "revoked"}` (with
  `WWW-Authenticate: Bearer`), `403 {"error": "missing-scope"}`, `400 {"error": "bad-days"}`,
  `404 {"error": "not-found"}`, `429 {"error": "slow-down"}` with `Retry-After` (seconds). On
  401 the extension clears its cache and badge and asks the owner to reconnect.
- **Limits** (in memory, one waitress process, so not multiplied by workers): 120 requests per
  hour per token; 20 failed token checks per 10 minutes per address (then even a good token
  waits). `last_used_at` is written at most once a minute.
- **CORS**: only the exact `EXTENSION_ORIGIN` (`chrome-extension://` + 32 letters a–p) gets
  `Access-Control-Allow-Origin`; preflight allows `GET` and the `Authorization` header, never
  credentials, never a wildcard. CORS is not the login: the token is.

## Card holder (since 26 Oct, on the Bills page)

Only the first 6 and last 4 digits are stored. Never ask for the full number, expiry or CVV.

| Route | Fields | Result |
|---|---|---|
| `POST /cards/` | `csrf_token`, `name` (0–60, empty = network + last 4), `kind` (`credit`/`debit`), `first6` (exactly 6 digits), `last4` (exactly 4 digits), `color` (`violet`, `orange`, `mint`, `sky`, `pink`, `ink`) | redirects to `/bills/#cards`; max 12 cards |
| `POST /cards/<id>/remove` | `csrf_token` | hides the card (`removed_at`), keeps the row; 404 for someone else's card |

`bills/list.html` gets `cards`: a list of `{card, network, number, bills, month}` where `number`
is already masked (`4111 11•• •••• 1234`) and `month` is `[(currency, amount)]` spent this month
with that card (bills whose `card_last4` matches). It also gets `month`: this month's receipts
in the main currency (`currency`, `total`, `count`, `categories` as `(category, amount, bar %)`,
`others` as `[(currency, total)]`), or `None`.

## Games (since 26 Oct, all in the browser)

`GET /tools/coin-flip`, `GET /tools/blackjack`, `GET /tools/case-spin` (logged in). Nothing is
posted or saved on the server; the case spin keeps its lists in `localStorage` (`case-spin-lists`).

## Admin

Nobody becomes admin by signing up any more. On the server PC:

```
.venv\Scripts\python -m flask --app app make-admin you@example.com
.venv\Scripts\python -m flask --app app make-admin you@example.com --remove
```

Removing the last admin is refused.

## Settings (`.env`)

| Name | Meaning |
|---|---|
| `APP_ENV` | `production` (default) or `development`. Production refuses to start without a real `SECRET_KEY` (32+ characters) and only sends cookies over HTTPS. |
| `TRUSTED_PROXIES` | Addresses allowed to tell us the visitor's real IP (Cloudflare Tunnel runs on this PC). Default `127.0.0.1,::1`. |
| `MAIL_BACKEND` | `resend`, `file` (saves emails in `instance/outbox/`), `memory` (tests) or `none`. Default: `resend` if `RESEND_API_KEY` is set, `file` in development, otherwise `none`. |
| `RESEND_API_KEY`, `MAIL_FROM`, `MAIL_REPLY_TO` | Real sending through Resend. |
| `DEFAULT_TIMEZONE` | Time zone for new accounts, e.g. `Asia/Ho_Chi_Minh` (default `UTC`). |
| `EXTENSION_ORIGIN` | The Chrome extension's exact origin `chrome-extension://<id>` for CORS on `/api/v1/`. Empty = none. Not a secret. |
