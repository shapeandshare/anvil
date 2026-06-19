---
aliases:
  - CSS Tooltip Viewport Overflow
code-refs:
  - anvil/api/static/css/components.css
  - anvil/api/static/js/core.js
created: '2026-06-18'
related:
  - '[[Reference/overflow-clipping-pattern]]'
session: 2026-06-18-tooltip-viewport-overflow
source: agent
summary: >-
  CSS-only tooltips with left:50%/translateX(-50%) overflow the viewport at
  screen edges. Fixed via JS-measured --tooltip-shift/--tooltip-arrow-x CSS
  variable nudging.
tags:
  - type/discovery
  - domain/ui
  - status/draft
title: CSS Tooltip Viewport Overflow
type: discovery
updated: '2026-06-18'
---
CSS-only tooltip centering (`left: 50%; transform: translateX(-50%)`) overflows the viewport when the trigger element is near the right or left edge. The `.tooltip-trigger` / `.tooltip-content` pattern uses `position: relative` on the trigger and `position: absolute` on the content, centering it above the trigger. This works well for centrally-positioned triggers but fails at viewport boundaries because CSS has no way to detect viewport overflow for dynamic positioning.

The fix uses JS to measure the tooltip's rendered bounding rect on mouseenter (after CSS `:hover` makes it visible), then applies `--tooltip-shift` and `--tooltip-arrow-x` CSS custom properties to nudge the tooltip back into view while keeping the `::after` caret aligned with the trigger. The variables are applied via `style.setProperty` in a `requestAnimationFrame` callback, ensuring no flash (the paint happens after the correction).

Two UI overflow patterns now documented in the vault: [[Reference/overflow-clipping-pattern]] (parent `overflow: hidden` clipping normal-flow children) and this one (CSS-only tooltips overflowing viewport boundaries). They share the same root cause — CSS alone cannot detect container/viewport overflow — but have different remediation strategies.

## References

- `anvil/api/static/css/components.css` — `.tooltip-content` and `.tooltip-content::after` rules
- `anvil/api/static/js/core.js` — `initTooltips()` function
- `anvil/api/templates/archetypes/training.html` — primary consumer of the tooltip pattern
