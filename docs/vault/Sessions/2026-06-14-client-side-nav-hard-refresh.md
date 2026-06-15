---
title: Client-Side Navigation Hard Refresh Fix
type: session-log
tags:
  - type/session-log
  - domain/frontend
created: '2026-06-14'
---
## Summary
Diagnosed and fixed a hard-refresh issue on `/v1/operations-page` (and all hero-page navigation). The client-side navigation interceptor in `core.js` only matched `.tab-item` elements (nav bar links). Hero-page navigation links (`.hero-card`, `.hero-cta`, `.hero-secondary`) were not intercepted, causing full page loads instead of AJAX content swaps.

## Files changed
- `anvil/api/static/js/core.js` — Extended click interceptor selector to include `.hero-card, .hero-cta, .hero-secondary`

## Root cause
The `loadContent()` function in `core.js` provides client-side navigation by intercepting link clicks, fetching the target page via AJAX, and swapping `<main>` content. However, the click handler only matched `.tab-item`:

```js
var tab = e.target.closest('.tab-item');
```

All 8 navigation links on the hero page (`archetypes/hero.html`) use `.hero-card` (7 links) or `.hero-secondary` (1 link), which bypassed the interceptor entirely:

```html
<a href="/v1/operations-page" class="hero-card" style="--i: 6">Ops</a>
```

Clicking any hero-page navigation link triggered a full page load (hard refresh).

## Fix
Extended the selector to match all navigation-related classes:

```js
var link = e.target.closest('.tab-item, .hero-card, .hero-cta, .hero-secondary');
```

## Key decisions
- The existing safety checks (skip external URLs with `:`, skip fragment-only `#` links) continue to apply to hero-page links
- No changes needed to `loadContent`'s error fallback (`window.location.href = url`) — fetch failures still fall back to hard refresh, which is the correct degradation behavior

## Discovery
- The client-side nav router in core.js uses a whitelist-based approach (opt-in selectors) rather than intercepting all internal `<a>` tags. This means any new page navigation element added to templates must be added to this whitelist or it will hard-refresh.
