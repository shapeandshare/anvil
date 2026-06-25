---
title: Static CSS/JS Has No Cache-Busting
type: discovery
tags:
  - type/discovery
  - domain/ui
  - status/draft
created: '2026-06-19'
updated: '2026-06-20'
aliases:
  - Static CSS No Cache Busting
  - CSS Cache Busting Gap
source: agent
session: 2026-06-20-hyperspace-theme-warp-effects
summary: >-
  Static CSS/JS <link>/<script> tags in base.html have no version query string
  and StaticFiles is mounted with default caching, so shipped CSS fixes can
  appear not to take effect until a hard refresh. Explains recurring 'I fixed it
  but it still looks broken' UI reports.
code-refs:
  - anvil/api/templates/base.html
  - anvil/api/app.py
related:
  - '[[Discoveries/playground-css-class-mismatch]]'
status: reviewed
---
All stylesheet and theme-layer asset references are version-less:

- `anvil/api/templates/base.html:9-13` — `tokens.css`, `base.css`, `utilities.css`, `components.css`, `code.css` are linked with bare `/static/css/<name>.css` hrefs (no `?v=` query).
- `anvil/api/templates/base.html:40` — the dynamically injected theme-layer `<link>` uses `'/static/css/themes/' + themeId + '.css'`, also version-less.
- `anvil/api/app.py:191` — `app.mount("/static", StaticFiles(...))` uses Starlette's default `StaticFiles`, which serves `ETag` + `Last-Modified` but no explicit `Cache-Control: no-cache`. Browsers frequently serve the previously cached CSS without revalidating.

## Consequence

A CSS-only fix that is correct in source can appear to have no effect in the browser until the user does a hard refresh (cache-disabled reload). This produces a recurring failure mode: a UI bug is "fixed" in a commit, but the reporter still sees the old behavior because their browser holds a stale `base.css`.

Concrete instance: the theme-picker transparency bug was fixed in commit `e68da70` (glass `--glass-bg` + `backdrop-filter` → solid `var(--surface)`), yet the transparent-panel symptom was reported again afterward. The source was already correct; the most probable cause was a stale cached `base.css`. See [[Sessions/2026-06-19-theme-picker-transparency-recheck]].

## Remediation (applied 2026-06-20)

**Option 1 was implemented** — version query parameter threaded into both the inline theme-loader script and the JS `ensureLayer()` function:

- `anvil/api/templates/base.html` — Inline script now sets `window.ANVIL_VERSION = '{{ version }}'` on page load and appends `?v=` to the theme-layer `<link>` href.
- `anvil/api/static/js/theme/theme-manager.js` — `ensureLayer()` now checks `window.ANVIL_VERSION` and appends it as a cache-busting query param when setting the CSS `<link>` href.
- `base.css` already had `?v={{ version }}`; the gap was the dynamically loaded theme CSS.

See [[Sessions/2026-06-20-hyperspace-theme-warp-effects]].

## References
- [[Discoveries/Discoveries|Discoveries]]

- `anvil/api/templates/base.html` — version-less `<link>` tags and inline theme-layer loader
- `anvil/api/app.py` — `StaticFiles` mount with default caching
