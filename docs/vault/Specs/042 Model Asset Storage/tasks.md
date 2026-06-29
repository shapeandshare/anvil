# Tasks: Model Asset Acquisition & Storage (LakeFS-ready)

**Input**: Design documents from `docs/vault/Specs/042 Model Asset Storage/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Tests are included per the project's TDD mandate (Article IV). Write tests before implementation — Red-Green-Refactor.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1)
- Include exact file paths in descriptions

## Path Conventions

- Project root at repository root — Python source in `anvil/`, tests in `tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create `anvil/db/models/model_asset.py` — ModelAsset ORM model with ModelAssetType (WEIGHTS/TOKENIZER/CONFIG) and ModelAssetStatus (PENDING/DOWNLOADING/AVAILABLE/UNAVAILABLE/CHECKSUM_MISMATCH) StrEnums, plus TimestampMixin
- [X] T002 [P] Create `anvil/db/models/asset_download_job.py` — AssetDownloadJob ORM model with FK to external_models, status, error fields, TimestampMixin
- [X] T003 [P] Create `anvil/db/models/user_secret.py` — UserSecret ORM model with user_id, key (unique per user), encrypted_value, TimestampMixin
- [X] T004 [P] Create `anvil/services/_shared/asset_download_job_status.py` — AssetDownloadJobStatus StrEnum (QUEUED/DOWNLOADING/COMPLETE/FAILED)
- [X] T005 [P] Create `anvil/db/repositories/model_asset_repository.py` — CRUD with get_by_model(), get_by_model_and_type(), add(), update_status(), update_progress()
- [X] T006 [P] Create `anvil/db/repositories/asset_download_job_repository.py` — CRUD with get(), add(), update_status()
- [X] T007 [P] Create `anvil/db/repositories/user_secret_repository.py` — CRUD with get(), get_all_for_user(), upsert(), delete()
- [X] T008 Generate Alembic migration for new tables (model_assets, asset_download_jobs, user_secrets)

**Checkpoint**: All new ORM models, enums, repositories, and migrations exist — foundational layer is ready

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before user story work

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T009 Create `anvil/services/_shared/encryption.py` — AES-256-GCM encrypt/decrypt via `cryptography` library, following ApiKeyStore pattern for key management (ANVIL_MASTER_SECRET env var with 0600 perms fallback)
- [X] T010 [P] Write unit tests for encryption in `tests/unit/services/test_encryption.py` — encrypt/decrypt roundtrip, key rotation, tampered ciphertext rejection
- [X] T011 [P] Write unit tests for ModelAssetRepository in `tests/unit/db/repositories/test_model_asset_repository.py`
- [X] T012 [P] Write unit tests for UserSecretRepository in `tests/unit/db/repositories/test_user_secret_repository.py`

**Checkpoint**: Foundation ready — encryption works, repos tested, user story implementation can begin

---

## Phase 3: User Story 1 - Learner Acquires and Stores a Model's Assets (Priority: P1) 🎯 MVP

**Goal**: A learner can download the weights, tokenizer, and config for an imported model; assets become managed, tracked artifacts; model metadata flips to "assets available".

**Independent Test**: For a metadata-only model, call the download endpoint, poll the job status until complete, verify assets land in the managed store with checksums recorded and entry shows "assets available".

### Tests for User Story 1

- [X] T013 [P] [US1] Write unit tests for ModelAssetService (submit + run + status) in `tests/unit/services/test_model_asset_service.py`
- [X] T014 [P] [US1] Write e2e tests for download endpoints in `tests/e2e/test_model_assets.py` — happy path, gated model with token, unsupported format rejection, concurrent download rejection

### Implementation for User Story 1

