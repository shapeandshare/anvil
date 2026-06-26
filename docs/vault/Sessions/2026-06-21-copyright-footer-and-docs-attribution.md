---
title: Copyright Footer and Docs Attribution — 2026-06-21
type: session-log
tags:
  - domain/governance
  - type/session-log
  - domain/ui
  - domain/tooling
created: '2026-06-21'
updated: '2026-06-21'
status: draft
source: agent
aliases:
  - Copyright Footer and Docs Attribution
---
# Copyright Footer and Docs Attribution

**Date**: 2026-06-21
**Context**: User requested copyright attribution across code, docs, and website for Josh Burt, findable but not over-the-top. Follow-up to 2026-06-20 bulk header addition — closes remaining gaps in non-source surfaces.

## Audit Findings

Exhaustive search found source code was already well-covered (424+ files with `Copyright © 2026 Josh Burt` headers). Gaps were in three specific surfaces:

| Gap | Impact |
|-----|--------|
| Website footer | No visible copyright on any page (only `/about` had "Built with 🔨 by Josh Burt") |
| README.md License section | No explicit `Copyright ©` line — just "Released under the MIT License" |
| CONTRIBUTING.md | No copyright notice at all |

Intentionally skipped: SVGs (decorative, not typically claimed), vault docs (internal artifacts), specs (covered by LICENSE legally).

## What Was Done

### 1. Website footer (`anvil/api/templates/base.html`)

Added a single `<footer>` element before `</body>` using design system tokens for consistency:
```html
<footer style="text-align:center;padding:var(--space-4) var(--space-3);
  font-size:var(--font-size-xs);color:var(--text-tertiary);
  border-top:1px solid var(--border-subtle);margin-top:var(--space-6);">
  &copy; 2026 Josh Burt &mdash; MIT License
</footer>
```

- Inherits theme colors via CSS custom properties — no new CSS needed
- `--text-tertiary` for subtlety, `--border-subtle` for a light separator
- Renders on **every page** via inheritance from base.html

### 2. README.md License section

Added `Copyright &copy; 2026 Josh Burt.` before the existing "Released under the MIT License." text.

### 3. CONTRIBUTING.md

Appended `&copy; 2026 Josh Burt. Released under the MIT License.` at the end of the file.

## Files Changed

```
3 files changed, 9 insertions(+), 2 deletions(-)
```

## References

- `anvil/api/templates/base.html` — layout template (inherited by all pages)
- `README.md` — project front page
- `CONTRIBUTING.md` — contributor guide
- `docs/vault/Sessions/2026-06-20-copyright-header-attribution.md` — prior session (bulk source headers)

## Related

- [[Sessions/2026-06-20-copyright-header-attribution|Copyright Header Attribution]] — prior session (bulk source headers)
- [[Design/Design|Design]] — UI design system including footer component
- [[Governance/Constitution|Governance]] — governance policies for copyright and licensing
