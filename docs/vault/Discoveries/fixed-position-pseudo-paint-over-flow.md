---
title: Fixed-Position Theme Effects Paint Over Flow Content in Root Stacking Context
type: discovery
tags:
  - type/discovery
  - domain/ui
created: '2026-06-26'
updated: '2026-06-26'
source: agent
code-refs:
  - anvil/api/static/css/login.css
  - anvil/api/static/css/base.css
aliases:
  - fixed-position-pseudo-paint-over-flow
---
# Fixed-Position Theme Effects Paint Over Flow Content in Root Stacking Context

**Type**: discovery
**Tags**: type/discovery, domain/ui
**Created**: 2026-06-26
**Updated**: 2026-06-26
**Status**: status/draft

## Summary

Theme CSS pseudo-elements (`::before`/`::after`) and canvas particle layers use `position: fixed` with `z-index: 0-1`. When `.app-main` doesn't establish its own stacking context, these pseudo-elements participate in the **root stacking context**. In CSS paint order, non-positioned flow content paints first (Step 3), then positioned elements with `z-index: 0` (Step 5), then positioned elements with `z-index > 0` (Step 7). This means theme effects paint ON TOP of login cards, footer text, and other flow content.

## The Problem

Theme CSS patterns commonly use:

```css
[data-skin="loom"] .app-main::before {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  /* decorative texture */
}
[data-skin="loom"] .app-main::after {
  position: fixed;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  /* decorative weft lines */
}
```

The particle canvas also uses:
```css
canvas.particle-canvas {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
}
```

Since `.app-main` itself is non-positioned (no `position`, `transform`, or `isolation`), it doesn't create a stacking context. Its `::before`/`::after` pseudo-elements with `position: fixed` participate directly in the **root stacking context** along with the canvas.

CSS painting order in the root stacking context:

| Step | What | Example |
|------|------|---------|
| 1 | Root background/borders | `<html>` background |
| 2 | Negative z-index positioned | (none) |
| 3 | **Non-positioned** | Login form content, footer text, hero text |
| 4 | Transform/opacity contexts | (none) |
| 5 | Positioned, z-index: 0 | Canvas (`z-index: 0`), `::before` (`z-index: 0`) |
| 7 | Positioned, z-index: 1+ | `::after` (`z-index: 1`) |

Theme effects at Steps 5 and 7 paint **after** and therefore **on top of** flow content at Step 3.

## The Fix

Give the flow content container its own stacking context with a `z-index` higher than the theme effects:

```css
.login-page,
.site-footer {
  position: relative;
  z-index: 2;  /* above all theme ::before/::after at z-index 0-1 */
}
```

This promotes the container to the root stacking context at `z-index: 2`, painting after the theme effects. The container's own `position: relative; z-index: 2` stacking context also isolates its children from the root context.

## Key Insight

The `position: fixed` pseudo-elements in theme CSS are intentionally at low z-index values (0-1) because they should sit behind any **positioned** content. But they still paint above **non-positioned** (flow) content in the root context. The fix isn't to change the theme CSS but to ensure pages that must be legible above effects establish their own stacking context.

This is subtly different from the `isolation: isolate` problem: that fix created a stacking context that broke footer/overflow behavior. This fix creates a stacking context on the container itself rather than using `isolation: isolate`.

## Related

- [[Discoveries/isolation-isolate-stacking-context-paint-order|Isolation/Isolate Stacking Context Paint Order]] — different stacking context pattern with `isolation: isolate`
- [[Discoveries/nav-bar-z-index-positioned-content-stacking|Nav-Bar Z-Index Competition]] — z-index competition between nav and hero content
- [[Reference/theme-creation-guide|Theme Creation Guide]] — guide for theme effect authoring
- [[Sessions/2026-06-26-login-stacking-glass-material|Login Card Stacking & Glass Material]] — session that applied this fix
