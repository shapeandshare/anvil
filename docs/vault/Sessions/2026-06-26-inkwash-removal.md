---
title: Inkwash Theme — Rework Then Removal
type: session-log
tags:
  - type/session-log
  - domain/ui
created: '2026-06-26'
updated: '2026-06-26'
source: agent
related:
  - Reference/theme-creation-guide
  - Sessions/2026-06-20-inkwash-black-rain
aliases:
  - Inkwash Theme Removal
---
# Session: Inkwash Theme — Rework Then Removal

**Date**: 2026-06-26
**Status**: Draft

## Summary

The user called the Inkwash theme "boring." Initially reworked it for more visual bite with a sumi-e ink wash painting concept (vermillion seal/stamp accent, multi-layer ink wash ambient, ink splash/explosion animations, richer signal mapping). The same session ended with the user requesting removal — all theme files and references were deleted.

## Phase 1 — Rework

The initial rework aimed to keep the ink metaphor while adding dramatic visual presence:

### `inkwash.css` — Richer palette + ambient effects

**Palette transformation:**
- Light mode: warm cream papers (`#f5efe0`, `#fffcf0`, `#ece2d0`) with **vermillion red** accent (`--accent: #c43a31`) — traditional East Asian seal/stamp color
- Dark mode: rich charcoal (`#0e0d0a`, `#1a1814`, `#24211b`) with brighter vermillion (`--accent: #e05a4a`)
- Accent colors shifted to muted natural pigments (moss `#5a7a4a`, amber `#c47a3a`, aged gold `#b89a42`, eggplant `#6a4e7a`, teal `#4a7a6e`)

**New CSS variables:** `--density: 0.4` (ink density, inverse of loss), `--brush: 0` (brush energy from tokens/sec)

**4-layer sumi-e wash ambient** (replaced single barely-visible gradient):
1. Primary ink pool — dense black at center, feathering outward
2. Secondary offset pool — creates depth
3. Tertiary vermillion accent layer — visible even at idle
4. Ghost wash — far-flung atmosphere

Organic 90vmin blob with irregular `border-radius` that breathes with `--brush`, growing by 20vmin at full brush energy.

**Ink splash animation** (milestone): 800ms — scales 0.2→2.0 with opacity fade
**Ink explosion animation** (divergence): 1200ms — chaotic blur-bloom-pulse-disperse sequence

### `inkwash.js` — Richer signal mapping

| Signal | Formula | Effect |
|--------|---------|--------|
| `--density` | `clamp01(1 - loss / L0)` | Low loss = refined dense ink, high loss = chaotic sparse |
| `--brush` | `clamp01(tps / 600000)` | Brush strokes animate when training is fast |
| `--clarity` | Same as density | Legibility control |
| `--bleed` | `legible ? 0 : clamp01(loss / L0)` | Ink feathering, zeroed at max legibility |
| `--rain` | `clamp01(loss / L0)` | Unchanged from original |

- Milestone/complete → `data-ink-state="splash"` with 900ms auto-clear (forge.js `flashTimer` pattern)
- Divergence → `data-ink-state="explosion"` + vars reset

## Phase 2 — Removal

User then requested removal. All traces cleaned:

| File | Action |
|------|--------|
| `anvil/api/static/css/themes/inkwash.css` | Deleted |
| `anvil/api/static/js/themes/inkwash.js` | Deleted |
| `anvil/api/templates/base.html` | Script tag removed |
| `tests/system/test_theme_engine.py` | `"inkwash"` removed from `THEME_IDS` list |

Historical vault references in `docs/vault/` (discovery notes, session logs, theme creation guide) were left in place as archival records.

## Key Files (final state)

```
Deleted:
  anvil/api/static/css/themes/inkwash.css
  anvil/api/static/js/themes/inkwash.js

Modified:
  anvil/api/templates/base.html            — Removed inkwash script tag
  tests/system/test_theme_engine.py        — Removed inkwash from THEME_IDS
```

## Lesson

The user went from "boring" to "remove" in a single session, bypassing the rework entirely. The rework was well-structured but never seen — suggests the user had already decided they wanted it gone before the delegation completed.

## Wikilinks

- [[Reference/theme-creation-guide]]
- [[Sessions/2026-06-20-inkwash-black-rain]]
