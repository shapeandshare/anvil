---
created: '2026-06-19T00:00:00.000Z'
tags:
  - type/session-log
  - domain/content
  - domain/tooling
title: 'Session: CMS & Python Ecosystem Landscape Report'
type: session-log
updated: '2026-06-19T00:00:00.000Z'
aliases:
  - 'Session: CMS & Python Ecosystem Landscape Report'
source: agent
---
# Session: CMS & Python Ecosystem Landscape Report

## Summary

Authored a reference report cataloging Content Management Systems and the Python CMS/content ecosystem, framed against anvil's dataset/corpus/governance layer (which is, architecturally, a domain-specific headless content system managed outside MLflow). While validating the new note against `make vault-audit`, discovered and fixed a forward-reference resolution bug in the mechanical audit's wikilink resolver.

## What Was Done

- Wrote `Reference/ContentManagementLandscape.md` — CMS architectural categories, Python ecosystem catalog (Wagtail, Django CMS, Plone, Pelican/MkDocs/Sphinx, headless options, supporting libraries), an anvil-vs-Wagtail pattern comparison, recommendations, and a verdict (keep the bespoke FastAPI/SQLAlchemy headless layer; borrow patterns not packages).
- Linked the new note inbound from `index.md` (new "Data Management" Quick Links row) to avoid orphaning.
- Fixed a resolver bug in `anvil/services/vault/vault_audit.py`: the `filename_index` was populated incrementally inside the audit loop, so notes linking to alphabetically-later targets were falsely flagged as broken. Now the full index is pre-built before wikilink validation.
- Added regression test `test_forward_wikilink_resolves` in `tests/services/vault/test_vault_audit.py`.
- Recorded the discovery in `Discoveries/vault-audit-forward-wikilink-resolution-bug.md` and linked it from the Discoveries MOC.

## Discoveries

- See [[Discoveries/vault-audit-forward-wikilink-resolution-bug|Vault Audit Forward Wikilink Resolution Bug]]. The fix removed all spurious vault-wide broken-link errors (~10 canonical notes affected); only 3 genuinely-missing ADR targets in an unrelated note remain.
- The audit resolver strips directory prefixes (`rsplit("/", 1)[-1]`) and matches on bare stem, so full-path wikilinks were never the fix — the resolver itself was.

## Verification

- `pytest tests/services/vault/test_vault_audit.py` — 10 passed (9 existing + 1 new regression).
- `ruff check` + `mypy` on `vault_audit.py` — clean.
- `anvil-vault audit` — new notes produce zero findings; remaining errors are pre-existing (missing `code-refs` on old ADRs, 3 missing ADR link targets) and out of scope.

## Session Artifacts

- `docs/vault/Reference/ContentManagementLandscape.md` — new reference report
- `docs/vault/Discoveries/vault-audit-forward-wikilink-resolution-bug.md` — new discovery note
- `docs/vault/index.md`, `docs/vault/Discoveries/Discoveries.md` — inbound links added
- `anvil/services/vault/vault_audit.py` — resolver fix
- `tests/services/vault/test_vault_audit.py` — regression test

## Remaining

- Pre-existing audit warnings/errors (missing frontmatter on legacy session logs, missing `code-refs` on older ADRs, 3 missing ADR targets) remain unaddressed — out of scope for this session.
