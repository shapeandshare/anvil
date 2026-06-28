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
Legacy CLI commands instantiate repositories/services directly inside `async with AsyncSessionLocal()`;
this feature instead builds an `AnvilWorkbench(session)` for convenience (the workbench is the
documented service seam). The CLI runs the import synchronously inline (submit + run_import), unlike
the API which fires it as a background task.

**Pattern**:
```python
def import_main() -> None:
    """Import a model from an external source."""
    parser = argparse.ArgumentParser(description="Import a model from an external source")
    parser.add_argument("source", help="Source type: huggingface or local")
    parser.add_argument("identifier", help="HF repo ID (e.g. TinyLlama/TinyLlama-1.1B-Chat-v1.0) or local path")
    parser.add_argument("--name", help="Display name for the registry entry")
    parser.add_argument("--revision", default="main", help="Source revision")
    args = parser.parse_args()

    async def _run() -> None:
        async with AsyncSessionLocal() as session:
            wb = AnvilWorkbench(session)
            job_id = await wb.model_imports.submit_import(
                source=args.source, identifier=args.identifier,
                revision=args.revision, name=args.name,
            )
            await wb.model_imports.run_import(job_id)  # inline (not fire-and-forget)
            await session.commit()
            print(f"Import complete, job ID: {job_id}")

    asyncio.run(_run())
```

## 3. REST API Pattern

**Decision**: Follow `APIRouter` per-file pattern with Pydantic request bodies.

**Rationale**: Every v1 route file in `anvil/api/v1/` follows this pattern. Routes use
`@router.post/get(...)` decorators, return `dict[str, Any]`, and are aggregated in
`anvil/api/v1/router.py` via `router.include_router(...)`. Route handlers obtain a session-bound
`AnvilWorkbench` via `workbench: AnvilWorkbench = Depends(get_workbench)` (`from ..deps import
get_workbench`) — verified the standard pattern in `datasets.py`. Some legacy routes (`registry.py`)
open `AsyncSessionLocal()` directly, but new routes should use `Depends(get_workbench)`.

**Background-task caveat**: The request-scoped session yielded by `get_workbench` is committed/closed
when the request returns. A fire-and-forget `asyncio.create_task(run_import(...))` therefore CANNOT
use the request workbench's session — the worker must open its own `AsyncSessionLocal()` and build a
fresh `AnvilWorkbench`.

**Key files**:
- `anvil/api/deps.py` — `get_workbench` dependency
- `anvil/api/v1/datasets.py` — canonical `Depends(get_workbench)` route pattern
- `anvil/api/v1/training.py` — submit + poll patterns
- `anvil/api/v1/router.py` — aggregator

## 4. SDK Client Pattern

**Decision**: Follow three-layer Transport → Command → DomainClient → AnvilClient facade.

**Rationale**: The existing SDK in `anvil/client/` uses a well-defined layered architecture:
- `Transport` (`anvil/client/_shared/transport.py`) — owns `httpx.AsyncClient`, all HTTP I/O
- `AbstractCommand` (`anvil/client/_shared/abstract_command.py`) — base class per API operation
- `RegistryClient` (`anvil/client/registry/registry_client.py`) — domain aggregator
- `AnvilClient` (`anvil/client/anvil_client.py`) — top-level facade with lazy sub-client properties

## 5. Async Job Infrastructure

**Decision**: Use pure asyncio with DB-persisted job state — no third-party queue. Create a NEW
`ModelImportJob` model (do NOT reuse the existing content `ImportJob`).

**Rationale**: The codebase has no Huey, Celery, or RQ. Async operations use:
- DB-persisted job models with status fields for durable state
- `asyncio.create_task()` for fire-and-forget background work — fired from the **API route layer**,
  NOT from inside the service (verified: `anvil/services/content/import_service.py` does NOT use
  `create_task`; the service is synchronous-at-the-service-level and the route fires the task)
- The background worker MUST open its OWN DB session (`async with AsyncSessionLocal()`), because the
  request-scoped session from `Depends(get_workbench)` is closed when the request returns

**Important correction**: There IS an existing `ImportJob` model
(`anvil/db/models/content_import_job.py`) and `IngestStatus` enum
(`anvil/services/content/ingest_status.py`) — but these belong to the **content-repository** domain
and are unrelated to model imports. Reusing them would conflate two domains and cause a class-name
collision. This feature creates a distinct `ModelImportJob` model + `ModelImportJobStatus` enum.

