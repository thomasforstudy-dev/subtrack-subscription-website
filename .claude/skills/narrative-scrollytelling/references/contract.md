# Story-map contract

The story map defines canonical content and presentation intent. It is not a
library configuration file; implementation adapters may translate it without
moving essential information into animation-only payloads.

```json
{
  "version": 1,
  "id": "method-story",
  "title": "How the method develops",
  "driver": "discrete-intersection",
  "steps": [
    {
      "id": "observe",
      "content": {"heading": "Start from evidence", "contentRef": "#observe-copy"},
      "presentation": {"stageRef": "#method-map", "visualState": "observe", "transitionIntent": "focus-observe"}
    }
  ],
  "scroll": {"mode": "native", "stickyStage": true, "snap": "none", "programmaticFocus": false},
  "navigation": {"anchors": true, "previousNext": true, "skipStory": true},
  "fallback": {"unsupportedDriver": "discrete", "noJs": "linear-document", "reducedMotion": "discrete-static-states", "noMotion": "linear-document"}
}
```

## Stable invariants

- `version` is `1`; `steps` is non-empty; every step id is non-empty and unique.
- Every `next`, `previous`, transition target and navigation marker resolves to
  a declared step. Cycles require an explicitly non-linear story mode.
- Every step has semantic `content` or a `contentRef`. A heading, instruction or
  required fact cannot exist only in `presentation`, canvas frames, keyframes,
  sound or transition labels.
- `driver` is `discrete-intersection`, `view-progress`, or `scroll-progress`.
  Feature-dependent and progress drivers declare an unsupported-driver fallback.
- `scroll.mode` is `native`; scroll does not programmatically move focus.
- `snap` is `none` or `proximity`. `mandatory` carries an `auditedOverride`
  covering zoom, reflow, large text, short viewports and reachability.
- A sticky interactive layer declares its focus strategy and safe offsets. The
  default sticky stage is non-focusable.
- Fallbacks expose the complete ordered content for no JavaScript, reduced
  motion and no motion.
- Passive step entry has no sound hook. Explicit navigation may reference a
  separate micro-interaction; the story map never owns audio playback.

## Accessibility basis

- WCAG 2.2 SC 1.3.2: a meaningful reading sequence is programmatically
  determinable.
- SC 2.4.3, 2.1.2 and 2.4.11: focus order remains operable, untrapped and not
  obscured by authored sticky content.
- SC 2.2.2: automatically started movement lasting more than five seconds and
  presented alongside other content has pause, stop or hide controls. The
  five-second condition is not a blanket maximum for every transition.
- SC 2.3.3 informs the reduced-motion policy but is Level AAA. Humane adopts a
  stronger product policy without presenting it as WCAG AA.
- CSS Scroll Snap warns that mandatory snap positions can make intervening
  content unreachable. `mandatory` is therefore an audited exception, not an
  automatic claim of WCAG failure.
