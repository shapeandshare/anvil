---
title: Overflow Clipping Pattern
type: reference
tags:
  - type/reference
  - domain/ui
created: '2026-06-14'
updated: '2026-06-14'
---
# Overflow Clipping Pattern

**Established**: 2026-06-14  
**Context**: Hero page buttons ("Start Training", "Learn the Concepts") were getting their bottoms clipped.

## The Problem

`.forge-section` had `overflow: hidden` to contain the ember particles and glow effects. However, this also clipped normal-flow children — specifically the buttons at the bottom of the flex column — because `overflow: hidden` clips the element's content box, including any in-flow children that extend to the bottom edge.

```css
/* ❌ Before — clips in-flow children */
.forge-section {
  overflow: hidden;
}
```

## The Fix

Each absolutely-positioned decorative child already had its own `overflow: hidden`. The parent-level `overflow: hidden` was redundant for the decorations and harmful for in-flow content:

| Container | `overflow: hidden` | Reason |
|-----------|-------------------|--------|
| `.forge-section` | Removed | Was clipping button bottoms |
| `.forge-embers` | Kept | Clips ember particles within absolute bounds |

```css
/* ✅ After — content flows naturally, embers still clipped */
.forge-section {
  /* no overflow: hidden */
}

.forge-embers {
  overflow: hidden; /* still clips ember particles */
}
```

## Principle

`overflow: hidden` on a parent should not be used as a blanket containment strategy for absolutely-positioned decorations. Instead, apply `overflow: hidden` directly to the decoration containers that need it. This avoids unintended clipping of normal-flow children.

## See Also

- [[Reference/ArchitectureOverview|Architecture Overview]]
