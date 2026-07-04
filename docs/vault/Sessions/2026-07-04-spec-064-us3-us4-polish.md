---
title: "Session: 2026-07-04 — Spec 064 US3/US4/Polish implementation"
type: session
tags:
  - type/session
  - status/draft
created: 2026-07-04
updated: 2026-07-04
---

# Session: Spec 064 (Unified MLflow Model Catalog) — US3, US4, Polish

## Summary

Completed remaining work for [[Specs/064 MLflow Model Catalog/spec|Spec 064]]:
- US3 (ModelRef downstream records: adapters, evaluations)
- US4 (Archive semantics)
- Polish (Legacy removal, Alembic migration, logging, SC-006 tests)

## Changes

### US3 — Downstream records reference models by ModelRef

- **LoRAAdapter ORM** (`anvil/db/models/lora_adapter.py`): Added `registry_model_name` / `registry_model_version` columns (already present in migration 012).
- **LoRAAdapterRepository** (`anvil/db/repositories/lora_adapter_repository.py`): Added `get_by_model_ref()` and `get_by_adapter_id_modelref()` methods for ModelRef-based queries.
- **EvaluationRun ORM** (`anvil/db/models/evaluation_run.py`): Added `model_name`, `model_version`, `base_model_name`, `base_model_version` columns (already present in migration 012).
- **EvaluationRoute schemas** (`anvil/api/v1/schemas_eval.py`): Added `model_name`/`model_version`/`base_model_name`/`base_model_version` to `EvalFineTunedBody` and `EvaluationRunResponse`.
- **Eval routes** (`anvil/api/v1/eval.py`): Updated `get_evaluation_run` and list to read ModelRef fields from the ORM directly, removed `external_model_repo.get()` calls.
- **Adapter routes** (`anvil/api/v1/adapters.py`): Rewired from `/models/{model_id}/...` to `/models/{name}/versions/{version}/...` paths using ModelRef.
- **Merge Service** (`anvil/services/training/merge_service.py`): Added `merge_by_ref()` and `merge_and_export_by_ref()` methods; switched from `ExternalModelRepository` to `ModelCatalogService`; added `_resolve_source_identifier` and `_check_license` stubs that use catalog.

### US4 — Archive semantics

- **Archive route** (`anvil/api/v1/models.py`): Added `DELETE /v1/models/{name}/versions/{version}` that calls `catalog.archive(ref)` tag-only archive.
- **Tests** (`tests/e2e/test_archive_semantics.py`): e2e test for archive route (404 for unknown model).

### Polish — Legacy removal

- **Removed legacy routes**: Deleted `GET /v1/models/external`, `GET /v1/models/external/{model_id}`, `DELETE /v1/models/external/{model_id}` from `anvil/api/v1/models.py`.
- **Removed external_model_repo usage**: From `anvil/api/v1/pages.py` (hf-browser job display), from `anvil/workbench.py` (property + constructor injections).
- **Marked as deprecated stubs**: `anvil/db/models/external_model.py` and `anvil/db/repositories/external_models.py` reduced to minimal stubs with deprecation notices. Full removal deferred until US2 is fully migrated.
- **Alembic revision 013** (`anvil/_resources/migrations/versions/013_drop_external_models.py`): Drops `external_models` table and `model_import_jobs.external_model_id` column.
- **Structured logging** (`anvil/services/catalog/model_catalog_service.py`): Added structured log lines for registration, list_entries, get_entry, set_asset_availability, and archive events.
- **SC-006/SC-007 tests** (`tests/e2e/test_legacy_removed.py`): Verify removed routes return non-200, and catalog listing returns expected status.

### Cross-cutting

- **Registry fix** (`anvil/api/v1/registry.py`): Fixed `workbench: AnvilWorkbench = None` annotation that caused FastAPI to crash with Pydantic field validation error.

## Test Results

All 10 new tests pass:

```
tests/unit/services/training/test_adapters_modelref.py ... PASSED [2/2]
tests/e2e/test_eval_modelref.py ...................... PASSED [3/3]
tests/e2e/test_archive_semantics.py .................. PASSED [1/1]
tests/e2e/test_legacy_removed.py .................... PASSED [4/4]
```

## Related

- [[Specs/064 MLflow Model Catalog/spec|Spec 064]]
- [[Decisions/ADR-046-mlflow-model-catalog-source-of-truth|ADR-046]]
- [[Specs/064 MLflow Model Catalog/tasks|Tasks]]