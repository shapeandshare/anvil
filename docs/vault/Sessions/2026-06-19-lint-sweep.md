---
title: 'Session: Codebase-Wide Lint Sweep'
type: session-log
tags:
  - type/session-log
  - domain/architecture
  - domain/governance
  - domain/tooling
created: '2026-06-19'
updated: '2026-06-19'
aliases:
  - 'Session: Codebase-Wide Lint Sweep'
  - lint-sweep
source: agent
---
# Session: Codebase-Wide Lint Sweep

**Date**: 2026-06-19
**Trigger**: Mypy config was hardened — needed to verify the codebase didn't regress. Ran `ruff`, `black`, `isort` across the full `anvil/` package and fixed ~125 lint errors.

## Work Done

### mypy Config Hardening

Added extra-strict flags beyond `--strict` in `pyproject.toml`:
- `enable_error_code = ["ignore-without-code", "possibly-undefined", "redundant-cast", "redundant-expr"]`
- `warn_unused_ignores = true`

Existing exceptions (`anvil.services.tracking`, `anvil.services.mlflow_inputs` with `ignore_errors = true`) preserved.

### Lint Fixes by Category

| Count | Category | Files Touched |
|-------|----------|--------------|
| 16 | B905 — zip missing `strict=` | `core/engine.py`, `core/autograd.py`, `services/dataset_import.py` |
| ~15 | B023 — lambda-in-loop unbounded variables | `_resources/migrations/scripts/migrate_to_mlflow_primary.py`, `services/tracking.py` |
| 9 | E712 — `== False` → `not` | `db/repositories/curation.py`, `services/dataset_curation.py` |
| 8 | F821 — undefined names | `_resources/migrations/scripts/migrate_to_mlflow_primary.py` (Experiment), `api/v1/training.py` (model), `services/inference.py` (Value/asyncio) |
| 13 | F811 — redefined unused names | `api/v1/router.py` (13 duplicate concept page route handlers) |
| ~15 | F401 — unused imports | `services/compute/modal_backend.py`, `services/compute/local_stdlib_backend.py`, `services/compute/local_torch_backend.py`, `services/corpus_loader.py`, `services/export.py`, `services/dataset_import.py`, `services/dataset_export.py`, `services/training.py`, `services/corpora.py`, `storage/file_info.py`, `cli.py` |
| 5 | F841 — unused local vars | `api/v1/corpora.py`, `cli.py`, `_resources/migrations/scripts/migrate_to_mlflow_primary.py` |
| 3 | B007 — unused loop vars | `services/dataset_curation.py`, `services/dataset_import.py` |
| 4 | E402 — misplaced module-level imports | `services/corpus_loader.py`, `services/demo_bootstrap.py`, `services/export.py`, `api/app.py` |
| 9 | RUF001/003 — ambiguous unicode chars | `api/v1/router.py`, `services/memory_estimator.py` |
| 1 | RUF005 — list concat → splat | `_pyfunc_model.py` |
| 1 | RUF059 — unpacked unused var | `_resources/migrations/scripts/migrate_to_mlflow_primary.py` |
| 1 | C401 — generator → set comprehension | `services/dataset_curation.py` |
| 1 | UP042 — `str, Enum` → `StrEnum` | `services/compute/compute_status.py` |
| 3 | ASYNC230/240 — blocking calls in async context | `api/v1/datasets.py`, `services/demo_bootstrap.py`, `services/demo_model_provider.py` |

### Black + isort

- `pyproject.toml` had duplicate TOML keys for `anvil/_resources/migrations/**` under `[tool.ruff.lint.per-file-ignores]` — merged.
- `anvil/services/inference.py` had a class method (`backward_graph`) at module-level indent (0 spaces instead of 4 inside `InferenceService`) — fixed, which cascaded into the rest of the file being parseable.
- Black reformatted 87 files; isort fixed imports across multiple services.

### Validation

- `black --check`: 121 files clean
- `isort --check`: all clean
- `ruff`: 29 remaining errors — all docstring-only (D100-D105, D400), pre-existing, no functional impact

## Discoveries Made

- [[Discoveries/dead-experiment-model-in-migration-script|`Experiment` model removed but migration script still references it]]
- [[Discoveries/duplicated-forward-pass-in-engine|Duplicated forward pass in `core/engine.py`]]

## Related

- [[Sessions/2026-06-19-mypy-strict-enforcement|Prior session: Mypy Strict Enforcement]]
- `AGENTS.md` — line 124 updated with new mypy flags
- `pyproject.toml` — `[tool.mypy]` section
