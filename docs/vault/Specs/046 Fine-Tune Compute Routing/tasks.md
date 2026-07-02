# Tasks: 046 Fine-Tune Compute Routing

**Input**: Design documents from `docs/vault/Specs/046 Fine-Tune Compute Routing/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included per Constitution Article IV (TDD Mandatory) — tests written before implementation.

**Organization**: One user story (P2). Tasks grouped by phase for independent execution.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1)
- Include exact file paths in descriptions

## Phase 1: Setup

**Purpose**: Verify branch and working tree are ready

- [ ] T001 Verify branch is `046-fine-tune-compute-routing` and working tree is clean

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Enum modifications that MUST be complete before `resolve_fine_tune()` can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T002 [P] Add `SAAS = "saas"` member to `ComputeBackend` enum in `anvil/services/compute/compute_backend.py` — update docstring attributes list
- [ ] T003 [P] Add `SAAS = "saas"` member to `ComputeBackendResult` enum in `anvil/services/compute/compute_backend_result.py` — update docstring attributes list
- [ ] T004 [P] Add `SAAS_FINETUNE = "saas-finetune"` member to `RegistryBackend` enum in `anvil/services/compute/registry_backend.py` — update docstring attributes list

**Checkpoint**: Enums ready — `resolve_fine_tune()` can now reference all backend identifiers

---

## Phase 3: User Story 1 — One Fine-Tune Config, Routed by Size (Priority: P2)

**Goal**: A learner submits a fine-tune; `resolve_fine_tune()` picks local or SaaS by `ResourceSpec` under D4 rules.

**Independent Test**: Call `resolve_fine_tune({"method": "lora", "base_model_ref": "tinyllama-1.1b", "compute_backend": "auto"})` and verify it returns a resolved dict with local backend. Repeat with a model sized above local envelope and verify it routes to SaaS (when _saas_configured is `True`) or raises `ComputeBackendUnavailable` (when `False`).

### Tests for User Story 1 ⚠️

> **NOTE**: Write these tests FIRST, ensure they FAIL before implementing `resolve_fine_tune()`

- [ ] T005 [P] [US1] Write unit test `test_resolve_finetune_fits_local_auto` — small fine-tune with `auto` resolves to local in `tests/unit/services/compute/test_resolve.py`
- [ ] T006 [P] [US1] Write unit test `test_resolve_finetune_over_local_auto_saas` — over-local fine-tune with `auto` + SaaS configured resolves to saas in `tests/unit/services/compute/test_resolve.py`
- [ ] T007 [P] [US1] Write unit test `test_resolve_finetune_over_local_auto_no_saas` — over-local fine-tune with `auto` + SaaS not configured returns guidance in `tests/unit/services/compute/test_resolve.py`
- [ ] T008 [P] [US1] Write unit test `test_resolve_finetune_explicit_local_over_limit` — explicit `local-cpu`/`local-gpu` with over-local fine-tune raises `ComputeBackendUnavailable` in `tests/unit/services/compute/test_resolve.py`
- [ ] T009 [P] [US1] Write unit test `test_resolve_finetune_explicit_saas_not_configured` — explicit `saas` with SaaS not configured raises `ComputeBackendUnavailable` in `tests/unit/services/compute/test_resolve.py`
- [ ] T010 [P] [US1] Write unit test `test_resolve_finetune_method_sizing` — verify different methods (full/lora/qlora) produce different routing outcomes in `tests/unit/services/compute/test_resolve.py`
- [ ] T011 [P] [US1] Write unit test `test_resolve_finetune_nmrg` — verify existing `resolve_backend()` tests still pass unchanged in `tests/unit/services/compute/test_resolve.py`

### Implementation for User Story 1

- [ ] T012 [US1] Implement `resolve_fine_tune()` in `anvil/services/compute/resolve.py` — add function that:
  - Accepts `config` dict with `method`, `base_model_ref`, `compute_backend` (defaults to `"auto"`)
  - Computes `ResourceSpec` via VRAM formula: `base_params * method_mult * quant_factor + overhead`
  - Method multipliers: `full=2.0×`, `lora=1.2×`, `qlora=0.6×`
  - Overhead constant: 0.5 GB
  - Applies D4 rules (user-facing `compute_backend` values — NO bare `"local"`):
    - `auto` + fits local → local (local-lora backend)
    - `auto` + over local + SaaS configured → saas
    - `auto` + over local + SaaS NOT configured → return guidance message (no raise)
    - `local-cpu`/`local-gpu` + fits local → local (local-lora backend)
    - `local-cpu`/`local-gpu` + over local → raise `ComputeBackendUnavailable`
    - `saas` + SaaS configured → saas
    - `saas` + SaaS NOT configured → raise `ComputeBackendUnavailable`
  - Returns `dict` with `"engine"`, `"device"`, `"backend"` keys
  - References existing `_detect_device()`, `_torch_available()` helpers in same file
  - Checks `_saas_configured` via module-level flag (to be set by spec 047 config)
  - Detects available host memory via `_detect_device()` (GPU VRAM if CUDA/MPS, else system RAM heuristic)
- [ ] T013 [US1] Refactor the existing `method in ("lora","qlora")` branch in `resolve_backend()` (`anvil/services/compute/resolve.py:111-119`) to **delegate** to `resolve_fine_tune()` — behavior-preserving for the local-only case, no duplicate routing logic (§11.4). Add a regression test asserting the delegated path matches prior local-only output when SaaS is not configured.
- [ ] T014 [US1] Add `_saas_configured()` helper function in `anvil/services/compute/resolve.py` — checks for SaaS backend availability (initially returns `False`; spec 047 will implement real check)
- [ ] T015 [US1] Add `_estimate_host_memory_gb()` helper in `anvil/services/compute/resolve.py` — returns available host memory in GB (GPU VRAM for CUDA/MPS, system RAM heuristics for CPU)
- [ ] T016 [US1] Verify all unit tests in T005–T011 pass — run `pytest tests/unit/services/compute/test_resolve.py -v -k "fine_tune"`

**Checkpoint**: At this point, `resolve_fine_tune()` is fully functional and verified by unit tests. Fine-tune routing works independently.

---

## Phase 4: Polish & Cross-Cutting Concerns

**Purpose**: e2e verification, typing, linting, and vault enrichment

- [ ] T017 [P] Write e2e test `test_finetune_routing_local` in `tests/e2e/test_finetune_routing.py` — submit a fine-tune via API and verify routing produces correct backend with normalized `ComputeResult` adapter shape
- [ ] T018 [P] Write e2e test `test_finetune_routing_over_local` in `tests/e2e/test_finetune_routing.py` — submit an over-local fine-tune via API and verify correct behavior
- [ ] T019 Run `make lint` on all changed files — fix any ruff/black/isort violations
- [ ] T020 Run `make typecheck` (mypy --strict) — fix any type errors; no `# type: ignore` or `Any` suppression
- [ ] T021 Verify existing tests pass unmodified (NMRG SC-004): run `make test` and confirm no regressions
- [ ] T022 Update vault — enrich session log in `docs/vault/Sessions/` with implementation decisions and discoveries

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user story work
- **User Story 1 (Phase 3)**: Depends on Foundational (Phase 2) — tests written before implementation
- **Polish (Phase 4)**: Depends on User Story 1 (Phase 3)

