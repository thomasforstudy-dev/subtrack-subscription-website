# AllOutFree — first-user guide and application QA

Date: 24 October 2026. **Report only; every finding below remains unresolved.**

**Result: 0 blockers, 5 majors, 6 minors (11 findings).**

## Environment and evidence

- Tested application commit: `6a8157f96478a6e77f5f74e2f19f167443a0998b` (`origin/claude/ai-features`). Report branch: `codex/qa-guide-tour`, worktree `subtrack-codex-qa2`.
- Started using this worktree's `run_local.bat`, at `http://127.0.0.1:5000`. Python **3.14.8**, real Microsoft Edge controlled by Playwright, fresh browser profiles; desktop **1440 × 1000**, phone viewport **390 × 844**. This is viewport emulation, not a physical phone.
- **SQLite only**, dedicated `instance/qa.db`; development mode, file email in the worktree's ignored `instance/outbox`, empty Gemini/OAuth/OCR keys. Only this worktree's requested `.env` was created from the example. The live checkout, live `.env`, SQL Server, services, deployment, schedulers, and other agents' work were not changed.
- Two generated local accounts, generated PDF/Word/image fixtures, generated test passwords. Screenshots contain synthetic data only. No credentials, email codes, extension key values, database files, invoices from the owner, or browser profiles belong in this commit.
- Page/layout sweep: 15 routes in all eight combinations of EN/VI, light/dark and 1440/390px (**120 visits**). Additional phone light/dark tours and public landing checks. Screenshots were taken after animations settled.

## Automated checks

Clean full rerun on the application commit above:

```powershell
.venv\Scripts\python -m pytest -q --basetemp=instance/qa-guide-full-temp --junitxml=instance/qa-guide-full-tests.xml
```

**661 passed, 0 failed, 0 skipped in 205.50 seconds.** The report commit changes documentation and screenshots only.

The initial attempt was not clean: 635 passes and 26 failures in `test_bill_jobs.py`, followed by a pytest cleanup `PermissionError` involving the shared temporary directory's `pytest-current`. That run also crossed a long wall-clock interval; those worker tests set a module-level due-time clock one hour ahead at import. A separate fresh run of the entire bill-worker module passed **94/94 in 46.11 seconds**, and the subsequent complete run above passed. The first result is retained here rather than silently omitted; no app/test code was changed to obtain the reruns. Detailed runner logs/XML remain ignored under `instance/`.

These results **do not verify SQL Server, hosted GitHub CI, live deployment, actual email delivery, OAuth sign-in, paid AI responses, physical microphone capture, or audible voice quality**.

## Bugs

Severity: blocker = no usable journey; major = a core function gives wrong results or cannot be used normally; minor = a workaround exists or a localized/accessibility defect. All screenshot paths below are relative to this report.

