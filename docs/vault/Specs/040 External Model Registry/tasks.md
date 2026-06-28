# Tasks: 040 External Model Registry & Import Paradigm

**Input**: Design documents from `docs/vault/Specs/040 External Model Registry/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1 is the single P1 story)
- Include exact file paths in descriptions

> **Naming note**: The import domain package is `anvil/services/model_import/` — NOT `import/`,
> because `import` is a Python reserved keyword and would make relative imports
> (`from ..import.x import Y`) a syntax error. The existing content-import `ImportService`
> (`anvil/services/content/import_service.py`) and `ImportJob` model
> (`anvil/db/models/content_import_job.py`) are UNRELATED — this feature introduces distinct
> `ModelImportService` and `ModelImportJob` to avoid name collisions.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and dependency/package scaffolding for the model-import domain.

- [X] T001 Add a new `finetune` extra in `pyproject.toml` under `[project.optional-dependencies]` with `huggingface_hub>=0.24,<2` (current latest is 1.x; `HfApi.model_info()` is stable across 0.x/1.x). This extra does NOT exist yet — only `gpu`, `compute`, `vault-health`, `dev` exist. Also add `huggingface_hub` to `[tool.setuptools.dynamic]`/dev test deps if tests need it installed, OR mark HF tests to skip when the extra is absent.
- [X] T002 Add `anvil-import = "anvil.cli:import_main"` and `anvil-import-status = "anvil.cli:import_status_main"` entries in `pyproject.toml` under `[project.scripts]`
- [X] T003 [P] Create `anvil/services/model_import/__init__.py` with bare docstring describing the model-import domain
- [X] T004 [P] Create `anvil/client/models/__init__.py` with bare docstring describing the models SDK client domain
- [X] T005 Add Alembic migration `005_add_external_models.py` in `anvil/_resources/migrations/versions/` with `revision = "005"`, `down_revision = "004"`, hand-written `op.create_table("external_models", ...)` and `op.create_table("model_import_jobs", ...)` following the `004_add_runtime_config.py` pattern (columns via `sa.Column("name", sa.String(n)/sa.Text()/sa.Integer(), ...)`, enums stored as `sa.String(20)`, timestamps as `sa.DateTime()` with `server_default=sa.func.now()`, FK via `sa.ForeignKey("external_models.id", ondelete="SET NULL")`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before the user story can be implemented.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T006 [P] Define shared type enums (`SourceType`, `RunnableStatus`, `AssetState`, `ModelImportJobStatus`) in `anvil/services/_shared/import_types.py` using `StrEnum` (UPPER_CASE members, lower_case values per Principle 11)
- [X] T007 [P] Define `ModelMetadata` Pydantic `BaseModel` and `ModelSourceError` exception (with `code`, `message`, `source` attributes) in `anvil/services/_shared/import_types.py`
- [X] T008 [P] Define `ModelSource` structural Protocol (PEP 544, `from typing import Protocol`) in `anvil/services/model_import/model_source.py` with `name: str` attribute and `async def resolve_metadata(identifier, *, token=None) -> ModelMetadata` method — mirror the `ComputeBackendProtocol` style in `anvil/services/compute/protocol.py`
- [X] T009 Create `ExternalModel` ORM entity in `anvil/db/models/external_model.py`: `class ExternalModel(Base, TimestampMixin)`, `__tablename__ = "external_models"`, columns via `Mapped[type] = mapped_column(...)`. Enum-typed columns stored as `String(20)` with the enum member as default (e.g. `mapped_column(String(20), default=SourceType.HUGGINGFACE)`), matching the `Dataset`/`Corpus` pattern. NumPy-style docstring. Fields per data-model.md.
- [X] T010 Create `ModelImportJob` ORM entity in `anvil/db/models/model_import_job.py` (separate file — one class per file): `class ModelImportJob(Base, TimestampMixin)`, `__tablename__ = "model_import_jobs"`, status as `String(20)` default `ModelImportJobStatus.QUEUED`, `external_model_id` as nullable FK to `external_models.id` (`ForeignKey(..., ondelete="SET NULL")`), `error_code`/`error_message` nullable, `started_at`/`finished_at` nullable `DateTime`
- [X] T011 [P] Create `ExternalModelRepository` in `anvil/db/repositories/external_models.py`: `__init__(self, session: AsyncSession)`, async methods `get(id)`, `get_all()`, `add(model)` (with `flush()` + `refresh()`), `find_by_source(source_type, source_identifier, revision_sha)` (via `select(...).where(...).scalar_one_or_none()`) for idempotency, `update_fields(id, **kwargs)`, `delete(id)` — match `anvil/db/repositories/datasets.py` exactly
- [X] T012 [P] Create `ModelImportJobRepository` in `anvil/db/repositories/model_import_jobs.py`: async `get(id)`, `add(job)`, `update_status(id, status, *, error_code=None, error_message=None, external_model_id=None, started_at=None, finished_at=None)`, following the repository pattern
- [X] T013 Ensure model registration: import `external_model` and `model_import_job` modules in `anvil/db/models/__init__.py` (e.g. `from . import external_model, model_import_job  # noqa: F401`) so they register on `Base.metadata` — NOTE: current `models/__init__.py` is docstring-only and relies on transitive imports via repositories; adding explicit imports here makes registration robust for Alembic and `get_expected_tables()`

**Checkpoint**: Foundation ready — user story implementation can now begin.

---

## Phase 3: User Story 1 — Learner Imports an External Model as Tracked Metadata (Priority: P1) 🎯 MVP

**Goal**: A learner imports a model (from HuggingFace or a local path) via CLI, REST API, or SDK, and sees a complete, tracked metadata entry in anvil's registry — without yet downloading any weights. Import is async job-based: submitting returns a job ID, caller polls for completion.

**Independent Test**: Submit an import for a TinyLlama-class model via the CLI (`anvil import huggingface TinyLlama/TinyLlama-1.1B-Chat-v1.0`); verify a job ID is returned; poll `GET /v1/models/import/{job_id}/status` until `complete`; verify a registry entry is created with all FR-006 fields and marked `metadata_only`. Repeat via the local-file source and verify identical tracking.

### Implementation for User Story 1

- [X] T014 [P] [US1] Implement HF Hub `ModelSource` in `anvil/services/model_import/hf_source.py`: guard the `huggingface_hub` import with `try: from huggingface_hub import HfApi except ImportError:` (the permitted optional-dep exception per Principle 14 — mirror the `_torch_available()` probe in `anvil/services/compute/resolve.py`); call `HfApi(token=...).model_info(identifier, revision=revision)`; respect `HF_TOKEN` env var (`os.environ.get("HF_TOKEN")`); map extracted fields to `ModelMetadata`; raise `ModelSourceError` with typed codes (`network_error`, `auth_required`, `rate_limited`, `not_found`, `invalid_identifier`, `parse_failure`) by catching the corresponding `huggingface_hub.utils` / `httpx` exceptions
- [X] T015 [P] [US1] Implement local-file `ModelSource` in `anvil/services/model_import/local_source.py`: read `config.json`, tokenizer files, and model card from a local directory using stdlib `json`/`pathlib`; extract available fields into `ModelMetadata`; no extra needed (always available)
- [X] T016 [US1] Implement `ModelImportService` in `anvil/services/model_import/model_import_service.py`:
  - Constructor takes `ExternalModelRepository`, `ModelImportJobRepository`, and `dict[SourceType, ModelSource]`
  - `async def submit_import(source, identifier, revision, name) -> int`: validate source exists in the registered-sources dict (raise `ValueError` if unknown), check `find_by_source` for idempotency (return existing model's job-equivalent if already imported at same revision), create `ModelImportJob` with status `QUEUED`, return job_id. (Background execution is started by the API layer via `asyncio.create_task`, NOT here — matching the codebase pattern where the service is synchronous and the route fires the task.)
  - `async def run_import(job_id)`: the worker coroutine — set job `RESOLVING`, call `ModelSource.resolve_metadata()`, compute `runnable_status` from resolved `architecture_family` (allow-list: `LlamaForCausalLM`) and weight format (allow-list: `safetensors`), create `ExternalModel` entry, set job `COMPLETE` with `external_model_id` — or on `ModelSourceError`, set job `FAILED` with the typed `error_code`/`error_message` (no partial entry)
  - `async def get_job_status(job_id) -> ModelImportJob | None`
  - `async def get_external_model(model_id) -> ExternalModel | None`
  - `async def list_external_models() -> Sequence[ExternalModel]`
- [X] T017 [US1] Wire into `AnvilWorkbench` in `anvil/workbench.py`: add lazy refs `self._external_model_repo`, `self._model_import_job_repo`, `self._model_imports` in `__init__` (all `= None`); add lazy properties `external_model_repo` → `ExternalModelRepository(self._session)`, `model_import_job_repo` → `ModelImportJobRepository(self._session)`, and `model_imports` → `ModelImportService(self.external_model_repo, self.model_import_job_repo, {SourceType.HUGGINGFACE: HfHubSource(), SourceType.LOCAL: LocalSource()})` — follow the existing `datasets`/`content_imports` lazy-property pattern
- [X] T018 [US1] Implement API routes in `anvil/api/v1/models.py`: `router = APIRouter()`; handlers take `workbench: AnvilWorkbench = Depends(get_workbench)` (import `from ...workbench import AnvilWorkbench` and `from ..deps import get_workbench`):
  - `POST /models/import` (status 202) — `ImportModelBody` Pydantic body (source, identifier, revision?, name?); call `workbench.model_imports.submit_import(...)`, then `asyncio.create_task(workbench.model_imports.run_import(job_id))` for fire-and-forget background resolution; return `{"job_id": ..., "status": "queued"}`
  - `GET /models/import/{job_id}/status` — return job status with error fields
  - `GET /models/external` — list all external models
  - `GET /models/external/{model_id}` — single model (404 via `HTTPException` if missing)
  - **Caveat**: a fire-and-forget `asyncio.create_task` using the request-scoped `workbench` session will outlive the request; the background worker MUST open its OWN session (`async with AsyncSessionLocal() as s:` and build a fresh `AnvilWorkbench(s)`), not reuse the request session. Implement `run_import` invocation accordingly.
- [X] T019 [US1] Register `models_router` in `anvil/api/v1/router.py`: add `from .models import router as models_router` and `router.include_router(models_router)`
- [X] T020 [US1] Add `import_main()` CLI function in `anvil/cli.py`: argparse with `source`, `identifier`, `--name`, `--revision` (default `main`); inner `async def _run()` using `async with AsyncSessionLocal() as session:` → `wb = AnvilWorkbench(session)` → `job_id = await wb.model_imports.submit_import(...)` → `await wb.model_imports.run_import(job_id)` (CLI runs it synchronously inline, not fire-and-forget) → `await session.commit()` → print job_id/result; top-level `asyncio.run(_run())`. Follow the `corpus_main` CLI pattern.
- [X] T021 [US1] Add `import_status_main()` CLI function in `anvil/cli.py`: argparse with `job_id`; inner `async def _run()` opens session, builds workbench, calls `wb.model_imports.get_job_status(job_id)`, prints status + error details; `asyncio.run(_run())`
- [X] T022 [P] [US1] Implement SDK commands in `anvil/client/models/` (each `AbstractCommand` subclass with one `async def execute()` calling `self._transport.request(HttpMethod.POST/GET, path, json=..., response_model=...)`):
  - `models_import_command.py`: `ModelsImportCommand` — `POST /v1/models/import`
  - `models_get_status_command.py`: `ModelsGetStatusCommand` — `GET /v1/models/import/{job_id}/status`
  - `models_get_command.py`: `ModelsGetCommand` — `GET /v1/models/external/{model_id}`
- [X] T023 [US1] Implement `ModelsClient` domain aggregator in `anvil/client/models/models_client.py`: `__init__(self, transport)` holds command instances; expose `async def import_model(...)`, `get_import_status(job_id)`, `get(model_id)` — match `RegistryClient` pattern
- [X] T024 [US1] Wire `models` property into `AnvilClient` facade in `anvil/client/anvil_client.py`: add `self._models: ModelsClient | None = None` in `__init__` and a lazy `models` property returning `ModelsClient(self._transport)`

**Checkpoint**: User Story 1 complete — import via CLI, API, and SDK all work end-to-end.

---

## Phase 4: Polish & Cross-Cutting Concerns

**Purpose**: Finalize, verify, and ensure NMRG invariant holds.

- [X] T025 [P] Add unit tests in `tests/unit/services/test_hf_source.py` — mock `HfApi`, verify metadata mapping and that each exception maps to the correct typed `error_code`
- [X] T026 [P] Add unit tests in `tests/unit/services/test_local_source.py` — use `tmp_path` with a `config.json`, verify metadata extraction
- [X] T027 [P] Add unit tests in `tests/unit/db/test_external_model_repo.py` — CRUD + `find_by_source` idempotency with in-memory SQLite
- [X] T028 [P] Add unit tests in `tests/unit/services/test_model_import_service.py` — submit → run → complete flow with a fake `ModelSource`; failure path sets `FAILED` with error code; runnable_status computation (allow-list hit vs miss)
- [X] T029 [P] Add e2e test in `tests/e2e/test_external_models.py` — `POST /v1/models/import`, poll status to `complete`, `GET /v1/models/external` shows the entry (use a fake/monkeypatched source so no network)
- [X] T030 Run `make lint` and `make typecheck` — fix any new violations (relative imports, one-class-per-file, NumPy docstrings, no lazy internal imports)
- [X] T031 Verify NMRG invariant: in a base (no-`finetune`) environment, assert `huggingface_hub` is NOT importable from the core/service path unless the `finetune` extra is installed; from-scratch training works unchanged; the dependency-isolation assertion passes
- [X] T032 Run full test suite `make test` — ensure pre-existing tests pass unmodified

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS the user story
- **User Story 1 (Phase 3)**: Depends on Foundational completion
- **Polish (Phase 4)**: Depends on User Story 1 completion

### Within Foundational

- T009 (ExternalModel) and T010 (ModelImportJob) before T011/T012 (repositories)
- T013 (registration) after T009, T010
- T006, T007, T008 are independent ([P])

### Within User Story 1

- Sources (T014, T015) and service (T016) before workbench wiring (T017)
- Workbench (T017) before API routes (T018), CLI (T020/T021)
- API routes (T018) before router registration (T019)
- SDK commands (T022) before ModelsClient (T023) before AnvilClient wiring (T024)

### Parallel Opportunities

- Setup: T003, T004 ([P])
- Foundational: T006, T007, T008 ([P]); T011, T012 ([P] after their models exist)
- US1: T014 + T015 (sources, independent); T022 (SDK commands, independent of service internals)
- Polish: T025–T029 (all test files, independent)

### Parallel Example: User Story 1

```bash
# Both ModelSource implementations in parallel:
Task: T014 [P] [US1] HF Hub ModelSource in anvil/services/model_import/hf_source.py
Task: T015 [P] [US1] Local-file ModelSource in anvil/services/model_import/local_source.py

# After service (T016) + workbench (T017), launch entry points:
Task: T018 [US1] API routes in anvil/api/v1/models.py
Task: T020 [US1] CLI import_main in anvil/cli.py
Task: T022 [P] [US1] SDK commands in anvil/client/models/
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (including the new `finetune` extra)
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1 — the full spec 040 delivery
4. **STOP and VALIDATE**: Test the import flow end-to-end via all three surfaces
5. Complete Phase 4: Polish (tests, lint, NMRG verification)

### Incremental Delivery

1. Setup + Foundational → infrastructure + schema ready
2. Add User Story 1 → MVP. Import works via CLI, API, and SDK.
3. Polish → tests pass, NMRG invariant verified, ready for merge.

---

## Notes & Verified Codebase Facts

- The `finetune` extra and `huggingface_hub` do **not** exist yet (verified) — T001 adds them.
- The package is `model_import/` (not `import/` — reserved keyword would break relative imports).
- `ExternalModel`/`ModelImportJob` are new; the existing content `ImportService`/`ImportJob` are unrelated.
- Enums are stored as `String(20)` columns (not native SQL enums), per the `Dataset`/`Corpus` pattern.
- API routes obtain the workbench via `Depends(get_workbench)` (`anvil/api/deps.py`); CLI uses `AsyncSessionLocal()` directly and does NOT use `AnvilWorkbench` — except this feature builds a workbench from the session for convenience (acceptable; CLI may instantiate `AnvilWorkbench(session)`).
- Background `run_import` MUST open its own session (not reuse the request-scoped one) when fired via `asyncio.create_task` from a route.
- Migrations are hand-written (not autogenerated) — `down_revision = "004"`.
- Model registration: add explicit imports in `anvil/db/models/__init__.py` (T013) since it is currently docstring-only.