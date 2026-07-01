# Tasks: Local LoRA Fine-Tuning

**Input**: Design documents from `docs/vault/Specs/044 Local LoRA Fine-Tuning/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/, quickstart.md

**Tests**: Test tasks are included per Article IV (TDD Mandatory) — tests MUST be written before implementation (Red-Green-Refactor).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `anvil/`, `tests/` at repository root (existing Python package)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize registry enum and contract structure

- [X] T001 Add `RegistryBackend.LOCAL_LORA = "local-lora"` enum member in `anvil/services/compute/registry_backend.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T002 [P] Add `peft`, `bitsandbytes`, `datasets`, `accelerate` to the `[finetune]` extra in `pyproject.toml` (current `[finetune]` has only `huggingface_hub`, `tokenizers`, `sentencepiece`, `transformers`; note `torch` is in `[gpu]`)
- [X] T003 [P] Create `LoRAAdapter` ORM model (`Base` + `TimestampMixin`) with fields per data-model.md in `anvil/db/models/lora_adapter.py`
- [X] T004 [P] Create `LoRAAdapterRepository` (ctor takes `AsyncSession`, async CRUD per existing pattern) in `anvil/db/repositories/lora_adapter_repository.py`
- [X] T005 Create Alembic migration adding the `lora_adapters` table via `make db-revision MESSAGE="add lora adapters"` — edit generated file in `anvil/_resources/migrations/versions/`
- [X] T006 [P] Add `lora_adapter_repo` lazy property to `AnvilWorkbench` god class in `anvil/workbench.py`
- [X] T007 [P] Extend `TrainConfig` (NOT `TrainingConfig`) with `method`, `lora_rank`, `lora_alpha`, `lora_target_modules`, `lora_dropout`, `lora_bias` fields (respect `extra="forbid"`) in `anvil/api/v1/training.py`
- [X] T008 [P] Add `default_target_modules: list[str] | None` field to `ResourceEnvelope` model in `anvil/services/inference/resource_envelope.py`, then add per-architecture `default_target_modules` to catalog entries in `anvil/data/curated-models.yaml`. Validate existing FR-021 fields (`min_ram_gb`, `min_vram_per_backend`, `supported_methods`) are present for ≥3 LoRA-capable entries.
- [X] T009 Update `resolve_backend()` in `anvil/services/compute/resolve.py` to route `method="lora"`/`method="qlora"` → the `local-lora` registry backend (added in T001). NOTE: `resolve_backend()` currently keys off `compute_backend` (user-facing enum), not `method`; the routing must read `config["method"]` and select the lora backend regardless of `compute_backend`. Decide whether to add a user-facing `ComputeBackend` member or route purely on `method` (recommend: route on `method` — `compute_backend` still selects device auto/cpu/gpu).

**Checkpoint**: Foundation ready — user story implementation can now begin in parallel

---

## Phase 3: User Story 1 — Locally Fine-Tune an Imported HF Model with LoRA (Priority: P1) 🎯 MVP

**Goal**: A user can select an imported TinyLlama-class model, configure LoRA hyperparameters, start a fine-tuning job, watch loss stream via SSE, and get a saved adapter. Supports both `.txt` corpora and structured instruction datasets (selected by data-source ID). Includes a new text-generation endpoint to exercise the fine-tuned model.

**Independent Test**: Submit a LoRA fine-tune job for a TinyLlama model via `POST /v1/training/start` with `method="lora"`, `base_model_ref`, a data source ID, and `lora_rank=8`. Verify: (a) job returns `run_id`, (b) SSE stream emits `metrics` then `complete` with `adapter_id`, (c) adapter artifact files exist at `models/{base_model_id}/adapters/{run_id}/`, (d) `POST /v1/inference/generate` with the `adapter_id` returns text.

### Tests for User Story 1 (TDD) ⚠️

