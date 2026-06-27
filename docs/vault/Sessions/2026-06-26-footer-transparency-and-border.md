---
title: "Session: Footer Transparency and Border Removal"
type: session-log
tags:
  - type/session-log
  - domain/ui
created: 2026-06-26
updated: 2026-06-26
source: agent
aliases:
  - 2026-06-26-footer-transparency-and-border
---

# Session: Footer Transparency and Border Removal

**Date**: 2026-06-26
**Status**: Completed

## Summary

Restored the `.site-footer` gradient background (lost during the 2026-06-23 stacking context fix) and removed the hard border-top line.

## What Changed

### 1. Footer background: solid → gradient

The 2026-06-23 stacking fix ([Sessions/2026-06-23-hero-page-footer-stacking-and-layout](Sessions/2026-06-23-hero-page-footer-stacking-and-layout)) replaced the footer's `linear-gradient` background with solid `background: var(--bg)` to create an opaque backdrop. This killed the transparency.

Restored the original gradient pattern from 2026-06-19:

```
background: linear-gradient(to bottom, transparent, color-mix(in srgb, var(--bg) 60%, transparent))
```

Applies in both:
- `.site-footer` CSS class (`base.css`)
- Inline style override (`base.html`)

The gradient fades from fully transparent at the top to a 60% tint of the theme's background at the bottom, so the footer blends into the page atmosphere. Works across all themes and light/dark modes because it uses the `--bg` token.

### 2. Border-top removed

Removed `border-top: 1px solid var(--border-subtle)` from both the CSS class and inline style. The gradient alone provides a clean visual transition.

## Files Changed

- `anvil/api/static/css/base.css` — `.site-footer`: restored gradient background, removed border-top
- `anvil/api/templates/base.html` — `<footer>` inline style: same changes

## Related

- [[Sessions/2026-06-23-hero-page-footer-stacking-and-layout]] — prior fix that inadvertently removed transparency
- [[Sessions/2026-06-19-version-footer-transparency]] — original transparency fix
- [[Sessions/2026-06-21-copyright-footer-and-docs-attribution]] — copyright footer addition
