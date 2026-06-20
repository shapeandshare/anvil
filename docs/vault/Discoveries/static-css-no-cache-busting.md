---
title: Static CSS/JS Has No Cache-Busting
type: discovery
tags:
  - type/discovery
  - domain/ui
  - status/draft
created: '2026-06-19'
updated: '2026-06-19'
aliases:
  - Static CSS No Cache Busting
  - CSS Cache Busting Gap
source: agent
session: 2026-06-19-theme-picker-transparency-recheck
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
---
All stylesheet and theme-layer asset references are version-less:

- `anvil/api/templates/base.html:9-13` — `tokens.css`, `base.css`, `utilities.css`, `components.css`, `code.css` are linked with bare `/static/css/<name>.css` hrefs (no `?v=` query).
- `anvil/api/templates/base.html:40` — the dynamically injected theme-layer `<link>` uses `'/static/css/themes/' + themeId + '.css'`, also version-less.
- `anvil/api/app.py:191` — `app.mount("/static", StaticFiles(...))` uses Starlette's default `StaticFiles`, which serves `ETag` + `Last-Modified` but no explicit `Cache-Control: no-cache`. Browsers frequently serve the previously cached CSS without revalidating.

## Consequence

A CSS-only fix that is correct in source can appear to have no effect in the browser until the user does a hard refresh (cache-disabled reload). This produces a recurring failure mode: a UI bug is "fixed" in a commit, but the reporter still sees the old behavior because their browser holds a stale `base.css`.

Concrete instance: the theme-picker transparency bug was fixed in commit `e68da70` (glass `--glass-bg` + `backdrop-filter` → solid `var(--surface)`), yet the transparent-panel symptom was reported again afterward. The source was already correct; the most probable cause was a stale cached `base.css`. See [[Sessions/2026-06-19-theme-picker-transparency-recheck]].

## Remediation options (not yet applied)

1. Append a cache-busting query string keyed on app version / build hash to every static asset href (e.g. `/static/css/base.css?v={{ app_version }}`), including the JS-built theme-layer link.
2. Configure `StaticFiles` (or a middleware) to send short-lived / revalidating `Cache-Control` headers for CSS/JS during the current single-page-reload UX.

Option 1 is the standard fix and the least surprising; it requires threading the version into the Jinja2 context and into the inline theme-loader script in `base.html`.

## References

- `anvil/api/templates/base.html` — version-less `<link>` tags and inline theme-layer loader
- `anvil/api/app.py` — `StaticFiles` mount with default caching
