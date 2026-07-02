# Tasks: 047 SaaS Fine-Tuning Pipeline (MVP)

**Input**: Design documents from `docs/vault/Specs/047 SaaS Fine-Tuning Pipeline/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

> **SCOPE (corrected 2026-07-02, Oracle-reviewed):** The assumed foundation (spec 032 SaaS
> pipeline, LakeFS 019/042, multi-tenancy) **does not exist in code**. This task list
> delivers a **thin, testable MVP**: a provider-backed SaaS fine-tune backend + a fix for the
> pre-existing adapter-persistence bug. Real AWS Batch, `ResourceSpec`, `job_events`,
> GPU-hour metering, LakeFS storage, and per-org concurrency/tenancy are **DEFERRED** to
> follow-on specs and are NOT in this task list.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- Include exact file paths in descriptions

## Path Conventions

- **Source**: `anvil/` at repository root
- **Tests**: `tests/unit/` and `tests/e2e/` at repository root

---

## Phase 1: Setup

**Purpose**: Verify the working branch and feature wiring.

- [ ] T001 Verify branch is `047-saas-fine-tuning-pipeline` and `.specify/feature.json` points to `docs/vault/Specs/047 SaaS Fine-Tuning Pipeline`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Fix the pre-existing adapter-persistence gap FIRST — it is a prerequisite for any credible SaaS "tracked adapter" result, and it is shared by the local path.

**⚠️ CRITICAL**: US1 (SaaS backend) cannot be verified until adapter persistence works.

### Tests (TDD — write first, must FAIL)

- [ ] T002 [P] Write failing unit test in `tests/unit/services/test_adapter_persistence.py` proving that after a LOCAL LoRA run completes, a `LoRAAdapter` DB row is created (via `LoRAAdapterRepository.get_by_model`) with a non-null `storage_path` and the row's `adapter_id` matches `ComputeResult.adapter_id`.
- [ ] T003 [P] Write failing unit test in `tests/unit/services/test_adapter_persistence.py` proving `LocalLoraBackend.run()` returns a `ComputeResult` with a non-null `adapter_id` (currently always `None`).

### Implementation

- [ ] T004 Populate `adapter_id` in `anvil/services/compute/local_lora_backend.py` — set `ComputeResult.adapter_id` (e.g. derived from the run/timestamp) alongside the existing `artifact_uris["adapter_path"]` at the success return (around lines 545-553).
- [ ] T005 Create adapter-persistence logic in `anvil/services/training/adapter_persistence.py` (new file, one class) — a service that, given a `ComputeResult` with an adapter path + the training config, creates a `LoRAAdapter` row via `LoRAAdapterRepository.add()`, populating the required fields: `external_model_id` (FK to `external_models.id` — resolve from `config["base_model_ref"]`), `run_id`, `adapter_id` (from `result.adapter_id`), `method`, `storage_path` (required, non-null), `lora_rank`, `lora_alpha` (required), and nullable `lora_target_modules` (JSON string), `lora_dropout`, `lora_bias`, `final_loss`. **Edge case (add a failing test first)**: when `base_model_ref` does not map to a registered `ExternalModel` (no `external_model_id`), persistence MUST NOT crash the run — log a warning and skip the row (the FK is `NOT NULL`). This preserves NMRG for ad-hoc/local base models.
- [ ] T006 Wire adapter persistence into the completion path — call the new persistence service from within the `on_complete` closure in `anvil/api/v1/training.py` (defined at line 772; the closure captures `config: TrainConfig`, `run_id`, `dataset_id`, `mlflow_run_id` — use `config.base_model_ref` for the base model, NOT the `_config` dict param) AND the `on_complete` in `anvil/cli.py` (around line 313), invoked only when `result.adapter_id` is set. Expose the service via `anvil/workbench.py` (God Class) following the existing repo/service property pattern (e.g. mirror the `lora_adapter_repo` property at line 590). Note: `on_complete` currently only fires MLflow + safetensors export for the `model is not None` (full-weight) path — ensure the adapter-persistence call is OUTSIDE that `if model is not None:` block so it runs for LoRA results (where `model is None`).

**Checkpoint**: A LOCAL LoRA fine-tune now persists a `LoRAAdapter` row. T002/T003 pass. This is independently valuable (fixes a real bug) and NMRG-safe for non-LoRA runs.

---

## Phase 3: User Story 1 — Provider-Backed SaaS Fine-Tune (Priority: P2) 🎯 MVP

**Goal**: A learner submits a LoRA/QLoRA fine-tune with `compute_backend="saas"`; when SaaS is configured, it dispatches to a `SaasFinetuneBackend` (submit-then-poll via an injected provider seam), streams metrics via the existing SSE pipeline, persists a `LoRAAdapter` row, and returns a `ComputeResult` with a real `adapter_id`.

**Independent Test**: With a fake `SaasFinetuneProvider` injected and `_saas_configured()` forced true, submit a LoRA fine-tune with `compute_backend="saas"`; verify it routes to `SaasFinetuneBackend`, the provider's submit/poll are invoked, metrics stream via SSE, a `LoRAAdapter` row is persisted, and the returned `ComputeResult` has a non-null `adapter_id`.

### Tests (TDD — write first, must FAIL)

- [ ] T007 [P] [US1] Write failing unit tests in `tests/unit/services/test_saas_finetune_backend.py` for `SaasFinetuneBackend.run()` using an injected fake provider (mirror `ModalBackend`'s `function_factory` seam): success path (returns `ComputeResult` with `adapter_id` + `artifact_uris["adapter_path"]`, `ComputeBackendResult.SAAS`), failure path, and user-cancellation via `stop_check` (single `failed` terminal state).
- [ ] T008 [P] [US1] Write failing unit test in `tests/unit/services/test_saas_finetune_backend.py` for `is_available()` delegating to `_saas_configured()`, and for auto-registration under `RegistryBackend.SAAS_FINETUNE`.
- [ ] T009 [P] [US1] Write failing unit test in `tests/unit/services/test_saas_finetune_backend.py` for routing: `resolve_fine_tune()` returns `ComputeBackendResult.SAAS` when `compute_backend="saas"` and `_saas_configured()` is true, and `training.py` maps that to `RegistryBackend.SAAS_FINETUNE` (guards against the current remap-only-in-LOCAL-branch bug).
- [ ] T010 [P] [US1] Write failing e2e HTTP test in `tests/e2e/test_saas_finetune.py`: submit a LoRA fine-tune with `compute_backend="saas"` (fake provider + SaaS forced-configured), assert a run is created, SSE `complete` event fires, and a `LoRAAdapter` row exists afterward.

### Implementation

- [ ] T011 [P] [US1] Create the minimal provider seam in `anvil/services/compute/saas_finetune_provider.py` (new file, one Protocol/class) — an async `SaasFinetuneProvider` Protocol with exactly three methods: `submit(config) -> job_ref`, `poll_status(job_ref) -> status`, `fetch_adapter(job_ref) -> local_path`. **No `ResourceSpec`, no tenant fields, no event abstractions** (YAGNI, Article XI).
- [ ] T012 [US1] Implement `SaasFinetuneBackend` in `anvil/services/compute/saas_finetune_backend.py` (new file) — satisfies `ComputeBackendProtocol`: `name = RegistryBackend.SAAS_FINETUNE`, `is_available()` delegates to `_saas_configured()`, `run()` follows `ModalBackend` submit-then-poll: submit via provider → poll loop (emit progress via `progress_callback`, honor `stop_check`) → `fetch_adapter` → return `ComputeResult(status=COMPLETED, adapter_id=..., artifact_uris={"adapter_path": ...}, backend=ComputeBackendResult.SAAS, engine=TrainingEngine.TORCH)`. Accept an optional injected provider for testing. Auto-register via `register(RegistryBackend.SAAS_FINETUNE, _saas_finetune_factory)`.
- [ ] T013 [US1] Implement real `_saas_configured()` in `anvil/services/compute/resolve.py` — replace `return False` (lines 193-204) with an env-based check (e.g. `ANVIL_SAAS_ENDPOINT` present). Keep it side-effect-free.
- [ ] T014 [US1] Fix the backend remap bug in `anvil/services/training/training.py` (lines 527-536) — add handling so that when `method in ("lora","qlora")` and `backend_name == ComputeBackendResult.SAAS`, `backend_name` is set to `RegistryBackend.SAAS_FINETUNE` (currently the LoRA remap only runs inside the `if backend_name == ComputeBackendResult.LOCAL:` block, so SaaS never remaps and `get_backend("saas")` would raise `ComputeBackendUnavailable`).
- [ ] T015 [US1] Emit the `submitted` SSE event for SaaS runs in `anvil/services/training/training.py` (around line 560) — the current guard is `if backend_name == ComputeBackendResult.MODAL:`; extend it so `SAAS_FINETUNE` runs also emit the `submitted` event.
- [ ] T016 [US1] Ensure SaaS completion persists a `LoRAAdapter` row — verify the Phase-2 adapter-persistence service is invoked for SaaS `ComputeResult`s (the `on_complete` path is backend-agnostic, so this should require no extra code; add an assertion-backed test rather than duplicate logic).

**Checkpoint**: A SaaS-routed LoRA fine-tune (with a fake provider) runs submit-then-poll, streams metrics, and persists a tracked adapter. All US1 tests pass. Local mode unchanged (NMRG).

---

## Phase 4: Polish & Cross-Cutting Concerns

- [ ] T017 [P] Add retry handling in `SaasFinetuneBackend.run()` — on transient provider failure, retry up to 3 times with exponential backoff (30s / 90s / 270s); exhaustion → single `failed` terminal state. (Backoff constants configurable; provider decides what's transient.)
- [ ] T018 [P] Document deferred capabilities — add follow-on spec notes (or issues) for: AWS Batch + `ResourceSpec` (032), durable `job_events` + GPU-hour metering (032), LakeFS stores (019/042), per-org concurrency + tenancy. Note these are prerequisites for the deferred FRs (FR-023a/b/c, SC-001/002/003).
- [ ] T019 Run `make typecheck` (mypy --strict) — fix any type errors in new/changed files
- [ ] T020 Run `make lint` (ruff → black --check → isort --check → pylint) — fix issues
- [ ] T021 Run `make test` — all tests pass; coverage meets `fail_under`
- [ ] T022 Run `make vault-audit` — 0 errors before committing vault changes

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: adapter-persistence fix — BLOCKS US1 verification
- **User Story 1 (Phase 3)**: depends on Phase 2 (needs adapter persistence to prove a tracked SaaS adapter)
- **Polish (Phase 4)**: depends on US1

### Within Each Phase

- Tests (T002/T003, T007–T010) MUST be written and FAIL before implementation
- Provider seam (T011) before backend (T012)
- `_saas_configured()` (T013) + remap fix (T014) before routing test (T009) passes
- Adapter-persistence service (T005) before wiring (T006)

### Parallel Opportunities

| Group | Tasks | Why parallel |
|-------|-------|-------------|
| Foundational tests | T002, T003 | Independent test functions |
| US1 tests | T007, T008, T009, T010 | Independent test cases |
| US1 seam then impl | T011 → T012 | T011 blocks T012 (dependency) |
| Polish | T017, T018 | Different files |

---

## Parallel Example: User Story 1

```bash
# Write all US1 tests first (they must fail):
Task: "Unit tests for SaasFinetuneBackend.run() with fake provider"
Task: "Unit test for is_available() + auto-registration"
Task: "Unit test for SAAS → SAAS_FINETUNE routing (remap bug guard)"
Task: "e2e test: submit SaaS LoRA → adapter row persisted"

