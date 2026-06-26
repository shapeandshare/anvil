---
title: Theme Picker Grid + Keyboard Navigation Pattern
type: reference
status: draft
created: 2026-06-19
updated: 2026-06-19
tags:
  - type/reference
  - domain/ui
aliases:
  - Theme Picker Grid Pattern
  - Picker Keyboard Navigation
related:
  - '[[Reference/theme-creation-guide]]'
---

# Theme Picker Grid + Keyboard Navigation Pattern

A reusable client-side pattern for a **dropdown selector that scales to many
options**, with full keyboard navigation and instant live preview. Built for the
behavioral-theme picker (`theme-manager.js` + `base.css`) once the gallery grew
to 17 themes and the single-column dropdown overflowed the screen. See
[[Sessions/2026-06-19-theme-gallery-expansion]] and
[[Decisions/ADR-031-behavioral-theme-engine]].

## Thesis

When a selector lists more options than fit comfortably in a vertical menu,
switch to a **scrollable 2-D grid** and make exploration cheap: highlighting an
option previews it live (no commit), arrows navigate the grid, Enter commits, and
Escape/click-away reverts to what was selected when the menu opened.

## Structure

```
#theme-picker-menu  (flex column, width 320px, max-width 100vw - space-4)
  ├── .theme-picker__grid      (grid, 2 cols, max-height min(58vh,440px), overflow-y:auto)
  │     └── .theme-picker__item (role=menuitemradio, roving tabindex, name + truncated hint)
  └── .theme-picker__controls  (pinned below the scroll area)
```

## Live preview without persistence

The key move is a `persist` flag on the apply function:

- `apply(id, mode, { persist:false })` — applies attributes / CSS layer / mapping
  but does **not** write `localStorage`. Used for hover/arrow highlight.
- `apply(id, mode, { persist:true })` — commit on Enter/click.
- On open, capture `previewBase = current()`; on Escape, click-away, or
  re-clicking the trigger, re-apply `previewBase` to revert.

This lets a user sweep the entire gallery and see each option full-screen, while
only the chosen one is saved.

## Keyboard contract

| Key | Action |
|---|---|
| ArrowLeft / ArrowRight | move ±1 tile (preview) |
| ArrowUp / ArrowDown | move ± one row (preview) |
| Home / End | jump to first / last (preview) |
| Enter / Space | commit highlighted option, close, focus trigger |
| Escape | cancel, revert to `previewBase`, close, focus trigger |

Column count is derived at runtime from `offsetTop` (`colCount()`) rather than
hard-coded, so Up/Down stay correct if the grid reflows. Active tile uses roving
`tabindex` (`0` active, `-1` others) + `focus()`; `aria-current` marks selection.

## When to use

- A dropdown/menu selector with ~8+ options where a single column overflows.
- Selectors where *previewing* the effect of an option is valuable (themes,
  layouts, palettes).

## When NOT to use

- Small option sets (≤6) — a plain vertical menu is simpler.
- Options whose preview is expensive or destructive (don't live-apply).

## Verification note

Because there is no JS unit-test harness in the repo, this pattern was validated
with a throwaway jsdom script (open → arrow-preview → no-persist → Enter-persist →
Escape/click-away-revert → Home/End) and guarded in CI by
`tests/system/test_theme_engine.py::TestPickerKeyboardNavigation`, which asserts
the shipped `theme-manager.js`/`base.css` contain the arrow handlers,
`previewApply`/`persist:false`/`commitSelection`, and the scrollable grid.
