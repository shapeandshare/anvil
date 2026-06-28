---
title: 'Session: Constitution Mechanical Checks — Automating Enforcement of All 45 Agent Mandates'
type: session-log
tags:
  - type/session-log
  - domain/tooling
  - domain/governance
  - domain/vault
created: '2026-06-27'
updated: '2026-06-27'
aliases:
  - Session: Constitution Mechanical Checks
  - constitution-mechanical-checks
status: draft
source: agent
code-refs:
  - anvil/services/vault/check_init_py_ownership.py
  - anvil/services/vault/check_relative_imports.py
  - anvil/services/vault/check_one_class.py
  - anvil/services/vault/check_import_placement.py
  - anvil/services/vault/check_nesting_depth.py
  - anvil/services/vault/check_py_typed.py
  - anvil/services/vault/check_core_deps.py
  - anvil/services/vault/check_layer_boundaries.py
  - anvil/services/vault/cli.py
  - shared/vault.mk
  - .github/workflows/ci-workflow.yml
  - tests/services/vault/test_check_init_py.py
  - tests/services/vault/test_check_relative_imports.py
  - tests/services/vault/test_check_one_class.py
  - tests/services/vault/test_check_import_placement.py
  - tests/services/vault/test_check_nesting_depth.py
  - tests/services/vault/test_check_py_typed.py
  - tests/services/vault/test_check_core_deps.py
  - tests/services/vault/test_check_layer_boundaries.py
---

# Session: Constitution Mechanical Checks — Automating Enforcement of All 45 Agent Mandates

**Date**: 2026-06-27
**Trigger**: Audit of all 45 agent mandates from AGENTS.md revealed 20 fully audit-ready (Category A), 16 needing operational definitions (Category B), and 3 not yet actionable as metrics (Category C). The session implemented automated mechanical enforcement for all Category A gaps that lacked tooling.

## What was done

### 1. Audit gap analysis

Analyzed all 45 agent mandates from AGENTS.md + constitution.md against existing tooling coverage. Found:

- **Already tooled**: 12 mandates (ruff, mypy, anvil-vault, ux-lint)
- **Not yet tooled (actionable gaps)**: 8 mandates with no automated check — these were implemented

### 2. Eight constitution check modules created

All modules follow the established `anvil/services/vault/check_*.py` pattern (NumPy docstrings, `@dataclass` result types, `main()` CLI entry point, exit 0/1).

| Module | CLI subcommand | What it enforces | Constitution rule |
|--------|---------------|-------------------|-------------------|
| `check_init_py_ownership.py` | `check-init-py` | `__init__.py` ownership policy in `anvil/` source tree | Art VI, Principle 6 |
| `check_relative_imports.py` | `check-relative-imports` | No absolute `from anvil.` imports inside the package | Principle 7 |
| `check_one_class.py` | `check-one-class` | One class per file (enums/exceptions allowed as companions) | Additional Constraints |
| `check_import_placement.py` | `check-import-placement` | Imports at top of file; lazy imports only for capability detection | Architecture Rules |
| `check_nesting_depth.py` | `check-nesting` | Max 2 levels of package nesting from `anvil/` | Art X §10.5 |
| `check_py_typed.py` | `check-py-typed` | PEP 561 `py.typed` marker exists + configured in `pyproject.toml` | Packaging Conventions |
| `check_core_deps.py` | `check-core-deps` | `anvil/core/` has zero third-party dependencies | Art I |
| `check_layer_boundaries.py` | `check-layers` | Layer discipline: Routes → God Class → Services → Repositories → DB | Art VII, Principle 5 |

### 3. CLI wiring (`cli.py`)

All 8 subcommands registered in `build_parser()`, `main()` dispatch, and `_cmd_*` handler functions following existing patterns (env var passthrough, lazy import of checker `main()`).

### 4. Makefile targets (`shared/vault.mk`)

9 new targets:

```
make check-init-py          make check-one-class         make check-nesting
make check-relative-imports  make check-import-placement  make check-py-typed
make check-core-deps        make check-layers
make constitution-check     # runs all 8 sequentially
```

### 5. CI gate (`.github/workflows/ci-workflow.yml`)

New `constitution-check` job added as a merge gate, depends on `bump-scope-guard`, listed in `gate-status` summarizer. Runs `make constitution-check` after `make setup`.

### 6. Eight test files (`tests/services/vault/`)

