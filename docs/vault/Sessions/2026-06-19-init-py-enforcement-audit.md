---
title: 'Session: Full __init__.py Enforcement Audit'
type: session-log
tags:
  - type/session-log
  - domain/architecture
  - domain/governance
  - domain/vault
created: '2026-06-19'
updated: '2026-06-19'
aliases:
  - 'Session: Full __init__.py Enforcement Audit'
  - init-py-enforcement-audit
source: agent
---
# Session: Full `__init__.py` Enforcement Audit

**Date**: 2026-06-19
**Trigger**: AGENTS.md rule #6 (Implicit Namespace) allowed `__init__.py` in theory but was not actively enforced — 12 violating `__init__.py` files existed under `anvil/` and the `scripts/ci/graph_health/` package.

> **⚠️ SUPERSEDED 2026-06-19** — The policy was reversed later the same day. See [[Sessions/2026-06-19-__init__-py-ownership-policy|Session: __init__.py Ownership Policy]]. The new policy replaces "No `__init__.py` (Strict)" with an "`__init__.py` Ownership Policy" where authoritative namespace levels get bare `__init__.py` files and data-only directories do not. This session is kept as historical record of what was removed and why.

## What was done

### 1. Deleted 12 violating `__init__.py` files

All sub-package `__init__.py` files under `anvil/` were deleted. Only `anvil/__init__.py` (the top-level public API) remains:

| Deleted file | Notes |
|---|---|
| `anvil/core/__init__.py` | Re-exported `Value`, `LlamaModel`, `train`, `Tokenizer`, `Vocabulary` |
| `anvil/db/__init__.py` | Re-exported `models`, `Base`, `get_db` |
| `anvil/db/models/__init__.py` | Re-exported all 7 ORM model classes |
| `anvil/db/repositories/__init__.py` | Re-exported all 6 repository classes |
| `anvil/api/__init__.py` | Docstring-only |
| `anvil/api/v1/__init__.py` | Docstring-only |
| `anvil/services/__init__.py` | Re-exported `CorpusService`, `DatasetService`, `InferenceService`, `TrainingService` |
| `anvil/services/chunking/__init__.py` | Docstring-only |
| `anvil/services/compute/__init__.py` | Re-exported `ComputeResult`, `ComputeStatus`, registry functions |
| `anvil/storage/__init__.py` | Re-exported `FileInfo`, `FileStore`, `LocalFileStore` |
| `anvil/supervisor/__init__.py` | Re-exported `MLflowService`, `ProcessSupervisor`, etc. |

### 2. Refactored `scripts/ci/graph_health/__init__.py`

This file contained both shared types (8 dataclasses), a filter function, and the `GraphHealthRunner` class. Extracted into:

| New file | Content |
|---|---|
| `scripts/ci/graph_health/types.py` | All 8 dataclasses: `NoteMetadata`, `ConnectivityMetrics`, `TopologicalMetrics`, `HygieneMetrics`, `TemporalMetrics`, `StructuralMetrics`, `HealthScore`, `ScoredPair`, `LinkPredictionResult`, `GraphHealthReport` |
| `scripts/ci/graph_health/runner.py` | `EXCLUDED_DIRS`, `should_exclude()`, `GraphHealthRunner` |

Old `__init__.py` deleted.

### 3. Updated 13 import statements across 7 files

| File | Old import | New import |
|---|---|---|
| `anvil/services/inference.py` | `from .compute import get_backend, resolve_backend` | `from .compute.registry import get_backend` + `from .compute.resolve import resolve_backend` |
| `anvil/api/v1/datasets.py` | `from anvil.services.chunking import FixedSizeWindowChunker` | `from anvil.services.chunking.window_chunker import FixedSizeWindowChunker` |
| `tests/.../test_resolve.py` | `from anvil.services.compute import resolve_backend` | `from anvil.services.compute.resolve import resolve_backend` |
| `tests/.../test_registry.py` | `from anvil.services.compute import register, get_backend, available_backends` | `from anvil.services.compute.registry import ...` |
| `scripts/ci/vault_audit.py` | `from graph_health import GraphHealthRunner` | `from graph_health.runner import GraphHealthRunner` |
| All 8 graph_health submodules | `from . import <Type>` | `from .types import <Type>` |

### 4. Strengthened AGENTS.md rule #6

Rewrote from vague "Implicit Namespace" to strict "No `__init__.py` (Strict)" with 4 sub-rules and explicit merge-review enforcement.

### 5. Strengthened Constitution Article VI

Updated to match the stricter wording — only `anvil/__init__.py` is permitted, detailed sub-rules about direct module paths, and explicit enforcement at merge review.

## Post-hoc note (superseded)

The `__init__.py` files deleted in this session were later **recreated as bare docstring-only files** per the revised `__init__.py` Ownership Policy. The import statement rewrites (direct module paths) remain valid and were preserved — they do not depend on `__init__.py` re-exports.

## Key insight

Python 3.3+ namespace packages (PEP 420) make all of this seamless. Imports like `from anvil.db import models` continue to work because `models` is discovered as a sub-namespace-package from the filesystem — no `__init__.py` needed. The only imports that break are those that depend on `__init__.py` re-exports (e.g., `from anvil.services.compute import resolve_backend` requires the `__init__.py` to import it from the `resolve` module first).

## Tags

- type/session-log
- domain/architecture
- domain/governance
- domain/vault
- status/draft
