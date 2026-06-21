---
created: '2026-06-20'
status: draft
source: agent
tags:
  - domain/ui
  - type/session-log
title: Nine New Themes — 2026-06-20
type: session-log
updated: '2026-06-20'
aliases:
  - Nine New Themes
---
# Nine New Themes

**Date**: 2026-06-20
**Context**: The user asked what other themes we might add; I suggested 9 concepts, and they asked for all of them fleshed out.

## What Was Done

### Vault
- Created `docs/vault/Reference/theme-creation-guide.md` — a comprehensive reference documenting the 3-step contract, signal-mapping patterns, color palette rules, and the full 26-theme table.

### Nine New Themes (17 → 26 total)

Each theme follows the established 3-step contract: CSS layer → JS module → `<script>` include in `base.html` + `THEME_IDS` entry in `tests/system/test_theme_engine.py`.

| Theme | ID | Signal | Modes | Technique |
|-------|----|--------|-------|-----------|
| Pulse | `pulse` | Throughput (TPS) | light/dark | Heartbeat animation on radial-gradient `::after` |
| Solar Flare | `solarflare` | Gradient norm | single | Coronal `radial-gradient` glow + `::after` burst animation |
| Deep Sea | `deepsea` | Loss | light/dark | Depth gradient on `::before`, bioluminescent dots on `::after`, milestone flash |
| Static | `static` | Loss volatility | single | SVG `feTurbulence` fractal noise overlay, rolling stddev window=8 |
| Vinyl | `vinyl` | Throughput (TPS) | light/dark | CSS `rotate()` on `.app-main`, wobble animation, skip on milestone |
| Echo | `echo` | Gradient norm + milestone | single | Expanding border-ring `::after` from viewport center |
| Prism | `prism` | Loss / milestone | light/dark | `hsl()` spectrum gradient on `::before`, milestone shifts hue by 45° |
| Loom | `loom` | Throughput (TPS) | light/dark | `repeating-linear-gradient` weft lines, density driven by TPS |
| Ash | `ash` | Loss | single | Dual `radial-gradient` ember glow + animated ember dots `::after` |

### First-time CSS/JS techniques used across the project
- **Loss volatility signal**: Rolling standard deviation over last 8 loss values (Static)
- **Dynamic hue shift**: `hsl()` in CSS driven by JS `--hue` var (Prism)
- **SVG feTurbulence filter**: CSS background-image inline data-URI (Static)
- **CSS rotate transform**: Applying `animation: rotate()` to `.app-main` (Vinyl)
- **Expanding ring animation**: `::after` with `border-radius: 50%` growing from 10vmin to ~100vmin (Echo)

### AGENTS.md Updated
- Line 3: timestamp includes `+ nine-new-themes`
- Line 314: preserved as-is (historical record of the first batch)
- New Recent Changes entry documenting the batch

### Files Changed
```
Created:
  anvil/api/static/css/themes/{pulse,solarflare,deepsea,static,vinyl,echo,prism,loom,ash}.css   (9 files)
  anvil/api/static/js/themes/{pulse,solarflare,deepsea,static,vinyl,echo,prism,loom,ash}.js     (9 files)
  docs/vault/Reference/theme-creation-guide.md                                                   (1 file)
  docs/vault/Sessions/2026-06-20-nine-new-themes.md                                              (1 file)
Modified:
  anvil/api/templates/base.html                        (+9 script includes)
  tests/system/test_theme_engine.py                    (+9 THEME_IDS entries)
  AGENTS.md                                            (last-updated, new Recent Changes entry)
```

## Wikilinks
- [[Reference/theme-creation-guide]]
- [[Sessions/2026-06-19-theme-gallery-expansion]]
- [[Decisions/ADR-031-behavioral-theme-engine]]
