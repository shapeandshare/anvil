---
title: CSP nonce does not cover inline onclick handlers
aliases: CSP nonce does not cover inline onclick handlers
type: discovery
tags:
  - type/discovery
  - domain/ui
  - status/draft
created: '2026-06-27'
updated: '2026-06-27'
source: agent
related: []
code-refs:
  - anvil/api/templates/operations.html
---
CSP `script-src 'nonce-...'` does not cover inline HTML event handler
attributes (`onclick="..."`, `onerror="..."`, etc.). Only `<script>`
elements with the matching nonce attribute are allowed to execute.
Event handlers must be attached programmatically via `addEventListener`
within a nonce-protected script block.

This applies to ALL templates served with the nonce-based CSP header.
The operations page was affected — every button did nothing when
clicked because the browser refused to execute the `onclick` handlers.

## References

- `anvil/api/templates/operations.html` (all onclick= removed)
- `anvil/api/app.py` (CSP header: `script-src 'self' 'nonce-{nonce}'`)