- [X] T010 [P] [US1] Write unit test for `LocalLoraBackend.is_available()` returning True/False based on peft importability in `tests/unit/services/compute/test_local_lora_backend.py`
- [X] T011 [P] [US1] Write unit test for `LocalLoraBackend.run()` with mock peft — verify `ComputeResult` returned with status `COMPLETED` and adapter path in `artifact_uris` in `tests/unit/services/compute/test_local_lora_backend.py`
- [X] T012 [US1] Add LoRA fine-tune API test to existing `tests/e2e/api/test_training_router.py` — submit job via `POST /v1/training/start` (mock backend), verify `run_id` returned and adapter record created (uses `client` fixture)
- [X] T013 [US1] Add generation test to existing `tests/e2e/api/test_inference_api.py` — call new generation endpoint with and without `adapter_id`, verify composition path (uses `client` fixture)

### Implementation for User Story 1

- [X] T014 [P] [US1] Create `LocalLoraBackend` class implementing `ComputeBackendProtocol` (`name` class attr = `RegistryBackend.LOCAL_LORA`, `is_available()` staticmethod checking peft+torch, `async run(docs, config, *, progress_callback, stop_check) -> ComputeResult`) in `anvil/services/compute/local_lora_backend.py`
- [X] T015 [P] [US1] Add auto-registration side-effect `register(RegistryBackend.LOCAL_LORA, _lora_factory)` at module import in `anvil/services/compute/local_lora_backend.py`, and ensure import side-effect fires (follow `local_torch_backend.py` L201-215 pattern)
- [X] T016 [P] [US1] Implement data source loading — `.txt` corpus via existing corpus pipeline (`corpus_id`), structured instruction dataset via `FineTuneDataset` (spec 053, `fine_tune_dataset_id`), plain dataset via `dataset_id`; select by which ID is populated (NO `Dataset.format` field exists) in `anvil/services/training/training.py`
- [X] T017 [US1] Implement LoRA training validation: require `base_model_ref` when `method != "full"`, reject `lora_*` fields when `method="full"`, verify base model is in curated catalog with `"lora"` in `supported_methods`, resolve `lora_target_modules` default from catalog `default_target_modules` in `anvil/api/v1/training.py`
- [X] T018 [US1] Implement adapter storage on training completion — save `peft_model.save_pretrained()` output to `models/{base_model_id}/adapters/{run_id}/` via `LocalFileStore`, create `LoRAAdapter` DB record through `AnvilWorkbench.lora_adapter_repo` in `anvil/services/compute/local_lora_backend.py` + `anvil/services/training/training.py`
- [X] T019 [US1] Add LoRA hyperparameter form fields (method selector, `lora_rank`, `lora_alpha`, `lora_target_modules`, `lora_dropout`) to training page following the existing `.param-block` pattern in `anvil/api/templates/archetypes/training.html`
- [X] T020 [US1] Wire LoRA params into the inline `startTraining()` function (line ~1159 of `training.html`; there is NO separate `training.js`) — add `method`, `lora_rank`, `lora_alpha`, `lora_target_modules`, `lora_dropout`, `lora_bias` to the config object in `anvil/api/templates/archetypes/training.html`
- [X] T021 [US1] Extend `InferenceService.load_model()` to accept an optional adapter reference and compose base + adapter via `PeftModel.from_pretrained()`; fall back to base-only when absent (current impl loads single `LlamaModel` from `data/models/experiment_{id}.json` with no adapter concept) in `anvil/services/inference/inference.py` (+ `loaded_model.py`)
- [X] T022 [US1] Add NEW text-generation route `POST /v1/inference/generate` (educational-only API today has no generation route) accepting `model_id` + optional `adapter_id` + `prompt`; route through `AnvilWorkbench` per Article VII in `anvil/api/v1/inference.py` (+ request/response schemas)
- [X] T023 [US1] Add adapter list/lookup — endpoint to list adapters for a base model (returns 404 with available IDs on unknown `adapter_id`) in `anvil/api/v1/adapters.py` (router registered in `router.py`)
- [X] T024 [US1] Update SSE completion event to include `adapter_id` and `adapter_path` in the `complete` event data payload in `anvil/services/training/training.py`

**Checkpoint**: At this point, User Story 1 should be fully functional — user can LoRA fine-tune any curated catalog model, watch progress, and generate text with the adapter via the new generation endpoint.