| ID | Page / step | Steps to reproduce | Expected | Actual / user impact | Screenshot | Severity | Lane |
|---|---|---|---|---|---|---|---|
| G01 | `/guide` → `/register?tour=1`; signup step 1 | Use a fresh logged-out browser with OAuth disabled. Click **Sign up with a guide**. Then click **Show me how**. Reproduced in EN desktop and VI phone. | Guide entry automatically starts a populated tour; unavailable Google/GitHub step is skipped to Email. | Guide entry shows no tour. Manual replay opens an empty card with no title, instructions, highlight, or Next label. Arrow Right recovers the Email step; remaining signup steps then work. A new user cannot understand the normal guided entry. | [Entry](2026-10-24-guide/G01-guide-signup-no-tour.png), [empty card](2026-10-24-guide/G01-signup-empty-tour.png), [phone entry](2026-10-24-guide/G01-guide-entry-phone-no-tour.png), [phone card](2026-10-24-guide/G01-signup-empty-phone.png) | **major** | UI |
| G02 | Phone app tour, steps 2, 8, 9, 10 | At 390 × 844, replay from Settings and follow all ten steps. | Bottom card stays clear of the highlighted button/area. | Card covers the raised Add plan button (step 2), the bottom of the AI tools area (8), part of reminder settings (9), and the Subby launcher (10). The button being explained is hidden by its explanation. Desktop placement did not overlap these targets. | [2](2026-10-24-guide/G02-phone-tour-overlap-2.png), [8](2026-10-24-guide/G02-phone-tour-overlap-8.png), [9](2026-10-24-guide/G02-phone-tour-overlap-9.png), [10](2026-10-24-guide/G02-phone-tour-overlap-10.png) | **major** | UI |
| G03 | `/subscriptions/new`, Other service tile | Click iCloud+, then Other; expand **More: cancel page & notes**. | A custom service starts from clear/default values, or retained values are explicitly explained. | Only the name clears: price remains 69,000 VND, reminders remain 7/1, and Apple's cancellation URL remains. A different custom plan can be saved with the wrong service's cancellation link and cost. | [Retained fields](2026-10-24-guide/G03-other-keeps-previous-price-cancel.png) | minor | UI |
| G04 | `/tools/food-roulette/` and `/tools/forecast/?period=week` | Save two food receipts with the same merchant: **60,000 VND** and **4 USD**. For the weekly forecast, put both in a completed prior week (16 October in this dataset). Open both tools. | Keep merchant averages separate by currency; never average raw VND and USD together. | Roulette says **about USD 30,002.00**. Forecast says **Usually VND 30,002** for the same merchant. Both compute `(60000 + 4) / 2` and attach one currency. Forecast's overall per-currency expected-spend totals remain separate; the merchant average is wrong. | [Roulette](2026-10-24-guide/G04-roulette-mixes-currencies.png), [forecast](2026-10-24-guide/G04-forecast-mixes-shop-currencies.png) | **major** | Backend |
| G05 | Subby, phone | At 390 × 844 open Subby, type a question, tap the Send arrow at bottom right. | Send remains visible and clickable. | Floating Subby launcher covers Send and intercepts the tap. A normal browser click times out; pressing Enter sends successfully. Touch users are left without an obvious send action. | [Covered Send](2026-10-24-guide/G05-phone-subby-send-covered.png) | **major** | UI |
| G06 | `/bills/new`, phone | Open **Type in a bill** at 390px, in either language/theme. Inspect shop, date, amount and item controls. | Form fields and actions fit the phone viewport without page-wide horizontal overflow. | Main input widths are about **702px**, right edge about **740px**; document scroll width is **655px** at a 390px viewport. Fields and item/remove controls extend off-screen. The bill list also measured page widths of 394px VI / 432px EN. This persists on this commit despite the earlier progress note about fixing bill width. | [Bill form](2026-10-24-guide/G06-phone-bill-form-overflows.png), [bill list](2026-10-24-guide/G06-layout-en-dark-bills.png) | **major** | UI |
| G07 | Tour dialog, keyboard | Replay the app tour. Immediately press **Shift+Tab** while the newly opened card has focus. | Keyboard focus stays within the modal tour, including its first reverse-Tab. | Focus moves to a background page button outside `.tour-card`. Forward Tab wraps correctly after reaching the card's buttons, but the initial reverse-Tab escapes. | [Background focus](2026-10-24-guide/G07-tour-shift-tab-escapes.png) | minor | UI |
| G08 | VI `/bills/jobs/1`, `/bills/drafts/1` | Set VI, upload generated Word bill, return to Bills, click **Read it for me**. Run the local reader once, open job and draft. IDs vary on a fresh database. | Job and review labels, instructions and actions use Vietnamese. | Most job and draft copy remains English: “Reading”, “Extraction complete”, “Check the draft”, “Unknown (null)”, all field labels and Accept/Save actions. Surrounding navigation is Vietnamese. This makes a sensitive confirmation step hard to understand. | [Job](2026-10-24-guide/G08-vietnamese-job-English.png), [draft](2026-10-24-guide/G08-vietnamese-draft-English.png) | minor | UI |
| G09 | VI Subby | Set VI, open Subby with no Gemini key; ask a Vietnamese reminder question. | Vietnamese interface and fallback labels. | Answer is Vietnamese, but the header says **FAQ Fallback** and the primary speech button remains **Voice**, also embedded in the greeting. | [VI Subby](2026-10-24-guide/G09-vi-subby-fallback-English.png) | minor | UI |
| G10 | Abandoned app tour, no-plan account | As a fresh second user, open the first dashboard, advance to step 3, navigate away without Finish/Skip, and return after more than 15 minutes. Do not add plans to that account. | An expired unfinished tour does not pop up again automatically. | A real **928-second (15m28s)** interval was measured with both wall and monotonic clocks. On return, the tour opened automatically at **step 1/10**. It interrupts the user again instead of staying dismissed/expired. | [Timed return](2026-10-24-guide/G10-abandoned-tour-restarts-after-15min.png) | minor | UI |
| G11 | Logged-out desktop guide / registration | Use a new desktop visitor at 1440px, open `/guide` or `/register`, look for the theme control and navigate by Tab. | A visitor can select light/dark at both supported widths. | The only theme toggle has `display:none`; there is no signed-in side rail for a guest. At phone width the header toggle is available. Desktop guests cannot discover or reach a theme choice. | [Guest desktop](2026-10-24-guide/G11-desktop-public-no-theme-control.png) | minor | UI |

## Journey checks that worked

