---
title: "045 Adapter Inference Export - tasks"
type: spec
tags:
  - type/spec
  - domain/training
  - domain/mlops
created: "2026-07-01"
updated: "2026-07-01"
description: "Task list for 045 - Adapter Inference, Merge & Export"
---

# Tasks: 045 - Adapter Inference, Merge & Export

**Input**: Design documents from `docs/vault/Specs/045 Adapter Inference Export/`
**Prerequisites**: plan.md (required), spec.md (required), data-model.md, contracts/api-contract.md, research.md, quickstart.md

**Tests**: Included — e2e tests for inference and merge+export flows (per spec US "Independent Test" requirement).

**Organization**: Tasks are grouped by logical phase. The spec has one user story (P2) with three
sub-features: ComputeResult adapter shape, adapter inference, and merge+export with lineage.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which sub-feature this task belongs to
- Include exact file paths in descriptions

## Path Conventions

- All source paths are relative to the `anvil/` package root inside the repository
- All test paths are relative to the `tests/` directory at repository root
- Repository root: `/Users/joshburt/.local/share/opencode/worktree/5354809a525912e5a56a6d4a6e81ccf9f89efdf3/playful-canyon`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Verify prerequisites and understand the existing codebase

No project initialization needed — this is an additive change to an existing Python package.
Prerequisites are confirmed by spec 044 implementation (LoRAAdapter, AdapterMergeService,
LocalLoraBackend all exist).

- [X] T001 Verify AdapterMergeService exists and understand current merge flow in `anvil/services/training/merge_service.py`
- [X] T002 [P] Verify InferenceService.load_model() adapter_id plumbing in `anvil/services/inference/inference.py`
- [X] T003 [P] Verify LoRAAdapterRepository and LoRAAdapter ORM in `anvil/db/repositories/lora_adapter_repository.py` and `anvil/db/models/lora_adapter.py`
- [X] T004 [P] Verify SafetensorsExportService interface in `anvil/services/training/export.py`
- [X] T005 [P] Verify TrackingService.register_source_model() for lineage in `anvil/services/tracking/tracking.py`

**Checkpoint**: Codebase readiness confirmed

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before user story work begins

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T006 Add `adapter_id: str | None = None` field to `ComputeResult` in `anvil/services/compute/result.py`
- [X] T007 [P] Update `ComputeResult` docstring to document the three result shapes (local, remote, adapter) in `anvil/services/compute/result.py`
- [X] T008 [P] Run `make typecheck` and `make test` to verify NMRG — no regressions from extending `ComputeResult`

**Checkpoint**: Foundation ready — ComputeResult supports adapter shape; existing tests pass

---

## Phase 3: Adapter Inference — Compose Base + Adapter at Load Time

**Goal**: `InferenceService.load_model()` actually composes a LoRA adapter onto the base model when
`adapter_id` is provided, using `peft.PeftModel.from_pretrained()`.

**Independent Test**: Load a base model with an adapter via the inference service, verify generated
text differs from base-only generation.

- [X] T009 [P] [INFER] Write unit test for adapter inference flow in `tests/unit/services/inference/test_adapter_inference.py`
- [X] T010 [P] [INFER] Write e2e test for generation endpoint with `adapter_id` in `tests/e2e/test_adapter_generation.py`
- [X] T011 [P] [INFER] Update `InferenceService.load_model()` in `anvil/services/inference/inference.py` to actually compose base model + adapter when `adapter_id` is provided.
- [X] T012 [P] [INFER] Add optional dependency guard for `peft`/`transformers` in inference (behind `[finetune]` extra) — fall back gracefully / raise clear "install anvil[finetune]" message if deps missing
- [X] T013 [P] [INFER] Handle adapter-base mismatch in inference — raise `ValueError` with clear message when adapter was trained for a different base model
- [X] T014 [P] [INFER] Handle unknown `adapter_id` in `InferenceService.load_model()` — look up via `LoRAAdapterRepository.get_by_adapter_id()` and raise descriptive `ValueError` listing available adapters (the route already maps `ValueError` → HTTP 404)

**Checkpoint**: Adapter inference works — base+adapter composition at load time produces fine-tuned output via the existing `/v1/inference/generate` endpoint

---

## Phase 4: Merge + Export — Non-Destructive Merge with Lineage Registration

**Goal**: `AdapterMergeService` performs non-destructive merge+export, producing a standalone
artifact registered in MLflow Model Registry with full lineage `(base, adapter)`.

**Independent Test**: Merge an adapter, verify standalone artifact exists, adapter still exists,
and lineage tags are present on the registered model version.

