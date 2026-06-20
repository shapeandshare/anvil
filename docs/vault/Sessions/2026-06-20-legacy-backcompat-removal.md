---
title: 'Session: Greenfield legacy and backward-compat removal'
type: session-log
source: agent
tags:
  - type/session-log
  - domain/database
  - domain/architecture
  - domain/tracking
created: '2026-06-20'
updated: '2026-06-20'
aliases:
  - 'Session: Legacy backcompat removal'
  - Legacy backcompat removal
related:
  - '[[Decisions/ADR-032-greenfield-legacy-removal]]'
  - '[[Discoveries/docstring-in-dict-literal-silent-concatenation]]'
---

# Session: Greenfield legacy and backward-compat removal

**Date**: 2026-06-20
**Branch**: `main`

## Problem

The project has no users, deployments, data, or released models, yet carried
backward-compatibility machinery sized for an installed base: a 15-file Alembic
chain with create-then-drop churn, a `use_gpu` boolean fully superseded by the
`compute_backend` enum, an `ANVIL_DB_PATH` deprecation shim, dead tombstone
modules, a one-shot MLflow migration script, three superseded `scripts/ci/`
wrappers, and an `experiment_1.json` fallback. Decision and rationale recorded
in [[Decisions/ADR-032-greenfield-legacy-removal]].

## Changes

### Migration squash
- Deleted 14 migration files (`002`–`014` + the `12a4027155f0` merge head) and
  rewrote `001_initial.py` to build the full canonical schema directly. Single
  Alembic head `001`, `down_revision = None`. Tables that were historically
  created then dropped (`experiments`, `registered_models`, `model_versions`)
  are never created.

### `use_gpu` removal
- `anvil/db/models/training_config.py` — dropped the `use_gpu` column.
- `anvil/api/v1/training.py` — removed the `use_gpu` payload field and the
  `use_gpu → local-gpu` translation shim.
- `anvil/api/v1/experiments.py` — removed `use_gpu` from `_hyperparams_from_mlflow`.
- `anvil/cli.py` — removed the `--gpu` flag and `USE_GPU` env var.
- `anvil/gpu.py` — `resolve_device()` no longer takes a `use_gpu` parameter.
- `anvil/services/training/memory_estimator.py` — `estimate_training_memory()`
  no longer takes `use_gpu`; GPU presence is inferred from `gpu_info`.

### Config cleanup
- `anvil/config.py` — removed the `ANVIL_DB_PATH` deprecation shim and the
  duplicate `db_path` alias key; only `ANVIL_STATE_DB_PATH` / `state_db_path`
  remain.
- `.env.example`, `README.md` — removed deprecated-variable notes.

### Dead-code deletion
- `anvil/services/tracking/experiments.py` (tombstone),
  `anvil/db/models/registry.py` (placeholder),
  `anvil/_resources/migrations/scripts/migrate_to_mlflow_primary.py` (one-shot,
  targets dropped tables), and the `scripts/ci/` wrappers
  `check_guarded_imports.py`, `check_adr_unique.py`, `vault_audit.py`
  (superseded by the `anvil-vault` CLI, see [[Decisions/ADR-025-vault-health-subsumption]]).
- Removed the `experiment_1.json` filesystem fallback from
  `anvil/services/inference/inference.py` and `demo_model_provider.py`.

### Tests and packaging
- Updated `use_gpu`-dependent tests, migration-count assertions
  (`test_migration_paths.py`, `test_wheel_contents.py`), and the
  `startup-contract.md` "14 migrations" → "1 migration".
- Removed `_resources/migrations/scripts/*.py` from `pyproject.toml`
  package-data.
- Rewrote the `Makefile` `train-gpu` target to pass `--backend local-gpu`
  instead of the dead `USE_GPU` env var.

## Critical review pass

A second review (two parallel explore agents + direct verification) caught
items the first pass missed:

- Stale `.pyc` files for all 14 deleted migrations in `versions/__pycache__/`.
- `pyproject.toml` still globbed the deleted `migrations/scripts/` directory.
- `Makefile train-gpu` exported the dead `USE_GPU=true`.
- A stale `use_gpu` docstring in `experiments.py` and a misleading `use_gpu`
  mock in `test_experiment_memory.py`.
- Four `--gpu` argparse stubs in `tests/e2e/test_cli_training_tracked.py` that
  no longer matched the real CLI.
- ORM provenance-field comments and the startup contract still cited
  `014_add_governance`.

All fixed. Verified the migrated schema matches ORM `Base.metadata` (tables,
columns, FKs, indexes) via a programmatic diff; confirmed a single Alembic head
and a working upgrade/downgrade/`ensure_migrated` roundtrip from an empty DB.

## Key discoveries

- **The frontend was never at risk** — `training.html` posts only
  `compute_backend`; the `useGpu` JS variable is a local display-only
  derivation, so removing the API field broke no client contract.
- **A docstring inside a dict literal silently dropped a key** — see
  [[Discoveries/docstring-in-dict-literal-silent-concatenation]]. Pre-existing
  in `_HYPERPARAM_COERCERS`; surfaced and fixed during this work.
- **`local-gpu` is not legacy** — it is the `ComputeBackend` enum value that
  *replaced* `use_gpu`, and was correctly left untouched.

## Files changed

```
53 files changed, 286 insertions(+), 1848 deletions(-)
(14 migration files + 6 dead modules/scripts/tests deleted)
```

## Verification

- `637 tests collected` with zero import errors.
- Touched-area suites green: `112 passed, 6 skipped` (skips are demo-model
  inference tests requiring a bootstrapped model).
- Zero `use_gpu` / `ANVIL_DB_PATH` / `USE_GPU` / `--gpu` / `cfg["db_path"]`
  references remain in executable code, `Makefile`, or `shared/*.mk`.
