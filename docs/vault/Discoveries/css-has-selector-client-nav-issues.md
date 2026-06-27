---
code-refs:
  - anvil/api/static/js/core.js
  - anvil/api/static/css/login.css
  - anvil/api/templates/login.html
created: '2026-06-26'
aliases:
  - CSS Has Selector Client Nav Issues
  - Has Selector Reliability
related:
  - Sessions/2026-06-26-unicorn-login-page-stacking-and-glass
session: 2026-06-26-unicorn-login-page-stacking-and-glass
source: agent
status: draft
tags:
  - type/discovery
  - domain/ui
  - status/draft
title: ':has() Selector Reliability with Client-Side Navigation'
type: discovery
updated: '2026-06-26'
---
## Summary

Using `:has(.login-page)` in CSS selectors to scope login-page-only rules proved unreliable when combined with the app's client-side navigation system (`core.js` `loadContent`). The server-rendered CSS file (`login.css`) persists in `<head>` after navigation because `loadContent` only removes `link[data-nav-css]` elements — it doesn't strip server-rendered stylesheet links. While `:has()` should dynamically re-evaluate when `.login-page` is removed from the DOM (via `currentMain.innerHTML = newMain.innerHTML`), it does not reliably stop matching, causing the login-page CSS rules to leak onto other pages.

## The Fix

Instead of relying on `:has()` dynamic re-evaluation, use a **class-based gate** coordinated across three files:

1. **`login.html`** — Inline script adds `page-login` class to `<html>` when the login page is server-rendered
2. **`login.css`** — All unicorn login-page rules use `html.page-login[data-skin="unicorn"]` selectors
3. **`core.js`** — `loadContent` explicitly strips `page-login` from `<html>` right after the main content swap (step 1a), before any new page scripts execute

This creates an imperative cleanup path that doesn't depend on CSS pseudo-class dynamic re-evaluation.

## Why This Pattern

- **Server-rendered CSS persists**: `loadContent` only removes `link[data-nav-css]` elements. Server-rendered `<link>` tags (from `{% block extra_css %}`) lack this attribute and survive navigation.
- **`:has()` re-evaluation is inconsistent**: Testing showed that `:has(.login-page)` selectors continued to match in some browser/rendering conditions after `.login-page` was removed from the DOM during content swap.
- **Imperative class removal is deterministic**: `classList.remove('page-login')` is a single synchronous DOM call that guarantees the selector stops matching, regardless of browser CSS engine behavior.
- **No style leak**: The `<style>` tag inside `{% block content %}` IS removed during content swap, so inline styles are safe. But external CSS files in `<head>` persist — the class gate prevents them from matching.

## Pattern for Future Page-Specific CSS

When adding CSS that should only apply to a specific page and must not leak after client-side navigation:

```
login.html:        <script>document.documentElement.classList.add('page-X');</script>
login.css / themes: html.page-X[data-skin="..."] .selector { ... }
core.js:            document.documentElement.classList.remove('page-X');  // in loadContent
```

## References

- `anvil/api/static/js/core.js` — `loadContent()` at line 217: class cleanup
- `anvil/api/static/css/login.css` — Lines 150-166: `html.page-login` selectors
- `anvil/api/templates/login.html` — Line 9: class injection
- [[Sessions/2026-06-26-unicorn-login-page-stacking-and-glass]]
