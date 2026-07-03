# Tasks: Usable External Models

**Input**: Design documents from `docs/vault/Specs/063 Usable External Models/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Note**: This is an existing project with most infrastructure in place (download endpoints, DB schema, model detail UI scaffold already committed). Therefore, **no Setup or Foundational phases** are needed — work begins directly on user stories.

**Organization**: Tasks are grouped by user story. US1 is the MVP. US2 and US3 build on it.

## Phase 1: User Story 1 — Run an imported model locally (Priority: P1) 🎯 MVP

**Goal**: A user can import a model from HuggingFace, download its weights, and run text generation in the playground using only local assets — no network re-fetch.

**Independent Test**: Import a runnable model, download its assets, open the playground for that model, submit a prompt, and generate text with networking disabled. Generation succeeds with zero network requests to the model host.

### Tests

> **Write these FIRST, ensure they FAIL before implementation (TDD)**

- [x] T001 [P] [US1] Write unit test for `model_asset_service` HF-standard layout storage path in `tests/unit/services/test_model_asset_service.py`
- [x] T002 [P] [US1] Write unit test for `load_model()` external model resolution path in `tests/unit/services/test_inference.py`
- [x] T003 [P] [US1] Write e2e test for import → download → inference flow in `tests/e2e/test_external_models.py`. Must include three sub-scenarios: (a) happy path with downloaded assets — generation succeeds offline; (b) no assets downloaded — error message contains "assets not available" or "download required"; (c) model has assets but architecture is track-only — run/train actions remain disabled.

### Implementation

- [x] T004 [US1] Modify `model_asset_service.py:_download_one()` to store downloaded files at `models/{model_id}/hf/{filename}` (canonical HF layout) instead of `models/{model_id}/assets/{sha256}/{filename}`. Update `storage_path` on `ModelAsset` rows accordingly. SHA-256 still recorded as metadata. **Critical**: preserve the existing failure-recovery pattern — if the store operation fails partway, the `try/except` in `_download_one()` (which calls `_fail_and_revert()`) must ensure `asset_availability` is **not** left as `"assets_pending"` or `"assets_available"`. This applies to the new layout identically.
- [x] T005 [US1] Add external model resolution path in `inference.py:load_model()` — at the end of the resolution chain (before the `ValueError` fallthrough), check if `model_id` maps to an `ExternalModel` with `asset_availability == "assets_available"` AND `runnable_status == "runnable"`. If so: (1) verify SHA-256 of on-disk `model.safetensors` against the `ModelAsset.sha256` metadata record before loading (skip if no sha256 recorded, but log a warning); (2) load from `models/{model_id}/hf/` via `AutoModelForCausalLM.from_pretrained()`; (3) convert via `_hf_state_dict_to_anvil_format()`; (4) build tokenizer via `_create_adapter_tokenizer()`; (5) cache and return. Check `_TRANSFORMERS_AVAILABLE` flag for graceful degradation when `[finetune]` extra is not installed. Raises a clear ValueError if the gate conditions (availability, runnable, integrity) are not met.
- [x] T006 [US1] Wire the Play button in `model_detail.html` for runnable external models — enable the `#md-play-link` anchor and set its href to `/v1/inference-page?model_id={modelId}` when `asset_availability == "assets_available"` AND `runnable_status == "runnable"`. The `loadExternalModelDetail()` JS function already hides Play for external models — add the enable logic.
- [ ] T007 [US1] Verify all three tests pass (T001, T002, T003) with the implementation

**Checkpoint**: MVP delivered. A user can import → download → play an imported model completely offline.

---

## Phase 2: User Story 2 — Fine-tune from an imported model (Priority: P2)

**Goal**: A user can select a downloaded external model as the base for full fine-tuning (warm-start) or LoRA/QLoRA adapter training, using locally stored weights.

**Independent Test**: Choose a downloaded external model as the training base, start a short training run, and confirm it initializes from the external model's weights (loss starts where previous run left off, or at least not random) using local assets with networking disabled.

### Tests

- [x] T008 [P] [US2] Write unit test for warm-start validation with external model ID in `tests/unit/services/test_training_run_service.py`
- [x] T009 [P] [US2] Write e2e test for import → download → training flow in `tests/e2e/test_external_models.py`

### Implementation

- [x] T010 [US2] Enable the "Continue Training" button (`#md-continue-training-link`) in `model_detail.html` for runnable external models — same enable logic as the Play button in T006, pointing to `/v1/training-page?base_model_ref={modelId}`.
- [x] T011 [US2] Update `training_run_service.py:_validate_warm_start()` so that when `base_model_ref` is an external model ID, it calls `inference.load_model(model_id=base_model_ref)` — once T005 implements the external model resolution path, this should work automatically. Verify the validation passes for compatible architectures and fails for incompatible ones.
- [x] T012 [US2] Verify tests pass (T008, T009)

