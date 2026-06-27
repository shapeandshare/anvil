---
created: '2026-06-26'
aliases:
  - Unicorn Login Page Stacking
  - Unicorn Theme Login Glass
related:
  - Reference/theme-creation-guide
source: agent
tags:
  - type/session-log
  - domain/ui
title: 'Unicorn Theme — Login Page Stacking, Training Gating & Glass Content Blocks'
type: session-log
updated: '2026-06-26'
---
# Session: Unicorn Theme — Login Page Stacking, Training Gating & Glass Content Blocks

**Date**: 2026-06-26
**Status**: Draft

## Summary

Fixed the unicorn theme's body-level overlays stacking above the login panel and regular page content. Implemented a class-based CSS gating mechanism (`html.page-login`) coordinated across three files to avoid `:has()` selector persistence issues during client-side navigation. Gated unicorn sprite/rainbow spawning in `unicornMapping` behind `bus.session()` so sprites only appear during active training. Made hero cards glass/transparent on the unicorn theme using `--glass-bg` and `backdrop-filter`.

## Changes

### `anvil/api/static/css/themes/unicorn.css` — Ambient z-index, glass hero cards
- `.unicorn-ambient` z-index lowered from 4 to 1 (behind `.app-shell` at z-index 2)
- Added `.hero-card` glass override: `background: var(--glass-bg); backdrop-filter: var(--glass-blur);`

### `anvil/api/static/css/login.css` — Unicorn login page overrides
- Added `html.page-login[data-skin="unicorn"]` rules:
  - `.app-shell { z-index: 6; }` — stacks above overlays
  - `.app-shell ~ .unicorn-ambient { filter: brightness(2); }`
  - `.app-shell ~ .unicorn-overlay { filter: brightness(2); }`
  - `.app-main::before { opacity: 0.35; }` — bright sparkle overlay
  - `.unicorn-floater, .unicorn-rainbow { display: none; }` — no sprites on login

### `anvil/api/templates/login.html` — page-login class
- Added inline script: `document.documentElement.classList.add('page-login')`
- Removed inline `<style>` block (moved to login.css)

### `anvil/api/static/js/core.js` — Class cleanup on navigation
- Added `document.documentElement.classList.remove('page-login')` in `loadContent` after main content swap, before script execution

### `anvil/api/static/js/themes/unicorn.js` — Training-gated sprite spawning
- Added `hasSession = !!bus.session()` in `unicornMapping`
- Gated `spawnUnicorn()`, `spawnRainbow()`, `burst()`, and initial spawn on `hasSession`
- Clouds are NOT gated — they always spawn

### `anvil/api/static/js/theme/theme-manager.js` — Reverted (no change)
- Original guard `!bus.session() && excitedPref === 'auto'` preserved
- Gating moved into `unicornMapping` where `bus` is available

## Stacking Architecture

| Layer | Login page | Non-login idle | Non-login training |
|-------|-----------|----------------|---------------------|
| z-index 6 | `.app-shell` | — | — |
| z-index 5 | `.unicorn-overlay` (behind app-shell) | — | `.unicorn-overlay` (sprites float) |
| z-index 2 | — | `.app-shell` | `.app-shell` |
| z-index 1 | `.unicorn-ambient` | `.unicorn-ambient` | `.unicorn-ambient` |

## Key Discoveries

### `:has()` reliability with client-side navigation
Using `:has(.login-page)` in CSS selectors caused issues because login.css persisted in `<head>` after navigation (server-rendered CSS is not removed by `loadContent`'s `link[data-nav-css]` cleanup). While `:has()` should re-evaluate dynamically, it proved unreliable. Switched to a class-based approach: login.html sets `page-login` on `<html>`, core.js strips it on every client-side navigation.

### Training session gating at the mapping level
Rather than modifying the complex `bindMapping` guard logic (which has multiple code paths for excitedPref), gating sprite spawning inside `unicornMapping` via `bus.session()` is simpler. The `bus` object is available as a parameter to the mapping function, so `hasSession` can be checked directly at the spawn level.

### z-index with body-level overlays
The unicorn theme appends `.unicorn-overlay` and `.unicorn-ambient` directly to `document.body` (not inside `.app-shell`). This means they participate in the root stacking context alongside `.app-shell`. At z-index 4-5 they paint above `.app-shell` (z-index 2). Lowering ambient to z-index 1 keeps clouds behind content while the overlay at 5 keeps sprites visible during training.

## Files Modified

```
Modified:
  anvil/api/static/css/themes/unicorn.css       — Ambient z-index: 4→1, glass hero cards
  anvil/api/static/css/login.css                  — html.page-login unicorn overrides
  anvil/api/templates/login.html                  — page-login class script, removed <style>
  anvil/api/static/js/core.js                     — page-login cleanup in loadContent
  anvil/api/static/js/themes/unicorn.js           — hasSession gating for sprites/rainbows
  anvil/api/static/js/theme/theme-manager.js      — Reverted to original (no functional change)
```

## Wikilinks

- [[Discoveries/css-has-selector-client-nav-issues]]
- [[Reference/theme-creation-guide]]
