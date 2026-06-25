---
aliases:
  - Transparent items with gap create see-through illusion
code-refs:
  - anvil/api/static/css/base.css
created: '2026-06-19'
related:
  - '[[Sessions/2026-06-19-theme-picker-transparency-recheck]]'
  - '[[Sessions/2026-06-19-theme-picker-transparency]]'
session: 2026-06-19-theme-picker-transparency-recheck
source: agent
summary: >-
  A flex/grid container with opaque background can still appear transparent when
  its children have background: transparent and gap separates them. The fix is
  making the children opaque too.
tags:
  - type/discovery
  - domain/ui
  - status/draft
title: Transparent Items with Gap Create See-Through Illusion
type: discovery
updated: '2026-06-19'
---
A container element (menu, panel, dropdown) and its children can have opaque backgrounds individually, yet the **visual surface still appears semi-transparent**. This happens when:

1. **Children have `background: transparent`** (common for clickable items that rely on hover state)
2. **The container uses `gap`** (flex or grid) to space items apart
3. **The `gap` areas are small** enough that the brain registers the children's transparent fill areas more strongly than the narrow opaque gaps

The result: the user perceives the *items* (transparent) as the panel surface, and the *gaps* (opaque) as insubstantial borders. The panel "feels" see-through even though the CSS `background` value on the container is an opaque color like `var(--surface)`.

## Fix

Give each child an opaque default background matching the container:

```css
.theme-picker__item {
  background: var(--surface); /* was: transparent */
}
```

Hover states still use a different shade for visual feedback:

```css
.theme-picker__item:hover {
  background: var(--surface-2);
}
```

This makes every pixel of the panel solidly filled, eliminating the transparent-illusion.

## Detection

Any flex/grid container where children are spaced with `gap` and have `background: transparent` is a candidate. Rule of thumb: if a panel looks transparent in the browser but its CSS `background` is opaque, check whether the *children* are transparent with `gap` between them.

## Instance

- `anvil/api/static/css/base.css` — `.theme-picker__item` fix (commit `e68da70` follow-up)
- See [[Sessions/2026-06-19-theme-picker-transparency-recheck]]

## See Also

- [[Discoveries/Discoveries|Discoveries]]
