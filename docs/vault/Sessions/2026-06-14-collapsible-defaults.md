---
title: 'Session: Collapsible Output/Logs Defaults'
type: session-log
tags:
  - type/session-log
  - domain/ui
created: '2026-06-14'
updated: '2026-06-14'
aliases:
  - 2026-06-14-collapsible-defaults
source: agent
---
# Session: Collapsible Output/Logs Defaults

**Date**: 2026-06-14

## What was done

Changed the Output section on the training page and Service Logs section on the operations page to default to **collapsed** instead of expanded.

### Files changed

- `anvil/api/templates/archetypes/training.html`
  - Output header: `aria-expanded="true"` → `"false"`
  - Toggle icon: added `collapsed` class (rotates chevron -90°)
  - Output body: added `collapsed` class (sets `max-height: 0`)

- `anvil/api/templates/operations.html`
  - Restructured Service Logs section with collapsible infrastructure (was a static card)
  - Added clickable header with toggle chevron and `aria-expanded="false"`
  - Wrapped log content in `section-card__content-collapsible collapsed`
  - Added keyboard-accessible JS toggle handler

### Pattern

The collapsible section pattern used across both pages:

```
.section-card__header--clickable   → clickable header with role="button"
  .output-toggle-icon.collapsed    → chevron rotated -90° via CSS
.section-card__content-collapsible → overflow hidden, max-height transition
  .collapsed                       → max-height: 0, zero padding
```

CSS is in `anvil/api/static/css/archetypes.css` (lines 603-660).

## Related

- [[Design/Design|Design]] — UI design system and component patterns
- [[Reference/ArchitectureOverview|Architecture]] — app UI architecture context