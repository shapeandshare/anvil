---
title: Design Canonization
type: session-log
tags:
  - type/session-log
  - domain/ui
  - domain/governance
created: '2026-06-14'
updated: '2026-06-14'
aliases:
  - 2026-06-14-design-canonization
source: agent
---
## Summary
Audited DESIGN.md v2.0.0 against the live hero page and CSS implementation. Found ~15 divergences including a missing 5th archetype, redesigned app shell (no bottom tab bar), forge brand theme (orange/yellow), ambient particles, expanded spacing tokens, and undocumented button/component variants. After confirming the forge redesign is canon, updated DESIGN.md to v2.1.0 and wrote a reference note documenting the divergence history.

## Files changed
- `DESIGN.md` — rewritten to v2.1.0: new Archetype E, updated app shell, forge theme documentation, expanded spacing scale, new button variants, ambient effects spec, updated Do's/Don'ts
- `docs/vault/Reference/design-divergence-resolution.md` — new discovery note

## Key decisions
- Bottom tab bar removed from spec (replaced by top tab-strip nav)
- Large-title nav bar removed from spec (tabs are the primary nav)
- Orange is now dual-purpose: warning semantic + forge brand accent (hero only)
- Ambient particles and radial gradient are now documented features present on all pages
- Hero card infinite bounce is canon (departure from restrained 150ms hover model)
- Gradient buttons (`btn-accent`, `btn--forge`) are official button variants

## Related

- [[Design/Design|Design]] — design system and canon
- [[Reference/design-divergence-resolution|Design Divergence Resolution]] — divergence history reference