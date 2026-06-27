---
aliases:
  - Hyperspace Surface Rush Overlaps Login Page
code-refs:
  - anvil/api/static/css/login.css
  - anvil/api/static/css/themes/hyperspace.css
  - anvil/api/templates/login.html
created: '2026-06-26'
related:
  - '[[Discoveries/isolation-isolate-stacking-context-paint-order]]'
  - '[[Discoveries/nav-bar-z-index-positioned-content-stacking]]'
session: 2026-06-26-hyperspace-surface-rush-login-stacking-fix
source: agent
summary: >-
  Hyperspace theme's .app-main::after (surface rush) renders on top of the login
  card because position:fixed; z-index:0 on a parent with z-index:auto paints
  after child content. Fixed by suppressing the pseudo-elements when .login-page
  is present, following the grid theme pattern.
tags:
  - type/discovery
  - domain/ui
  - status/draft
title: Hyperspace Surface Rush Overlaps Login Page
type: discovery
updated: '2026-06-26'
---
The hyperspace theme's `::after` pseudo-element on `.app-main` paints **after** the element's child content in the CSS stacking context. Since `.app-main` has `position: relative; z-index: auto` (no stacking context), its `::after` participates in `.app-shell`'s stacking context and paints at `z-index: 0` — but **after** all children of `.app-main`, including the `.login-card`.

The same-pattern fix was already applied to the grid theme in `login.css:124-130`. Adding the hyperspace selectors to the same rule hides `.app-main::before` and `::after` when `.login-page` is present.

**Root cause:** A `position: fixed; z-index: 0` pseudo-element on a parent that does NOT establish a stacking context (i.e. `z-index: auto`) will paint after all of that parent's child content because `::after` is generated as the last child of the element. It is sibling to the content, not layered behind it. This is the same class of stacking-context subtlety as `[[Discoveries/isolation-isolate-stacking-context-paint-order]]` and `[[Discoveries/nav-bar-z-index-positioned-content-stacking]]`.

**Fix:** Add `[data-skin="hyperspace"] .app-main:has(.login-page)::after, [data-skin="hyperspace"] .app-main:has(.login-page)::before { display: none; }` to `login.css`.

## References
- [[Discoveries/Discoveries]]
- `anvil/api/static/css/login.css` — theme override rules
- `anvil/api/static/css/themes/hyperspace.css` — `.app-main::after` (surface rush), `.app-main::before` (starfield)
- `anvil/api/templates/login.html` — `.login-page` inside `.app-main`
- [[Sessions/2026-06-26-hyperspace-surface-rush-login-stacking-fix]]
