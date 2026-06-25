---
aliases:
  - CSS Electrostatic Particle Field Technique
  - Radial Gradient Particle Field
code-refs:
  - anvil/api/static/css/themes/static.css
created: '2026-06-20'
related:
  - '[[Reference/theme-creation-guide]]'
  - '[[Discoveries/theme-presence-tiers-css-vs-session-gated-js]]'
  - '[[Sessions/2026-06-20-nine-new-themes]]'
session: 2026-06-20-static-electrostatic-particles
source: agent
summary: >-
  Multi-layer radial-gradient particles on ::before for an electrostatic
  discharge effect, driven by a CSS custom property with background-position
  drift animation.
tags:
  - type/discovery
  - domain/ui
  - status/draft
title: Electrostatic Particle Field via Radial Gradient Layers
type: discovery
updated: '2026-06-20'
---
# Electrostatic Particle Field via Radial Gradient Layers

## Context

The Static behavioral theme shipped with a CRT-noise `feTurbulence` SVG overlay on `.app-main::after` driven by loss volatility (`--snow`). While the noise effect was thematically consistent ("static" as in TV snow), it lacked a particle-like visual that matched the name's other meaning: **static electricity**. The user requested something thematic beyond the noise.

The challenge: the theme uses `::after` for the noise overlay, so adding a separate particle layer required `::before`, and the effect had to work **CSS-only** (no JS DOM injection) since the theme's `particleConfig` is `{ type: 'css' }` and the JS module only sets a CSS variable.

## Technique: Multi-Position Radial Gradient Particle Field

Place **15+ `radial-gradient` layers** on the `::before` pseudo-element, each representing a single tiny particle (1–2px dot) at a fixed viewport-relative position. Animate them as a group by shifting `background-position` across a scaled-up `background-size` canvas:

```css
[data-skin="static"] .app-main::before {
  /* 15 particle positions across the viewport */
  background-image:
    radial-gradient(2px 2px at 8%  22%, rgba(143, 196, 255, 0.9), transparent),
    radial-gradient(1px 1px at 30% 65%, rgba(200, 224, 255, 0.8), transparent),
    /* ...13 more layers at diverse coordinates... */;
  background-size: 300% 300%;
  animation: static-sparks 6s ease-in-out infinite;
  transition: opacity var(--dur-slow) var(--ease);
}

@keyframes static-sparks {
  0%, 100% { background-position: 0% 0%; opacity: low; }
  20%      { background-position: 40% 25%; opacity: medium; }
  40%      { background-position: 80% 50%; opacity: low; }
  60%      { background-position: 50% 80%; opacity: high; }
  80%      { background-position: 20% 10%; opacity: medium; }
}
```

### Key Parameters

| Parameter | Value | Why |
|-----------|-------|-----|
| Particle count | 15 | Enough for density, no perf concern (pure CSS, no DOM) |
| Particle sizes | 1px, 1.5px, 2px | Variety avoids uniform dot-grid appearance |
| Colors | `rgba(143..255, 0.6..0.9)` | Blue-white electrostatic color; varied opacity for depth |
| `background-size` | 300% × 300% | Gives the drift animation room to pan without revealing edges |
| Animation duration | 6s | Slow enough to feel like drifting, fast enough to notice motion |
| Keyframes | 5 stops at uneven intervals (0/20/40/60/80%) | Non-repeating feel — particles never "cycle" through a fixed path visibly |
| Opacity per stop | Varies (0.01–0.04 base + `--snow` multiplier) | Creates a spark/pop effect as different particles brighten at different phases |

### Signal Integration

The `--snow` CSS variable (set by the JS module as `clamp01(stddev(loss_window) / L0)`) scales the layer's opacity. At low volatility the particles are nearly invisible; at high volatility they become a visible sparkle field. On divergence (`data-static-state="snowstorm"`), a separate keyframe using `steps(4)` creates a chaotic flicker.

### Edge Cases

- **z‑index layering**: `::before` at `z-index: 40`, `::after` (noise) at `z-index: 41`. The noise overlay sits above the particles, giving a depth effect where sparks seem to float beneath the CRT static.
- **Reduced motion**: Both pseudo-elements get `display: none` under `prefers-reduced-motion: reduce`.
- **Position diversity**: Coordinates are deliberately non-uniform — spread across all quadrants, no two at the same X or Y, varied distances from edges. This prevents obvious dot-clustering.
- **Performance**: Pure CSS, no layout thrashing, no rAF loop. 15 `radial-gradient` layers with one `background-position` animation is GPU-composited.

## Comparison to Other Patterns

| Technique | Used by | Complexity | Dynamic range |
|-----------|---------|------------|---------------|
| CSS radial-gradient particle field | **Static** (this) | Low — pure CSS, single property | Medium — opacity + position |
| SVG feTurbulence noise | Static (noise layer) | Low — data URI | Low — opacity only |
| CSS animated ember dots | Ash, Ember Drift | Low — pattern repeat | Low — animated position |
| JS DOM sprite injection | Unicorn | High — rAF, DOM nodes | High — per-particle lifecycles |

This technique occupies a useful middle ground: more dynamic than fixed-pattern ember dots, but zero JS runtime cost.

## References
- [[Discoveries/Discoveries|Discoveries]]

- `anvil/api/static/css/themes/static.css` — `::before` particle field, `::after` noise overlay
- `anvil/api/static/js/themes/static.js` — sets `--snow` from loss volatility
- [[Reference/theme-creation-guide]]
- [[Discoveries/theme-presence-tiers-css-vs-session-gated-js]]
