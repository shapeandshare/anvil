---
title: Theme Removal Pattern — Complete Excision from the Theme Engine
type: discovery
status: draft
source: agent
related:
  - '[[Reference/theme-creation-guide]]'
  - '[[Decisions/ADR-031-behavioral-theme-engine]]'
  - '[[Discoveries/signal-gated-decorations-invisible-at-rest]]'
code-refs:
  - anvil/api/static/js/theme/theme-manager.js
  - anvil/api/templates/base.html
  - tests/system/test_theme_engine.py
  - anvil/api/static/js/theme/theme-registry.js
session: 2026-06-26-vinyl-theme-removal
created: '2026-06-26'
updated: '2026-06-26'
summary: >-
  Removing the vinyl theme revealed the five-layer surface area every behavioral
  theme touches: CSS file, JS file, base.html script tag, theme-manager excited
  overrides, and test fixture list. Each layer must be cleared for a complete
  excision.
tags:
  - type/discovery
  - domain/ui
  - status/draft
aliases:
  - Theme Removal Pattern
---
# Theme Removal Pattern — Complete Excision from the Theme Engine

The vinyl theme was removed from the codebase. Its excision surfaced the full surface area a theme touches when integrated into the engine: theme-specific CSS/JS files, registration, page-level script loading, cross-theme CSS overrides in `theme-manager.js`, and test fixture lists. A theme removal is not complete until every layer is cleared.

## What Was Found

A behavioral theme in the anvil theme engine touches five distinct layers. Removing one requires touching all five:

1. **Theme CSS file** — `anvil/api/static/css/themes/vinyl.css` (design tokens, decorative pseudo-elements, state-driven animations, reduced-motion overrides)
2. **Theme JS file** — `anvil/api/static/js/themes/vinyl.js` (theme registration via `window.ThemeRegistry.register()`, signal bus `mapping()` for DOM injection and CSS variable publishing, teardown function)
3. **Page script loading** — `anvil/api/templates/base.html` (every theme JS is a separate `<script src="...">` tag in the HTML head's script bundle — vinyl was the last of 27 theme scripts)
4. **Cross-theme CSS overrides** — `theme-manager.js` function `replaceExcitedStyle()` had hardcoded `[data-skin="vinyl"]` selectors for animation-duration/timing overrides in the Excited mode
5. **Test fixture list** — `tests/system/test_theme_engine.py` `THEME_IDS` constant enumerates every theme name; `THEME_CSS_LAYERS` is derived from this list

## Implications for Future Theme Operations

- Adding or removing a theme is never a single-file operation. The task checklist is: add/remove CSS → add/remove JS → update `base.html` script bundle → update `replaceExcitedStyle()` in `theme-manager.js` if the theme has animated elements → update `THEME_IDS` in the test file.
- The `replaceExcitedStyle()` function is a manual maintenance burden — every theme with `data-skin="..."` selectors in animated elements requires a corresponding override line there. A potential refactor would be to have each theme declare its own excited-mode overrides (e.g., a `mapping.excitedOverride` property or a CSS custom property approach) instead of centralizing them in the manager.
- The test fixture is derived from the `THEME_IDS` list, which drives both JS asset resolution and CSS layer validation. Removing an entry automatically removes it from all derived lists, which is correct by construction.
- Theme JS files are loaded unconditionally in `base.html` — there is no lazy loading. Every theme's `register()` call runs on every page load regardless of which theme is active. This is fine for the current set (~27 small IIFEs) but would be worth revisiting if the theme count grows significantly.

## References

- `anvil/api/templates/base.html` — theme script bundle (line 139 removed)
- `anvil/api/static/js/theme/theme-manager.js` — `replaceExcitedStyle()` at line 157 (vinyl selectors removed)
- `anvil/api/static/css/themes/vinyl.css` — deleted (417 lines)
- `anvil/api/static/js/themes/vinyl.js` — deleted (199 lines)
- `tests/system/test_theme_engine.py` — `THEME_IDS` list (line 48 removed)