| File | Tests |
|------|-------|
| `test_check_init_py.py` | 7 tests — valid packages, missing init, data dirs, imports in init |
| `test_check_relative_imports.py` | 7 tests — relative pass, absolute fail, TYPE_CHECKING allow, suppression |
| `test_check_one_class.py` | 8 tests — one class pass, multi fail, enum/exception companions, suppression |
| `test_check_import_placement.py` | 7 tests — top-of-file pass, lazy fail, try/except allow, suppression |
| `test_check_nesting_depth.py` | 17 tests — depth 1/2 pass, 3+ fail, skip dirs, mixed |
| `test_check_py_typed.py` | 7 tests — exists/empty pass, missing/content fail, package-data config |
| `test_check_core_deps.py` | 26 tests — stdlib pass, third-party fail, TYPE_CHECKING skip, intra-package |
| `test_check_layer_boundaries.py` | 28 tests — all layer violations, clean files, unknown layers, stdlib |

### 7. Bugs fixed

- **`check_init_py_ownership.py`**: `ast.Str` was removed in Python 3.14 — replaced with `ast.Constant` only
- **`check_py_typed.py`**: `main()` read `sys.argv[1]` directly, which was the subcommand name when called from the CLI handler. Changed to accept optional `argv` parameter

## Vault health

Pre-audit: Ran `make vault-audit` — must pass 0 errors before commit.

## Changes made

| Entity | Action |
|--------|--------|
| `anvil/services/vault/check_init_py_ownership.py` | **CREATED** — 247 lines |
| `anvil/services/vault/check_relative_imports.py` | **CREATED** — 177 lines |
| `anvil/services/vault/check_one_class.py` | **CREATED** — 212 lines |
| `anvil/services/vault/check_import_placement.py` | **CREATED** — 241 lines |
| `anvil/services/vault/check_nesting_depth.py` | **CREATED** — 136 lines |
| `anvil/services/vault/check_py_typed.py` | **CREATED** — 164 lines |
| `anvil/services/vault/check_core_deps.py` | **CREATED** — 471 lines |
| `anvil/services/vault/check_layer_boundaries.py` | **CREATED** — 268 lines |
| `anvil/services/vault/cli.py` | **UPDATED** — 8 subcommands + handlers wired in |
| `anvil/services/vault/__init__.py` | **UPDATED** — docstring lists all new checks |
| `shared/vault.mk` | **UPDATED** — 9 new make targets |
| `.github/workflows/ci-workflow.yml` | **UPDATED** — constitution-check CI gate |
| `tests/services/vault/test_check_init_py.py` | **CREATED** — 7 tests |
| `tests/services/vault/test_check_relative_imports.py` | **CREATED** — 7 tests |
| `tests/services/vault/test_check_one_class.py` | **CREATED** — 8 tests |
| `tests/services/vault/test_check_import_placement.py` | **CREATED** — 7 tests |
| `tests/services/vault/test_check_nesting_depth.py` | **CREATED** — 17 tests |
| `tests/services/vault/test_check_py_typed.py` | **CREATED** — 7 tests |
| `tests/services/vault/test_check_core_deps.py` | **CREATED** — 26 tests |
| `tests/services/vault/test_check_layer_boundaries.py` | **CREATED** — 28 tests |

## See also

- [[Decisions/ADR-019-pydantic-basemodel-over-dataclass|ADR-019]] — Pydantic BaseModel over Dataclass (enforced by check-one-class)
- [[Decisions/ADR-020-one-class-per-file|ADR-020]] — One Class Per File (enforced by check-one-class)
- [[Decisions/ADR-021-init-py-ownership-policy|ADR-021]] — `__init__.py` Ownership (enforced by check-init-py)
- [[Decisions/ADR-025-numpy-docstring-enforcement|ADR-025]] — NumPy Docstring Enforcement
- [[Decisions/ADR-027-type-checking-conditional-allow|ADR-027]] — TYPE_CHECKING Exception Discipline
- [[Decisions/ADR-028-ci-merge-gate-enforcement|ADR-028]] — CI Merge Gate Enforcement (updated by this session)
- [[Decisions/ADR-034-vault-health-subsumption|ADR-034]] — Vault Health Subsumption (pattern followed)
- [[Decisions/ADR-041-simplicity-first-boring-technology|ADR-041]] — Simplicity First (enforced by all checks)
- `AGENTS.md` — Agent Behavioral Principles (project root, source of truth for mandates)
- `.specify/memory/constitution.md` — Constitution (project root, canonical rules enforced)
