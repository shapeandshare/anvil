---
title: Navigation Chips Need Button Visual Weight
type: discovery
source: agent
code-refs:
  - anvil/api/static/css/archetypes.css
  - anvil/api/static/css/components.css
  - anvil/api/templates/partials/related-lessons.html
tags:
  - type/discovery
  - domain/ui
created: '2026-07-19'
updated: '2026-07-19'
aliases:
  - Navigation Chips Need Button Visual Weight
---

# Navigation Chips Need Button Visual Weight

**Found**: 2026-07-19
**Context**: User feedback reported that `.related-lessons__chip` links "have hyperlink text and not fully button like buttons." Investigation revealed that the muted `--text-secondary` color + outlined border treatment made navigation chips visually underwhelming.

## The Tension

UX rules (line 77) mandate `<a>` for navigation — the chip is semantically correct. But users expect visual button weight for interactive elements. The design system's button convention (DESIGN.md line 454: "Do use filled (not outlined) buttons") was being violated by the chip's outlined/muted style.

## The Fix Applied

Changed `.related-lessons__chip` in `archetypes.css` (PR #407):
- Muted outlined pill → filled accent button
- `background: var(--surface-2)` → `background: var(--accent)`
- `color: var(--text-secondary)` → `color: #fff`
- `border: 1px solid var(--border)` → `border: none`
- `border-radius: var(--radius-xl)` (30px) → `var(--radius-lg)` (20px)
- Added `min-height: 32px`, `font-weight: 500`, `cursor: pointer`
- Hover: `filter: brightness(1.15)` matching `.btn-primary:hover`
- Active: `transform: scale(0.97)` matching DESIGN.md button press

## Broader Pattern

The same muted-chip pattern exists on other elements:
- `.tag` in `components.css` — uses `--text-secondary`, `--surface-2`, hover-fill
- `.example-prompt` in `components.css` — uses `--text-secondary`, `--surface-2`, accent-fill on hover
- `.sampling-hero-chip` in `components.css` — uses `--text-tertiary`, `--surface-2`

These may need similar treatment if users report the same "not button-like" feedback.

## References
- `anvil/api/static/css/archetypes.css` — chip rules around line 2226
- `anvil/api/static/css/components.css` — `.tag` (line 304), `.example-prompt` (line 162)
- `anvil/api/templates/partials/related-lessons.html` — shared partial on 11 pages
- [[Sessions/2026-07-19-feedback-ui-fixes]]