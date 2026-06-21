---
aliases:
  - Multi-Layer Radial-Gradient Background-Image Invisible
  - Radial Gradient Rain Effect Failure
created: '2026-06-20'
source: agent
tags:
  - type/discovery
  - domain/ui
title: Multi-Layer Radial-Gradient Rain Effect Invisible on Pseudo-Elements
type: discovery
updated: '2026-06-20'
code-refs:
  - anvil/api/static/css/themes/inkwash.css
  - anvil/api/static/css/themes/ash.css
---
# CSS `radial-gradient` Rain Effect on Pseudo-Elements: Visibility Failure with Many Layers

## Context

Implementing a "black rain" droplet effect on the Ink Wash theme's `.app-shell::before` pseudo-element using multiple `radial-gradient()` layers in `background-image`. The same pseudo-element mechanism works — proven by a solid red overlay at `z-index: 999` — but the droplet approach failed to produce visible output.

## The Problem

Three approaches were attempted, all invisible to the user:

1. **20 droplets, `background-size: 100% 200%`** — Percentage-based background sizing meant only ~10 droplets were in the visible viewport slice (50% of the 200%-tall image). The sparse pattern at ~18% opacity was invisible.

2. **40 droplets, `background-size: 200px 200px`, pixel animation** — Switched to fixed tile sizing (matching Ash theme's working soot pattern). Still invisible. Opacity at 22% (baseline `--rain: 0.4` × 0.55).

3. **49 droplets, `background-size: 240px 240px`, `.app-shell::before`** — Moved from `.app-main::before` to `.app-shell::before` (same as Hyperspace's working grid). Still invisible. Opacity at 24% (0.4 × 0.6).

## Diagnosis via Reduction

The pseudo-element **does** render — replacing the `background-image` with `background: rgba(0, 0, 0, 0.12)` produced a visible dark tint. Replacing it with `background: red` produced a full red screen. So the mechanism works.

A simplified test with **5 large** elliptical `radial-gradient()` layers (5×10px to 6×12px, `rgba(31,28,23, 0.6–0.9), transparent`) was then deployed to confirm the multi-gradient approach works at all.

## Comparison with Working Theme

Ash theme uses `background-image` with ~24 `radial-gradient()` layers. Key differences from the failing inkwash approach:

| Property | Ash (working soot) | Inkwash (failing rain) |
|---|---|---|
| Number of layers | ~24 | 40–49 |
| Shape | Circular (single stop) | Elliptical (1.5–2px × 2–5px) |
| Color stops | 1 (hard circle) | 2 (fade to transparent) |
| Tile size | 240×240px | 200–240px |
| Attached to | `.app-main::after` | `.app-shell::before` |

## Likely Root Causes (Unconfirmed)

1. **Layer count + 2-stop gradients**: The browser may silently drop or refuse to composite 49 `radial-gradient()` layers when each produces a soft-edged ellipse (two color stops → gradient texture per layer). Ash's hard circles (one stop, bitmap-like) at ~24 layers work.

2. **Elliptical gradient overhead**: `radial-gradient(w h at ...)` creates an anti-aliased elliptical alpha ramp per layer. At 49 layers, this may exceed per-element GPU compositing limits (Chrome caps `background-image` layers at ~100 for parsing but may stop rendering soft layers earlier).

3. **Tiny sizing**: Droplets at 1–2px × 2–5px are at the edge of sub-pixel rendering. With anti-aliased soft edges, the effective visible area of each droplet may be too small to register above the page background, even with 49 × 24% opacity × tiling.

## Mitigation / Fix

Use larger, fewer droplets with hard edges (single `radial-gradient` stop, like Ash) or switch to a different mechanism entirely (canvas particle system, repeating pattern, etc.).

## Files Referenced

- `anvil/api/static/css/themes/inkwash.css` — Rain effect (multiple radial-gradient layers)
- `anvil/api/static/css/themes/ash.css` — Working soot particle pattern (reference)
- `anvil/api/static/css/base.css` — `.app-shell` stacking context (z-index: 2, overflow-y: auto)

## Wikilinks

- [[Reference/theme-creation-guide]]
- [[Decisions/ADR-031-behavioral-theme-engine]]
- [[Discoveries/css-multi-background-position-parallax]]
