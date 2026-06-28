---
title: 'Session: Mechanical Constitution Remediation — Fixing All Enforcement Gaps Across the Codebase'
type: session-log
tags:
  - type/session-log
  - domain/tooling
  - domain/governance
  - domain/vault
created: '2026-06-28'
updated: '2026-06-28'
aliases:
  - Session: Mechanical Constitution Remediation
  - constitution-remediation
status: draft
source: agent
code-refs:
  - anvil/api/v1/router.py
  - anvil/api/v1/datasets.py
  - anvil/api/v1/health_ops.py
  - anvil/api/v1/learning.py
  - anvil/api/v1/stream_event.py
  - anvil/api/v1/transport.py
  - anvil/api/v1/inference.py
  - anvil/api/v1/inference_schemas.py
  - anvil/api/v1/schemas.py
  - anvil/api/v1/schemas_dataset.py
  - anvil/api/v1/schemas_governance.py
  - anvil/api/v1/schemas_content.py
  - anvil/api/v1/schemas_corpus.py
  - anvil/api/v1/schemas_eval.py
  - anvil/api/v1/schemas_misc.py
  - anvil/api/v1/config.py
  - anvil/api/v1/corpora.py
  - anvil/api/v1/eval.py
  - anvil/api/v1/eval_datasets.py
  - anvil/api/v1/governance.py
  - anvil/api/v1/registry.py
  - anvil/api/v1/content.py
  - anvil/client/_shared/stream_event.py
  - anvil/client/_shared/transport.py
  - anvil/client/_shared/api_error.py
  - anvil/client/_shared/authentication_error.py
  - anvil/client/_shared/connection_error.py
  - anvil/client/_shared/not_found_error.py
  - anvil/client/_shared/rate_limit_error.py
  - anvil/client/_shared/server_error.py
  - anvil/client/_shared/validation_error.py
  - anvil/core/engine.py
  - anvil/services/training/torch_engine.py
  - anvil/services/compute/local_torch_backend.py
  - anvil/services/compute/modal_backend.py
  - anvil/services/datasets/corpora.py
  - anvil/services/datasets/dataset_curation.py
  - anvil/services/vault/types_note_metadata.py
  - anvil/services/vault/types_connectivity_metrics.py
  - anvil/services/vault/types_topological_metrics.py
  - anvil/services/vault/types_hygiene_metrics.py
  - anvil/services/vault/types_temporal_metrics.py
  - anvil/services/vault/types_structural_metrics.py
  - anvil/services/vault/types_health_score.py
  - anvil/services/vault/types_scored_pair.py
  - anvil/services/vault/types_link_prediction_result.py
  - anvil/services/vault/types_finding.py
  - anvil/services/vault/types_mechanical_report.py
  - anvil/services/vault/types_graph_health_report.py
  - anvil/services/vault/connectivity.py
  - anvil/services/vault/hygiene.py
  - anvil/services/vault/prediction.py
  - anvil/services/vault/report.py
  - anvil/services/vault/scanner.py
  - anvil/services/vault/scoring.py
  - anvil/services/vault/structural.py
  - anvil/services/vault/temporal.py
  - anvil/services/vault/topology.py
  - anvil/services/vault/vault_audit.py
  - anvil/services/vault/vault_health_service.py
  - anvil/db/models/__init__.py
  - anvil/_resources/migrations/versions/__init__.py
  - anvil/workbench.py
  - tests/services/vault/test_report.py
  - tests/services/vault/test_scanner.py
  - tests/services/vault/test_scoring.py
  - tests/unit/services/test_vault_connectivity.py
  - tests/unit/services/test_vault_hygiene.py
  - tests/unit/services/test_vault_scoring.py
  - tests/unit/services/test_vault_structural.py
  - tests/unit/services/test_vault_topology.py
---

# Session: Mechanical Constitution Remediation — Fixing All Enforcement Gaps

**Date**: 2026-06-28
**Trigger**: Fresh `make constitution-check` revealed 89 violations across 6 of 9 constitution checks. This session ran 15 parallel subagents to remediate systematically.

## What was done

### 1. Relative imports (51 violations fixed)

Converted absolute `from anvil.X` imports to relative imports in 6 files:

| File | Violations fixed |
|------|-----------------|
| `anvil/api/v1/router.py` | 16 |
| `anvil/api/v1/datasets.py` | 12 |
| `anvil/client/_shared/transport.py` | 10 |
| `anvil/api/v1/health_ops.py` | 7 |
| `anvil/api/v1/learning.py` | 5 |
| `anvil/client/_shared/stream_event.py` | 1 |

