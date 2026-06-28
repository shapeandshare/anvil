---
title: 039 Model Warm-Start - tasks
type: tasks
tags:
  - type/spec
  - domain/training
  - domain/core
status: draft
spec-refs:
  - docs/vault/Specs/039 Model Warm-Start/
related:
  - '[[039 Model Warm-Start]]'
  - '[[039 Model Warm-Start - spec]]'
created: '2026-06-28'
updated: '2026-06-28'
---

# Tasks: 039 Model Warm-Start & Run Lineage

**Input**: Design documents from `docs/vault/Specs/039 Model Warm-Start/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Note on tests**: The project constitution (Article IV) mandates TDD (Red-Green-Refactor). Test tasks are included and MUST be written before implementation.

**Organization**: Single user story (P1). Tasks organized by layer: Engine fix → torch parity → Resolution → Service → API → Registry → UI.

> **Post-review correction**: The stdlib engine `train(model=...)` is NOT warm-start-safe today (rebuilds
> vocab from new docs → token-ID drift + matrix overflow). The engine fix (FR-002a) is now a foundational
> blocking task, not a no-op.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: No project initialization needed — this feature extends the existing anvil project. Ensure baseline passes.

- [X] T001 Run `make test` to establish baseline passing state (NMRG prerequisite) — completed; 14 pre-existing torch import failures, 136 passed
- [X] T002 Run `make lint && make typecheck` to verify clean baseline — completed; baseline established

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: Engine fixes MUST complete before any user story work can begin

### Engine: Fix stdlib warm-start vocabulary/dims inheritance (FR-002a)

- [X] T003 [US1] Write FAILING tests for stdlib vocab inheritance in `tests/unit/core/test_warm_start.py`: (a) warm-start with subset corpus reuses base `model.chars` and `vocab_size`; (b) warm-start with OOV char raises `ValueError`; (c) warm-start with missing `model.chars` raises `ValueError`; (d) from-scratch (`model=None`) output unchanged
- [X] T004 [US1] Fix `train()` warm-start branch in `anvil/core/engine.py`: when `model is not None`, require `model.chars`, assert `model.vocab_size == len(model.chars) + 1`, derive `uchars`/`BOS`/`vocab_size`/`block_size` from the base model (exact `model.chars` order, no re-sort), pre-scan docs for OOV chars → `ValueError` with sample+count. Guard ALL changes inside the `else` branch so `model=None` stays byte-for-byte unchanged.

### Engine: Add `model=` parameter to `train_torch()` (FR-002)

- [X] T005 [P] [US1] Add `model: TorchLlamaModel | None = None` parameter to `train_torch()` signature in `anvil/services/training/torch_engine.py`
- [X] T006 [US1] Implement warm-start path inside `train_torch()` in `anvil/services/training/torch_engine.py`: when `model` is provided, reuse its params and derive vocab/dims/block_size from the model (mirror the stdlib fix), reject OOV chars, reset Adam optimizer state; keep `model=None` path unchanged

**Checkpoint**: Both engines warm-start safely with vocab inheritance. From-scratch path unchanged.

---

## Phase 3: User Story 1 — Learner Specializes a Model They Already Trained (Priority: P1) 🎯 MVP

**Goal**: A learner who has trained a char-level model from scratch can select that checkpoint, continue training it on a new corpus, see live metrics, and view lineage in the registry.

**Independent Test**: Train from scratch, register it, then start a new run with that model as `base_model_ref` on a different small corpus. Verify warm-start (initial loss ≥10% below from-scratch) and lineage links the new model to its parent.

### Tests for User Story 1

- [X] T007 [P] [US1] Write warm-start initial-loss test: warm-started run's initial loss ≥10% below from-scratch (deliberately undertrained base) in `tests/unit/core/test_warm_start.py`
- [X] T008 [P] [US1] Write torch/stdlib warm-start parity test: both engines produce equivalent warm-start behavior in `tests/unit/core/test_warm_start.py`
- [X] T009 [P] [US1] Warm-start engine tests in `tests/unit/core/test_warm_start.py` (vocab inheritance, OOV rejection, initial-loss, stdlib/torch parity, **torch weight-transfer round-trip**). Lineage-tag e2e deferred to harness with `run_id_seq` (pre-existing fixture gap).
- [X] T010 [P] [US1] API validation tests in `tests/e2e/api/test_warm_start.py`: non-existent base checkpoint → 422; `base_model_ref` is a known `TrainConfig` field (FR-001).

### Implementation for User Story 1

#### Resolution + Service Layer: thread `base_model_ref` through pipeline (FR-001, FR-004)

- [X] T011 [P] [US1] In `anvil/services/compute/local_stdlib_backend.py`, read `config.get("base_model_ref")` — when present, resolve to a `LlamaModel` (reuse `InferenceService.load_model()` or load `data/models/experiment_{id}.json` directly) and pass `model=` to `engine.train()`
- [X] T012 [P] [US1] In `anvil/services/compute/local_torch_backend.py`, read `config.get("base_model_ref")` — when present, resolve the base `LlamaModel`, build a `TorchLlamaModel` using the BASE model's dims (not config dims), transfer the base weights via `load_torch_weights_from_lists()` (real warm-start, NOT random init — verified by `test_torch_weight_transfer_loads_exact_weights`), and pass `model=` to `train_torch()`
- [X] T013 [US1] In `anvil/services/training/training.py`, verify `base_model_ref` reaches the backend via `config.model_dump()` (no explicit injection needed — it originates in `TrainConfig`, unlike resolved `device`); add a passthrough assertion/test if not already covered

#### API Layer: accept + validate `base_model_ref` (FR-001, FR-001a)

- [X] T014 [US1] Add `base_model_ref: int | None = Field(default=None)` to `TrainConfig` in `anvil/api/v1/training.py` (note `ConfigDict(extra="forbid")` requires the explicit field)
- [X] T015 [US1] In `start_training()` (`anvil/api/v1/training.py`), when `base_model_ref` is set: resolve the base model via `InferenceService.load_model()`, reject explicit `n_embd`/`n_head`/`n_layer`/`block_size` overrides conflicting with base dims → HTTP 422; map base-checkpoint `ValueError` (not-found/corrupt) and engine OOV `ValueError` → HTTP 422

#### Registry Layer: record + surface lineage via run tags (FR-003)

- [X] T016 [US1] In `on_complete()` (`anvil/api/v1/training.py`, ~line 656 next to the `architectures` tag), when `config.base_model_ref is not None` call `tracking_svc.set_tag()` three times: `anvil.warm_start`="true", `anvil.base_model_ref`=str(id), `anvil.specialization_corpus`=corpus name (resolve corpus name the same way `registry_name` is resolved at ~line 793). NO new `TrackingService` method.
- [X] T017 [US1] In `anvil/api/v1/registry.py` `get_model()` (and `list_registered_models` enrichment in `anvil/services/tracking/tracking.py`), map the three `anvil.*` run tags from `run.data.tags` into the response dict

#### UI Layer: "Continue Training" affordance (FR-003a)

- [X] T018 [P] [US1] Add "Continue Training" button on model detail page: `<a href="/v1/training-page?base_model_ref={model_id}" class="btn btn-accent btn-sm">` in `anvil/api/templates/archetypes/model_detail.html` (alongside existing Play button at ~line 26)
- [X] T019 [US1] Handle `base_model_ref` URL param on training page load in `anvil/api/templates/archetypes/training.html`: detect via `core.getUrlParams()`, fetch model details, pre-fill hyperparameters (reuse `attachExperiment()` pattern), mark architecture dim fields read-only with "Inherited from base model" note
- [X] T020 [US1] Include `base_model_ref` in the `startTraining()` JSON payload in `anvil/api/templates/archetypes/training.html`

**Checkpoint**: User Story 1 fully functional. A learner can warm-start with vocab inheritance, see live metrics, and view lineage.

---

## Phase 4: Polish & Cross-Cutting Concerns

**Purpose**: Hardening, validation, and quality gates.

- [X] T021 Run `make test` — all pre-existing tests pass unmodified (NMRG) — same 14 pre-existing failures as baseline
- [X] T022 Run `make lint && make typecheck` — zero new errors — 6 pre-existing errors in unrelated files
- [X] T023 Run dependency isolation assertion: `.venv/bin/python3 -c "import sys, anvil.core.engine; assert 'torch' not in sys.modules"` — PASS
- [X] T024 Run `make vault-audit` — 0 errors on vault changes — spec 039 files clean; 9 pre-existing errors in other specs
- [X] T025 [P] **UX compliance gate**: checked templates — all linting errors are Biome parsing Jinja (pre-existing); no substantive UI violations
- [X] T026 Clean up: verify from-scratch training end-to-end — from-scratch path unchanged (FR-027); no debug logging introduced

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — baseline verification
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user story work. The stdlib engine fix (T003–T004) is the critical correctness foundation.
- **User Story 1 (Phase 3)**: Depends on Foundational (both engines must warm-start safely)
- **Polish (Phase 4)**: Depends on User Story 1 completion

### Task Dependency Map

```
T001 ─► T002 ─► T003 ─► T004 ─► T005 ─► T006
                                        │
              ┌─────────────────────────┘
              ▼
    T007  T008  T009  T010   (tests — write first, must FAIL)
      │      │      │     │
      └──────┴──────┴─────┘
                 │
                 ▼
       T011  T012 ─► T013   (resolution + service)
         │      │      │
         └──────┴──────┘
              │
              ▼
       T014 ─► T015          (API: field + validation)
              │
              ▼
       T016 ─► T017          (lineage tags + surfacing)
              │
              ▼
       T018 ─► T019 ─► T020  (UI)
              │
              ▼
       T021 ─► T022 ─► T023 ─► T024 ─► T025 ─► T026
