# Narrative scrollytelling patterns

## Story shapes

| Shape | Best for | Structure |
| --- | --- | --- |
| Step-and-stage | A sequence of claims changing one shared diagram | Flowing semantic steps beside one sticky, normally non-focusable stage |
| Chapter reveal | An essay, method or timeline where each section can stand alone | Normal-flow sections with discrete active-state enhancement |
| Progressive diagram | A relationship whose intermediate visual states are meaningful | Semantic step captions plus view/scroll progress driving the visual only |
| Before-to-after | One transformation with a few causal beats | Ordered explanation with explicit start/end states and a static comparison fallback |

Do not choose scrollytelling when ordinary headings, an ordered list, tabs or a
short video explain the material more directly. Long prose stays in document
flow; the sticky stage supports it rather than becoming a second reading order.

## Driver choice

- `discrete-intersection`: default for prose. Activate once a stable part of a
  step crosses a documented threshold; tolerate reverse and fast scrolling.
- `view-progress`: use when the visibility of one element naturally controls a
  visual reveal. Provide a discrete/static fallback.
- `scroll-progress`: reserve for a true continuum. Never put a required fact at
  an exact fraction or require the user to scrub precisely.

Prefer `IntersectionObserver` for discrete activation. High-frequency scroll
handlers do not perform layout reads and DOM writes on every event. Native CSS
scroll/view timelines may enhance supported browsers; feature detection selects
the fallback elsewhere.

## Sticky stages and navigation

Keep the semantic story in normal flow. A sticky stage receives an explicit
start and end, reserves its layout space, and releases before it collides with
the next section or footer. Interactive controls belong in the steps unless a
tested focus strategy proves the sticky layer remains logical and unobscured.

Chapter anchors are real URLs. Previous/next controls supplement native scroll;
they do not replace it. A skip-story control reaches the equivalent linear
content or the section after the enhanced narrative.
