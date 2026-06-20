---
title: 'ADR-022: Domain-Driven Package Decomposition'
type: decision
tags:
  - type/decision
  - domain/governance
  - domain/architecture
created: '2026-06-19'
updated: '2026-06-19'
aliases:
  - ADR-022
  - domain-driven-decomposition
status: draft
source: agent
code-refs:
  - .specify/memory/constitution.md
  - AGENTS.md
---

# ADR-022: Domain-Driven Package Decomposition

## Status

Draft

## Context

The `anvil/services/` package has grown to **29 flat `.py` modules** (30 with `__init__.py`). This is a direct consequence of the **one-class-per-file rule** — a service like `dataset_import.py` is its own file, but so are its tightly-coupled result type (`import_result.py`), its value object (`parsed_sample.py`), and its error types. These 4+ files all belong to the same domain but are scattered across a flat namespace alongside unrelated services.

The existing sub-packages (`services/compute/`, `services/chunking/`, `db/models/`, `db/repositories/`, `api/v1/`) demonstrate that the project already uses domain-aligned sub-packaging in places. What's missing is a **governing principle** that tells maintainers:
1. *When* to create a sub-package (trigger threshold)
2. *How* to name it (plural nouns vs underscore-prefixed)
3. *What* goes in it (services + their tightly-coupled types)
4. *How* imports work across domains
5. *How* this pairs with the existing one-class-per-file and `__init__.py` ownership rules

Without this principle, the shallowness problem will recur. Every new service adds 2-3 support files (result type, error class) at the parent level under one-class-per-file, accelerating the namespace clutter.

### Current flat-module count by top-level package

| Package | Flat modules | Has sub-packages? | Notes |
|---------|:-:|:-:|-------|
| `anvil/services/` | 29 | Yes (2) | 🚩 exceeds 12x threshold |
| `anvil/db/` | 5 | Yes (2) | Fine — protocol + mixin + migration |
| `anvil/api/` | 2 | Yes (1) | Fine |
| `anvil/core/` | 5 | No | Fine |
| `anvil/storage/` | 2 | No | Fine |
| `anvil/supervisor/` | 2 | No | Fine |

## Decision

**Encode Domain-Driven Package Decomposition as Constitution Article X**, with the following rules:

### §10.1 — Domain threshold

When a package exceeds **12 peer `.py` modules**, evaluate for domain splits. This is a guideline, not a hard gate — a package with 11 tightly-related modules should stay flat, while a package with 8 modules from 3 distinct domains should split.

### §10.2 — Tight coupling rule

Result/error/value types that serve exactly one service module co-locate with that service in its domain sub-package. This directly addresses the one-class-per-file proliferation problem:

```
# Before (flat — 4 files for one domain concept):
services/
  dataset_import.py       # DatasetImportService
  import_result.py        # ← only used by dataset_import.py
  parsed_sample.py        # ← only used by dataset_import.py

# After (domain sub-package — 4 files, one directory):
services/datasets/
  __init__.py             # bare, docstring-only
  import_service.py       # DatasetImportService
  import_result.py        # co-located
  parsed_sample.py        # co-located
```

### §10.3 — Cross-domain shared types

Types used by 2+ domains go in `_shared/`. This is an internal infrastructure sub-package (underscore prefix).

### §10.4 — Naming

- **Domain sub-packages**: plural nouns (`training/`, `datasets/`, `compute/`)
- **Internal sub-packages**: underscore-prefixed (`_shared/`, `_types/`, `_errors/`)

### §10.5 — Nesting limit

Maximum 2 levels from the parent package root. Deeper nesting is replaced by longer, more explicit module names.

### §10.6–§10.9 — Pairing with existing rules

DDD does not override Article VI (`__init__.py` Ownership Policy), one-class-per-file, or the relative-imports-only rule. It enhances them by determining *where* a class file lives.

## Consequences

### Positive

- **Prevents namespace re-clutter**: Tightly-coupled result/error types are co-located with their service, not dumped at the parent level.
- **Clear import paths**: `from ..datasets.import_service import DatasetImportService` is self-documenting — you know the domain from the path.
- **Self-documenting boundaries**: A directory listing tells you the bounded contexts (`ls services/` shows `training/`, `datasets/`, `tracking/`, etc.).
- **Pairs naturally with one-class-per-file**: The rule that creates the clutter also makes the domains easy to identify (each file is one concept → natural clustering).
- **Compatible with existing infrastructure**: No changes to build, CI, or mypy config. The bare `__init__.py` pattern is already established.

### Negative

- **Import paths get longer**: `from .._shared.result_base import ResultBase` is longer than `from .result_base import ResultBase`. This is the cost of domain clarity.
- **Refactoring cost**: Splitting an existing flat package requires updating every import chain that crosses the old boundary. Mitigated by §10.9 (structural-change-only commits).
- **Over-splitting risk**: Aggressive maintainers might create a sub-package for every 3 modules. The 12-module threshold and nesting limit guard against this.

### Neutral

- **Not a hard-and-fast rule**: The threshold is a MUST EVALUATE, not a MUST SPLIT. A package with 13 tightly-integrated modules that all change together should stay flat.

## Compliance

- Enforced at merge review — new sub-packages without an `__init__.py` or with a non-docstring `__init__.py` are reject-worthy under Article VI.
- Vault audit will flag package directories that exceed the 12-module threshold as a recommendation (not a blocker) for evaluation.
- ADR-021 (`__init__.py` Ownership Policy) remains the authority on `__init__.py` rules.