- [X] T015 [P] [MERGE] Write unit test for non-destructive merge in `tests/unit/services/training/test_merge_export.py`
- [X] T016 [P] [MERGE] Write e2e test for full merge+export flow with lineage verification in `tests/e2e/test_adapter_merge_e2e.py`
- [X] T017 [MERGE] Inject `TrackingService` dependency into `AdapterMergeService`: add `tracking: TrackingService` as a third constructor arg in `anvil/services/training/merge_service.py`, expose `AdapterMergeService` as a lazy property on `AnvilWorkbench` in `anvil/workbench.py`, and update the inline instantiation in `anvil/api/v1/adapters.py:149` to use the workbench property.
- [X] T018 [MERGE] Refactor `AdapterMergeService.merge()` in `anvil/services/training/merge_service.py` to be non-destructive
- [X] T019 [MERGE] Add `merge_and_export()` method to `AdapterMergeService`
- [X] T020 [MERGE] Add MLflow lineage registration after successful merge+export (depends on T017 tracking dependency)
- [X] T021 [P] [MERGE] Handle merge on quantized base (QLoRA)
- [X] T022 [MERGE] Handle license-restricted base — check the `ExternalModel.license` column

**Checkpoint**: Merge+export works end-to-end — adapter persists, standalone artifact is registered with lineage

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple phases

- [X] T023 [P] Run full test suite: `make test` — verify NMRG (SC-004)
- [X] T024 [P] Run `make typecheck` — verify `mypy --strict` is clean
- [X] T025 [P] Run `make lint` — verify ruff, black, isort, pylint are clean
- [X] T026 Update AGENTS.md if agent context was not updated during plan phase (run `.specify/scripts/bash/update-agent-context.sh opencode`)
- [X] T027 Enrich vault: add session note to `docs/vault/Sessions/` and verify `make vault-audit` passes

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **Inference (Phase 3)**: Depends on Foundational (ComputeResult field) — can start independently of Phase 4
- **Merge+Export (Phase 4)**: Depends on Foundational (ComputeResult field) — can start independently of Phase 3
- **Polish (Phase 5)**: Depends on Phase 3 and Phase 4

### Within Each Phase

- Tests MUST be written and FAIL before implementation (TDD, Article IV)
- Models before services
- Services before endpoints
- Core logic before error handling
- Phase complete before moving to next

### Parallel Opportunities

- **Phase 1**: T002, T003, T004, T005 — all independent, all in parallel
- **Phase 2**: T007 (docstring) can run in parallel with T006 (field addition)
- **Phase 3**: T009 (test), T010 (e2e test) first; T011 (inference composition), T012 (dep guard), T013 (mismatch), T014 (unknown ID) — all in parallel since they touch different methods
- **Phase 4**: T015 (test), T016 (e2e test) first; T017 (inject TrackingService dep) is a prerequisite for T020 (lineage); T018 (non-destructive refactor), T019 (merge_and_export), T021 (quantized), T022 (license) can partially parallelize; T020 (lineage) depends on T017 + T019
- **Phase 5**: All [P] tasks (T023, T024, T025) can run in parallel

## Parallel Example: Phase 3 (Adapter Inference)

```bash
# Launch all inference implementation tasks in parallel:
Task: "Update InferenceService.load_model() in anvil/services/inference/inference.py"
Task: "Add optional dependency guard in anvil/services/inference/inference.py"
Task: "Handle adapter-base mismatch in anvil/services/inference/inference.py"
Task: "Handle unknown adapter_id in anvil/services/inference/inference.py"
```

## Parallel Example: Phase 4 (Merge + Export)

```bash
# Prerequisite: inject TrackingService dependency + workbench wiring (T017)
Task: "Inject TrackingService into AdapterMergeService + expose on AnvilWorkbench"

# First wave — independent implementation (after T017):
Task: "Refactor AdapterMergeService.merge() to be non-destructive (T018)"
Task: "Handle merge on quantized base in merge_service.py (T021)"
Task: "Handle license-restricted base via ExternalModel.license (T022)"

# Second wave — depends on refactored merge + tracking dep:
Task: "Add merge_and_export() method to AdapterMergeService (T019)"
Task: "Add MLflow lineage registration after merge+export (T020, depends on T017+T019)"
```

---

## Implementation Strategy

### MVP First (Phase 2 + Phase 3 — Adapter Inference)

1. Complete Phase 1: Setup (verify codebase)
2. Complete Phase 2: Foundational (ComputeResult adapter_id field)
3. Complete Phase 3: Adapter inference (base+adapter composition)
4. **STOP and VALIDATE**: Test adapter inference independently (T009, T010)
5. Demo ready: base+adapter inference works

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add Adapter Inference → Test independently → Deploy/Demo (MVP!)
3. Add Merge + Export → Test independently → Deploy/Demo
4. Each increment adds value without breaking previous work

### Notes

- [P] tasks = different files, no dependencies
- Phase 3 and Phase 4 can be implemented in parallel by different developers
- All adapter-related tests require `[finetune]` extras installed (`peft`, `transformers`, `torch`)
- No new dependencies introduced — everything already in `[finetune]` extra from spec 044
- ComputeResult field addition (T006) and the `AdapterMergeService` TrackingService injection (T017) are the cross-cutting changes
- The `/v1/inference/generate` endpoint and adapter REST routes ALREADY EXIST (spec 044) — this spec fills the composition + non-destructive-merge + lineage gaps, it does NOT create new endpoints
