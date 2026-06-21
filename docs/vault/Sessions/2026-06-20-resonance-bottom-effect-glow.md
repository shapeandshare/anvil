---
aliases:
  - Resonance Bottom Effect Glow
created: '2026-06-20'
source: agent
status: draft
tags:
  - type/session-log
  - domain/ui
title: 'Session: Resonance Bottom Effect — EQ Bar → Soft Ambient Glow'
type: session-log
updated: '2026-06-20'
---
# Session: Resonance Bottom Effect — EQ Bar → Soft Ambient Glow

**Date**: 2026-06-20
**Scope**: `anvil/api/static/css/themes/resonance.css` only. No JS, no registration, no test changes.

## What changed

The Resonance theme's bottom-of-page effect was a fixed bar (22vh) with repeating vertical purple lines (`repeating-linear-gradient` at 90deg, 4px lines every 14px) that pulsed via `scaleY` animation (`resonance-wave`). It used a `-webkit-mask-image` to fade the top edge. The user reported it "does not come off well and it is not visually appealing."

### Replacement: soft radial ambient glow

Replaced the entire `.app-main::after` block with a **radial gradient glow** radiating upward from the bottom center:

```css
background: radial-gradient(
  ellipse 90% 70% at 50% 100%,
  color-mix(in srgb, var(--accent) calc(6% + var(--amp, 0) * 18%), transparent) 0%,
  color-mix(in srgb, var(--accent) calc(2% + var(--amp, 0) * 6%), transparent) 40%,
  transparent 65%
);
opacity: calc(0.5 + var(--tone, 0.4) * 0.4);
```

Key design decisions:

- **`color-mix(in srgb, var(--accent) X%, transparent)`** — adapts to both dark mode (`--accent: #b07cff`) and light mode (`--accent: #7d3fd0`) automatically. No hardcoded hex values.
- **`--amp`** (gradient norm, 0→1) controls glow depth: at idle it's 6%→2% accent, at full signal it's 24%→8% accent. The `calc()` expression scales linearly.
- **`--tone`** (from loss, higher = cleaner) controls overall presence: opacity ranges 0.5→0.9.
- **No animation keyframes** — the glow is purely ambient, no pulsing or oscillation. It breathes through the signal-driven CSS vars.
- **45vh height** — generous but soft, fades to transparent at 65% of that.
- **`ellipse 90% 70% at 50% 100%`** — centered at the bottom edge, wider than tall, so it reads as a floor glow not a pillar.

Removed:
- The `resonance-wave` keyframe animation
- The `-webkit-mask-image` / `mask-image` hack
- The `transform: scaleY(...)` and `transform-origin: bottom`
- The `repeating-linear-gradient` background
- The separate reduced-motion animation override (replaced with a simple `opacity: 0.7` static fallback)

## Rationale

The EQ-bar visualizer pattern (repeating vertical lines) felt disconnected from the iOS design language — it was a literal signal-visualization trope rather than an ambient atmospheric effect. The radial glow approach is:

- **iOS-native**: soft gradients are the standard ambient treatment in Apple's design language (control center, music player, widgets)
- **Signal-responsive without being literal**: the glow deepens with training activity but doesn't try to "draw" the signal waveform
- **Mode-safe**: `color-mix` with `var(--accent)` means it's correct in both light and dark without any mode-specific CSS
- **Zero animation overhead**: no keyframes, no layout thrashing from `scaleY` transforms

## Verification

`lsp_diagnostics` clean — only pre-existing `!important` warnings from the reduced-motion global rule (standard across all themes, intentional).

## Related

- [[Reference/theme-creation-guide]] — the 3-step contract for theme CSS layers
- [[Discoveries/css-ambient-glow-via-color-mix]] — the `color-mix` + `var(--accent)` pattern for mode-safe glow effects