**Remaining**: 2 violations in `anvil/_resources/migrations/env.py` — Alembic's `importlib` loading mechanism prevents relative imports (documented in-file).

### 2. `__init__.py` ownership (2 violations fixed)

- **`anvil/db/models/__init__.py`**: Stripped import block (model registration re-exports). Kept copyright + docstring only.
- **`anvil/_resources/migrations/versions/__init__.py`**: Created bare docstring-only `__init__.py`.

**Remaining**: 1 violation in `anvil/data/demo/small/hello-world/` — tool flags it because immediate dirname `hello-world` isn't in the data-dir skip list, but the Constitution Article VI says the entire `data/` tree is data-only and must NOT have `__init__.py`.

### 3. Layer boundaries (11 violations fixed)

Refactored two route files to go through the `AnvilWorkbench` god class instead of importing services/repositories directly:

- **`anvil/api/v1/datasets.py`** (9 violations): Removed direct imports from `db.models`, `db.repositories`, `services`. Added methods to `DatasetCurationService` (``get_sample``, ``update_sample_text``, ``get_active_samples``, ``get_operations``, ``get_active_texts``). Added `scan_and_chunk` method to `corpora.py`. Added `tracking` property to `AnvilWorkbench` and re-exported `AuditAction`/`AuditOutcome` as class attributes.
- **`anvil/api/v1/learning.py`** (2 violations): Removed `InferenceService`/`TrackingService` direct instantiation. Added `inference`/`tracking` properties to `AnvilWorkbench`. Routes now use `Depends(get_workbench)`.

### 4. One-class-per-file (3 major splits)

- **`anvil/api/v1/schemas.py`** (42 classes → 7 domain files): Split into `schemas_dataset.py`, `schemas_governance.py`, `schemas_content.py`, `schemas_corpus.py`, `schemas_eval.py`, `schemas_misc.py`. Updated 9 import sites.
- **`anvil/api/v1/inference.py`** (7 classes → extracted): Moved 7 Pydantic request body classes to `inference_schemas.py`.
- **`anvil/services/vault/_types.py`** (12 classes → 12 files): Split into `types_*.py` at `anvil/services/vault/`. Updated 19 import sites across vault services and tests.

### 5. Package nesting (3 flattens)

| Package | Depth | Fix |
|---------|-------|-----|
| `anvil/client/_shared/errors/` | 3 | Flatten: moved 7 error files to `_shared/`, deleted `errors/` dir |
| `anvil/api/v1/schemas/` | 3 | Flatten: moved 6 files to `v1/` with `schemas_` prefix |
| `anvil/services/vault/_types/` | 3 | Flatten: moved 12 files to `vault/` with `types_` prefix |

### 6. Core dependencies (3 violations fixed)

Moved `anvil/core/torch_engine.py` → `anvil/services/training/torch_engine.py`. Updated 2 import sites (`local_torch_backend.py`, `modal_backend.py`). `anvil/core/` now has zero third-party dependencies (Article I compliance).

## Key discoveries

1. **Tool precision limitation in `check-init-py`**: The `_DATA_DIRS` set only checks immediate dirname, not ancestry. Subdirectories under `data/` with `.py` files (e.g. `hello-world/` demo samples) are incorrectly flagged as missing `__init__.py` when they should not have one. Fix would be to check if any ancestor is in `_DATA_DIRS`.

2. **Layer checker blind spot**: `check_layer_boundaries.py` only matches absolute `anvil.X` import prefixes. Relative imports like `from ...db.models.X import Y` bypass detection entirely. The checker should resolve relative imports to their absolute form before matching against forbidden targets.

3. **Alembic env.py exemption**: `anvil/_resources/migrations/env.py` cannot use relative imports because Alembic loads it via `importlib.util.spec_from_file_location` + `exec_module`, which doesn't set `__package__`. This is a genuine case warranting permanent exemption; consider adding a suppression comment `# import-placement:allow` or a skip-list in the checker.

4. **Caching bug in `AnvilWorkbench`** (found and fixed): `dataset_curation()` and `dataset_export()` factory methods cached a single instance, ignoring the `dataset_id` parameter — calling with a different dataset_id silently returned the wrong instance. Changed to return a fresh instance per call.

## Vault health

Ran `make vault-audit` — must pass 0 errors before vault commit. Session log and this note added.

## Changes made