- [X] T015 [US1] Implement `UserSecretService` in `anvil/services/model_import/user_secret_service.py` — get_secret(), set_secret(), delete_secret(), resolve_token() with UserSecret > env var precedence
- [X] T016 [P] [US1] Add HF file discovery + download methods to `anvil/services/model_import/hf_source.py` — list_repo_files(), download_file() via hf_hub_download, wrapped in run_in_executor
- [X] T017 [P] [US1] Create `anvil/services/model_import/format_detector.py` — format verification via safetensors.safe_open() (FR-033), reject non-safetensors weight formats (FR-030)
- [X] T018 [US1] Implement `ModelAssetService` in `anvil/services/model_import/model_asset_service.py` — submit_download() (create job + pre-create ModelAsset rows), run_download() (resolve files → stream → SHA-256 → FileStore.put() → update status), get_job_status() (aggregate + per-asset), model-level lock check
- [X] T019 [US1] Expose ModelAssetService via `AnvilWorkbench` in `anvil/workbench.py` — add `model_assets` property, wire dependencies
- [X] T020 [US1] Add `POST /v1/models/{id}/download` route returning HTTP 202 + job_id in `anvil/api/v1/models.py` — follow _fire_background_import() pattern
- [X] T021 [US1] Add `GET /v1/models/{id}/download/{job_id}/status` route returning job + aggregate progress in `anvil/api/v1/models.py`
- [X] T022 [US1] Add `GET /v1/models/{id}/assets` route returning ModelAsset list in `anvil/api/v1/models.py`
- [X] T023 [US1] Add `POST /v1/user/secrets` and `GET /v1/user/secrets` routes in `anvil/api/v1/user_secrets.py` for HF token management
- [X] T024 [P] [US1] Add SDK client commands — `anvil/client/models/download_assets_command.py` (POST) and `anvil/client/models/download_status_command.py` (GET status)

**Checkpoint**: At this point, the learner can download model assets end-to-end, track progress, and the model entry flips to ASSETS_AVAILABLE

---

## Phase 4: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple areas

- [X] T025 [P] Run `make lint`, `make typecheck`, `make test` — fix any failures introduced by this feature
- [X] T026 [P] Update `docs/vault/Specs/Specs.md` — add 042 entry to the spec index
- [X] T027 [P] Verify Alembic migration is reversible: `alembic downgrade -1` then `alembic upgrade +1`
- [X] T028 [P] Run `make vault-audit` — must report 0 errors

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately. All T001–T008 can run in parallel within their grouping.
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational completion.
- **Polish (Phase 4)**: Depends on all user stories being complete.

### Within User Story 1

- Tests (T013, T014) MUST be written and FAIL before implementation begins
- Models/repos before services (T015–T017 before T018)
- Service before API wiring (T018 before T019–T023)
- API before SDK (T020–T023 before T024)
- Story complete before moving to Polish

### Parallel Opportunities

- All Phase 1 tasks marked [P] can run in parallel (distinct files)
- T010, T011, T012 (test files) can run in parallel
- T013, T014 (US1 test files) can run in parallel
- T016, T017 (HF source + format detector) can run in parallel
- T024 (SDK) can run in parallel with T020–T023 after T018 is done

---

## Parallel Example: User Story 1

```bash
# Launch tests first (write, expect fail):
task: "Write unit tests for ModelAssetService in tests/unit/services/test_model_asset_service.py"
task: "Write e2e tests for download endpoints in tests/e2e/test_model_assets.py"

# Launch independent components in parallel:
task: "Add HF download methods to anvil/services/model_import/hf_source.py"
task: "Create format detector in anvil/services/model_import/format_detector.py"
task: "Implement UserSecretService in anvil/services/model_import/user_secret_service.py"

# After service is done, wire API in parallel:
task: "Add POST download route in anvil/api/v1/models.py"
task: "Add GET status route in anvil/api/v1/models.py"
task: "Add GET assets route in anvil/api/v1/models.py"
task: "Add secrets routes in anvil/api/v1/secrets.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup — all models, enums, repos, migration
2. Complete Phase 2: Foundational — encryption, unit tests for repos
3. Complete Phase 3: User Story 1 — full end-to-end asset download
4. **STOP and VALIDATE**: Run e2e tests, verify SC-001 through SC-005
5. Polish

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Each PHASE within US1 adds value: models → service → API → SDK

### Notes

- [P] tasks = different files, no dependencies
- [US1] label maps task to user story for traceability
- Each phase should be independently completable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate independently
