---
title: Vinyl Theme Removal — 2026-06-26
type: session-log
status: draft
source: agent
tags:
  - domain/ui
  - type/session-log
created: '2026-06-26'
updated: '2026-06-26'
aliases:
  - Vinyl Theme Removal
---
# Vinyl Theme Removal — 2026-06-26

**Date**: 2026-06-26
**Context**: User requested removing the vinyl theme (warm analog tape-deck with spinning reels and VU meters) from the codebase. The theme had CSS design tokens, DOM-injected tape-deck elements, signal bus mapping for reel speed/VU needle deflection, and was registered as a first-class theme in the engine.

## What Was Done

### 1. Deleted theme asset files

- `anvil/api/static/css/themes/vinyl.css` — 417 lines: design tokens (dark + light modes), `.app-main::before` warm glow, `.vinyl-tape-deck` container, `.vinyl-reel` spinning reels, `.vinyl-tape-band`, `.vinyl-vu` meters with `.vinyl-vu-needle`, state animations (`data-vinyl-state="peak"` and `data-vinyl-state="diverged"`), legible mode, and `prefers-reduced-motion` overrides.
- `anvil/api/static/js/themes/vinyl.js` — 199 lines: theme registration (`id: 'vinyl'`), `vinylMapping()` signal bus handler publishing `--rpm`, `--level`, `--warmth` CSS vars, DOM injection of `.vinyl-tape-deck` via `buildTapeDeck()`, milestone/complete/divergence signal handlers, and teardown cleaning up all `data-vinyl-*` attributes and CSS vars.

### 2. Removed script tag from base.html

`anvil/api/templates/base.html` — removed `<script src="/static/js/themes/vinyl.js"></script>` from the theme script bundle (was the last of 27 theme scripts).

### 3. Removed CSS overrides from theme-manager.js

`anvil/api/static/js/theme/theme-manager.js` `replaceExcitedStyle()` — removed two hardcoded `[data-skin="vinyl"]` selectors: `.vinyl-reel` animation-duration override and `.vinyl-vu-needle` transition-duration override.

### 4. Removed from test fixture list

`tests/system/test_theme_engine.py` — removed `"vinyl"` from `THEME_IDS` constant. The `THEME_CSS_LAYERS` and `THEME_REGISTRATIONS` lists are derived from this, so the removal propagated correctly.

### 5. Removed from reference guide

`docs/vault/Reference/theme-creation-guide.md` — removed the vinyl row from the theme registry table.

## Files Changed

```
Deleted:
  anvil/api/static/css/themes/vinyl.css
  anvil/api/static/js/themes/vinyl.js

Modified:
  anvil/api/templates/base.html                     (removed vinyl.js script tag)
  anvil/api/static/js/theme/theme-manager.js        (removed vinyl selectors from replaceExcitedStyle)
  tests/system/test_theme_engine.py                 (removed "vinyl" from THEME_IDS)
  docs/vault/Reference/theme-creation-guide.md       (removed vinyl table row)
```

## Validation

- `lsp_diagnostics` clean on all modified files
- 58/58 local theme-engine tests pass (0 new failures)
- 1 pre-existing test failure (`test_effect_controls_in_picker` — unrelated, effect controls are JS-injected and not in the server-rendered HTML)
- 26 pre-existing Docker container test failures (`service "anvil" is not running`)
- grep for `vinyl` in `anvil/` package code returns only one false-positive comment in `particle-system.js` line 1302 (`// ── Spin Effect (rotating vinyl particles) ──` — describes a particle visual, not the theme)
- grep for `vinyl` in `tests/` returns zero matches

## Notes / Follow-ups

- The `replaceExcitedStyle()` function in `theme-manager.js` centralizes animation-speed overrides for every theme. Each theme with `data-skin` selectors in animated elements needs a manual entry there — a maintenance burden that grows linearly with the theme count. A cleaner pattern would be to let each theme declare its own excited-mode behavior.
- The vinyl theme's tape-deck injection (`buildTapeDeck()` in `vinylMapping()`) was the canonical example for the [[Discoveries/signal-gated-decorations-invisible-at-rest]] discovery note, since its primary visuals only appeared during an active training session. That note still references vinyl as a case study.
- Theme removal is never a single-file operation. See [[Discoveries/theme-removal-pattern-complete-excision]] for the full five-layer checklist.

## Wikilinks

- [[Discoveries/theme-removal-pattern-complete-excision]]
- [[Discoveries/signal-gated-decorations-invisible-at-rest]]
- [[Reference/theme-creation-guide]]
- [[Reference/theme-picker-grid-keyboard-nav]]
- [[Sessions/2026-06-20-vinyl-theme-reroll-tape-deck]]
- [[Sessions/2026-06-20-nine-new-themes]]