### Within User Story 1

- Tests (T005–T011) are written first and fail before implementation
- T012 (resolve_fine_tune) is the core implementation
- T013 refactors the existing `resolve_backend()` lora/qlora branch to delegate to `resolve_fine_tune()` (depends on T012)
- T014, T015 are helper functions that T012 depends on
- T016 verifies everything passes

### Parallel Opportunities

| Tasks | Can Run In Parallel | Reason |
|-------|-------------------|--------|
| T002, T003, T004 | ✅ Yes | Different enum files, no dependencies |
| T005–T011 | ✅ Yes | All test cases in same file, no inter-dependencies (same test module, different functions) |
| T017, T018 | ✅ Yes | Two e2e test functions in same file |
| T014, T015 | ✅ Yes | Two independent helper functions; T012 depends on both |
| T012 → T013 | ⛔ Sequential | T013 (delegation refactor) depends on T012 (resolve_fine_tune must exist first) |
| T019, T020, T021 | ✅ Yes | Lint, typecheck, and test runs are independent |

## Implementation Strategy

### MVP Scope (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (enum additions — 3 parallel tasks)
3. Write failing tests (T005–T011 — 7 parallel tasks)
4. Implement `resolve_fine_tune()` (T012) + helpers (T014, T015), then refactor the lora/qlora branch to delegate (T013)
5. Run tests to verify all pass (T016)
6. **STOP and VALIDATE**: Routing is independently functional
7. Run Polish phase (lint, typecheck, e2e tests)
8. Deploy/demo ready

### Incremental Delivery

1. **Phase 1 + 2** → Enums ready
2. **Phase 3 (tests + resolve_fine_tune)** → Core routing works, tested, NMRG verified 🎯 MVP
3. **Phase 4** → CI gates pass, vault enriched, ready to ship

### Parallel Team Strategy

With multiple developers:

1. Developer A: Phase 2 enums (T002–T004 — all parallel)
2. Developer B: Phase 3 tests (T005–T011 — all parallel)
3. Developer A + B: Phase 3 implementation (T012 resolver + T014/T015 helpers, then T013 delegation refactor) after tests are written
4. Developer A or B: Phase 4 polish (T017–T022)

## Notes

- [P] tasks = different files, no dependencies
- [US1] label maps task to the single user story
- Tests MUST fail before implementing (Red-Green-Refactor per Constitution Article IV)
- Verify existing `resolve_backend()` unchanged after implementation (NMRG SC-004)
- Commit after each logical group
- No new runtime dependencies — all additions use existing imports and patterns