---
aliases:
  - CSS Ambient Glow via color-mix
created: '2026-06-20'
status: draft
tags:
  - domain/ui
  - type/discovery
title: CSS Ambient Glow via color-mix + var(--accent)
type: discovery
updated: '2026-06-20'
---
# CSS Ambient Glow via `color-mix` + `var(--accent)`

**Type**: discovery
**Tags**: domain/ui, type/discovery
**Created**: 2026-06-20
**Updated**: 2026-06-20
**Status**: draft

## The Pattern

A mode-safe ambient glow effect that adapts to both light and dark themes without any mode-specific CSS:

```css
.element::after {
  content: "";
  position: fixed;
  inset: auto 0 0 0;
  height: 45vh;
  pointer-events: none;
  z-index: 0;
  background: radial-gradient(
    ellipse 90% 70% at 50% 100%,
    color-mix(in srgb, var(--accent) calc(6% + var(--signal, 0) * 18%), transparent) 0%,
    color-mix(in srgb, var(--accent) calc(2% + var(--signal, 0) * 6%), transparent) 40%,
    transparent 65%
  );
  opacity: calc(0.5 + var(--tone, 0.4) * 0.4);
}
```

## Why It Works

- **`color-mix(in srgb, var(--accent) X%, transparent)`** blends the theme's accent color with transparency at the CSS level. In dark mode `--accent` is a bright purple (`#b07cff`); in light mode it's a deep purple (`#7d3fd0`). The glow automatically picks the right color for the current mode.
- **No hardcoded hex values** — the glow is defined entirely in terms of the theme's token system. A systemic restyle is a token edit.
- **Signal-driven depth** — the `calc(6% + var(--signal, 0) * 18%)` expression lets a training signal (0→1) linearly scale the glow intensity from subtle to pronounced.
- **`ellipse 90% 70% at 50% 100%`** — centered at the bottom edge, wider than tall, reads as a floor glow rather than a pillar.

## When to Use

- Bottom-of-page ambient effects that should feel like atmospheric light rather than a pattern/texture
- Any theme that wants a "warmth" or "energy" floor glow driven by training signals
- Replaces patterns like repeating-linear-gradient bars, hard-edge masks, or scaleY animations that feel disconnected from the iOS design language

## When NOT to Use

- When the theme needs a specific pattern/texture (grid, scanlines, noise) — those should use their own background approach
- When the glow needs to be a specific color unrelated to `--accent` — use a direct color value instead
- When the effect needs to be visible on very short pages (the 45vh height may be clipped)

## Applied In

- Resonance theme (`anvil/api/static/css/themes/resonance.css`) — replaced a repeating-linear-gradient EQ bar with this radial glow pattern

## See Also

- [[Reference/theme-creation-guide]] — the 3-step contract for theme CSS layers
- [[Sessions/2026-06-20-resonance-bottom-effect-glow]] — the session that introduced this pattern
