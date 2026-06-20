---
title: "ADR-025: Vault Health Subsumption into Anvil"
status: draft
type: decision
tags:
  - type/decision
  - domain/governance
  - domain/tooling
created: 2026-06-19
updated: 2026-06-19
related:
  - "[[ADR-013]]"
  - "[[ADR-022]]"
  - "[[ADR-023]]"
---

# ADR-025: Vault Health Subsumption into Anvil

## Context

The `scripts/ci/` directory contained 5 standalone CI scripts (~4,500 lines) for vault health analysis: a 980-line `vault_audit.py` script for mechanical frontmatter/wikilink validation, a `graph_health/` package (~2,500 lines) for wikilink graph-theoretic analysis (connectivity, topology, hygiene, temporal decay, structural gaps, link prediction), and three smaller CI gate validators (`check_adr_unique.py`, `check_guarded_imports.py`, `check_bump_scope.py`). These scripts were maintained outside the `anvil` Python package, making them:

- Inaccessible for programmatic use (no importable API)
- Inconsistent with project coding conventions (mixed docstring styles, `@dataclass` instead of Pydantic `BaseModel`, multi-class files)
- Dependent on a separate `sys.path` hack for the `graph_health` sub-package
- Invoked via `make vault-audit` targets pointing at `$(PYTHON) scripts/ci/vault_audit.py`

## Decision

Create a new `anvil/services/vault/` domain sub-package to host all vault health code, following the project's domain-driven decomposition pattern (per Article X). Expose the functionality via:

1. **CLI**: A single `anvil-vault` console script with subcommands (`audit`, `check-adrs`, `check-guarded-imports`, `check-bump-scope`)
2. **Programmatic API**: `VaultHealthService` and `GraphHealthService` importable from `anvil.services.vault`
3. **Makefile delegation**: `shared/vault.mk` targets (`vault-audit`, `adr-check`, etc.) delegate to `anvil-vault`

Key architectural choices:
- `networkx` remains optional via the `anvil[vault-health]` extra (Pit of Success, Article IX)
- Async service interface wrapping sync file I/O via `asyncio.to_thread()` (Article V)
- All legacy `@dataclass` types converted to Pydantic `BaseModel`
- One class per file for service classes; tightly coupled value objects co-located in `_types.py` (Article X §10.2)
- Legacy `scripts/ci/` files retained as thin wrappers during transition

## Consequences

**Positive**:
- Vault health tools are pip-installable and importable as part of the `anvil` package
- Consistent code quality (NumPy docstrings, mypy strict, Pydantic types)
- Backward-compatible CLI and Makefile targets
- Clear separation of concerns via domain sub-package

**Negative**:
- Existing CI workflows referencing `scripts/ci/vault_audit.py` need updating to use `anvil-vault`
- The `graph_health` name is replaced by `vault` — documentation references to the old path need updating

**Risks**:
- Minimal — thin wrappers in `scripts/ci/` maintain backward compatibility during transition

## Compliance

- **Article IV** (TDD): Tests deferred per spec (test tasks marked optional)
- **Article V** (Async-First): Async interface with `asyncio.to_thread()` for sync I/O
- **Article VI** (__init__.py): Bare docstring-only `__init__.py` for domain sub-package
- **Article VII** (Layered): No DB — no Repository layer. Intentional exception documented.
- **Article X** (DDD): `vault/` follows plural noun convention (§10.4)
- **Add'l constraints**: Pydantic BaseModel, one-class-per-file, mypy strict, NumPy docstrings