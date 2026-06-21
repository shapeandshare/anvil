---
title: "Session: Graph Health Subsumption"
type: session-log
aliases:
  - 2026-06-19 Graph Health Subsumption
  - Graph Health Subsumption Session
source: agent
tags:
  - type/session-log
  - domain/governance
  - domain/tooling
created: 2026-06-19
updated: 2026-06-19
---

# Session: Graph Health Subsumption into Anvil

## Summary

Migrated all vault health CI scripts from `scripts/ci/` into a new `anvil/services/vault/` domain sub-package with proper project conventions. The legacy code included a 980-line `vault_audit.py` script, a 9-file `graph_health/` package (~2,500 lines), and 3 CI gate validators.

## What Was Done

- Created `anvil/services/vault/` with 17 Python files (~3,500 lines total)
- Migrated all 8 analysis modules (connectivity, topology, hygiene, temporal, structural, scoring, prediction, report) from `scripts/ci/graph_health/`
- Implemented `VaultHealthService` and `GraphHealthService` with async interfaces
- Created `anvil-vault` CLI with `audit`, `check-adrs`, `check-guarded-imports`, `check-bump-scope` subcommands
- Converted all legacy `@dataclass` types to Pydantic `BaseModel`
- Registered `vault-health` optional extra in `pyproject.toml`
- Updated `shared/vault.mk` to delegate to `anvil-vault`
- Replaced legacy `scripts/ci/` scripts with thin wrappers (deleted `graph_health/`)
- Added ADR-025 documenting the architecture decision

## Discoveries

- The `graph_health/` package had a tight coupling between `_is_spec_subfile` (shared between `connectivity.py` and `structural.py`), which required preserving cross-module import patterns
- The link prediction module (`prediction.py`) uses scikit-learn optionally via try/except ImportError, which is consistent with the project's lean dependency approach
- The legacy vault audit used bare `@dataclass` extensively (12+ types) — all successfully converted to BaseModel
- `mypy --strict` initially found 35+ type issues across the migrated code; all resolved

## Decisions

See `docs/vault/Decisions/ADR-034-vault-health-subsumption.md`

## Session Artifacts

- `anvil/services/vault/` — new domain sub-package (17 files)
- `shared/vault.mk` — updated to use `anvil-vault`
- `pyproject.toml` — added `vault-health` extra and `anvil-vault` script
- `scripts/ci/` — legacy scripts replaced with thin wrappers; `graph_health/` deleted

## Remaining

- Write unit test files in `tests/services/vault/` (test directory created, no tests yet)
- Full end-to-end validation: `make vault-audit` should produce identical output