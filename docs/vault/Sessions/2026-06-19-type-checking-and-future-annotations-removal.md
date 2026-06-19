---
title: 'Session: TYPE_CHECKING and from __future__ import annotations Removal'
type: session-log
tags:
  - type/session-log
  - domain/architecture
  - domain/governance
  - status/draft
created: '2026-06-19'
updated: '2026-06-19'
aliases:
  - 'Session: TYPE_CHECKING and Future Annotations Removal'
  - type-checking-removal
source: agent
---
# Session: TYPE_CHECKING and `from __future__ import annotations` Removal

**Date**: 2026-06-19
**Trigger**: Policy enforcement — "circular imports are an architecture problem, not a typing problem."

## Problem

The codebase had two crutches for circular/forward-reference imports:

1. **`TYPE_CHECKING`** — 10 files used `if TYPE_CHECKING:` blocks to import types that would otherwise create circular dependencies at module load time. The guard hid legitimate architecture problems (bidirectional coupling between modules).

2. **`from __future__ import annotations` (PEP 563)** — 49 files used this import, which turns all annotations into lazily-evaluated strings. This was added historically because Python <3.10 needed it for PEP 604 union syntax (`str | None`) and forward references. Since the project now targets Python 3.11+, PEP 604 syntax is valid everywhere, and string-literal forward refs work without deferred evaluation.

## What was fixed

### Phase 1: `TYPE_CHECKING` (10 files)

Every file's `if TYPE_CHECKING:` block was audited for whether the guarded import was:
- A type annotation dependency that could be moved to a direct module-level import (no actual circular dep existed), or
- A submodule that was already imported lazily inside function bodies (the TYPE_CHECKING was redundant)

Files fixed:
- `anvil/services/metrics_collectors.py` — `TrackingService` had no circular dep; moved to direct import
- `scripts/ci/graph_health/__init__.py` — removed entire TYPE_CHECKING block; submodules imported lazily in `run_all()`
- `scripts/ci/graph_health/scanner.py`, `topology.py`, `hygiene.py`, `prediction.py`, `scoring.py`, `temporal.py`, `structural.py`, `report.py` — moved `networkx` and package-internal types to module-level imports

### Phase 2: `from __future__ import annotations` (49 files)

All 49 files with this import were individually audited and the import was removed. The audit verified that every type annotation uses:
- Built-in types (`str`, `int`, `list`, etc.)
- Types imported at module level
- Types defined earlier in the same file
- String-literal forward references (e.g., `Mapped[list["CorpusFile"]]`)

The string-literal pattern works without PEP 563 because `"CorpusFile"` in `list["CorpusFile"]` is a string literal value passed to `__class_getitem__`, not a name lookup.

## Key discoveries

1. **`from __future__ import annotations` was entirely unnecessary** across the entire codebase. Every forward reference was already using string literals, and PEP 604 union syntax is native in Python 3.10+.

2. **String literals in subscript expressions** like `list["CorpusFile"]` and `Mapped["Corpus | None"]` are NOT name lookups — they're just values passed to `__class_getitem__`. This means forward references work fine without any deferred evaluation, even in complex nested generics like `Mapped[list["CorpusFile"]]`.

3. **`TYPE_CHECKING` was often guarding non-existent circular imports**. In `metrics_collectors.py`, the import of `TrackingService` was guarded but `tracking.py` never imported back — there was no circular dependency.

## Validation

- `grep` for `TYPE_CHECKING` and `from __future__ import annotations` across all `.py` files: **zero matches**
- `ast.parse()` on all 163 Python files: **all pass**
- `ruff check` on all modified files: **zero new errors** (all 7 remaining errors are pre-existing)
- Zero lint errors introduced

## AGENTS.md updated

Rule #9 broadened to forbid both `TYPE_CHECKING` and `from __future__ import annotations`, with guidance on string-literal forward references.

## Related

- [[Discoveries/from-future-annotations-unnecessary|`from __future__ import annotations` Is Unnecessary in a Python 3.11+ Codebase]]
