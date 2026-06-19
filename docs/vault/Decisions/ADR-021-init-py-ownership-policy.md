---
title: 'ADR-021: __init__.py Ownership Policy'
type: decision
tags:
  - type/decision
  - domain/governance
  - domain/architecture
created: '2026-06-19'
updated: '2026-06-19'
aliases:
  - ADR-021
  - init-py-ownership-policy
status: draft
code-refs:
  - AGENTS.md
  - .specify/memory/constitution.md
---
# ADR-021: `__init__.py` Ownership Policy

## Status

Draft

## Context

The anvil codebase was originally designed with a strict "No `__init__.py` (Strict)"
policy (Constitution Article VI, v1.4.0) that permitted only `anvil/__init__.py`
and required all sub-packages to be implicit namespace packages (PEP 420).

This policy was enforced via two prior sessions:
- A full audit that deleted 11 `__init__.py` files from sub-packages and rewired
  imports to direct module paths (see [[Sessions/2026-06-19-init-py-enforcement-audit]]).
- An import-ban enforcement that redirected all internal imports away from
  `__init__.py` re-export aggregators (see [[Sessions/2026-06-19-init-import-ban-enforcement]]).

### Problems with the strict policy

1. **Silent namespace collision risk** — PEP 420 implicit namespace packages are
   designed for splitting a namespace across multiple distributions. Using them
   for directories fully owned by one distribution means any third-party package
   could install files into `anvil.core`, `anvil.db`, etc., without detection.

2. **Tooling friction** — Many Python tools (mypy, pylint, coverage, IDEs) have
   subtle issues with implicit namespace packages. A bare `__init__.py` resolves
   these ambiguities by explicitly declaring "this directory is a package."

3. **Developer confusion** — The absence of `__init__.py` in directories that
   are clearly packages (containing `.py` modules, being imported as packages)
   violated the principle of least surprise for developers accustomed to
   standard Python packaging conventions.

4. **Inconsistency with `anvil/__init__.py`** — The root had an `__init__.py`
   but its sub-packages did not. This was arbitrary — either ALL levels are
   implicit namespace or NONE are.

## Decision

**Replace "No `__init__.py` (Strict)" with an `__init__.py` Ownership Policy.**

The rule is: every directory that is a fully-owned Python package level — a
directory containing `.py` modules that forms a complete, authoritative part
of the `anvil.*` namespace — MUST have a bare `__init__.py` to assert ownership
and designate it as a regular package.

### Specific rules

- **Authoritative levels** (fully owned by the `anvil` project) get a bare
  `__init__.py` — a docstring-only file describing the package's purpose.
  No re-exports, no imports.
- **Data-only directories** (`static/`, `templates/`, `data/`, `_resources/`,
  and similar non-Python-package directories) MUST NOT have `__init__.py`.
- All internal imports MUST continue to use direct module paths
  (`from .module import X`, not `from . import X`).
- No `__init__.py` may re-export symbols for internal consumption.
- Adding or removing `__init__.py` at a package level requires justification
  that the level is (or is not) a fully-owned authoritative namespace level.

### Directories that received `__init__.py`

| Directory | Purpose |
|-----------|---------|
| `anvil/core/` | Stdlib-only training engine |
| `anvil/db/` | Async SQLAlchemy database layer |
| `anvil/db/models/` | ORM model definitions |
| `anvil/db/repositories/` | Repository pattern data-access classes |
| `anvil/services/` | Business logic and orchestration |
| `anvil/services/chunking/` | Text chunking strategies |
| `anvil/services/compute/` | Compute backend abstraction |
| `anvil/api/` | FastAPI web server and presentation |
| `anvil/api/v1/` | API v1 route definitions |
| `anvil/storage/` | File storage abstraction |
| `anvil/supervisor/` | Background process manager |

### Directories correctly excluded

`anvil/data/`, `anvil/api/static/`, `anvil/api/templates/`, `anvil/_resources/`,
`anvil/_resources/migrations/` — these are data/resource directories, not Python
package levels.

## Consequences

### Positive

- Clear ownership assertion at every package level — no silent namespace collisions.
- Resolves tooling ambiguities (mypy, pylint, IDEs all work better with regular
  packages).
- Follows principle of least surprise for Python developers.
- The docstring-only constraint prevents the re-export wiring problem that the
  original deletion audit was trying to solve.

### Negative

- Breaks from the strict PEP 420 implicit-namespace orthodoxy — but the practical
  benefits outweigh the theoretical purity.
- The 11 `__init__.py` files are a maintenance surface (they must remain
  docstring-only; no imports may be added).

### Neutral

- The import rewrites from the prior enforcement sessions remain valid — imports
  use direct module paths, which is the correct pattern regardless of `__init__.py`
  presence.
- The import ban from `__init__.py` is still meaningful: since files are
  docstring-only, importing from them would be a no-op.

## Compliance

- Enforced at merge review — any `__init__.py` added to a data-only directory,
  or any `__init__.py` containing re-exports or imports, is reject-worthy.
- `make lint` must continue to pass (ruff's `__init__.py` per-file ignores
  already accommodate docstring-only files).