- Logged-out `/guide` displays eight steps with “Look for” button examples; both languages fit desktop/phone. Following its signup entry exposed G01. OAuth buttons are intentionally absent without credentials, so the shown-provider path is unverified.
- Once recovered using Arrow Right, signup Email/Username/Password/Create highlights and Next/Back/arrows/Esc/Skip worked. Weak passwords and duplicate usernames were refused. A generated account confirmed its local 6-digit email code. Logout/back navigation did not expose Settings, and logging in again worked.
- The first dashboard visit automatically started the 10-step app tour. Desktop highlights/page navigation were correct. Finish stayed closed on the next visit. Replay worked from account menu, Settings and a middle `/guide` Show me link (bill step 6). Phone placement/focus issues are G02/G07.
- All five service presets filled name, amount, currency, cycle, cancellation URL and reminders. Currency/cycle chips and live preview updated. Reminder chips never exceeded three; manually entering four was refused. Six plans were saved across weekly/monthly/yearly and USD/VND, including today/tomorrow/40 days out. Edit/archive/restore and search/sort worked. Monthly totals checked by hand: **USD 51.52**, **VND 503,333** (display-rounded); currencies were separate.
- Calendar showed October/November grids and the correct next-renewal days; today (24 October) had the today class/outline. All-plan ICS contained six events with starts **20261024, 20261025, 20261031, 20261124, 20261203, 20271024**. Google review URL carried the chosen all-day date and time zone. Nothing was saved in an external Google account.
- Bills: four food receipts with item lines, a generated PDF-backed receipt, a generated Word draft accepted as a bill, and a synthetic last-four-only card bill. Edit/archive/restore, Paid/unpaid, CSV export and private file download worked. PDF/Word/photo uploads were accepted; photos clearly offered manual entry without OCR. Requesting Word reading queued a job; one local `flask process-documents` invocation reported **succeeded: 1, retry: 0, failed: 0, lost: 0**. No scheduler or model service was started.
- Links: example.com title filled as “Example Domain”; tags, pin/unpin action, search/Clear, editing, and confirmation/deletion of a disposable synthetic link worked.
- Settings: reminder switch off/on persisted, hour chips filled the hour box, manual hour 16 cleared the previous chip selection, time zone persisted. “Send a test” refused an unconfirmed address; after confirmation three file emails succeeded and the fourth was refused. Language and theme tiles worked. Extension keys: five active keys disabled creation, revocation freed a slot, replacement creation succeeded, Copy matched the generated key in the clipboard (value never logged).
- Forecast Tomorrow/Next week/Next month rendered. Before adding the accepted Word receipt, completed-week expected spend was **USD 1.33 / VND 30,000** over three weeks, matching saved eligible receipts. Populated Ask Gemini gave a polite unavailable/quota message with no key. Roulette completed five checked spins across both modes; each named winner matched the pointer angle. G04 is the separate amount defect.
- Read aloud: text PDF, 65-page PDF, Word and pasted text accepted; scanned PDF explained missing OCR, PNG refused, 45MB PDF refused. Missing-key Play fell back to browser voice. Pause/next/previous/stop/speed/page-60 and same-document Continue from part 60 after reload worked at the UI state level. Audio quality was not judged in headless Edge.
- Subby: English and Vietnamese typing worked via Enter, built-in answer/handoff behavior was polite without a key, Read used browser fallback. Explicit microphone access produced a polite permission-denied message with a typing alternative. Real microphone transcription and audible output are **unverified**, not counted as a pass. Across this walkthrough there were two Subby questions and fewer than 15 Ask Gemini/voice requests; no key was supplied and no model download/training occurred.
- Keyboard Tab reached service presets, cycle controls (visible label focus), reminder chips and Save; sampled bill/link/settings/key/reader controls had keyboard focus. This is not a blanket accessibility certification; the tour focus defect is G07.
- A 404 page rendered in both languages. XSS probes in a plan name/notes and link title/notes displayed as literal text; no injected script/image element appeared.

## Security checks (bounded, synthetic users only)

Using user B's valid authenticated browser context, changing IDs to user A's records returned **404** for plan edit, calendar review, bill edit, exact private download `/bills/files/1`, link edit, job and draft pages. POSTs with B's legitimate CSRF token returned **404** for A's plan archive, bill archive, link delete and key revoke. A form POST without CSRF returned **400**. B's bill JSON export returned **200** without A's markers. A guessed subscription export path was **404**, so that guessed URL is not claimed as export-isolation evidence.

No cross-account exposure was observed in these specific checks. This is not a full security audit.

## Confusing for a new user

- The guide says AI reads an uploaded bill, but the upload first opens a manual form. The extra **Read it for me** action appears after returning to Bills, and local reading waits for a separately run worker. Show this sequence where the user uploads.
- Signup lands on Subscriptions; the app tour starts only after navigating to Overview. The signup tour says the app shows you around “right after”, which creates an expectation of an immediate handoff.
- “Take the tour” explains controls but blocks interaction with the highlighted page; explicitly tell users to finish/skip before filling a form.
- Draft review exposes “Extractor: rules v1”, “Unknown (null)” and revision jargon to a beginner.
- Dense tables require a separate horizontal gesture to reach icon actions on phone. Make this discoverable even where the table's own scroll container works.
- Missing Gemini configuration is described as busy/out of free quota. The fallback is polite, but the cause is unclear in a local first-run setup.

## Local reproduction / scope

From `C:\Users\buith\Projects\subtrack-codex-qa2`, run `run_local.bat` and browse `http://127.0.0.1:5000/guide`. Use this checkout's synthetic SQLite settings only. Stop only its local Flask window/process when finished. The browser tooling and generated fixture/profile/credential files are outside the repository in `subtrack-qa-tools\guide-tour`; they are not part of the report commit.

No merge, deployment, production migration, real email, checkpoint download, GOT-OCR training or Phi-3.5-mini training was performed.