## 6. ModelSource Protocol

**Decision**: Use PEP 544 `Protocol` (structural typing, not ABC), consistent with
`ComputeBackendProtocol` in `anvil/services/compute/protocol.py`.

**Rationale**: The existing compute backend protocol uses structural typing — any class with matching
name, `is_available()`, and `async def run()` satisfies it. ModelSource follows the same
pattern: any class with `name` and `async def resolve_metadata()` satisfies it.

## 7. Authentication & the `[finetune]` Extra

**Decision**: Add a NEW `[finetune]` optional-dependencies extra containing `huggingface_hub`.
Authenticate via the `HF_TOKEN` env var at runtime.

**Rationale (corrected)**: Verification confirmed the `[finetune]` extra and `huggingface_hub` do
NOT currently exist in `pyproject.toml` (only `gpu`, `compute`, `vault-health`, `dev` extras exist).
This feature must ADD the extra. The `huggingface_hub` import in `hf_source.py` is guarded with
`try: from huggingface_hub import HfApi except ImportError:` — the permitted optional-dependency
exception under Principle 14 (No Lazy Imports), mirroring the `_torch_available()` capability probe
in `anvil/services/compute/resolve.py`. `HfApi` natively supports `HF_TOKEN`. No credentials persisted.

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

**Decision**: New `model_import/` domain sub-package under `anvil/services/` (NOT `import/` — a Python
reserved keyword) for the import service and ModelSource implementations. New ORM models under
`anvil/db/models/`. New SDK client sub-package under `anvil/client/`.

**Rationale**: The model-import domain is distinct from training, datasets, tracking, and compute. Per
Article X (Domain-Driven Decomposition) and Article VI (init.py ownership), a new domain sub-package
with its own bare `__init__.py` is warranted. The package CANNOT be named `import` because `import`
is a reserved keyword — `from ..import.x import Y` is a syntax error (verified).

**Files to create**:
```
anvil/db/models/external_model.py          # ExternalModel ORM entity
anvil/db/models/model_import_job.py         # ModelImportJob ORM entity
anvil/db/repositories/external_models.py    # ExternalModelRepository
anvil/db/repositories/model_import_jobs.py  # ModelImportJobRepository
anvil/services/model_import/
├── __init__.py                            # Bare docstring
├── model_import_service.py                # Import orchestration
├── model_source.py                        # ModelSource Protocol
├── hf_source.py                           # HF Hub ModelSource (huggingface_hub behind try/except)
└── local_source.py                        # Local file ModelSource
anvil/services/_shared/import_types.py     # enums + ModelMetadata + ModelSourceError
anvil/api/v1/models.py                     # API routes for external models
anvil/client/models/
├── __init__.py
├── models_client.py                       # Domain aggregator
├── models_import_command.py               # Import command
├── models_get_status_command.py           # Status command
└── models_get_command.py                  # Get command
```

**Files to modify**:
```
pyproject.toml              # Add `finetune` extra (huggingface_hub) + anvil-import entry points
anvil/db/models/__init__.py # Import new model modules for Base.metadata registration
anvil/workbench.py          # Wire ModelImportService + repositories
anvil/cli.py                # Add import_main() + import_status_main()
anvil/api/v1/router.py      # Register models router
anvil/client/anvil_client.py # Expose models property
anvil/_resources/migrations/versions/005_add_external_models.py  # down_revision = "004"
```

## 11. Model Registration Mechanism (verified)

**Decision**: Explicitly import the new model modules in `anvil/db/models/__init__.py`.

**Rationale**: `anvil/db/registry.py` does `from . import models` and claims this "registers models via
models/__init__.py" — but `models/__init__.py` is currently docstring-only and imports nothing.
Verified: `get_expected_tables()` returns 0 tables when only `registry.py` is imported, but 22 tables
after `anvil.workbench` is imported (because workbench → repositories → model modules transitively
import each model). This transitive registration is fragile. Adding explicit
`from . import external_model, model_import_job  # noqa: F401` to `models/__init__.py` makes the new
tables reliably discoverable. Migrations remain hand-written (not autogenerated), so the migration
itself does not depend on this — but `get_expected_tables()` (used by db health checks) does.
