---
title: "Session: Version Footer Transparency"
type: session-log
tags:
  - type/session-log
  - domain/ui
created: 2026-06-19
updated: 2026-06-19
aliases:
  - Session: Version Footer Transparency
source: agent
---

# Session: Version Footer Transparency

**Date**: 2026-06-19
**Branch**: opencode/proud-cactus
**Status**: Completed

## Summary

Removed the hard "black edge" at the bottom of every page by giving the
`anvil v{version}` site footer a transparent-to-faded gradient background so it
blends into the page atmosphere instead of reading as an opaque black band.

## Changes

- **File**: `anvil/api/static/css/base.css`
- **Rule**: `.site-footer` → added
  `background: linear-gradient(to bottom, transparent, color-mix(in srgb, var(--bg) 60%, transparent))`
- The footer had no background of its own and sat as a sibling of `.app-main`,
  so the page's radial-gradient/ambient atmosphere (scoped to `.app-main`) did
  not extend behind it. The fallback to the opaque `body` background
  (`var(--bg)`) is what produced the hard black band the user reported.

## Context

User request: the version footer needs transparency — "the black edge is very
distracting."

## Notes

- The fix uses `color-mix` against the `--bg` design token rather than a
  hardcoded color, so the fade adapts across all themes and light/dark modes
  per the design system (DESIGN.md / tokens.css).
- The footer is rendered in `anvil/api/templates/base.html` (`.site-footer`),
  as a sibling of `.app-main` inside `.app-shell`.

## References

- `anvil/api/static/css/base.css` — `.site-footer` rule
- `anvil/api/templates/base.html` — footer markup

## Related

- [[Design/Design|Design]] — UI design system including footer layout and theme tokens
- [[Reference/ArchitectureOverview|Architecture]] — app chrome and page structure context
