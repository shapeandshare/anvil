# Research: 040 External Model Registry & Import Paradigm

## 1. Model Registry Architecture

**Decision**: Create a new `ExternalModel` ORM entity — there is no native model registry to extend.

**Rationale**: Codebase exploration reveals the "model registry" (spec 003) is entirely MLflow-based via
`TrackingService` (`anvil/services/tracking/tracking.py`). The migration `001_initial.py` explicitly
skipped `registered_models` and `model_versions` tables that were dropped. There is zero native ORM
infrastructure for model registry. The ExternalModel entity will be a new first-class ORM model.

**Alternatives considered**:
- Extend MLflow Model Registry → rejected because MLflow is an external sidecar; external model metadata
  must survive independently of MLflow's availability
- Reuse existing ContentRepository schema → rejected because the content domain models (Corpus, Source,
  Version, Blob) are for file-level content, not model metadata

## 2. CLI Entry Point Pattern

**Decision**: Follow existing `argparse` + `asyncio.run()` pattern in `anvil/cli.py`.

**Rationale**: Every CLI command in the project uses this pattern. The CLI entry point is registered in
`pyproject.toml` under `[project.scripts]`. Examples: `anvil-train`, `anvil-corpus`, `anvil-vault`.

**Pattern**:
```python
def import_main() -> None:
    """Import a model from an external source."""
    parser = argparse.ArgumentParser(description="Import a model from an external source")
    parser.add_argument("source", help="HF Hub model ID (e.g., TinyLlama/TinyLlama-1.1B-Chat-v1.0) or local path")
    parser.add_argument("--name", help="Display name for the registry entry")
    args = parser.parse_args()

    async def _run() -> None:
        wb = AnvilWorkbench(...)
        job_id = await wb.models.import_model(source=args.source, name=args.name)
        print(f"Import submitted, job ID: {job_id}")

    asyncio.run(_run())
```

## 3. REST API Pattern

**Decision**: Follow `APIRouter` per-file pattern with Pydantic request bodies.

**Rationale**: Every v1 route file in `anvil/api/v1/` follows this pattern. Routes use
`@router.post/path/get(...)` decorators, return `dict[str, Any]`, and are aggregated in
`anvil/api/v1/router.py` via `router.include_router(...)`.

**Key files**:
- `anvil/api/v1/registry.py` — model registry routes (existing MLflow-based)
- `anvil/api/v1/training.py` — training routes with submit + poll + SSE patterns
- `anvil/api/v1/router.py` — aggregator

## 4. SDK Client Pattern

**Decision**: Follow three-layer Transport → Command → DomainClient → AnvilClient facade.

**Rationale**: The existing SDK in `anvil/client/` uses a well-defined layered architecture:
- `Transport` (`anvil/client/_shared/transport.py`) — owns `httpx.AsyncClient`, all HTTP I/O
- `AbstractCommand` (`anvil/client/_shared/abstract_command.py`) — base class per API operation
- `RegistryClient` (`anvil/client/registry/registry_client.py`) — domain aggregator
- `AnvilClient` (`anvil/client/anvil_client.py`) — top-level facade with lazy sub-client properties

## 5. Async Job Infrastructure

**Decision**: Use pure asyncio with DB-persisted job state — no third-party queue.

**Rationale**: The codebase has no Huey, Celery, or RQ. Async operations use:
- `asyncio.Queue` for in-memory event streaming (training SSE pattern)
- DB-persisted job models with status fields for durable state
- `loop.run_in_executor()` for CPU-bound background work (from `LocalStdlibBackend`)
- The existing `ImportJob` model + `ContentImportJobRepository` + `IngestStatus` enum already exist
  for content imports and can serve as a pattern reference

**For spec 040**: A new `ImportJob`-like model for model imports (or reuse the existing one) with:
- `POST /v1/models/import` → creates job, returns `job_id`
- `GET /v1/models/import/{job_id}/status` → polling endpoint
- Status lifecycle: `queued → resolving → complete | failed`

## 6. ModelSource Protocol

**Decision**: Use PEP 544 `Protocol` (structural typing, not ABC), consistent with
`ComputeBackendProtocol` in `anvil/services/compute/protocol.py`.

**Rationale**: The existing compute backend protocol uses structural typing — any class with matching
name, `is_available()`, and `async def run()` satisfies it. ModelSource should follow the same
pattern: any class with `resolve_metadata()` and `name` satisfies it.

## 7. Authentication

**Decision**: `HF_TOKEN` env var at runtime, checked by the HF Hub ModelSource implementation.

**Rationale**: Standard HuggingFace convention. The `huggingface_hub` library natively supports
`HF_TOKEN` via `HfApi(token=...)` or the env var. No persistence of credentials in anvil's config.

## 8. Import Idempotency

**Decision**: Same `(source_type, source_identifier, revision)` → return existing entry, no error.

**Rationale**: Clarified in spec session. The canonical identity triple is
`(source_type, source_id, revision_sha)`. Duplicate detection is an upsert that returns the existing
entry. Different revision → distinct version.

## 9. Error Taxonomy

**Decision**: Typed error codes aligned with HF Hub HTTP error taxonomy.

**Error codes**: `network_error`, `auth_required`, `rate_limited`, `not_found`, `invalid_identifier`,
`parse_failure`.

**Rationale**: Each maps to a standard HF Hub API response: network timeouts, 401/403 auth errors,
429 rate limits, 404 not found, 422/invalid identifiers, and malformed model card responses.
The error code is recorded on the job status for programmatic handling by CLI/API/SDK consumers.

## 10. Project Structure

**Decision**: New `import/` domain sub-package under `anvil/services/` for the import service and
ModelSource implementations. New ORM model under `anvil/db/models/`. New SDK client sub-package under
`anvil/client/`.

**Rationale**: The import domain is distinct from training, datasets, tracking, and compute. Per
Article X (Domain-Driven Decomposition) and Article VI (init.py ownership), a new domain sub-package
with its own bare `__init__.py` is warranted. The model entity is tightly coupled to the import
service so it lives alongside it.

**Files to create**:
```
anvil/db/models/external_model.py          # ExternalModel ORM entity
anvil/db/repositories/external_models.py   # ExternalModel repository
anvil/services/import/
├── __init__.py                            # Bare docstring
├── import_service.py                      # Import orchestration
├── model_source.py                        # ModelSource Protocol
├── hf_source.py                           # HF Hub ModelSource
└── local_source.py                        # Local file ModelSource
anvil/api/v1/models.py                     # API routes for external models
anvil/client/models/
├── __init__.py
├── models_client.py                       # Domain aggregator
├── models_import_command.py               # Import command
├── models_get_command.py                  # Get command
└── models_list_command.py                 # List command
```

**Files to modify**:
```
pyproject.toml              # Add anvil-import entry point
anvil/workbench.py          # Wire ImportService + ExternalModelRepository
anvil/cli.py                # Add import_main() function
anvil/api/v1/router.py      # Register models router
anvil/client/anvil_client.py # Expose models property
anvil/_resources/migrations/versions/  # Add 005 migration
```
