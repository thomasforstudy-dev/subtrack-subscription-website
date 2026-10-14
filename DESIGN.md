# SubTrack Design System

Source of truth for how SubTrack looks. Extracted from `app/static/style.css`.
Every new screen (Stitch designs, templates, CSS) should match this file.

## 1. Visual theme and atmosphere

Calm, plain and trustworthy. A near-white page (`#fafafa`) with white panels,
thin grey borders and **black** as the only strong colour. No gradients, no
shadows, no decoration: the content (service names, prices, dates) is the
design. Neutral temperature, light mode only, low density, generous whitespace.

Mood words: calm, clean, quiet, honest, utilitarian, "a tidy paper ledger".

## 2. Color palette and roles

| Name | Hex | Role |
|---|---|---|
| Ink Black (`--text`) | `#1a1a1a` | Body text, headings, **primary buttons**, active chips |
| Slate Grey (`--muted`) | `#5c5c5c` | Secondary text, notes, captions |
| Hairline Grey (`--line`) | `#d9d9d9` | Every border and table divider |
| Paper (`--bg`) | `#fafafa` | Page background |
| Pure White | `#ffffff` | Top bar, tables, cards, inputs, link lists |
| Due Blush (`--due`) | `#fff4f0` | Row highlight for a subscription that renews soon |
| Pin Cream | `#fffbea` | Background of a pinned link |
| Lookup Grey | `#f3f3f3` | Field shown while a link title is loading |

Rules:
- Black is the only accent. Do not add blue/purple/gradient brand colours.
- "Urgent" is shown with Due Blush, never with saturated red fills.
- Text on white or Paper is always Ink Black or Slate Grey (passes contrast).

*Landing page only (new, not yet in `style.css`):* one small status accent may
be used sparingly for reminder states: Amber `#b45309` (renews soon) and
Alert Red `#b91c1c` (unexpected charge). Text or thin borders only, no big fills.

## 3. Typography rules

- Family: `Segoe UI, system-ui, sans-serif`. No other font.
- Body: 16px (1rem), weight 400, line-height 1.45.
- Page title (`h1`): 24px (1.5rem), margin-bottom 1rem.
- Brand name: weight 650.
- Link title / emphasis: weight 600.
- Form label: 14.4px (0.9rem). Chip and small text: 13.6px (0.85rem).
- Muted notes: Slate Grey, 14.4px.
- Numbers (prices, dates) use the same font, never monospace.

*Landing page only:* big chapter headlines may scale up to 48px (desktop) /
32px (phone), weight 650, line-height 1.1. Same font.

## 4. Component stylings

- **Top bar:** white, 1px Hairline bottom border, padding 12px 20px, brand left, links right, gap 1rem.
- **Primary button:** Ink Black fill, white text, **no border, square corners**, padding 8px 14px, width fits content.
- **Text button (`.inline`):** transparent, underlined, no padding. Used for "Delete" style actions.
- **Input / select / textarea:** inherits font, padding 7px 8px, thin border, square corners. Labels sit above, gap 4px.
- **Table:** white, full width, 1px Hairline row dividers, cell padding 9px 10px, left aligned. A due row uses Due Blush.
- **Chip:** pill (999px radius), 1px Hairline border, white fill, 13.6px text. Active chip: Ink Black fill, white text.
- **Link list:** white box with 1px Hairline border, rows separated by Hairline, row padding 10px 12px. Pinned row uses Pin Cream.
- **Flash message:** white box, 1px Hairline border, padding 10px 13px, friendly one-liner.
- **Landing-page cards (new):** white, 1px Hairline border, 8px radius, no shadow (or one very soft shadow for floating cards in the hero).

## 5. Layout principles

- Content column: max width 52rem (832px), centred, padding 24px 20px 48px.
- Forms: single column, max 24rem, gap 12px. Quick-add rows may span full width.
- Base spacing unit: 4px (multiples of 4: 4, 8, 12, 16, 20, 24, 48).
- Breakpoint: 640px. Below it, grids become one column and row actions wrap under the text.
- Must work at **390px** phone width with no sideways scrolling.
- Screen sizes the owner designs for: laptop 16:10 (1440x900), desktop 16:9 (1920x1080), phone 9:16 (390x844).

*Landing page:* full-width chapters, each about one screen tall; text and visual
sit side by side on laptop/desktop and stack (text first) on phone. A thin chapter
progress rail on the right edge on laptop/desktop, a top progress bar on phone.

## 6. Stitch generation notes

Keywords: calm, minimal, near-white paper, hairline borders, black buttons,
Segoe UI, whitespace, no gradients, no heavy shadows, plain and honest.

Palette to name in prompts: Ink Black #1a1a1a, Slate Grey #5c5c5c, Hairline Grey
#d9d9d9, Paper #fafafa, White #ffffff, Due Blush #fff4f0, Pin Cream #fffbea.

Component prompts:
- "A subscriptions table on a white panel with hairline row dividers: service, price, next renewal date. Rows renewing within 7 days have a pale blush background. A black square 'Add subscription' button sits above the table."
- "A pinned links list in a white bordered box: each row has a bold page title, a small grey note, and Open / Edit actions. Pinned rows have a pale cream background. Filter chips (pill shaped, black when active) sit above."
- "A simple sign-up form, single column, 24rem wide, labels above fields, one black 'Sign up' button, friendly error message in a white bordered box."
