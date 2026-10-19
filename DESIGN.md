# SubTrack Design System

Source of truth for how SubTrack looks. Every new screen (Stitch designs,
templates, CSS) should match this file.

Version 2 (2026-10-15): colourful "chaos → calm" story, Plus Jakarta Sans,
help bot. `app/static/style.css` still has version 1 (black/white, Segoe UI)
until the UI lane rebuilds it.

## 1. Visual theme and atmosphere

The page tells a story with colour. It starts as **subscription rush hour**:
a deep navy night full of loud brand colours, flying cards, ticking countdowns
and red "renews in 2 days" badges. As the visitor scrolls, SubTrack tidies it
up and the page turns **bright, calm and friendly**: soft lilac background,
violet buttons, mint "you're safe" ticks.

Mood words: chaos → calm, rush hour, energetic, playful, friendly, trustworthy at the end.

## 2. Color palette and roles

**SubTrack brand (calm side, used everywhere in the app)**

| Name | Hex | Role |
|---|---|---|
| SubTrack Violet | `#6d4aff` | Primary buttons, links, active chips, progress rail |
| Violet Deep | `#4b2fd6` | Button hover, headline highlight |
| Mint Safe | `#16c79a` | Success, "reminder set", "you're covered" ticks |
| Sun Yellow | `#ffc83d` | Pinned links, small highlights, bot accent |
| Coral Due | `#ff5a5f` | Renews soon / unexpected charge (text, badges, borders) |
| Lilac Mist | `#f4f1ff` | Calm page background |
| White | `#ffffff` | Cards, tables, inputs, chat bubbles |
| Ink | `#16142b` | Body text and headings on light backgrounds |
| Slate | `#5f5d78` | Secondary text, captions |
| Hairline | `#e4e0f5` | Borders and dividers on light backgrounds |

**Rush-hour side (landing chapters 1–2 only)**

| Name | Hex | Role |
|---|---|---|
| Midnight Navy | `#0e0b2b` | Background of the chaos chapters |
| Night Line | `#2a2557` | Borders on dark |
| Real brand colours | Spotify `#1db954`, Netflix `#e50914`, YouTube `#ff0033`, ChatGPT `#10a37f`, Adobe `#fa0f00`, iCloud `#3693f3` | Only on the service cards, to make the pile-up feel loud |

Rules:
- The transition navy → lilac happens between chapter 2 and chapter 3 ("Add them once").
- Coral is for warnings only, never for normal buttons.
- Text on Midnight Navy is White or `#c9c5ff`; text on Lilac/White is Ink or Slate.

## 3. Typography rules

- Family: **Plus Jakarta Sans** (Google Fonts, weights 400/500/600/800), fallback `system-ui, sans-serif`. Supports Vietnamese.
- Display (chapter headline): 64px desktop / 48px laptop / 34px phone, weight 800, line-height 1.05, letter-spacing -0.02em.
- Heading (h1): 28px, weight 800. Subheading (h2): 20px, weight 600.
- Body: 16px, weight 400, line-height 1.5. Small / labels: 14px, weight 500.
- Chapter label: 12px, weight 600, uppercase, letter-spacing 0.12em.
- Prices and countdown numbers: same font, weight 800, `font-variant-numeric: tabular-nums`.

## 4. Component stylings

- **Top bar:** transparent over navy in chaos chapters, white with Hairline border once calm. Brand left; Log in link + Violet "Sign up" button right.
- **Primary button:** Violet fill, white text, 12px radius, padding 12px 20px, weight 600. Hover: Violet Deep, lifts 2px.
- **Secondary button:** white fill, Hairline border, Ink text, 12px radius.
- **Card:** white, 16px radius, 1px Hairline border, soft shadow `0 8px 24px rgba(22,20,43,.08)`.
- **Service card (chaos):** brand-coloured left stripe or logo tile, price + "renews in X days" Coral badge, tilted -6° to 6°, motion streaks behind it.
- **Input:** white, 1px Hairline, 10px radius, Violet focus ring.
- **Table / list:** white card, Hairline dividers; a "renews soon" row gets a pale Coral tint `#fff0f0`; a pinned row gets pale Sun `#fff8e1`.
- **Chip:** pill, Hairline border; active chip Violet fill, white text.
- **Help bot (see section 7).**

## 5. Layout principles

- Base spacing unit: 4px (4, 8, 12, 16, 24, 32, 48, 64).
- App content column: max 52rem. Landing content column: max 1200px.
- Breakpoint 640px; must work at **390px** with no sideways scroll.
- Target screens: laptop 16:10 (1440×900), desktop 16:9 (1920×1080), phone 9:16 (390×844).
- Landing: each chapter is one screen tall. Text + visual side by side on laptop/desktop, stacked (text first) on phone. Chapter progress rail on the right (desktop), thin progress bar under the top bar (phone).

## 6. Scroll animation plan (vanilla JS + CSS, no libraries)

