---
created: '2026-06-20'
status: draft
source: agent
tags:
  - domain/ui
  - type/session-log
title: Arcade 80s Party Theme — 2026-06-20
type: session-log
updated: '2026-06-20'
aliases:
  - Arcade 80s Party Theme
---

# Arcade 80s Party Theme

**Date**: 2026-06-20
**Context**: The user asked to pivot the `stainedglass` theme (loss-led, single-mode, cathedral-glass visual) into an 80s party theme with a new name and visual recommendations. Chose **Arcade** (loss-led, light/dark) via poll.

## What Was Done

### Theme Pivot: Stained Glass → Arcade

Replaced the `stainedglass` theme with `arcade` (27 total themes preserved, one replaced in-place). Old CSS/JS files deleted.

**Palette**: Deep purple-black dark mode, lavender-white light mode. Hot pink (`#ff2d78`), cyan (`#00d4ff`), lime green (`#00ff88`), electric yellow (`#ffe033`), purple (`#c050ff`) neon accents — evoking 80s arcade cabinets.

**Visual overlay** (`::before` on `.app-main`):
- Hot pink horizontal grid lines × cyan vertical grid lines (48px spacing) for a Tron/synthwave floor
- Subtle CRT scanlines (2px repeating)
- Dual radial glow — pink bloom top-left, cyan bloom bottom-right

**Signal behavior** (Loss-led):
- `--neon` CSS var driven by `clamp01(1 - loss / L0)` — lower loss = brighter neon glow
- **Milestone flash**: `data-arcade-flash` triggers a 1-second "1UP" rainbow gradient burst across the full overlay (matching the `prism` flash pattern)
- **Divergence**: `data-arcade-state="game-over"` — red-tinted grid + red radial pulse (dim for light mode)

### Visual Recommendations (all three implemented)

1. **Confetti particle effect** — new `confetti` registered effect in `particle-system.js` (15–120 particles). Five neon colors (pink, cyan, yellow, green, purple) as mixed rectangles and strips, falling with sway and rotation, driven by `--neon`. Replaced `shard` on the Arcade theme.

2. **Neon nav-bar glow** — `box-shadow` dual-layer glow (hot pink outer, cyan inner) on `.nav-bar`, intensity scales with `--neon`. Light mode uses desaturated pink/green version. Pure CSS, no DOM elements.

3. **Active tab neon underline** — `::after` pseudo-element on `.tab-item.active` with `position: absolute`. A 2px accent→cyan→accent gradient bar that widens (40%→70%) and brightens (0.4→1.0 opacity) with `--neon`. Turns solid red in GAME OVER state.

### Registration points updated
- `base.html` — replaced script include
- `test_theme_engine.py` — replaced in `THEME_IDS`
- `theme-creation-guide.md` — updated theme table entry
- `AGENTS.md` — historical references left as-is (describe past work)

### Files Changed

```
Created:
  anvil/api/static/css/themes/arcade.css        (158 → 248 lines after recommendations)
  anvil/api/static/js/themes/arcade.js           (replaces stainedglass.js)
  docs/vault/Sessions/2026-06-20-arcade-80s-party-theme.md

Modified:
  anvil/api/static/js/theme/particle-system.js   (+confetti effect, ~65 lines)
  anvil/api/templates/base.html                   (stainedglass.js → arcade.js)
  tests/system/test_theme_engine.py              (stainedglass → arcade)
  docs/vault/Reference/theme-creation-guide.md   (stainedglass → arcade, modes single→light/dark)
  docs/vault/Reference/particle-effect-authoring.md (catalogued effects list)
  docs/vault/Discoveries/css-grid-overlay-replacement-techniques.md (updated code-ref)

Deleted:
  anvil/api/static/css/themes/stainedglass.css
  anvil/api/static/js/themes/stainedglass.js
```

### First-time techniques
- **Neon nav-bar glow**: `box-shadow` on `.nav-bar` driven by a theme-private CSS var (`--neon`) — first theme to use ambient box-shadow on the navigation shell.
- **Confetti particle effect**: first canvas particle effect with mixed-color palette (5 fixed neon hues) rather than a single hue family or monochrome.
- **Active tab underline**: first theme to decorate `.tab-item.active` with a signal-driven `::after` indicator.

## Wikilinks
- [[Reference/theme-creation-guide]]
- [[Reference/particle-effect-authoring]]
- [[Discoveries/css-grid-overlay-replacement-techniques]]
- [[Sessions/2026-06-20-theme-square-grid-fixes]]