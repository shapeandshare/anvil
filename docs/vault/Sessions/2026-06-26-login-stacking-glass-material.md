---
title: 'Session: Login Card Stacking & Glass Material'
type: session-log
tags:
  - type/session-log
  - domain/ui
created: '2026-06-26'
updated: '2026-06-26'
source: agent
aliases:
  - 2026-06-26-login-stacking-glass-material
---
# Session: Login Card Stacking & Glass Material

**Date**: 2026-06-26
**Status**: Completed

## Summary

Fixed the login panel to sit above theme particle/texture effects (loom, ash) while matching the translucent glass material used by hero page content blocks. Also fixed footer theme variable issues and stacking context.

## What Changed

### 1. Login page stacking context (`login.css`)

Added `position: relative; z-index: 2` to `.login-page`. Theme effects (loom thread particles, ash soot, and most themes' `::before`/`::after` pseudo-elements) use `position: fixed` with `z-index: 0-1` in the root stacking context. Since positioned elements paint after non-positioned flow content, the theme effects rendered ON TOP of the login card. The fix lifts `.login-page` above all fixed-position theme effects.

Affects: `anvil/api/static/css/login.css`

### 2. Login card glass material (`login.css`)

Swapped the login card's background from solid `--surface` to the design system's glass tokens:

- `background: var(--glass-bg)` — semi-transparent per-theme glass background (ash: `rgba(26, 22, 18, 0.85)`)
- `border: 1px solid var(--glass-border)` — matching frosted border
- `backdrop-filter: var(--glass-blur)` — frosted glass blur effect

The hero page uses `background: var(--surface)` which is opaque, but the soot (ash `::after`, z-index: 1) renders on top of hero cards making them appear hazy. Without the same soot covering the login card (now elevated at z-index: 2), the solid surface background looked disconnected. The glass tokens give the login card a similar translucent feel.

Affects: `anvil/api/static/css/login.css`

### 3. Footer font-size token fix (`base.css`, `base.html`)

The footer used `font-size: var(--font-size-xs)` which was never defined in `tokens.css` or any theme — the token `--font-size-xs` didn't exist in the design system. Changed to `font-size: var(--text-footnote)` which is the correct semantic token from the fluid type scale.

Affects:
- `anvil/api/static/css/base.css` — `.site-footer` CSS class
- `anvil/api/templates/base.html` — `<footer>` inline style

### 4. Footer stacking context (`base.css`)

Added `position: relative; z-index: 2` to `.site-footer` — same pattern as the login page fix. Theme effects at `z-index: 0-1` (including ash soot `::after` at z-index: 1) were painting on top of the footer text.

Affects: `anvil/api/static/css/base.css`

### 5. Added `--border-subtle` token (`tokens.css`)

The `--border-subtle` CSS variable was referenced in `base.css` (footer border-top) but never defined in `tokens.css` or any theme. Added `--border-subtle: var(--separator)` as a theme alias. (Note: the footer border-top was later removed in a separate session, but the token is now available if other components reference it.)

Affects: `anvil/api/static/css/tokens.css`

## Files Changed

- `anvil/api/static/css/login.css` — login page stacking + glass material
- `anvil/api/static/css/base.css` — footer font-size + stacking fix
- `anvil/api/templates/base.html` — footer inline font-size sync
- `anvil/api/static/css/tokens.css` — added `--border-subtle` alias

## Related

- [[Reference/theme-creation-guide|Theme Creation Guide]] — theme CSS `::before`/`::after` conventions
- [[Discoveries/nav-bar-z-index-positioned-content-stacking|Nav-Bar Z-Index Competition]] — related stacking context pattern
- [[Discoveries/isolation-isolate-stacking-context-paint-order|Isolation/Isolate Stacking Context Paint Order]] — CSS stacking context primer
- [[Sessions/2026-06-26-footer-transparency-and-border|Footer Transparency and Border Removal]] — prior footer session
