---
aliases:
  - Glacier Blizzard to Frostbite
created: '2026-06-20'
status: draft
source: agent
tags:
  - domain/ui
  - type/session-log
title: Glacier Blizzard to Frostbite Refinement — 2026-06-20
type: session-log
updated: '2026-06-20'
---
# Glacier Blizzard to Frostbite — 2026-06-20

**Date**: 2026-06-20
**Context**: User iterated on the Glacier theme's visual ambience — started with "stronger thicker snow, think blizzard," then rejected the criss-cross line pattern, and settled on a frostbite vignette aesthetic.

## What Was Done

### Round 1 — Blizzard mode

Increased the intensity of Glacier's existing sleet/streak effects:

**CSS** (`glacier.css`):
- **`::before`** (frost glow): widened opacity range from 0.25–0.55 to 0.2–0.9, bumped gradient alphas ~25%.
- **`::after`** (sleet lines): replaced the single 1px / 40px-spacing diagonal layer with **three layers** at different angles (58°, -38°, 0°) with thicker lines (3px/2px/1px) and denser spacing (28px/33px/18px). This created a criss-cross intersection pattern.

**Snow particles** (`particle-system.js`, `snow` effect):
- Flake count: 100–350 → **200–700**
- Flake radius: 0.8–3.0px → **1.5–5.0px**
- Opacity: 0.25–0.80 → **0.40–0.95**
- Wind drift multiplier at peak freeze: 1.5× → **2.2×**
- Bottom snow cover: threshold lowered to freeze > 0.3, wider (10px) and denser (0.126 max alpha)

### Round 2 — Remove criss-cross

User reported "awful criss-cross pattern" from the three intersecting line angles. Collapsed to two parallel layers at the same angle (62°) — thick 3px lines at 22px spacing + fine 1.5px lines at 37.5px spacing.

### Round 3 — Full re-theme of `::after`

User decided the sleet/streak lines weren't thematically helpful. Replaced entirely with a **frostbite vignette**:

- **`::after`**: `radial-gradient(ellipse 70% 65% at 50% 45%)` — transparent at center, dark cold blue-black at edges. Opacity driven by `--freeze` (0 → ~0.65). Dark mode uses near-black `rgba(2, 8, 16, 0.85)` at perimeter; light mode uses icy gray-blue `rgba(155, 195, 214, 0.70)`.
- The z-order stacks ::after (vignette) above ::before (frost glow) — the cold corners wrap over the ambient ice light.

### Retained from prior work

- Canvas `snow` particle effect with boosted counts and sizes
- Frost glow radial gradients on `::before`

## Key Lesson

Multi-angle `repeating-linear-gradient` layers on overlapping pseudo-elements create unattractive grid/criss-cross intersections. For a natural wind-blown look, keep all line layers at the **same angle**. Or better yet, replace line effects with an atmospheric radial gradient if the lines aren't serving the theme.

## Files Changed

- `anvil/api/static/css/themes/glacier.css` — replaced sleet streaks with frostbite vignette; boosted frost glow
- `anvil/api/static/js/theme/particle-system.js` — boosted `snow` effect counts, sizes, opacity, drift, and bottom cover

## Related

- [[Design/Design|Design]] — UI design system including theme and particle effects
- [[Reference/theme-creation-guide|Theme Creation Guide]] — theme authoring reference
- [[Discoveries/canvas-particle-amplitude-vs-frequency-perceived-speed|Canvas Particle Amplitude vs Frequency]] — related particle system discovery
