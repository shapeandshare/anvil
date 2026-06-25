---
aliases: []
created: '2026-06-23T00:00:00.000Z'
source: agent
tags:
  - type/discovery
  - domain/ui
title: Nav-Bar Z-Index Competition with Page Content Positioned Elements
type: discovery
updated: '2026-06-23T00:00:00.000Z'
code-refs:
  - anvil/api/static/css/base.css
---

# Nav-Bar Z-Index Competition with Page Content Positioned Elements

**Type**: discovery
**Tags**: type/discovery, domain/ui
**Created**: 2026-06-23
**Updated**: 2026-06-23
**Status**: status/draft

## Summary

When page content elements (hero section buttons, titles, etc.) use `position: relative; z-index: 1` without being in their own stacking context, they participate in the nearest ancestor stacking context at the same level as `.nav-bar` (also `z-index: 1`). Since they appear later in DOM order, they paint **on top** of the nav-bar and all its children — including the theme-picker dropdown menu.

## The Problem

The hero page has positioned elements inside `.forge-section`:

```css
.hero-actions { position: relative; z-index: 1; }
.forge-icon   { position: relative; z-index: 1; }
.hero-title   { position: relative; z-index: 1; }
```

These participate in `.app-shell`'s stacking context. `.nav-bar` also participates at `z-index: 1`. Within the same z-index level, later DOM order wins — so `.hero-actions` paints on top of `.nav-bar`.

The theme-picker dropdown (absolutely positioned, `z-index: 60`) is trapped inside `.nav-bar`'s stacking context. When it extends downward into `.app-main`, it gets covered by `.hero-actions`.

## The Fix

Raise `.nav-bar`'s z-index above page content levels:

```css
.nav-bar {
  z-index: 10;  /* was 1 */
}
```

The nav-bar should always stack above page content. Value 10 leaves room for content at z-indexes 2-9.

## Key Insight

`z-index` is scoped to the nearest ancestor stacking context. Elements inside different stacking contexts can only be compared at the parent context level. `.nav-bar` creates a stacking context with `position: relative; z-index: 1`, and its children with higher `z-index` values (like `z-index: 60`) only outrank other children within the same context — they cannot escape above the nav-bar's own z-index in the parent context.

## Related
- [[Discoveries/Discoveries|Discoveries]]

- [[Sessions/2026-06-23-theme-picker-dropdown-z-index-and-excited-fix]]
- [[Discoveries/isolation-isolate-stacking-context-paint-order]]
