---
title: Playground Example Prompt CSS Class Mismatch
type: discovery
tags:
  - type/discovery
  - domain/ui
  - status/draft
created: 2026-06-19
updated: 2026-06-19
code-refs:
  - anvil/api/templates/archetypes/playground.html
  - anvil/api/static/css/components.css
source: agent
aliases:
  - Playground CSS Class Mismatch
  - Example Prompt CSS Mismatch
---

# Playground Example Prompt CSS Class Mismatch

## Discovery

The playground inference page's "Try:" example prompt chips were unstyled ("missing formatting"). The root cause was a CSS class name mismatch:

- **CSS** (in `components.css`, line 143) defined the styled chip as `.example-prompt`
- **HTML** (in `playground.html`, lines 36-40) used `class="example-chip"` — no CSS existed for that class

Additionally, the JavaScript click handler at line 246 used `document.querySelectorAll('.example-chip')`, which would have silently matched zero elements after the fix.

The `.example-label` (the "Try:" prefix) had no CSS definition at all.

## Fix

1. Changed all `example-chip` class references in the HTML to `example-prompt`
2. Updated the JS selector from `'.example-chip'` to `'.example-prompt'`
3. Added `.example-label` rule to `components.css` for consistent inline styling

## Impact

The example prompt chips now render with proper inline-block layout, rounded corners, hover highlight, and cursor pointer — matching the design system.

## See Also

- [[Discoveries/Discoveries|Discoveries]]
