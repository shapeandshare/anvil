---
title: Greenfield Legacy and Backward-Compatibility Removal
type: decision
status: draft
source: agent
created: '2026-06-20'
updated: '2026-06-20'
aliases:
  - Greenfield Legacy and Backward-Compatibility Removal
  - ADR-032
related:
  - '[[Decisions/ADR-024-auto-db-migration]]'
  - '[[Decisions/ADR-034-vault-health-subsumption]]'
  - '[[Sessions/2026-06-20-legacy-backcompat-removal]]'
code-refs:
  - anvil/_resources/migrations/versions/001_initial.py
  - anvil/config.py
  - anvil/db/models/training_config.py
  - anvil/gpu.py
tags:
  - type/decision
  - domain/database
  - domain/architecture
  - status/draft
---

# ADR-032: Greenfield Legacy and Backward-Compatibility Removal

## Status

accepted

## Context

anvil has no users, no deployments, no persisted data, and no released models in
the wild. Despite this, the codebase had accumulated backward-compatibility
machinery appropriate only for a project with installed base obligations:

- A 15-file Alembic migration chain (`001`–`014` plus a merge head) where later
  migrations *dropped* tables that earlier migrations had created
  (`experiments`, `registered_models`, `model_versions`), plus a duplicated
  `002b`/`006` registry-table branch reconciled by a merge revision.
- A `use_gpu` boolean carried through the ORM, API, CLI, and memory estimator —
  fully superseded by the `compute_backend` enum (see ADR-015) but retained with
  a translation shim mapping `use_gpu=True` to `compute_backend="local-gpu"`.
- An `ANVIL_DB_PATH` → `ANVIL_STATE_DB_PATH` deprecation shim and a duplicate
  `db_path` config alias.
- Tombstone modules (`services/tracking/experiments.py`,
  `db/models/registry.py`), a one-shot `migrate_to_mlflow_primary.py` script
  targeting tables that no longer exist, and three `scripts/ci/` wrappers
  superseded by the `anvil-vault` CLI (see ADR-025).
- An `experiment_1.json` filesystem fallback path predating MLflow-primary
  lineage.

Carrying this machinery imposes ongoing comprehension and maintenance cost with
zero compensating benefit, because there is no prior schema or API contract to
preserve.

## Decision

Treat the project as greenfield and remove all backward-compatibility surface:

1. **Squash the migration chain into a single `001_initial.py`** that builds the
   current canonical schema directly. Tables that were created-then-dropped are
   simply never created. The squashed migration declares `down_revision = None`
   and is the sole Alembic head.
2. **Remove `use_gpu` entirely** — ORM column, API payload field, CLI `--gpu`
   flag / `USE_GPU` env var, and the `estimate_training_memory` parameter.
   `compute_backend` is the single source of truth for accelerator selection.
3. **Remove the `ANVIL_DB_PATH` shim and the `db_path` alias.** Only
   `ANVIL_STATE_DB_PATH` / `state_db_path` remain.
4. **Delete dead modules, the one-shot migration script, the superseded CI
   wrappers, and the `experiment_1.json` fallback.**

This is a deliberate, one-time license granted by the absence of an installed
base. It is **not** a standing policy: once anvil has real deployments, normal
additive-migration and deprecation discipline resumes.

## Consequences

**Easier:**
- A newcomer reads one migration file to understand the schema, not fifteen
  with create/drop churn.
- `compute_backend` is the only accelerator knob — no dual-write or translation
  shim to keep in sync.
- Config resolution has a single env var and a single dict key.

**Harder / risks:**
- Any database created by a *previous* anvil checkout cannot be upgraded through
  the new chain — it must be recreated. Acceptable given zero deployments.
- The ORM-vs-migration schema divergences that predated the squash
  (`corpus_files` composite unique constraint; `audit_events.sequence` unique
  constraint vs. unique index) were *preserved as-is* in the squash to match the
  historical migrated schema rather than silently "fixing" them.

## Compliance

- A fresh `MigrationService.ensure_migrated()` against an empty database reaches
  head `001` and creates all ten tables.
- A programmatic diff of the migrated schema against ORM `Base.metadata`
  (tables, columns, foreign keys, indexes) shows parity, with `run_id_seq` the
  only intentional non-ORM table.
- `grep` confirms zero `use_gpu`, `ANVIL_DB_PATH`, `USE_GPU`/`--gpu`, or
  `cfg["db_path"]` references remain in executable code, the `Makefile`, or
  `shared/*.mk`.
- Alembic reports exactly one head (`001`).

## See Also

- [[Decisions/README|Decisions]]
