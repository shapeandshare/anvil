---
title: 'Theme Decorative Layer Z-Index Convention'
type: discovery
tags:
  - type/discovery
  - domain/ui
status: draft
created: '2026-06-26'
updated: '2026-06-26'
aliases:
  - theme-decorative-layer-z-index-convention
source: agent
code-refs:
  - anvil/api/static/css/themes/
  - anvil/api/static/css/archetypes.css
---

# Theme Decorative Layer Z-Index Convention

**Type**: discovery  
**Tags**: type/discovery, domain/ui  
**Created**: 2026-06-26  
**Updated**: 2026-06-26  
**Status**: status/draft

## Summary

Every behavioral theme uses `.app-main::before` and `.app-main::after` pseudo-elements (and occasionally separate overlay elements) to render atmospheric background effects — gradients, scanlines, sparkles, noise, vignettes, flashes, warp lines, and particle fields. These are *decorative layers* that must never compete with or obscure page content.

This discovery establishes and enforces a strict z-index convention for these layers, fixing a bug where several themes painted overlays on top of hero page content at z-index 40-41.

## The Convention

Within `.app-main`'s stacking context (created by `isolation: isolate` on `.app-main`):

| z-index | Layer | Examples |
|---------|-------|----------|
| **0** | `::before` | Background gradients (forge glow, oldgrowth scanlines), warp lines (loom), sparkle fields (static), rainbow gradients (unicorn), baseline atmospheric effects |
| **1** | `::after` | Animated overlays: weft/horizontal thread lines (loom), lightning flashes (stormfront), noise textures (static), flare bursts (solarflare), expanding sonar rings (echo), vignettes (oldgrowth), petal sway (bloom), floating sprite clouds (unicorn overlay), blinking cursors (mainframe, pulse) — *when they overlap content* |
| **1** | Other overlays | `.unicorn-overlay`, `.app-main::after`, any `position: fixed` decorative element that paints over the page |
| **2+** | **Content** | `.hero-page`, `.hero-card`, `.hero-actions`, nav bar, dropdown menus, modals, toasts |

### Rationale for z-index: 0

`::before` renders as the first child of `.app-main` in CSS tree order. Setting it to `z-index: 0` (positioned, paints in stacking step 6) means it renders *after* normal flow content (stacks at step 3) but *before* `::after` and content containers at z-index 1+. This is the correct position for "behind everything" atmospheric layers.

### Rationale for z-index: 1

`::after` renders as the last child of `.app-main` in CSS tree order. At `z-index: 1`, if no content container has `z-index: 2+`, the `::after` would paint *on top* of all content (including text). Content containers must be explicitly raised above this layer. Content that needs to be above the atmosphere uses `z-index: 2`.

### Why Not Higher

Themes shipped with z-index values as high as 41. These were arbitrary and caused:

- **Content occlusion**: Hero page cards, buttons, and text were painted below these overlays, making them appear washed out or transparent
- **Fragile stacking**: Any new positioned content risked being buried under an unknown z-index ceiling
- **No semantic meaning**: A value of 40 vs 41 conveyed no information about layer purpose

## Exceptions

Two themes have corner-positioned elements at `z-index: 40` that do not overlap centered hero content:

- `mainframe.css` — `::after` at z-index 40: a 0.7ch × 1.1em cursor blink in the bottom-right corner (`right: var(--space-4); bottom: var(--space-4)`)
- `pulse.css` — `::after` at z-index 40: a 1.4em heartbeat pulsing circle in the bottom-right corner (`right: var(--space-5); bottom: var(--space-5)`)

These were left unchanged because they don't overlap the hero page's centered content. They occupy a **decorative corner niche** at the bottom-right of the viewport. New theme elements must follow the 0/1/2 convention above — corner exceptions are evaluated case by case.

## Enforcement

When creating or modifying a theme:
- `::before` MUST use `z-index: 0`
- `::after` MUST use `z-index: 1` (for full-page overlays)
- Corner-only decorative elements MAY use higher values, but only when their `position: fixed` coordinates place them outside the centered content area (within ~60px of an edge)
- Content layers (`.hero-page`, nav, modals) use `z-index: 2` to sit above decorative layers

## Related

- [[Discoveries/Discoveries|Discoveries]]
- [[Sessions/2026-06-26-hero-content-above-theme-overlays|Hero Content Above Theme Overlays]]
