---
title: Glass Diffusion via Canvas Blur
type: discovery
tags:
  - type/discovery
  - domain/ui
created: '2026-06-23T00:00:00.000Z'
updated: '2026-06-23T00:00:00.000Z'
source: agent
aliases:
  - Glass Diffusion via Canvas Blur
related:
  - '[[Reference/particle-effect-authoring]]'
  - '[[Reference/theme-creation-guide]]'
status: draft
code-refs:
  - anvil/api/static/js/theme/particle-system.js
  - anvil/api/static/js/theme/theme-manager.js
  - anvil/api/static/css/base.css
---
# Glass Diffusion via Canvas Blur

## Problem

When a user enables "Reduce effects" (the in-app accessibility toggle), the existing behavior pauses the particle animation loop **and** sets `canvas.style.opacity = '0'`, making all canvas-based particles abruptly disappear. This is jarring — the background goes from lively to barren in one click. The user still wants ambient particles visible, but motion-diffused, to preserve the sense of a living workspace without the visual stimulation of motion.

Additionally, a DOM overlay approach with `backdrop-filter: blur()` was attempted but caused two classes of problems:

1. **z-index conflicts** — any overlay positioned between the particle canvas (z:0) and the content (z:1+) required careful stacking management and bumped `.app-main`'s z-index, which broke dropdown menus (theme picker at z:60 within nav) by creating stacking context competition.
2. **backdrop-filter compositing layers** — the overlay, even at `opacity: 0` with no filter, created compositing layers that interfered with the canvas in some browser rendering pipelines.

## Solution

Instead of an external overlay, apply `filter: blur(12px)` directly to the particle `<canvas>` element when "Reduce effects" is on. This is a two-line change in `particle-system.js`:

### `onEffectLevelChange` (reactive path)

```javascript
// Before (particles hidden):
if (canvas) canvas.style.opacity = '0';

// After (particles blurred, still visible):
if (canvas) canvas.style.filter = 'blur(12px)';
```

### `ps.apply()` (initial/reapply path)

At the end of `apply()`, after `startAnimation()`:

```javascript
if (canvas) {
  canvas.style.filter = legible ? 'blur(12px)' : '';
}
```

This ensures the blur is applied on first load if the preference is already active, not only when snapping from OFF→ON.

### Companion CSS

Since the particles are now blurred (rather than hidden), the shell background gradient behind them becomes more prominent. To further reduce visual motion, the gradient is muted when `[data-glass-diffusion]` is set on `<html>`:

```css
[data-glass-diffusion] .app-shell {
  background: radial-gradient(ellipse 1200px 700px at 50% 5%,
    color-mix(in srgb, var(--accent-orange) 6%, transparent), transparent);
}
```

(from the original 12% accent-orange mix to 6%)

## Why this works (and the overlay approach didn't)

| Concern | Overlay approach | Canvas-blur approach |
|---------|-----------------|---------------------|
| **z-index** | New element at z:1 competes with nav (z:1) and requires bumping app-main (z:1) | No new element — canvas stays at z:0, no stacking change |
| **Dropdown menus** | Bumping app-main z-index creates stacking context conflicts with absolute-positioned dropdowns (z:60 inside nav) | Content stacking untouched — dropdowns render normally |
| **Particle visibility** | Possible compositing-layer interference when backdrop-filter element shares z-index stack with canvas | Particles are rendered on their own canvas; filter applies to canvas contents only |
| **Simplicity** | Requires JS DOM creation, insertion tracking, teardown, two CSS classes | Two lines of JS in one function; zero new DOM elements |

## Implications

- **Theme authors** do not need to change anything — the blur is applied uniformly across all canvas-based particle effects (snow, rain, ember, aurora, petal, biolum, ribbon, streak, ink, thread, matrix, leaf, prism, pulse, energy, flare, shard, debris, spray, bubble, spin, spark, confetti, etc.).
- **CSS-only effects** (themes with `particleConfig: { type: 'css' }`, like Default, Ash, Static, Echo, Resonance, Unicorn, Vinyl) are unaffected by this change since `onEffectLevelChange` returns early for non-canvas configs.
- When the canvas is later removed and recreated (theme switch), `ps.apply()` re-applies the blur via the added line at the end of the function.