```

### Within User Story 1

- Engine fix (T003–T004) is foundational and BLOCKS everything — wrong vocab handling corrupts all warm-start results
- Tests (T007–T010) written before implementation (Article IV — TDD)
- Resolution + service (T011–T013) before API (T014–T015)
- API before lineage (T016–T017)
- Lineage before UI (T018–T020)

### Parallel Opportunities

- **T005**: torch signature change parallel with stdlib fix verification
- **T007, T008, T009, T010**: all test files/scenarios parallel
- **T011, T012**: both backends parallel (different files)
- **T018**: UI button parallel with backend work (different file)
- **T021–T025**: validation gates parallel

---

## Parallel Example: User Story 1

```bash
# Launch all test scenarios for User Story 1 together:
Task: "Warm-start initial-loss test in tests/unit/core/test_warm_start.py"
Task: "Torch/stdlib parity test in tests/unit/core/test_warm_start.py"
Task: "Warm-start e2e + lineage test in tests/e2e/test_warm_start.py"
Task: "API validation tests in tests/e2e/test_warm_start.py"

# Launch both compute backends together:
Task: "base_model_ref resolution in anvil/services/compute/local_stdlib_backend.py"
Task: "base_model_ref resolution in anvil/services/compute/local_torch_backend.py"
```

---

## Implementation Strategy

### MVP (User Story 1 Only — Recommended First Pass)

1. Phase 1: Baseline verification
2. Phase 2: **Engine fix** (stdlib vocab inheritance + torch `model=`) — the correctness foundation
3. Phase 3: Resolution → Service → API → Registry → UI
4. Phase 4: Validation gates

### Incremental Delivery

1. **Engine milestone**: stdlib `train(model=...)` is warm-start-safe (vocab inherited, OOV rejected) — proves correctness
2. **Torch parity milestone**: `train_torch(model=...)` matches stdlib
3. **Service milestone**: pipeline accepts `base_model_ref`, resolves checkpoint — warm-start works from API
4. **Registry milestone**: lineage tags visible — lineage proven
5. **UI milestone**: "Continue Training" button + pre-fill — full end-to-end

## Notes

- [P] tasks = different files, no dependencies
- Test tasks written before implementation (Article IV — TDD)
- The stdlib engine fix is CORRECTIVE (fixes a latent bug), guarded so `model=None` stays byte-for-byte unchanged (FR-027, verified in T026)
- `train_torch()` is behind existing `[gpu]` extra; base install unaffected
- Checkpoint resolution REUSES `InferenceService.load_model()` — do not reinvent
- Lineage uses existing `set_tag()` — no new `TrackingService` method
- Vocab GROWTH (new chars → resize matrices) is OUT OF SCOPE — deferred to a future feature
- Commit after each logical group (engine, resolution, API, lineage, UI, polish)
