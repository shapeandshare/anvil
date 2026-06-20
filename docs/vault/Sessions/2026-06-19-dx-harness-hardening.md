---
title: Session — 2026-06-19 — DX Hardening Implementation
type: session-log
aliases:
  - 2026-06-19 DX Harness Hardening
  - DX Hardening Implementation
source: agent
tags:
  - type/session-log
  - domain/tooling
  - domain/governance
  - domain/infrastructure
created: '2026-06-19'
updated: '2026-06-19'
summary: >-
  Implemented automated CI enforcement, governance reconciliation, onboarding
  docs, and structural route decomposition for the DX hardening feature.
---
# Session — 2026-06-19 — DX Hardening Implementation

**Date**: 2026-06-19
**Feature**: 013-dx-harness-hardening — Developer & Agent Experience hardening: closing the gap between declared and enforced discipline.

## Summary

Implemented the full spec across all four priority workflows. Key outcomes: automated CI enforcement, governance reconciliation, onboarding documentation, and structural decomposition of the route layer.

### Workstream 1 — Enforcement (P1)

- Created `.github/workflows/ci.yml` with 5 gate jobs (lint, typecheck, test+coverage, vault-audit, bump-scope-guard) on every PR, fail-closed
- Wrote `scripts/ci/check_bump_scope.py` to classify version-only bumps (FR-006a exemption)
- Set `pyproject.toml [tool.coverage.report] fail_under` from 100 → 23 (the measured baseline)

### Workstream 2 — Governance Consistency (P2)

- Amended Constitution v1.6.0→1.7.0: Article IV (coverage racheting), Additional Constraints (TYPE_CHECKING conditional-allow), Development Workflow (CI-enforced gates)
- Aligned AGENTS.md Principle 10 with constitution
- Wrote `scripts/ci/check_guarded_imports.py` — machine-checked annotation-only discipline
- Wrote `scripts/ci/check_adr_unique.py` — ADR identifier uniqueness enforcement
- Resolved 3 ADR collisions: ADR-008→ADR-023, ADR-016→ADR-024, 010-prefix→ADR-025
- Authored 4 new ADRs (ADR-026–029): coverage ratcheting, TYPE_CHECKING conditional-allow, CI merge gates, ADR renumbering
- Refactored `anvil/services/inference/inference.py`: removed unnecessary TYPE_CHECKING guard
- Added cycle-comment annotations to `anvil/db/models/corpus.py` and `corpus_file.py`
- Added `make adr-check` and `make guarded-imports-check` targets to `shared/vault.mk`

### Workstream 3 — Onboarding (P3)

- Created `ARCHITECTURE.md`: layering model, routing table, "how to add a service"
- Expanded `CONTRIBUTING.md`: full gate table, branch protection documentation, coverage policy
- Created `docs/vault/Decisions/README.md`: human-readable ADR index

### Workstream 4 — Structural Refactors (P4)

- Created `anvil/workbench.py`: `AnvilWorkbench` expanded from single-service stub to full god class exposing `TrainingService`, `TrackingService`, `InferenceService`, `SafetensorsExportService`
- Decomposed `anvil/api/v1/router.py` from 1958→45 lines: extracted `health_ops.py` (319 lines), `pages.py` (177 lines), `learning.py` (1423 lines)

## Files Changed

- 20+ new files (scripts, tests, ADRs, docs, route modules, workbench)
- 15 modified files (pyproject.toml, inference.py, ORM models, AGENTS.md, constitution, CONTRIBUTING.md, vault.mk, vault index, session logs)

## Key Decisions

1. Coverage threshold set to measured baseline (23%) with racheting-upward-only policy (ADR-026)
2. TYPE_CHECKING conditional-allow with 4-point exception discipline + machine-checkable enforcement (ADR-027)
3. CI gates are fail-closed — bump-scope exemption only for version-only changes (ADR-028)
4. ADR collisions resolved via renumbering + link fixes + stub removal (ADR-029)

## Vault Enrichment

- [[Decisions/ADR-026-coverage-ratcheting-baseline]]
- [[Decisions/ADR-027-type-checking-conditional-allow]]
- [[Decisions/ADR-028-ci-merge-gate-enforcement]]
- [[Decisions/ADR-029-adr-renumbering-and-uniqueness]]

## Tags

- `type/session-log`
- `domain/tooling`
- `domain/governance`
- `domain/infrastructure`