# Then implement seam → backend → routing fixes:
Task: "Create SaasFinetuneProvider Protocol (3 methods)"
Task: "Implement SaasFinetuneBackend (submit-then-poll)"
```

---

## Implementation Strategy

### MVP First

1. Phase 1: Setup
2. Phase 2: Fix adapter persistence (independently valuable bug fix)
3. Phase 3: Provider-backed SaaS backend
4. **STOP and VALIDATE**: e2e — submit SaaS LoRA (fake provider) → tracked adapter row
5. Phase 4: Polish + document deferrals

### What This MVP Explicitly Does NOT Do (deferred)

- No real AWS Batch dispatch / `ResourceSpec` (FR-023a) — provider seam is a fake in tests
- No durable `job_events` / Last-Event-ID replay — reuses existing in-memory SSE queue
- No GPU-hour usage metering / billback (SC-002) — no metering table added
- No LakeFS storage (FR-023b, SC-001, SC-003) — adapters stored via `LocalFileStore`
- No per-org concurrency limit / `org_id` scoping (FR-023c) — no tenancy in codebase yet

Each deferred item is a follow-on spec; the provider seam + `LoRAAdapter` persistence are the
stable integration points they build on.

---

## Notes

- [P] tasks = different files (or independent test functions), no dependencies
- Verify tests fail before implementing (TDD, Constitution Article IV)
- Reuse patterns: `ModalBackend` (submit-then-poll + `function_factory` test seam), `LocalLoraBackend` (PEFT config schema), `LocalFileStore` (artifact storage)
- Keep the provider seam to 3 methods — do NOT add `ResourceSpec`/tenant/event surface (YAGNI, Article XI)
- One class per file; `mypy --strict`; NumPy docstrings; relative imports only