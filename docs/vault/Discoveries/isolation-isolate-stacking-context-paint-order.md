---
title: 'Isolation: Isolate — Stacking Context Effect on Sibling Paint Order'
type: discovery
tags:
  - type/discovery
  - domain/ui
status: reviewed
created: '2026-06-23'
updated: '2026-06-23'
aliases:
  - isolation-isolate-stacking-context-paint-order
source: agent
code-refs:
  - anvil/api/static/css/
---
# isolation: isolate — Stacking Context Effect on Sibling Paint Order

**Type**: discovery  
**Tags**: type/discovery, domain/ui  
**Created**: 2026-06-23  
**Updated**: 2026-06-23  
**Status**: status/draft

## Summary

`isolation: isolate` on a positioned element creates a new stacking context. In the parent stacking context's paint order, this child stacking context is painted in Step 6 ("child stacking contexts and positioned descendants with z-index: auto, in DOM order"). A sibling with `position: relative` (also Step 6) that appears LATER in the DOM will paint ON TOP of the `isolation: isolate` element's entire content, including overflow.

## The Problem

On the anvil hero page:

```css
.app-main { position: relative; isolation: isolate; }
.site-footer { position: relative; }
```

Painting order in `.app-shell`'s stacking context:
1. `.app-main` (child stacking context) painted first
2. `.site-footer` (positioned descendant) painted second — ON TOP

When `.app-main`'s content overflows its box (because it's taller than the flex-distributed height), the overflow content is part of `.app-main`'s stacking context. The footer paints OVER this overflow, making it appear to "float on top of the content blocks."

## The Fix

Two approaches:

**Option A** (chosen): Remove both `isolation: isolate` from `.app-main` and `position: relative` from `.site-footer`. The footer becomes a non-positioned block (Step 3 in paint order), painted BEFORE `.app-main`'s content (Step 6). Add `background: var(--bg)` to the footer to prevent visual overlap in edge cases.

**Option B**: Keep `isolation: isolate` but ensure the footer never has `position: relative` (or any property that promotes it to Step 6 painting). Use `margin-top: auto` and natural flow positioning.

## Key Insight

`position: relative` alone is enough to move an element to Step 6 of the stacking order, where it competes with stacking contexts created by `isolation: isolate`, `transform`, `opacity < 1`, etc. The fix is to either:
- Not promote the footer to Step 6 (don't use `position: relative`)
- Or ensure `.app-main` doesn't create a stacking context (don't use `isolation: isolate`)

## Related
- [[Sessions/2026-06-23-hero-page-footer-stacking-and-layout]]