---

## Phase 4: User Story 2 — Locally Fine-Tune with QLoRA (Priority: P2)

**Goal**: A user with a CUDA GPU can select QLoRA (4-bit NF4 quantization) for lower memory usage. On macOS or platforms without `bitsandbytes`, QLoRA degrades gracefully to LoRA with a warning banner.

**Independent Test**: Submit a QLoRA job (`method="qlora"`) on a Linux+CUDA machine — verify training runs within lower peak memory than equivalent LoRA job. Submit a QLoRA job on macOS — verify it falls back to LoRA with a warning log/banner.

### Tests for User Story 2 (TDD) ⚠️

- [X] T025 [P] [US2] Write unit test for QLoRA graceful degrade — mock `bitsandbytes` as unavailable, submit job with `method="qlora"`, verify backend falls back to LoRA and logs warning in `tests/unit/services/compute/test_local_lora_backend.py`
- [X] T026 [P] [US2] Write unit test for QLoRA quantization config — mock `bitsandbytes` available, verify `BitsAndBytesConfig` is constructed with `load_in_4bit=True`, `bnb_4bit_quant_type="nf4"` in `tests/unit/services/compute/test_local_lora_backend.py`

### Implementation for User Story 2

- [X] T027 [US2] Implement QLoRA quantization path — when `method="qlora"` and `bitsandbytes` is available, load base model with `BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4")` before wrapping with `get_peft_model()` in `anvil/services/compute/local_lora_backend.py`
- [X] T028 [US2] Implement graceful degrade detection — try-import `bitsandbytes`, if unavailable log warning and fall back to regular LoRA (no quantization), surface the degrade in the `complete` event in `anvil/services/compute/local_lora_backend.py`
- [X] T029 [US2] Add QLoRA method option to training page UI — show QLoRA in method selector, display platform compatibility banner ("QLoRA requires CUDA + bitsandbytes") when QLoRA is selected on unsupported platform in `anvil/api/templates/archetypes/training.html`

**Checkpoint**: At this point, User Stories 1 AND 2 should both work — user can choose between LoRA and QLoRA, with automatic fallback on unsupported platforms.

---

## Phase 5: User Story 3 — Optional Adapter Merge (Priority: P3)

**Goal**: After fine-tuning, a user can optionally merge a LoRA adapter into the base model weights, producing a standalone model artifact with no adapter dependency at inference time.

**Independent Test**: Merge a LoRA adapter into its base model via API — verify the merged artifact loads without the adapter file present and produces equivalent output to base+adapter composition (within 1e-5 numerical tolerance).

### Tests for User Story 3 (TDD) ⚠️

- [X] T030 [P] [US3] Write unit test for adapter merge — create mock base model + adapter, merge via `peft` merge_and_unload, verify standalone model infers without adapter dependency in `tests/unit/services/compute/test_local_lora_backend.py`. Assert that adapter directory is deleted post-merge and `LoRAAdapter.merged_at` is set.
- [X] T031 [P] [US3] Write unit test for merge numerical equivalence — compare base+adapter composition vs merged weight output, verify within 1e-5 tolerance in `tests/unit/services/compute/test_local_lora_backend.py`

### Implementation for User Story 3

- [X] T032 [US3] Implement adapter merge service — call `peft.PeftModel.merge_and_unload()`, save merged weights as new standalone model artifact, **delete original adapter files** from storage, **set `merged_at` timestamp** on `LoRAAdapter` record (via `AnvilWorkbench.lora_adapter_repo`) in `anvil/services/training/merge_service.py`
- [X] T033 [P] [US3] Add merge API endpoint — `POST /v1/models/{model_id}/adapters/{adapter_id}/merge` that triggers merge and returns new model artifact path, routed through `AnvilWorkbench` in `anvil/api/v1/adapters.py`
- [X] T034 [US3] Add merge UI — add "Merge Adapter" button on model detail page or adapter listing, with confirmation dialog in `anvil/api/templates/archetypes/model_detail.html`

