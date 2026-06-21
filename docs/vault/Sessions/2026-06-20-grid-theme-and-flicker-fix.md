---
title: 'Session: Hologram → Grid Theme Rework + Perspective-Floor Flicker Fix'
type: session-log
tags:
  - type/session-log
  - domain/ui
created: '2026-06-20T00:00:00.000Z'
updated: '2026-06-20T00:00:00.000Z'
source: agent
aliases:
  - Grid Theme Session
  - Hologram to Grid Rework
---
# Session: Hologram → Grid Theme Rework + Perspective-Floor Flicker Fix

**Date**: 2026-06-20
**Status**: Completed

## Summary

Reworked the `hologram` theme in three escalating steps driven by user feedback:

1. **Hologram polish** — made the hex-lattice background truly tessellate
   (removed the central vignette blob mask) and replaced the generic falling-dash
   `glitch` particle effect with a `holopoint` volumetric point-cloud.
2. **"Make it Tron-themed"** — pivoted to an electric grid-world aesthetic. Per
   user direction ("we don't want to infringe on copyrights"), the theme was
   **renamed to the trademark-safe generic name "Grid"** (`hologram` → `grid`),
   gaining the signature receding **perspective grid floor**, neon cyan/amber
   palette, and a `ribbon` light-cycle-trail particle effect.
3. **Flicker fix** — the perspective grid floor shimmered along the bottom of the
   screen; root-caused as sub-pixel moiré aliasing and fixed.

## Step 1 — Hologram Tessellation + Point Cloud (intermediate, since renamed)

- Background: dropped the `radial-gradient` vignette mask that faded the hex grid
  to a central blob; made it `background-repeat: repeat` full-viewport; added
  vertex dots to the SVG hex tile; replaced the static scanline with a traveling
  scan-sweep (`holo-scan`).
- Particles: `glitch` → `holopoint` (neighbor-linking point cloud that resolves
  into a wireframe lattice as `--focus` rises; scatters red on divergence).
- Added a `data-hologram-state="diverged"` collapse state + `complete` handler.

> This step was entirely superseded by Step 2 (the theme was renamed and
> re-skinned). It is recorded for audit-trail continuity only.

## Step 2 — Rename + Reskin to "Grid"

**Trademark note**: "Tron" is a trademark. We delivered the *aesthetic* (electric
grid world, light-cycle ribbons) under the generic, non-infringing name **Grid**.

**Files renamed/created** (old `hologram.css` / `hologram.js` deleted):

- `anvil/api/static/css/themes/grid.css` — new theme:
  - Near-black palette, electric cyan accent (`#2de2ff`), amber secondary
    (`#ff9f1c`) for the program/derez contrast. Tokens `--grid-rgb` / `--beam-rgb`.
  - **Perspective grid floor**: `.app-main::before` is a `repeating-linear-gradient`
    grid laid on the ground plane via `transform: perspective() rotateX()`,
    scrolling toward the viewer (`grid-floor` keyframes), fading to a glowing
    **horizon line** (`.app-main::after`).
  - Neon glow (not chromatic ghosting) on cards/headings, intensity scaled by
    `--focus`.
  - `data-grid-state="derez"` divergence state: floor + horizon flip to amber and
    glitch-shake (`grid-derez`).
- `anvil/api/static/js/themes/grid.js` — registers `id: 'grid'`, `displayName:
  'Grid'`, `modes: ['single']`, `particleConfig: { type: 'ribbon' }`. Loss →
  `--focus`; divergence → `data-grid-state="derez"`; complete → focus locks to 1.
- `anvil/api/static/js/theme/particle-system.js` — `holopoint` effect replaced by
  **`ribbon`**: bright white-cored heads race axis-aligned and lay glowing
  right-angle trails (light-cycle look); higher `--focus` adds more/faster riders;
  `derez` turns them amber.

**Wiring updated**:

- `anvil/api/templates/base.html` — script include `hologram.js` → `grid.js`
  (placed alphabetically after `glacier.js`).
- `tests/system/test_theme_engine.py` — `THEME_IDS` `hologram` → `grid`.
- `docs/vault/Reference/particle-effect-authoring.md` — catalogue note updated
  (`holopoint`/`glitch` → `ribbon`).
- `docs/vault/Reference/theme-creation-guide.md` — existing-themes table row
  `hologram` → `grid`.

## Step 3 — Perspective-Floor Flicker Fix

**Symptom**: the grid floor shimmered/strobed along the bottom of the screen,
worst near the horizon and in motion.

**Root cause**: sub-pixel moiré aliasing. The steep `rotateX(70deg)` tilt crushed
"far" grid rows below one device pixel; as `background-position` animated, the
hard 2px lines flipped which pixel they occupied each frame → flicker.

**Fix** (four compounding mitigations):

1. **Soft-edged lines** — hard `solid 79→81px` bands → `transparent→solid→transparent`
   gradient ramps (pre-anti-aliased edges).
2. **Gentler tilt** — `perspective(36vh) rotateX(70deg)` → `perspective(60vh) rotateX(58deg)`.
3. **Fade the far region** — mask now `transparent 22% → solid 58%`, removing the
   worst-aliasing rows near the horizon (biggest single win).
4. **GPU hints + slower scroll** — `backface-visibility: hidden`,
   `will-change: background-position`, `1.6s` → `2.4s`.

Also re-pinned the `grid-derez` shake keyframes to the **new** perspective/angle
(they still used the old `36vh`/`70deg`, which would snap on divergence).

Full reusable write-up: [[Discoveries/css-perspective-grid-floor-subpixel-flicker]].

## Files Modified

- `anvil/api/static/css/themes/grid.css` — **new** (was `hologram.css`, deleted)
- `anvil/api/static/js/themes/grid.js` — **new** (was `hologram.js`, deleted)
- `anvil/api/static/js/theme/particle-system.js` — `holopoint` → `ribbon`
- `anvil/api/templates/base.html` — script include rename
- `tests/system/test_theme_engine.py` — `THEME_IDS` rename
- `docs/vault/Reference/particle-effect-authoring.md` — catalogue update
- `docs/vault/Reference/theme-creation-guide.md` — table update

## Tests / Verification

- LSP diagnostics clean on `grid.js` (zero) and `grid.css` (only the expected
  `!important` warnings inside the `prefers-reduced-motion` resets, matching every
  other theme). Remaining `particle-system.js` hints are pre-existing unused-var
  hints in *other* effects, not in `ribbon`.
- `tests/system/test_theme_engine.py` is parametrized correctly with `[grid]`
  (no stale `[hologram]`). The container-dependent CSS-layer assertions fail
  uniformly for **all** themes because no docker container is running locally —
  these require `make test-system`; not a regression.

## Follow-ups / Notes

- Picked **"Grid"** as the non-infringing name; trivial to rename again if a
  different label is preferred.
- Noticed a pre-existing inconsistency: `base.html` includes `arcade.js` and
  `unicorn.js` that are not all reflected in the test `THEME_IDS` list — unrelated
  to this work, flagged for a future tidy.

## Related

- [[Discoveries/css-perspective-grid-floor-subpixel-flicker|Perspective Grid Flicker]]
- [[Reference/theme-creation-guide|Theme Creation Guide]]
- [[Reference/particle-effect-authoring|Particle Effect Authoring]]
- [[Decisions/ADR-031-behavioral-theme-engine|ADR-031: Behavioral Theme Engine]]
- [[Sessions/2026-06-20-theme-square-grid-fixes|Session: Theme Square-Grid Fixes]] — the prior hologram hex-grid work this supersedes
