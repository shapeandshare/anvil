---
title: "Session: Vault Audit Cleanup — Zero Errors"
type: session-log
tags:
  - type/session-log
  - domain/vault
  - domain/tooling
created: 2026-06-19
updated: 2026-06-19
aliases:
  - "Session: Vault Audit Cleanup"
source: agent
---

# Session: Vault Audit Cleanup — Zero Errors

**Date**: 2026-06-19
**Branch**: opencode/proud-cactus
**Status**: Completed

## Summary

Drove `anvil-vault audit` from **141 errors to 0**. The largest single cause
(69 errors) was a bug in the audit tool itself; the remainder were genuine
missing-frontmatter and stale-link issues across decision, discovery, and
session notes.

## Changes

### Tooling fix (root cause of 69 false positives)

- **`anvil/services/vault/vault_audit.py`** — `VaultAuditService` built its
  `filename_index` in the same loop that validated wikilinks, so links to
  alphabetically-later files were wrongly reported broken. Split into a
  two-pass approach (build full index, then validate). See
  [[Discoveries/vault-audit-index-ordering-bug|Vault Audit Index Ordering Bug]].
- **`tests/services/vault/test_vault_audit.py`** — added regression test
  `test_forward_wikilink_not_flagged_broken` (TDD: written failing first).

### Vocabulary sync

- **`anvil/services/vault/vault_audit.py`**, **`anvil/services/vault/hygiene.py`**
  — added `status/superseded` to `STATUS_VOCAB`. It was already documented in
  `docs/vault/_meta/tags.md` but missing from the code, so
  `Discoveries/from-future-annotations-unnecessary.md` (legitimately
  superseded) was flagged.

### Content fixes

- Added `code-refs:` to 23 decision/discovery notes that lacked them.
- Added `aliases:` / `source:` to ~45 agent notes (decisions, discoveries,
  session logs) that predated the schema requirement.
- Fixed 3 stale `related:` wikilinks in
  `Decisions/ADR-025-vault-health-subsumption.md` (bare `[[ADR-013]]` etc. →
  full path-qualified links to existing ADRs).
- Linked the new discovery note from `Discoveries/Discoveries.md`.

## Verification

- `anvil-vault audit --vault-dir docs/vault` → **0 errors** (was 141).
- `pytest tests/services/vault/` → 46 passed.
- `mypy` clean on changed source files; `ruff` clean.

## Notes

- The pre-existing repo-wide `black --check .` non-conformance (113 files on
  the base branch) is out of scope; changed files match their surrounding
  existing style and pass `ruff`/`mypy`.
- Remaining audit output is WARN-level only (older notes with no frontmatter),
  which does not fail the error gate.