Built later with `IntersectionObserver` + CSS transitions. Everything must also
look fine with animations off (`prefers-reduced-motion`).

| Chapter | Effect while scrolling |
|---|---|
| 1 Rush hour | Service cards fly in from all edges and pile up, slightly tilted; countdown badges tick down; a charge ticker scrolls along the bottom. |
| 2 The surprise | Bank notifications drop in one by one with a shake; the red total counts up. |
| 3 Add them once | Background fades navy → lilac; the flying cards snap into a tidy list one by one; the monthly total counts up. |
| 4 We remind you | Timeline markers (14 / 7 / 3 days) light up in order; the email card slides in. |
| 5 Pinned links | Link cards drop in and a yellow pin "sticks" on each. |
| 6 Card payments | Countdown days roll like an odometer. |
| 7 Calm | Mint tick draws itself; confetti-free, just a soft glow on the button. |

## 7. Help bot ("Subby")

- Floating round Violet button bottom-right with a small face icon; on phone it sits above the bottom edge.
- Chat panel: white card, 20px radius, header with bot name "Subby", status dot, and a Fun-mode badge.
- Bot bubbles: Lilac Mist; user bubbles: Violet with white text.
- Personality: **cheeky and funny like Grok**, but always gives the real answer first and never insults the user.
- Input row: text field + **mic button** (hold or tap to talk) + send. While listening: big pulsing Violet mic, live waveform, the words appear as they are heard. Bot replies can be **read aloud** (speaker icon, auto-speak toggle).
- Suggested question chips: "How do reminders work?", "Is it free?", "How do I add Netflix?".
- **Hand-off card** when Subby doesn't know: "This one's above my pay grade 😅 — talk to the human:" with two buttons, **Messenger** (`#0084ff`) and **Zalo** (`#0068ff`), plus "Send my question to the owner".

## 8. Stitch generation notes

Keywords: chaos to calm, subscription rush hour, midnight navy, brand-coloured flying cards, motion streaks, lilac mist, violet buttons, mint ticks, rounded cards, Plus Jakarta Sans, playful, friendly.

Component prompts:
- "Rush-hour hero on midnight navy: dozens of tilted subscription cards in real brand colours flying in with motion streaks, coral 'renews in 2 days' badges, a ticker of charges along the bottom, huge white headline."
- "A calm subscriptions list on lilac background: white rounded card, service logo, price, next renewal date, coral tint on rows renewing soon, violet 'Add subscription' button, monthly total in big bold numbers."
- "A help chat panel called Subby: lilac bot bubbles, violet user bubbles, suggested question chips, a mic button with live waveform, and a hand-off card with Messenger and Zalo buttons."

## 9. App shell v3: header, menu, footer, logo (20 Oct 2026)

Ideas taken from the owner's references (`UI-UX idea` folder: floating pill menu,
dark active pill, bottom tab bar with a raised + button). Plain CSS + `static/nav.js`.
Previews: `docs/design/shell-v3-*.png`, `docs/design/logo-v1.png`.

- **Logo / favicon** (`static/favicon.svg`, phone icon `static/icon-192.svg`): violet
  tile (`#8b6dff` to `#4b2fd6`), a white card with a navy stripe and a sun chip
  (subscriptions and bills) and a mint chain link that reads as an **S** (saved links).
- **Header**: logo left; the five main pages in a white pill in the middle, where a
  navy highlight slides (springy easing) to the link you point at and back to the
  current page; right: violet **+ Thêm gói**, VI/EN switch, account chip (avatar
  initial + name) that opens a menu: Settings, Reminders, Admin, Log out.
  Turns glassy with a soft shadow once the page scrolls. No JS: the current link is
  painted navy and the menu still opens (`<details>`).
- **Phone (≤ 960 px)**: the pill menu hides; a white floating **tab bar** at the bottom
  (Overview, Subscriptions, **+**, Bills, Links) with a raised violet + button ringed in
  the page colour, and a dot above the current tab. Calendar moves into the account menu.
- **Footer** (every page except the landing story, which has its own): logo + one line,
  columns App / Account / Help (Ask Subby, source on GitHub), © line. Stays at the bottom
  of short pages.
- **Motion** (one signature move, the rest only answers what you do): when you change
  page, the browser glides the dark menu pill (and the phone tab dot) from the old page's
  link to the new one (cross-document View Transitions; other browsers just change page).
  Pointing at a link slides a soft lilac pill behind it; the account menu pops open; the +
  icon turns. No fade-in on every page. Subby's "need help?" bubble: first page of a visit
  only, never on phones. All motion is off with `prefers-reduced-motion`.
- **Labels** in sentence case (no ALL-CAPS), no "A · B · C" strings.
- **Static files** carry `?v=<last change>` (`app/__init__.py`), because Cloudflare lets
  browsers keep CSS/JS for 4 hours: without it an update showed new pages with old CSS.

- Only one `<a data-nav-target>` per page (the header link): tests rely on it.