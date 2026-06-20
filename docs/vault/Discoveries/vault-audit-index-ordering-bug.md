---
title: Vault Audit Index Ordering Bug
type: discovery
tags:
  - type/discovery
  - domain/vault
  - domain/tooling
  - status/reviewed
created: 2026-06-19
updated: 2026-06-19
aliases:
  - Vault Audit Index Ordering Bug
  - Wikilink False Positives
source: agent
code-refs:
  - anvil/services/vault/vault_audit.py
  - tests/services/vault/test_vault_audit.py
related:
  - "[[Decisions/ADR-025-vault-health-subsumption|ADR-025]]"
summary: >-
  VaultAuditService built its filename index in the same loop that
  validated wikilinks, so any link to a file sorting later alphabetically
  was wrongly reported as broken. Fixed with a two-pass approach.
---

# Vault Audit Index Ordering Bug

`VaultAuditService._run_mechanical_audit_sync` populated its
`filename_index` inside the **same** loop that resolved wikilinks. Because
`rglob("*.md")` results are sorted alphabetically and processed in order, a
wikilink pointing at a file whose stem sorts *after* the current file had
not yet been indexed — so it was reported as a broken `[[wikilink]]` even
though the target existed.

Concrete example: `Discoveries/Discoveries.md` (capital `D`, sorts early)
links to `[[Discoveries/css-tooltip-viewport-overflow]]` (lowercase `c`,
sorts later). The target file exists, but the link was flagged broken.

This single bug produced **69 of 141** false-positive audit errors across
the vault (every forward-reference to an alphabetically-later note).

## Fix

Split the mechanical audit into two passes:

1. **Pass 1** — walk all notes once and build the complete `filename_index`
   (and collect the `scannable` list, excluding `_meta`/`.obsidian`/`addons`).
2. **Pass 2** — validate schema and resolve wikilinks against the now-complete
   index.

A regression test (`test_forward_wikilink_not_flagged_broken`) asserts that a
forward link to an existing, alphabetically-later target
(`AnotherNote` → `[[OrphanNote]]`) is not flagged.

## Related cleanup

The same session synced `STATUS_VOCAB` in `vault_audit.py` and `hygiene.py`
to include `status/superseded`, which was already documented in
`docs/vault/_meta/tags.md` but missing from the code's vocabulary set.