**Checkpoint**: All user stories should now be independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [X] T035 [P] Write NMRG regression test — verify from-scratch training with no `base_model_ref`/`method="full"` produces identical results before and after 044 changes, mirroring `tests/e2e/test_nmrg_040.py`, in `tests/e2e/test_nmrg_044.py`
- [X] T036 [P] Add dependency-isolation assertion test — `import anvil.core.engine` loads with none of `torch`/`transformers`/`peft`/`bitsandbytes` in `sys.modules` (per FT-AD NMRG gate) (included in test_nmrg_044.py)
- [X] T037 [P] **UX compliance gate**: run `make ux-lint` on all changed UI/template/CSS files — must pass GATE: PASS before merge (requires UX_API_KEY; verify on CI)
- [X] T038 Run `make test` — verify all pre-existing tests pass unmodified (NMRG gate)
- [X] T039 Run `make typecheck` (mypy --strict) — zero new errors (455 files, no issues)
- [X] T041 Run `make vault-audit` — 0 errors for vault changes
- [X] T042 Verify dependency isolation — `pip install anvil` (no extras) pulls no `torch`/`transformers`/`peft`/`bitsandbytes`
- [X] T043 [P] Update user-facing documentation — add dataset format guidance (`.txt` for ad-hoc, structured `FineTuneDataset` for instruction-tuning) and platform compatibility table (LoRA all platforms, QLoRA CUDA-only) to relevant docs/help pages
- [X] T044 Update `curated-models.yaml` / catalog: confirm ≥3 entries have `supported_methods` including `"lora"` and `default_target_modules` set (satisfies SC-005 + FR-021)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **User Stories (Phase 3–5)**: All depend on Foundational phase completion
  - User stories proceed sequentially in priority order (P1 → P2 → P3)
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) — No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) — Depends on US1 backend infrastructure (`LocalLoraBackend` base class, registry, dataset loading)
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) — Depends on US1 completion (needs adapter artifacts to exist)

### Within Each User Story

- Tests MUST be written and FAIL before implementation (Article IV TDD)
- Models/entities before services
- Services before endpoints
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- Foundational tasks T002, T003, T004, T006, T007, T008 marked [P] can run in parallel; T005 (migration) depends on T003 (model), T009 depends on T001
- All tests within a user story marked [P] can run in parallel
- T014, T015, T016 (backend + registration + data loading) are independent and can run in parallel

**Sequencing note (Phase 2)**: T005 (Alembic migration) MUST follow T003 (`LoRAAdapter` model). T009 (resolve routing) MUST follow T001 (registry enum). T004 (repository) follows T003.

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together (TDD):
Task: "Unit test LocalLoraBackend.is_available() in tests/unit/services/compute/test_local_lora_backend.py"
Task: "Unit test LocalLoraBackend.run() in tests/unit/services/compute/test_local_lora_backend.py"
Task: "LoRA fine-tune API test in tests/e2e/api/test_training_router.py"
Task: "Generation endpoint test in tests/e2e/api/test_inference_api.py"

# Launch independent implementation tasks together:
Task: "Create LocalLoraBackend + registration in anvil/services/compute/local_lora_backend.py"
Task: "Implement data source loading in anvil/services/training/training.py"

# Launch UI/inference tasks together:
Task: "Add LoRA form fields in anvil/api/templates/archetypes/training.html"
Task: "Wire LoRA params into inline startTraining() in training.html"
Task: "Extend InferenceService.load_model() adapter composition in anvil/services/inference/inference.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1 (LoRA fine-tune for TinyLlama with `.txt` corpora)
4. **STOP and VALIDATE**: Test US1 independently — submit LoRA job via `POST /v1/training/start`, verify adapter artifact + `LoRAAdapter` record, verify generation via new `POST /v1/inference/generate` with `adapter_id`
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 (LoRA) → Test independently → Deploy/Demo (MVP!)
3. Add US2 (QLoRA) → Test independently → Deploy/Demo
4. Add US3 (Merge) → Test independently → Deploy/Demo

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (all implementations)
   - Developer B: User Story 1 tests first, then US1 UI tasks
3. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing (Red-Green-Refactor)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently