# Tasks: Client SDK

**Input**: Design documents from `docs/vault/Specs/026 Client SDK/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: TDD is MANDATORY per Constitution Article IV (Red-Green-Refactor). Test tasks are
included and MUST be written first and observed to FAIL before implementation. Coverage
`fail_under` ratchet (currently 23) MUST NOT decrease.

**Organization**: Tasks grouped by user story (spec priorities P1–P3) for independent delivery.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1–US6 maps to spec.md user stories
- All paths are repo-relative; SDK lives under `anvil/client/`, tests under `tests/`.

## Path Conventions

- SDK package: `anvil/client/` (domain sub-packages + `_shared/` infrastructure)
- Unit tests: `tests/unit/client/`
- e2e tests (in-process via `httpx.ASGITransport(app=app)`): `tests/e2e/api/test_client_*.py`
- Every `.py` file: one class (Constitution); bare docstring-only `__init__.py`; NumPy docstrings.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the SDK package skeleton with constitution-compliant `__init__.py` files.

- [x] T001 Create SDK package root `anvil/client/__init__.py` (bare docstring-only, per Article VI) describing the client SDK's purpose
- [x] T002 [P] Create `anvil/client/_shared/__init__.py` (bare docstring-only) describing cross-domain SDK infrastructure
- [x] T003 [P] Create `anvil/client/_shared/errors/__init__.py` (bare docstring-only) describing the typed exception hierarchy
- [x] T004 [P] Ensure test directories `tests/unit/client/` and `tests/unit/client/_shared/` exist (created implicitly when the first test file lands). Do NOT add `__init__.py` to test directories — pytest uses rootdir-based discovery, consistent with the existing `tests/` layout
- [x] T005 Verify SDK packaging: confirm `anvil.client*` is captured by existing `[tool.setuptools.packages.find] include = ["anvil*"]` and inherits top-level `anvil/py.typed` (no pyproject change expected; record finding in plan notes)

**Checkpoint**: Empty, importable `anvil.client` package skeleton exists.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The `_shared/` transport, config, envelope, errors, command base, and SSE event
types. EVERY user story depends on these.

**⚠️ CRITICAL**: No user-story work can begin until this phase is complete.

### Enums & value types (parallel — distinct files)

- [x] T006 [P] Implement `HttpMethod` StrEnum in `anvil/client/_shared/http_method.py` (GET/POST/PUT/DELETE/PATCH)
- [x] T007 [P] Implement `StreamEventType` StrEnum in `anvil/client/_shared/stream_event_type.py` (metrics/complete/error/divergence/heartbeat/export_error per data-model.md)

### Error hierarchy (TDD)

- [x] T008 [P] Write failing unit tests for status→exception mapping in `tests/unit/client/_shared/test_errors.py` (covers ApiError, AuthenticationError, NotFoundError, ValidationError, RateLimitError, ServerError, ConnectionError)
- [x] T009 [P] Implement `ApiError` base in `anvil/client/_shared/errors/api_error.py` (carries `status_code: int | None`, `message: str`)
- [x] T010 [P] Implement `AuthenticationError` in `anvil/client/_shared/errors/authentication_error.py`
- [x] T011 [P] Implement `NotFoundError` in `anvil/client/_shared/errors/not_found_error.py`
- [x] T012 [P] Implement `ValidationError` in `anvil/client/_shared/errors/validation_error.py`
- [x] T013 [P] Implement `RateLimitError` (with `retry_after: float | None`) in `anvil/client/_shared/errors/rate_limit_error.py`
- [x] T014 [P] Implement `ServerError` (preserves server message) in `anvil/client/_shared/errors/server_error.py`
- [x] T015 [P] Implement `ConnectionError` in `anvil/client/_shared/errors/connection_error.py`

### Config, envelope, stream event (TDD)

- [x] T016 [P] Write failing unit tests for `ServerConfig` env/arg/default resolution + validation in `tests/unit/client/_shared/test_server_config.py`
- [x] T017 Implement `ServerConfig` (BaseModel + `from_env`) in `anvil/client/_shared/server_config.py` — makes T016 pass
- [x] T018 [P] Write failing unit tests for generic `Response[T]` envelope unwrap in `tests/unit/client/_shared/test_response.py`
- [x] T019 Implement generic `Response[T]` (BaseModel, Generic[T]) in `anvil/client/_shared/response.py` — makes T018 pass
- [x] T020 [P] Implement `StreamEvent` (BaseModel: `type: StreamEventType`, `data: dict[str, Any]`) in `anvil/client/_shared/stream_event.py` (depends on T007)

### Transport (TDD) — the sole httpx-primitive holder

- [x] T021 Write failing unit tests for `Transport` in `tests/unit/client/_shared/test_transport.py`
- [x] T022 Implement `Transport.__init__` + `request(...)` in `anvil/client/_shared/transport.py` — makes T021 pass
- [x] T023 Implement `Transport.stream_sse(...)` async generator in `anvil/client/_shared/transport.py`
- [x] T024 Implement `Transport.download(...)` in `anvil/client/_shared/transport.py`
- [x] T025 Implement `Transport.aclose()` in `anvil/client/_shared/transport.py`

### Command base

- [x] T026 Implement `AbstractCommand` ABC in `anvil/client/_shared/abstract_command.py`

**Checkpoint**: `_shared/` infrastructure complete, unit-tested, `mypy --strict` clean. User stories can now begin (in parallel if staffed).

---

## Phase 3: User Story 1 - Install and Connect (Priority: P1) 🎯 MVP

**Goal**: A developer instantiates `AnvilClient`, connects, and verifies the server is reachable via a health check.

**Independent Test**: Instantiate `AnvilClient(base_url=...)`, call `await client.health.get()`, confirm success; point at a bad URL and confirm `ConnectionError` (no hang).

### Tests for User Story 1 (TDD — write first, must FAIL)

- [x] T027 [P] [US1] Write failing e2e test `tests/e2e/api/test_client_health.py`: `AnvilClient` against ASGI app returns health success; unauthenticated health works (FR-010)
- [x] T028 [P] [US1] Write failing unit test `tests/unit/client/test_anvil_client.py`: facade wiring (config readback, sub-clients present, async context manager closes transport), and `ConnectionError` on unreachable URL

### Implementation for User Story 1

- [x] T029 [P] [US1] Implement `HealthGetCommand` (`GET /v1/health`) in `anvil/client/health/health_get_command.py`
- [x] T030 [P] [US1] Implement `HealthDetailedCommand` (`GET /v1/health/detailed`) in `anvil/client/health/health_detailed_command.py`
- [x] T031 [US1] Implement `HealthClient` aggregator + `anvil/client/health/__init__.py` in `anvil/client/health/health_client.py`
- [x] T032 [US1] Implement `AnvilClient` facade in `anvil/client/anvil_client.py` per contracts/client-facade.md
- [x] T033 [US1] Export public API from `anvil/client/__init__.py` docstring-compliant surface check — make T027, T028 pass

**Checkpoint**: MVP — developers can connect and health-check in ≤5 lines (SC-001). Validate independently.

---

## Phase 4: User Story 2 - Manage Datasets (Priority: P1)

**Goal**: Full dataset lifecycle (list/get/create/update/delete/upload/export/search) via the SDK.

**Independent Test**: Create→list→get→update→upload→delete a dataset against the ASGI app; assert typed `Dataset` objects and `NotFoundError` after delete.

### Tests for User Story 2 (TDD — write first, must FAIL)

- [x] T034 [P] [US2] Write failing e2e test `tests/e2e/api/test_client_datasets.py` covering all 7 acceptance scenarios (create/list/get/update/upload/delete/search) + NotFoundError post-delete

### Implementation for User Story 2

- [x] T035 [P] [US2] Implement `Dataset` DTO (BaseModel) in `anvil/client/datasets/dataset.py` per data-model.md
- [x] T036 [P] [US2] Implement `DatasetListCommand` (`GET /v1/datasets[?q=]`) in `anvil/client/datasets/dataset_list_command.py` (depends on T026, T035)
- [x] T037 [P] [US2] Implement `DatasetGetCommand` (`GET /v1/datasets/{id}`) in `anvil/client/datasets/dataset_get_command.py` (depends on T026, T035)
- [x] T038 [P] [US2] Implement `DatasetCreateCommand` (`POST /v1/datasets`) in `anvil/client/datasets/dataset_create_command.py` (depends on T026, T035)
- [x] T039 [P] [US2] Implement `DatasetUpdateCommand` (`PUT /v1/datasets/{id}`) in `anvil/client/datasets/dataset_update_command.py` (depends on T026, T035)
- [x] T040 [P] [US2] Implement `DatasetDeleteCommand` (`DELETE /v1/datasets/{id}[?force=]`) in `anvil/client/datasets/dataset_delete_command.py` (depends on T026)
- [x] T041 [P] [US2] Implement `DatasetUploadCommand` (multipart `POST /v1/datasets/upload`) in `anvil/client/datasets/dataset_upload_command.py` (depends on T026, T035)
- [x] T042 [P] [US2] Implement `DatasetExportCommand` (`GET /v1/datasets/{id}/export?format=` → download) in `anvil/client/datasets/dataset_export_command.py` (depends on T024, T026)
- [x] T043 [US2] Implement `DatasetsClient` aggregator (incl. `search` delegating to list) + `anvil/client/datasets/__init__.py` (bare docstring) in `anvil/client/datasets/datasets_client.py` (depends on T036–T042)
- [x] T044 [US2] Wire `datasets` sub-client into `AnvilClient` in `anvil/client/anvil_client.py` — make T034 pass (depends on T043, T032)

**Checkpoint**: US1 + US2 both work independently.

---

## Phase 5: User Story 3 - Train Models Programmatically (Priority: P1)

**Goal**: Start training, stream typed SSE progress events, poll status, stop a run.

**Independent Test**: Start a short run against the ASGI app; assert `TrainingStartResult` ids; consume `client.training.stream(run_id)` asserting `metrics`→`complete` typed events; `stop` yields terminal state.

### Tests for User Story 3 (TDD — write first, must FAIL)

- [x] T045 [P] [US3] Write failing e2e test `tests/e2e/api/test_client_training.py`: start→stream (assert StreamEventType.METRICS with step/loss, then COMPLETE)→status→stop; assert no event data loss (SC-005)

### Implementation for User Story 3

- [x] T046 [P] [US3] Implement `TrainingConfig` DTO (BaseModel, validation: n_head divides n_embd) in `anvil/client/training/training_config.py` per data-model.md
- [x] T047 [P] [US3] Implement `TrainingStartResult` DTO in `anvil/client/training/training_start_result.py` (run_id/mlflow_run_id/experiment_id)
- [x] T048 [P] [US3] Implement `TrainingStartCommand` (`POST /v1/training/start`) in `anvil/client/training/training_start_command.py` (depends on T026, T046, T047)
- [x] T049 [P] [US3] Implement `TrainingStatusCommand` (`GET /v1/training/{run_id}/status`) in `anvil/client/training/training_status_command.py` (depends on T026)
- [x] T050 [P] [US3] Implement `TrainingStopCommand` (`POST /v1/training/{run_id}/stop`) in `anvil/client/training/training_stop_command.py` (depends on T026)
- [x] T051 [P] [US3] Implement `TrainingStreamCommand` (SSE async generator on `GET /v1/training/stream/{run_id}`) in `anvil/client/training/training_stream_command.py` (depends on T023, T026)
- [x] T052 [US3] Implement `TrainingClient` aggregator + `anvil/client/training/__init__.py` (bare docstring) in `anvil/client/training/training_client.py` (depends on T048–T051)
- [x] T053 [US3] Wire `training` sub-client into `AnvilClient` in `anvil/client/anvil_client.py` — make T045 pass (depends on T052, T032)

**Checkpoint**: All P1 stories (US1–US3) complete — full MVP automation loop (connect → data → train → observe).

---

## Phase 6: User Story 4 - Manage Experiments and Models (Priority: P2)

**Goal**: List/compare experiments, fetch metrics, register and list models.

**Independent Test**: After a run, list experiments, compare two, get metrics, register a model, list registry — all typed.

### Tests for User Story 4 (TDD — write first, must FAIL)

- [x] T054 [P] [US4] Write failing e2e test `tests/e2e/api/test_client_experiments.py` (list/get/compare/metrics/delete/artifacts)
- [x] T055 [P] [US4] Write failing e2e test `tests/e2e/api/test_client_registry.py` (register/list/get/delete)

### Implementation for User Story 4 — Experiments (one command class per file)

- [x] T056 [P] [US4] Implement `Experiment` DTO in `anvil/client/experiments/experiment.py` per data-model.md
- [x] T057 [P] [US4] Implement `ExperimentListCommand` (`GET /v1/experiments`) in `anvil/client/experiments/experiment_list_command.py` (depends on T026, T056)
- [x] T058 [P] [US4] Implement `ExperimentGetCommand` (`GET /v1/experiments/{id}`) in `anvil/client/experiments/experiment_get_command.py` (depends on T026, T056)
- [x] T059 [P] [US4] Implement `ExperimentCompareCommand` (`GET /v1/experiments/compare?id=...`) in `anvil/client/experiments/experiment_compare_command.py` (depends on T026, T056)
- [x] T060 [P] [US4] Implement `ExperimentMetricsCommand` (`GET /v1/experiments/{id}/metrics`) in `anvil/client/experiments/experiment_metrics_command.py` (depends on T026)
- [x] T061 [P] [US4] Implement `ExperimentDeleteCommand` (`DELETE /v1/experiments/{id}`) in `anvil/client/experiments/experiment_delete_command.py` (depends on T026)
- [x] T062 [P] [US4] Implement `ExperimentArtifactsCommand` (`GET /v1/experiments/{exp}/runs/{run}/artifacts`) in `anvil/client/experiments/experiment_artifacts_command.py` (depends on T026)
- [x] T063 [P] [US4] Implement `ExperimentDownloadCommand` (`GET /v1/experiments/{exp}/runs/{run}/download?path=` → download) in `anvil/client/experiments/experiment_download_command.py` (depends on T024, T026)
- [x] T064 [US4] Implement `ExperimentsClient` aggregator + `anvil/client/experiments/__init__.py` (bare docstring) in `anvil/client/experiments/experiments_client.py` (depends on T057–T063)

### Implementation for User Story 4 — Registry (one command class per file)

- [x] T065 [P] [US4] Implement `RegisteredModel` DTO in `anvil/client/registry/registered_model.py` per data-model.md
- [x] T066 [P] [US4] Implement `RegistryRegisterCommand` (`POST /v1/registry/models`) in `anvil/client/registry/registry_register_command.py` (depends on T026, T065)
- [x] T067 [P] [US4] Implement `RegistryListCommand` (`GET /v1/registry/models[?search=]`) in `anvil/client/registry/registry_list_command.py` (depends on T026, T065)
- [x] T068 [P] [US4] Implement `RegistryGetCommand` (`GET /v1/registry/models/{id}`) in `anvil/client/registry/registry_get_command.py` (depends on T026, T065)
- [x] T069 [P] [US4] Implement `RegistryDeleteCommand` (`DELETE /v1/registry/models/{id}[/versions/{v}]`) in `anvil/client/registry/registry_delete_command.py` (depends on T026)
- [x] T070 [US4] Implement `RegistryClient` aggregator + `anvil/client/registry/__init__.py` (bare docstring) in `anvil/client/registry/registry_client.py` (depends on T066–T069)

### Facade wiring for User Story 4

- [x] T071 [US4] Wire `experiments` + `registry` sub-clients into `AnvilClient` in `anvil/client/anvil_client.py` — make T054, T055 pass (depends on T064, T070, T032)

**Checkpoint**: US1–US4 work independently.

---

## Phase 7: User Story 5 - Authentication and Session Management (Priority: P2)

**Goal**: Both auth modes — `X-API-Key` (foundational) and session login/logout with cookie capture + CSRF on cookie writes.

**Independent Test**: Authed API-key request succeeds; `login()` then a cookie-authed write succeeds with CSRF; invalid creds → `AuthenticationError`.

### Tests for User Story 5 (TDD — write first, must FAIL)

- [x] T072 [P] [US5] Write failing e2e test `tests/e2e/api/test_client_auth.py`: api-key request OK; `login()` captures `anvil_session` cookie; cookie-authed POST attaches `X-CSRF-Token`; invalid key → AuthenticationError
- [x] T073 [P] [US5] Write failing unit test in `tests/unit/client/_shared/test_transport_csrf.py`: CSRF header attached only for cookie-auth state-changing methods; api-key path is CSRF-exempt

### Implementation for User Story 5

- [x] T074 [US5] Implement `AnvilClient.login(api_key)` (`POST /login`, capture session cookie via httpx cookie jar) in `anvil/client/anvil_client.py` (depends on T032)
- [x] T075 [US5] Implement `AnvilClient.logout()` (`POST /logout`, clear cookie) in `anvil/client/anvil_client.py` (depends on T074)
- [x] T076 [US5] Extend `Transport` to track auth mode + attach `X-CSRF-Token` for cookie-authed POST/PUT/DELETE/PATCH (CSRF-exempt under api-key) in `anvil/client/_shared/transport.py`; surface session-expiry as `AuthenticationError` — make T072, T073 pass (depends on T022)

**Checkpoint**: Dual-auth fully functional; US1–US5 independent.

---

## Phase 8: User Story 6 - File Operations and Inference (Priority: P3)

**Goal**: Download artifacts, export datasets to disk, run inference sampling.

**Independent Test**: List+download an artifact to disk; export a dataset to a file; sample text from a registered model.

### Tests for User Story 6 (TDD — write first, must FAIL)

- [x] T077 [P] [US6] Write failing e2e test `tests/e2e/api/test_client_inference.py` (models list + sample)
- [x] T078 [P] [US6] Write failing e2e test `tests/e2e/api/test_client_files.py` (experiment artifact list+download to tmp_path; dataset export to tmp_path)

### Implementation for User Story 6

- [x] T079 [P] [US6] Implement `InferenceSampleCommand` (`POST /v1/inference/sample`) in `anvil/client/inference/inference_sample_command.py` (depends on T026)
- [x] T080 [P] [US6] Implement `InferenceModelsCommand` (`GET /v1/inference/models`) in `anvil/client/inference/inference_models_command.py` (depends on T026)
- [x] T081 [US6] Implement `InferenceClient` aggregator + `anvil/client/inference/__init__.py` (bare docstring) in `anvil/client/inference/inference_client.py` (depends on T079, T080)
- [x] T082 [US6] Verify artifact download / dataset export commands (T042, T063) stream to disk correctly; add any missing wiring (depends on T042, T063)
- [x] T083 [US6] Wire `inference` sub-client into `AnvilClient` in `anvil/client/anvil_client.py` — make T077, T078 pass (depends on T081, T032)

**Checkpoint**: US1–US6 independent. Primary spec stories complete.

---

## Phase 9: Remaining Domain Coverage (FR-012 completeness, Priority: P3)

**Goal**: Complete the full API surface — corpora, eval, compute, services, governance, content
(incl. content SSE streams) — so no endpoint requires raw HTTP.

> **FR-012 vs SC-002**: FR-012 (expose all 12 domains) is the *requirement*; SC-002 (no endpoint
> requires raw HTTP) is its *measurable criterion*. Both are satisfied by completing this phase —
> they are intentionally the same body of work expressed as requirement + success metric.

> **Granularity note (one-class-per-file still applies)**: Each domain task below enumerates the
> command files it produces. Every enumerated command/DTO/aggregator is its own `.py` file with
> exactly one class (Constitution one-class-per-file) and is committed atomically. The long-tail
> P3 domains are grouped into one task per domain for planning legibility; split each into its
> enumerated per-file commits during implementation (mirrors the per-file granularity used for
> datasets/training/experiments/registry above).

### Tests (TDD — write first, must FAIL)

- [x] T084 [P] Write failing e2e test `tests/e2e/api/test_client_corpora.py` (create/list/get/delete/ingest/files/analyze-path)
- [x] T085 [P] Write failing e2e test `tests/e2e/api/test_client_compute_services.py` (compute backends; services list/logs/start/stop; demo bootstrap)
- [x] T086 [P] Write failing e2e test `tests/e2e/api/test_client_eval_governance.py` (eval perplexity + eval-datasets; governance audit/licenses/report)
- [x] T087 [P] Write failing e2e test `tests/e2e/api/test_client_content.py` (corpora/sources/sessions/versions + at least one SSE stream)

### Implementation (each command/DTO/aggregator = one file, one class)

- [x] T088 [P] Implement `corpora` domain under `anvil/client/corpora/`: DTOs + one command file each for create/fork/list/get/delete/ingest/files/file-get/resolve-path/analyze-path (`corpus_*_command.py`) + `CorporaClient` (`corpora_client.py`) + bare `__init__.py` per contracts/commands.md (depends on T026)
- [x] T089 [P] Implement `compute` domain under `anvil/client/compute/`: `ComputeBackendsCommand` (`GET /v1/compute/backends`, `compute_backends_command.py`) + `ComputeClient` (`compute_client.py`) + bare `__init__.py` (depends on T026)
- [x] T090 [P] Implement `services` domain under `anvil/client/services/`: one command file each for services list/logs/restart-all/log-clear/start/stop/restart/kill-port + demo-bootstrap (`service_*_command.py`, `demo_bootstrap_command.py`) + `ServicesClient` (`services_client.py`) + bare `__init__.py` (depends on T026)
- [x] T091 [P] Implement `eval` domain under `anvil/client/eval/`: one command file each for perplexity + eval-dataset create/append-records/get (`eval_*_command.py`) + `EvalClient` (`eval_client.py`) + bare `__init__.py` (depends on T026)
- [x] T092 [P] Implement `governance` domain under `anvil/client/governance/`: one command file each for audit-list/audit-verify/dataset-report/licenses/takedown (`governance_*_command.py`) + `GovernanceClient` (`governance_client.py`) + bare `__init__.py` (depends on T026)
- [x] T093 [P] Implement `content` domain under `anvil/client/content/`: one command file each for corpora/sources/sessions(stage/validate/accept/abandon)/freeze/composition-preview/tag/version-get/lineage/revert/locks/imports endpoints + SSE stream commands for composition/injection/locks/import (`content_*_command.py`) + `ContentClient` (`content_client.py`) + bare `__init__.py` (depends on T023, T026)
- [x] T094 Wire corpora/compute/services/eval/governance/content sub-clients into `AnvilClient` in `anvil/client/anvil_client.py` — make T084–T087 pass (depends on T088–T093, T032)

**Checkpoint**: FR-012 satisfied — all 12 domains reachable; SC-002 (no raw HTTP needed) met.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Quality gates, docs, decision records, and success-criteria validation. (No UI in this feature → UX-lint/review tasks N/A.)

- [x] T095 [P] Author ADR in `docs/vault/Decisions/` recording the SDK architecture decision (four-layer client, httpx transport, in-distribution packaging) per Constitution + research.md R12
- [x] T096 [P] Run `make typecheck` (`mypy --strict`) across `anvil/client/` and fix any findings — zero suppression (SC-006)
- [x] T097 [P] Run `make lint` (ruff/black/isort/pylint) across `anvil/client/` + `tests/unit/client/` + `tests/e2e/api/test_client_*.py` and fix findings
- [x] T098 Run `make test` (full suite incl. coverage) — all SDK tests pass; confirm coverage `fail_under` ratchet NOT decreased (Article IV)
- [x] T099 Validate `quickstart.md` examples compile/run against a live `make run` server (manual smoke per quickstart §7)
- [x] T100 [P] Add SDK section to `README.md` and update `docs/vault/Sessions/` session log; run `make vault-audit` (0 errors) per Vault Enrichment Protocol
- [x] T101 [P] Add SC-003 overhead assertion in `tests/e2e/api/test_client_perf.py`: for the 5 common ops (health, list datasets, start training, list experiments, create dataset), assert SDK-induced overhead (`total_sdk_call_time − server_processing_time`) stays under 100ms over a small sample (validates SC-003)
- [x] T102 [P] Add concurrent-operations e2e test in `tests/e2e/api/test_client_concurrency.py`: drive two operations from a single `AnvilClient` via `asyncio.gather` and assert both succeed independently (validates spec edge cases "concurrent operations" + "non-blocking monitoring")

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories.
- **User Stories (Phases 3–9)**: All depend on Foundational (Phase 2).
  - US1 (Phase 3) is the MVP and also delivers `AnvilClient`, which US2–US6 + Phase 9 extend (they all add/wire sub-clients into the same facade).
  - After US1's facade exists, US2–US6 + Phase 9 are largely independent and parallelizable.
  - US5 (Phase 7) extends `Transport`/`AnvilClient` for session auth — independent of US2–US4 logic.
- **Polish (Phase 10)**: Depends on all desired stories complete.

### User Story Dependencies

- **US1 (P1)**: After Foundational. Establishes `AnvilClient` facade (shared extension point).
- **US2 (P1)**: After US1 facade exists (wires `datasets`). Otherwise independent.
- **US3 (P1)**: After US1 facade exists (wires `training`); needs `stream_sse` (T023). Independent of US2.
- **US4 (P2)**: After US1 facade. Independent of US2/US3.
- **US5 (P2)**: After US1 facade + Transport (T022). Independent of US2–US4.
- **US6 (P3)**: After US1 facade; reuses download (T024) + experiment download (T063). Independent.
- **Phase 9 (P3)**: After US1 facade; content SSE reuses T023.

### Within Each User Story

- Tests written and observed FAILING before implementation (Article IV).
- DTOs/value types before commands; commands before the DomainClient aggregator; aggregator before facade wiring.
- Facade-wiring task is the integration point that makes the story's e2e test pass.

### Parallel Opportunities

- Setup: T002, T003 parallel.
- Foundational: all 7 error classes (T009–T015) parallel after T008; enums T006/T007 parallel; config/response/stream-event test+impl pairs parallel.
- Within a story: all command files marked [P] parallel (distinct files); the aggregator + facade-wiring are sequential (shared files).
- Across stories: once US1's facade lands, US2/US3/US4/US5/US6/Phase-9 command implementation can proceed in parallel by different developers.
- **Shared-file serialization (NOT [P] with each other)**: every facade-wiring/login/logout task edits the SAME file `anvil/client/anvil_client.py` — T032, T044, T053, T071, T074, T075, T083, T094 must serialize (or be carefully merged). Likewise T022/T023/T024/T025/T076 all edit `anvil/client/_shared/transport.py` and must serialize.

---

## Parallel Example: User Story 4 (Experiments)

```bash
# After T056 (Experiment DTO), launch all experiment command files in parallel:
Task: "Implement ExperimentListCommand in anvil/client/experiments/experiment_list_command.py"
Task: "Implement ExperimentGetCommand in anvil/client/experiments/experiment_get_command.py"
Task: "Implement ExperimentCompareCommand in anvil/client/experiments/experiment_compare_command.py"
Task: "Implement ExperimentMetricsCommand in anvil/client/experiments/experiment_metrics_command.py"
Task: "Implement ExperimentDeleteCommand in anvil/client/experiments/experiment_delete_command.py"
Task: "Implement ExperimentArtifactsCommand in anvil/client/experiments/experiment_artifacts_command.py"
Task: "Implement ExperimentDownloadCommand in anvil/client/experiments/experiment_download_command.py"
# Then T064 (aggregator) and T071 (facade wiring) sequentially.
```

---

## Implementation Strategy

### MVP First (User Stories 1–3, all P1)

1. Phase 1: Setup.
2. Phase 2: Foundational (CRITICAL — blocks everything).
3. Phase 3: US1 (connect + health) → **STOP & VALIDATE** (SC-001).
4. Phase 4: US2 (datasets) → validate.
5. Phase 5: US3 (training + SSE) → validate. **Full P1 MVP: connect → data → train → observe.**

### Incremental Delivery

- Foundation → US1 (MVP) → US2 → US3 → US4 → US5 → US6 → Phase 9 (full coverage) → Polish.
- Each story is independently testable via its `tests/e2e/api/test_client_*.py` file.

### Parallel Team Strategy

- Whole team builds Setup + Foundational together.
- One developer lands US1 (facade) first to create the shared extension point.
- Then split: dev A → US2, dev B → US3, dev C → US4/US5, dev D → US6 + Phase 9.
- Coordinate edits to `anvil/client/anvil_client.py` + `anvil/client/_shared/transport.py` (shared files) to avoid conflicts.

---

## Notes

- [P] = different files, no dependencies on incomplete tasks.
- Every `.py` file holds exactly one class (Constitution one-class-per-file); enums in own files.
- All `__init__.py` are bare docstring-only — NO re-exports for internal use (Article VI).
- Internal imports use relative paths (`from .x import Y`, `from .._shared.x import Y`).
- `mypy --strict` clean; no `# type: ignore` / `as any` suppression.
- Commit after each task or logical group (only when explicitly requested).
- Shared files `anvil/client/anvil_client.py` and `anvil/client/_shared/transport.py` are touched by multiple tasks — serialize those (see Parallel Opportunities).
