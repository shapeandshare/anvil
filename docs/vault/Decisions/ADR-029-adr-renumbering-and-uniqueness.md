---
title: ADR Renumbering and Uniqueness Enforcement
type: decision
tags:
  - type/decision
  - domain/governance
  - domain/vault
created: 2026-06-19
updated: 2026-06-19
aliases:
  - ADR-029-adr-renumbering-and-uniqueness
source: agent
code-refs:
  - scripts/ci/check_adr_unique.py
  - docs/vault/Decisions/
  - scripts/ci/vault_audit.py
---

# ADR-029: ADR Renumbering and Uniqueness Enforcement

**Status**: Draft  
**Created**: 2026-06-19

## Context

Architecture Decision Records (ADRs) are the project's authoritative mechanism for recording decisions. Each ADR is expected to have a unique `ADR-0NN` identifier. A review discovered three identifier collisions:

| Collision | Files |
|-----------|-------|
| ADR-008 | `automated-semver-release` (earlier) + `data-page-tabbed-layout` (later) |
| ADR-016 | `mlflow-primary-lineage` (earlier) + `auto-db-migration` (later) |
| ADR-010 | `disable-local-mlflow-server` (official `ADR-010-`) + `numpy-docstring-enforcement` (used `010-` prefix without `ADR-`) |

Collisions break the "one number = one decision" contract and make wikilinks and cross-references ambiguous.

## Decision

1. **Renumber the later duplicate** in each collision to the next free sequential number (ADR-023 through ADR-025):
   - `data-page-tabbed-layout` → **ADR-023** (original ADR-008 retained)
   - `auto-db-migration` → **ADR-024** (original ADR-016 retained)
   - `numpy-docstring-enforcement` → **ADR-025** (original ADR-010 retained; also normalizes `010-` prefix to standard `ADR-0NN-` format)

2. **Fix all inbound wikilinks** in vault notes to point to the new filenames.

3. **Leave redirect stubs** at each old filename pointing to the new location.

4. **Enforce uniqueness going forward** via a gate (`scripts/ci/check_adr_unique.py` or folded into `vault_audit`) that rejects any change introducing a duplicate ADR identifier.

## Rationale

- Renumbering to sequential free numbers is the cleanest long-term invariant fix. Off-pattern filenames are normalized simultaneously.
- The vault-audit gate's link-resolution check verifies no broken links.
- The uniqueness gate prevents recurrence without human review.

## Alternatives considered

- **Slug-as-identifier** (rejected): using the full filename slug instead of the number as the canonical ID would preserve collision avoidance but break the human-readable "by-number" reference convention.
- **Grandfather existing collisions** (rejected): leaves the spatial issue unresolved permanently.
- **No redirect stubs** (rejected): redirects handle readers/bookmarks that used the old name; they are short, auditable, and trivially maintained.

## Status

Renumbering and link fixes applied. Uniqueness enforced by `scripts/ci/check_adr_unique.py`.

## See Also

- [[Decisions/README|Decisions]]
