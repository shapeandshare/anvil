# Context — 080 FK Indexes and N+1 Prevention

> Cross-references: `../066-codebase-remediation/data-inventory.md`, `shared-decisions.md` Decision 5.

## Current State (verified)

- **Zero `selectinload`/`joinedload`** usage in any repository (`grep -rln "selectinload\|joinedload" anvil/db/repositories/` → 0).
- **No index** on the target FK columns (`grep -n "index=True\|Index(" fine_tune_dataset.py lora_adapter.py` → none).
- Latest migration: `014_add_download_job_source_columns.py` → new migration is **015**.

## ⚠️ LIVE INCONSISTENCY DISCOVERED

`013_drop_external_models.py` DROPS the `external_models` table, but these models STILL reference it:
- `fine_tune_dataset.py:74` → `ForeignKey("external_models.id", ondelete="SET NULL")`
- `lora_adapter.py:69` → `ForeignKey("external_models.id", ondelete="CASCADE")`

Also `external_model.py` is marked LEGACY/deprecated (SC-006, scheduled for removal). **Before adding an index on `external_model_id`, resolve whether these FKs are dangling.** Options:
1. If `external_models` truly dropped, these FK constraints are dead — the index is moot, and the FKs should be repointed to `catalog_identities` or removed. Escalate — this is a data-model bug beyond this spec's scope.
2. If `external_models` still exists (migration 013 may only drop it conditionally), proceed with the index.

**ACTION**: The implementer MUST verify the actual DB schema state (`013_drop_external_models.py` contents) before touching `lora_adapters.external_model_id` / `fine_tune_datasets.external_model_id` indexes.

## Target FK Indexes (verify each is still valid)

| Table | Column | Index name | Notes |
|-------|--------|-----------|-------|
| `fine_tune_datasets` | `dataset_id` | `ix_fine_tune_datasets_dataset_id` | FK to `datasets` — safe |
| `fine_tune_datasets` | `chat_template_id` | `ix_fine_tune_datasets_chat_template_id` | FK to `chat_templates` — safe |
| `fine_tune_datasets` | `external_model_id` | — | ⚠️ FK to dropped table — RESOLVE FIRST |
| `lora_adapters` | `external_model_id` | — | ⚠️ FK to dropped table — RESOLVE FIRST |
| `datasets` | `license_id` | `ix_datasets_license_id` | FK to `license_catalog` — safe |
| `corpora` | `license_id` | `ix_corpora_license_id` | verify column exists |
| `content_corpora` | `license_id` | `ix_content_corpora_license_id` | verify column exists |

## N+1 Audit

No eager loading exists. Audit service code for relationship access in loops:
```bash
grep -rn "for .* in .*:" anvil/services/ | grep -i "corpus\|dataset\|version\|run"
```
Focus on: `corpus.files`, `version.entries`, `run.metric_deltas`, `run.samples`. Add `selectinload()` in the repository method that fetches the parent.

## Decision Reference

`shared-decisions.md` Decision 5: new migration is `015_add_fk_indexes.py`. Use Alembic autogenerate then hand-verify index names.

## Gotchas

- SQLite: prefer `selectinload()` over `joinedload()` for to-many (avoids the 64-join limit).
- Adding `index=True` to `mapped_column` will make Alembic autogenerate detect it — but hand-write the migration to control index names.
- Small tables still benefit; index write-overhead is negligible for this workload.
- Don't add indexes to the dangling `external_model_id` FKs until the data-model inconsistency is resolved.