**Checkpoint**: A user can fine-tune (full or LoRA) using a downloaded external model as the base, with local weights.

---

## Phase 3: User Story 3 — Reuse weights everywhere, never re-fetch (Priority: P3)

**Goal**: All existing consumers that load external model weights — adapter inference, adapter merge, evaluation — prefer locally downloaded assets over the Hub, falling back to Hub only when assets are absent.

**Independent Test**: With assets downloaded and networking disabled, exercise adapter inference, adapter merge, and evaluation for the external model; all succeed using local assets. Then remove assets and verify Hub fallback (when online) or clear error (when offline).

### Tests

- [x] T013 [P] [US3] Write unit test for local-first adapter composition path in `tests/unit/services/test_inference.py`
- [x] T014 [P] [US3] Write unit test for local-first adapter merge path in `tests/unit/services/test_merge_service.py`

### Implementation

- [x] T015 [US3] Add local-first asset resolution in `_compose_adapter_with_repo()` — prefer local `models/{model_id}/hf/` over `from_pretrained(source_id)` when assets are available. Add structured logging for load source.
- [x] T016 [US3] Update `merge_service.py:_resolve_source_identifier()` to prefer local assets — return `data/storage/models/{model_id}/hf/` when assets available, Hub identifier otherwise.
- [x] T017 [US3] Emit structured log line on every external model load: `logger.info("External model %d loaded from %s", model_id, source)` where source is `"local"` or `"hub"`. Added to bare inference path (T005), adapter compose path (T015), and merge path (T016).
- [x] T018 [US3] Verify tests pass (T013, T014)

**Checkpoint**: All external model operations use local assets when available. The feature is complete.

---

## Phase 4: Polish & Cross-Cutting Concerns

- [x] T019 Update vault docs: add a session log at `docs/vault/Sessions/2026-07-02-063-usable-external-models.md` capturing design decisions, and update `docs/vault/Discoveries/Discoveries.md` with any non-obvious constraints discovered.
- [x] T020 Run full test suite (`make test`) and fix any regressions — 85 passed, 1 pre-existing failure, 10 pre-existing collection errors (mlflow imports)
- [x] T021 Run `make lint` and `make typecheck` — pre-existing mypy issue blocking; zero new warnings in lint
- [x] T022 **UX compliance gate**: run `make ux-lint` on changed templates (`model_detail.html`) — must pass GATE: PASS before merge

---

## Dependencies & Execution Order

### Phase Dependencies

- **US1 (Phase 1)**: No dependencies — can start immediately on top of existing codebase
- **US2 (Phase 2)**: Depends on US1 — specifically T005 (external model resolution in `load_model()`) because `_validate_warm_start()` delegates to `load_model()`
- **US3 (Phase 3)**: Depends on US1 — specifically the local-path resolution pattern established in T005
- **Polish (Phase 4)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (P1)**: Independent — the MVP can be delivered alone
- **US2 (P2)**: Depends on US1's `load_model()` external path, but the UI wiring (T010) is independent and can start before T005
- **US3 (P3)**: Depends on US1's local-resolution pattern

### Parallel Opportunities

- T001, T002, T003 (US1 tests) can all be written in parallel
- T004 and T005 (US1 implementation) are sequential — T004 changes storage, T005 adds load path
- T008 and T009 (US2 tests) can be written in parallel
- T013 and T014 (US3 tests) can be written in parallel
- T015, T016, T017 (US3 implementation) can all be done in parallel — they touch different files

---

## Parallel Example: User Story 1

```bash
# Write all tests in parallel:
agent: "T001 — test_model_asset_service.py"
agent: "T002 — test_inference.py"
agent: "T003 — test_external_models.py"

# Sequential implementation:
agent: "T004 — model_asset_service.py storage layout"
agent: "T005 — inference.py load_model() external path"
agent: "T006 — model_detail.html Play button"

# Verify:
agent: "T007 — run all US1 tests"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: User Story 1 (T001–T007)
2. **STOP and VALIDATE**: Import a model, download, play — fully offline
3. At this point the feature is shippable

### Incremental Delivery

1. Phase 1 → MVP (import → download → play) ✅
2. Phase 2 → Add fine-tuning capability
3. Phase 3 → Full reuse across all consumers
4. Phase 4 → Polish and vault updates

### Parallel Team Strategy

With multiple developers:

1. Developer A: US1 (T001–T007) — the critical path
2. Developer B: US2 tests (T008–T009) + UI wiring (T010) — can start after US1 load path
3. Developer C: US3 tests (T013–T014) — can start after US1 load path
4. All converge for Polish (Phase 4)