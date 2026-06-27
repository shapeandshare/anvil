---
created: '2026-06-20'
status: draft
source: agent
tags:
  - domain/ui
  - type/session-log
title: Unicorn Theme + Prism Vibrancy — 2026-06-20
type: session-log
updated: '2026-06-20'
aliases:
  - Unicorn Theme + Prism Vibrancy
---
# Unicorn Theme + Prism Vibrancy

**Date**: 2026-06-20
**Context**: User asked for a unicorns-and-rainbows theme, then asked to make Prism more vibrant.

## What Was Done

### New Theme: Unicorn (27th theme, 26→27 total)

A whimsical magical theme with dual light/dark mode and dual-signal mapping:

- **Loss-driven** `--magic` — convergence brings out a full-spectrum rainbow gradient overlay on `.app-main::before` (8-stop HSL gradient, hue steps of 51°)
- **Throughput-driven** `--twinkle` — 16-position `radial-gradient` starfield on `.app-main::after`, twinkling via CSS animation
- **Milestone** — hue shifts by 51° (rainbow order), triggers a `saturate(1.6)` rainbow burst with 0.50 opacity peak
- **Divergence** — `data-unicorn-state="faded"`: rainbow desaturated to purple grays, stars vanish, all magic set to 0
- **Light mode** — soft lavender cream palette (`#faf0ff` bg, `#d040b0` accent)
- **Dark mode** — deep midnight purple palette (`#0d0618` bg, `#ff7ae9` accent)

### Prism Vibrancy Boost

Enhanced the existing Prism theme (loss + milestone spectrum) for more punch:

| Dimension | Before | After |
|-----------|--------|-------|
| Accent colors | `#a88cff`, `#50d4a0`, `#ffd060`, `#60cce0` | `#c090ff`, `#50e8a8`, `#ffd860`, `#60d4f0` |
| Rainbow opacity (dark) | `0.02 + prism × 0.15` (max 0.17) | `0.05 + prism × 0.28` (max 0.33) |
| HSL lightness | 60–70% | 48–60% (punchier) |
| Gradient stops | 7 | 8 (added hue+420 wrap-around) |
| saturate filter | none | `saturate(1.3)` dark / `saturate(1.2)` light |
| Flash peak | 0.45 opacity | 0.65 opacity + `saturate(1.8) brightness(1.3)` |
| Monochrome | 0.25, light grays | 0.40, dark grays, `saturate(0)` |

### Files Changed

```
Created:
  anvil/api/static/css/themes/unicorn.css   (CSS tokens, rainbow ::before, sparkle ::after, burst/flash, divergence, reduced-motion)
  anvil/api/static/js/themes/unicorn.js     (loss→magic, TPS→twinkle, milestone hue+51, burst, divergence teardown)
Modified:
  anvil/api/static/css/themes/prism.css     (vibrancy bump: opacity, saturation, HSL, flash, monochrome)
  anvil/api/templates/base.html             (+1 script include for unicorn)
  tests/system/test_theme_engine.py         (+1 THEME_IDS entry for unicorn)
```

## Wikilinks

- [[Reference/theme-creation-guide]]
- [[Decisions/ADR-031-behavioral-theme-engine]]
- [[Sessions/2026-06-19-theme-gallery-expansion]]
- [[Sessions/2026-06-20-nine-new-themes]]
- [[Sessions/2026-06-26-prism-theme-enhancements-and-removal]]

> **Note**: The Prism theme was removed on 2026-06-26 per user request. See the linked session log for the full enhancement-to-removal history.
