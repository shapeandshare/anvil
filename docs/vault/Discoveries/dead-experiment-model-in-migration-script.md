---
title: Experiment Model Removed but Migration Script Still References It
type: discovery
status: draft
source: agent
session: 2026-06-19-lint-sweep
code-refs:
  - anvil/_resources/migrations/scripts/migrate_to_mlflow_primary.py
  - anvil/db/models/
created: '2026-06-19'
updated: '2026-06-19'
tags:
  - type/discovery
  - domain/database
  - status/draft
aliases:
  - Experiment Model Removed from Codebase
---
# `Experiment` Model Removed but Migration Script Still References It

The `experiments` table was dropped in Alembic migration 013 as part of the MLflow migration. The `Experiment` SQLAlchemy ORM model was removed from `anvil/db/models/` at the same time.

However, the one-shot migration script `anvil/_resources/migrations/scripts/migrate_to_mlflow_primary.py` still imports and references `Experiment` (~10 references: queries, type annotations, attribute access). Since the class no longer exists anywhere in the codebase, the script would fail at runtime with `NameError`.

## Resolution

A local `Experiment` model class was defined inline in the migration script using `Mapped`/`mapped_column` (matching the project's SQLAlchemy 2.0 pattern) to bind to the legacy `experiments` table. This allows the script to function against pre-migration databases, but it is dead code against any database created after migration 013.

## Implications

- The migration script is a historical artifact — it can only run against databases that still have an `experiments` table (pre-migration 013). Against current databases the `Experiment` class will be defined but the table won't exist.
- Consider marking the script as deprecated or removing it if all production databases have been migrated.
- Also note: `ModelVersion` and `RegisteredModel` from `anvil/db/models/registry.py` are similarly absent (registry module is a docstring placeholder), causing additional F821 errors in the same script.

## References

- `anvil/_resources/migrations/scripts/migrate_to_mlflow_primary.py`
- `anvil/db/models/` (no `Experiment` model exists)
- Alembic migration 013 (dropped `experiments` table)