| Entity | Action |
|--------|--------|
| `anvil/api/v1/router.py` | **UPDATED** — 16 absolute imports → relative |
| `anvil/api/v1/datasets.py` | **UPDATED** — 12 absolute imports → relative, removed layer violations |
| `anvil/api/v1/health_ops.py` | **UPDATED** — 7 absolute imports → relative |
| `anvil/api/v1/learning.py` | **UPDATED** — 5 absolute imports → relative, removed layer violations |
| `anvil/client/_shared/stream_event.py` | **UPDATED** — 1 absolute import → relative |
| `anvil/client/_shared/transport.py` | **UPDATED** — 10 absolute imports → relative |
| `anvil/core/engine.py` | **UPDATED** — 1 absolute import → relative (layer fix) |
| `anvil/db/models/__init__.py` | **UPDATED** — stripped imports, docstring-only |
| `anvil/_resources/migrations/versions/__init__.py` | **CREATED** — bare docstring |
| `anvil/api/v1/schemas.py` | **DELETED** — replaced by schemas_*.py package |
| `anvil/api/v1/schemas_dataset.py` | **CREATED** — 8 dataset schema classes |
| `anvil/api/v1/schemas_governance.py` | **CREATED** — 6 governance schema classes |
| `anvil/api/v1/schemas_content.py` | **CREATED** — 15 content schema classes |
| `anvil/api/v1/schemas_corpus.py` | **CREATED** — 4 corpus schema classes |
| `anvil/api/v1/schemas_eval.py` | **CREATED** — 3 eval schema classes |
| `anvil/api/v1/schemas_misc.py` | **CREATED** — 6 misc schema classes |
| `anvil/api/v1/inference_schemas.py` | **CREATED** — 7 inference body classes extracted |
| `anvil/api/v1/config.py` | **UPDATED** — schemas import paths |
| `anvil/api/v1/content.py` | **UPDATED** — schemas import paths |
| `anvil/api/v1/corpora.py` | **UPDATED** — schemas import paths |
| `anvil/api/v1/eval.py` | **UPDATED** — schemas import paths |
| `anvil/api/v1/eval_datasets.py` | **UPDATED** — schemas import paths |
| `anvil/api/v1/governance.py` | **UPDATED** — schemas import paths |
| `anvil/api/v1/registry.py` | **UPDATED** — schemas import paths |
| `anvil/client/_shared/errors/__init__.py` | **DELETED** |
| `anvil/client/_shared/errors/*` (7 files) | **DELETED** — moved to `_shared/` |
| `anvil/client/_shared/api_error.py` | **MOVED** from `errors/` |
| `anvil/client/_shared/authentication_error.py` | **MOVED** from `errors/` |
| `anvil/client/_shared/connection_error.py` | **MOVED** from `errors/` |
| `anvil/client/_shared/not_found_error.py` | **MOVED** from `errors/` |
| `anvil/client/_shared/rate_limit_error.py` | **MOVED** from `errors/` |
| `anvil/client/_shared/server_error.py` | **MOVED** from `errors/` |
| `anvil/client/_shared/validation_error.py` | **MOVED** from `errors/` |
| `anvil/client/_shared/__init__.py` | **UPDATED** — removed errors sub-package reference |
| `anvil/core/torch_engine.py` | **MOVED** → `anvil/services/training/torch_engine.py` |
| `anvil/services/compute/local_torch_backend.py` | **UPDATED** — import path |
| `anvil/services/compute/modal_backend.py` | **UPDATED** — import path |
| `anvil/services/datasets/corpora.py` | **UPDATED** — added `scan_and_chunk` method |
| `anvil/services/datasets/dataset_curation.py` | **UPDATED** — added 5 methods |
| `anvil/workbench.py` | **UPDATED** — added `tracking`/`inference` properties, audit enums, fixed caching bug |
| `anvil/services/vault/_types.py` | **DELETED** — replaced by 12 `types_*.py` files |
| `anvil/services/vault/types_*.py` (12 files) | **CREATED** — one class per file |
| `anvil/services/vault/*.py` (11 files) | **UPDATED** — import paths |
| `tests/services/vault/*.py` (3 files) | **UPDATED** — import paths |
| `tests/unit/services/test_vault_*.py` (5 files) | **UPDATED** — import paths |

## See also

- [[Decisions/ADR-007-llama-engine-evolution|ADR-007]] — Llama Engine Evolution
- [[Decisions/ADR-020-one-class-per-file|ADR-020]] — One Class Per File (enforced by check-one-class)
- [[Decisions/ADR-021-init-py-ownership-policy|ADR-021]] — `__init__.py` Ownership (enforced by check-init-py)
- [[Decisions/ADR-041-simplicity-first-boring-technology|ADR-041]] — Simplicity First
- `2026-06-27-constitution-mechanical-checks.md` — Prior session: created the 8 check tools
- `.specify/memory/constitution.md` — Constitution (source of truth)