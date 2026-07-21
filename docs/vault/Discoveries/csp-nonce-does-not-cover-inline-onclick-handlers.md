---
title: CSP nonce does not cover inline onclick handlers
aliases: CSP nonce does not cover inline onclick handlers
type: discovery
tags:
  - type/discovery
  - domain/ui
  - status/draft
created: '2026-06-27'
updated: '2026-07-21'
source: agent
related: []
code-refs:
  - anvil/api/templates/operations.html
  - anvil/api/templates/archetypes/models.html
  - anvil/api/templates/archetypes/model_detail.html
  - anvil/api/templates/teach.html
  - anvil/api/templates/datasets.html
  - anvil/api/templates/dataset_curation.html
  - anvil/api/templates/data_add.html
  - anvil/api/templates/data_sources.html
  - anvil/api/templates/archetypes/training.html
  - anvil/api/templates/archetypes/playground.html
  - anvil/api/templates/archetypes/experiment.html
  - anvil/api/templates/archetypes/content_library.html
  - anvil/api/templates/config.html
---
CSP `script-src 'nonce-...'` does not cover inline HTML event handler
attributes (`onclick="..."`, `onerror="..."`, etc.). Only `<script>`
elements with the matching nonce attribute are allowed to execute.
Event handlers must be attached programmatically via `addEventListener`
within a nonce-protected script block.

This applies to ALL templates served with the nonce-based CSP header.
The operations page was affected — every button did nothing when
clicked because the browser refused to execute the `onclick` handlers.

## Recurrence (2026-07-21)

This exact mistake recurred at much larger scale: a code-generation pass
converting 15 navigation `<a href>` elements to `<button>` (across 13
templates, per [[Decisions/ADR-050-nav-cta-button-styling-override|ADR-050]])
added `onclick="window.location.href='...'"` to every one of them. All 15
buttons were silently non-functional — clicking did nothing, with a CSP
violation logged to console on each click. The bug was NOT caught by:

- `node --check` / JS syntax validation (onclick= is syntactically valid JS)
- `scripts/ci/ux_lint.py` (`make ux-lint`) — has no notion of CSP header
  configuration, cannot statically prove an `onclick=` attribute is dead
- `lsp_diagnostics` / Biome (flags Jinja `{% %}` as parse errors, unrelated)

It was only caught by manually re-reading the CSP header in `app.py` and
then verifying with a REAL Playwright click-through against a running
server. Static syntax/lint checks are necessary but **not sufficient**
for CSP-relevant interactive elements — always verify with an actual
browser click when adding/converting `onclick`-style navigation.

**Actionable follow-up**: consider extending `scripts/ci/ux_lint.py` with
a regex check that flags any `onclick="` attribute in a template known to
be served behind the nonce-based CSP (i.e., any template extending
`base.html` that is not `/docs`/`/redoc`/`/openapi.json`) as an S4 finding.
This would catch the mistake mechanically before it reaches a browser test.

## References

- `anvil/api/templates/operations.html` (original incident, all onclick= removed)
- `anvil/api/app.py` (CSP header: `script-src 'self' 'nonce-{nonce}'`)
- [[Decisions/ADR-050-nav-cta-button-styling-override|ADR-050: Navigation CTA Elements Rendered as button]] (recurrence, 15 buttons across 13 templates)
