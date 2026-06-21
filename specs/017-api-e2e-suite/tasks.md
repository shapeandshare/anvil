# Tasks: Whole-API E2E Test Suite

**Input**: Design documents from `specs/017-api-e2e-suite/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: This feature IS a test suite — no separate test tasks needed (all implementation tasks produce tests).

**Organization**: Tasks are grouped by user story. All 14 per-router test modules are marked [P] for parallel execution.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- Include exact file paths in descriptions

## Path Conventions

- Single project — `tests/e2e/api/` for new test modules
- Shared factories live in `tests/e2e/api/conftest.py`
- Existing tests remain in `tests/e2e/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the `tests/e2e/api/` test directory and shared conftest.py with all factory fixtures and helper functions that unblock every per-router module.

**This is the critical path — must be completed before any user story tasks.**

- [X] T001 Create `tests/e2e/api/` directory structure and `tests/e2e/api/__init__.py` (empty)
- [X] T002 Create `tiny_corpus_bytes()` helper in `tests/e2e/api/conftest.py` — returns a deterministic ~100-byte `.txt` payload string
- [X] T003 Create `make_corpus(client, tmp_path)` factory fixture in `tests/e2e/api/conftest.py` — POST to `/v1/corpora` with name "e2e-test-corpus", write the tiny corpus bytes to a temp file, ingest via `POST /v1/corpora/{id}/ingest`, return the corpus record dict
- [X] T004 Create `make_dataset(client)` factory fixture in `tests/e2e/api/conftest.py` — POST to `/v1/datasets` with name "e2e-test-dataset", return the dataset record dict. Accept optional `corpus_id` parameter for from-corpus creation.
- [X] T005 Create `TINY_TRAINING_CONFIG` constant and `make_trained_run(client)` factory fixture in `tests/e2e/api/conftest.py` — creates a corpus + dataset (self-seeding), starts training with tiny config (`n_embd=16, n_layer=1, n_head=4, num_steps=5, compute_backend="local-stdlib"`) via `POST /v1/training/start`, polls to terminal completion via `poll_until_terminal`, returns `{"run_id": ..., "experiment_id": ..., "status": ..., "final_loss": ...}`
- [X] T006 Create `make_registered_model(client)` factory fixture in `tests/e2e/api/conftest.py` — calls `make_trained_run`, registers via `POST /v1/registry/models` with the run_id, asserts 201, returns `{"model_id": ..., "version": ...}`
- [X] T007 Create `poll_until_terminal(client, run_id, timeout_s=60)` helper function in `tests/e2e/api/conftest.py` — polls `GET /v1/training/{run_id}/status` every 1 second, returns terminal status string (`"completed"` or `"failed"`), raises `asyncio.TimeoutError` if timeout exceeded
- [X] T008 Create `read_sse_events(client, url, max_events=5, timeout_s=30)` helper function in `tests/e2e/api/conftest.py` — uses `client.stream("GET", url)`, parses SSE `event:` and `data:` lines, returns `list[tuple[str, dict]]`, raises `asyncio.TimeoutError` if timeout exceeded

**Checkpoint**: `tests/e2e/api/conftest.py` complete with all factory fixtures and helpers. All 14 per-router modules can now be implemented in parallel.

---

## Phase 2: User Story 1 — Developer Self-Verifies All APIs (Priority: P1) 🎯 MVP

**Goal**: A developer can run `make test` and get pass/fail for every API endpoint across all 14 routers. Each module covers happy-path + error-path for its router's endpoints.

**Independent Test**: Run `python -m pytest tests/e2e/api/test_health_ops.py tests/e2e/api/test_compute.py tests/e2e/api/test_pages.py -v` and observe they pass without any prior setup. Then run the remaining modules similarly.

**This is the core deliverable. All 14 test modules are [P] — they can be implemented in parallel.**

### Simple / Stateless Routers (no training dependency — simplest first)

- [X] T009 [P] [US1] Create test module `tests/e2e/api/test_compute.py` — `GET /v1/compute/backends` returns a list with `"local-stdlib"` available, each item has `value`, `label`, `available`, `reason` fields (direct response, no envelope)
- [X] T010 [P] [US1] Create test module `tests/e2e/api/test_health_ops.py` — `GET /v1/health` returns 200 with `status: "healthy"` and `version`/`uptime_seconds`/`system`/`gpu` fields; `GET /v1/services` returns service list with `web` and `mlflow` entries; `POST /v1/demo/bootstrap` idempotent (second call returns `corpora_created=0, corpora_skipped>0`); test concurrent bootstrap returns 409; assert service-control endpoints return safe status responses (no process destabilization)
- [X] T011 [P] [US1] Create test module `tests/e2e/api/test_pages.py` — every HTML route (`/`, `/v1/acceptable-use`, `/v1/training-page`, `/v1/experiments-page`, `/v1/datasets-page`, `/v1/operations-page`, `/v1/inference-page`, `/v1/content-page`, `/v1/about`, `/v1/learn`, `/v1/learn/graph`, `/v1/models-page`, `/v1/model-detail/{id}`) returns 200 with a known landmark string (page title or heading). Reference actual page titles from `anvil/api/v1/pages.py` and `anvil/api/v1/learning.py` to determine the expected landmark strings for each route — read the handler to find the HTML template name or the first `<h1>`/`<title>` element. **Learning router coverage (FR-001)**: this module covers the `learning` router's HTML lesson routes (`/v1/learn` and all `/v1/learn/*` lessons) — enumerate the 14 lessons from `learning.py` and assert each renders 200 with its landmark.
- [X] T012 [P] [US1] Create test module `tests/e2e/api/test_corpora.py` — create corpus via `POST /v1/corpora` (200 + `data.id`), ingest with include/exclude patterns, list corpora, get single corpus detail via `GET /v1/corpora/{id}`, get files listing, get single file content, fork corpus, delete corpus, `resolve-path` and `analyze-path` endpoints. Error paths: unknown corpus returns 404.
- [X] T013 [P] [US1] Create test module `tests/e2e/api/test_datasets.py` — create dataset via `POST /v1/datasets` (200 + `data.id`), list (`GET /v1/datasets` returns `data.datasets` list), get detail (`GET /v1/datasets/{id}`), update (`PUT /v1/datasets/{id}`), delete (`DELETE /v1/datasets/{id}`), upload, clone, import (from-corpus, import-corpus, preview-import), curate (dedup, filter, replace), samples CRUD (list, edit, delete), export, metrics, operations. Error paths: duplicate name (422), unknown id (404).
- [X] T014 [P] [US1] Create test module `tests/e2e/api/test_training_router.py` — `GET /v1/training/configs` returns presets; `POST /v1/training/start` with tiny config captures run_id + status `"running"`; `GET /v1/training/{run_id}/status` returns terminal state via `poll_until_terminal`; SSE stream via `read_sse_events` returns at least one `metrics` event; `POST /v1/training/{run_id}/stop` returns 200; `GET /v1/forward-pass/graph` returns `{model, nodes[], edges[]}`. Error paths: unknown run_id returns 404. **FR-008 compliance**: assert loss values are finite/numeric using `math.isfinite()` — never assert exact loss values.
- [X] T015 [P] [US1] Create test module `tests/e2e/api/test_experiments.py` — after `make_trained_run`: list experiments (`GET /v1/experiments`), get detail (`GET /v1/experiments/{id}`), compare 2 runs (`GET /v1/experiments/compare`), get metrics (non-empty loss series with finite numeric values — assert using `math.isfinite()` per **FR-008**), get tracking link/data, list artifacts (`GET /v1/experiments/{eid}/runs/{rid}/artifacts`), download artifact (200 + non-empty body), retry-export, delete experiment. Error paths: unknown experiment returns 404. **Degraded-tracking handling (spec Assumptions)**: the experiment-tracking sidecar is NOT started in tests — read experiment results from local run state; do NOT assert a tracking-server run identifier is present or require a live tracking server. The `/mlflow` endpoint may return a degraded/placeholder payload — assert it responds without error rather than asserting live tracking data.
- [X] T016 [P] [US1] Create test module `tests/e2e/api/test_registry_api.py` — register model via `POST /v1/registry/models` (201 + model_id + version), list models (`GET /v1/registry/models`), get model detail (`GET /v1/registry/models/{id}`), get version detail (`GET /v1/registry/models/{id}/versions/{v}` with params/bytes/safetensors ref), delete a version (`DELETE /v1/registry/models/{id}/versions/{v}`), delete the model (`DELETE /v1/registry/models/{id}`). Error paths: register from unknown run (404/422), unknown model (404).
- [X] T017 [P] [US1] Create test module `tests/e2e/api/test_inference_api.py` — require a `make_trained_run` or use demo model; test `POST /v1/inference/tokenize`, `/embeddings`, `/attention`, `/sampling-distribution`, `/backward-graph`, `/autograd-example`, `/loss-breakdown` each return documented response shapes; `GET /v1/inference/forward-graph` and `/model-params` return expected structure; `GET /v1/inference/models` lists at least the demo model; `POST /v1/inference/sample` returns non-empty generated text. Error paths: sample with unknown model returns 404/422. **Learning router coverage (FR-001)**: this module also covers the `learning` router's data routes (`GET /v1/inference/models`, `POST /v1/inference/sample`) — confirm these are exercised here so no separate `test_learning.py` is needed.
- [X] T018 [P] [US1] Create test module `tests/e2e/api/test_eval.py` — `POST /v1/eval-datasets` creates eval dataset; `POST /v1/eval-datasets/{name}/records` appends records; `GET /v1/eval-datasets/{name}` reads back records; `POST /v1/eval/perplexity` against a trained model + eval dataset yields finite numeric perplexity (assert `math.isfinite(result)` per **FR-008** — never assert exact perplexity values).
- [X] T019 [P] [US1] Create test module `tests/e2e/api/test_governance.py` — `GET /v1/governance/licenses` returns seeded OSI/CC catalog; `GET /v1/governance/audit` returns audit events list; `GET /v1/governance/audit/verify` confirms hash chain integrity on a fresh DB; after creating a dataset, chain grows and still verifies; `GET /v1/governance/datasets/{id}/report` returns provenance report; `POST /v1/datasets/{id}/takedown` marks dataset and creates audit event. Error paths: report/takedown for unknown id returns 404.
- [X] T020 [P] [US1] Create test module `tests/e2e/api/test_content.py` — full reproducibility lifecycle: `POST /v1/content/corpora` → `POST /v1/content/sources` → `POST /v1/content/sessions` (open) → `POST /v1/content/sessions/{id}/stage` → `POST /v1/content/sessions/{id}/validate` → `POST /v1/content/sessions/{id}/accept` (atomic fold) → `POST /v1/content/corpora/{id}/freeze` (immutable version) → `GET /v1/content/versions/{id}` + `/lineage`. Test `/tag`, `/revert`, composition `/preview`; locks (acquire/list/release); imports (create/get); at least one SSE stream via `/content/stream/composition`. Error paths: empty-version accept, session abandon, unknown version (404).

**Checkpoint**: All 14 router modules passing independently. Developer can run `make test` and verify any router's API contracts.

---

## Phase 3: User Story 4 — Cross-Router Integration Verified (Priority: P2)

**Goal**: A lifecycle integration test proves the full user workflow — upload corpus → build dataset → train → experiment → register → download → inference — composes correctly across routers.

**Independent Test**: Run `python -m pytest tests/e2e/api/test_lifecycle_journey.py -v -s` and observe it completes a full train-to-inference pipeline within the time budget (initial 90s target, validated against the measured baseline) with deterministic output.

- [X] T021 [US4] Create test module `tests/e2e/api/test_lifecycle_journey.py` — single end-to-end test chaining: upload corpus via `/v1/corpora` + ingest → build dataset via `/v1/datasets` → start training with tiny config via `/v1/training/start` → poll via `poll_until_terminal` to completion → confirm experiment + metrics via `/v1/experiments/{id}/metrics` (finite loss values read from local run state — do NOT require live tracking server per spec Assumptions) → register model via `/v1/registry/models` (201) → download artifact via `/v1/experiments/{eid}/runs/{rid}/download` (non-empty body) → load + sample inference via `/v1/inference/sample` (non-empty output). Assert each step returns the expected status code and key response fields; on any step failure, the assertion message MUST name the failed step (do not silently skip subsequent steps, per US4.2). Assert training loss is finite (not NaN/inf). Assert generated text is non-empty. Initial 90-second timebox; record the actual measured runtime so T029 can set the final SC-002 threshold to measured-time-plus-headroom.

**Checkpoint**: Full pipeline works end-to-end — the most important integration test passes.

---

## Phase 4: User Story 2 — CI Pipeline Catches Regressions (Priority: P1)

**Goal**: The CI pipeline runs the full API test suite on every PR, and a broken API contract produces a clear CI failure.

**Independent Test**: Introduce a deliberately broken endpoint assertion in a test module, commit, observe CI pipeline failure with a clear error message identifying the broken contract. Then revert.

- [X] T022 [US2] Verify the new `tests/e2e/api/` directory is auto-discovered by `make test` (it lives under `tests/` and is excluded from `--ignore=tests/system` — confirm via `python -m pytest tests/e2e/api/ --collect-only | grep "test_"`)
- [X] T023 [US2] Verify CI `test` job includes the new tests by confirming `make test` discovers and runs all 15 test modules. Run `make test` locally and confirm the total collected test count increases by the number of new tests. Document the new coverage % for the user.
- [X] T024 [US2] Verify a deliberately broken assertion produces a CI-failing error message identifying the endpoint path and the expected vs actual contract (manual verification by introducing a temporary `assert False` in one test)

**Checkpoint**: CI pipeline catches API regressions automatically.

---

## Phase 5: User Story 3 — Clear, Isolated Debug Output (Priority: P2)

**Goal**: Each test module runs independently, self-seeds its data, and produces clear failure messages identifying the endpoint and contract violated.

**Independent Test**: Run a single test module in isolation (e.g., `python -m pytest tests/e2e/api/test_datasets.py -v`) and confirm it self-seeds, runs, and passes without depending on other modules. Introduce a failure and confirm the error message includes the endpoint path.

- [X] T025 [US3] Review all test modules for clear assertion messages — every assertion that might fail should include a message string with the endpoint path (e.g., `assert r.status_code == 200, f"GET /v1/datasets/{ds_id}: expected 200, got {r.status_code}"`). Update `tests/e2e/api/conftest.py` factory fixtures to include endpoint paths in their internal assertions. **SC-006 compliance**: ensure each test module has a brief module-level docstring describing which router and endpoints it covers, so developers adding new endpoints can follow the pattern. Add a comment at the top of each module mapping it to its router source file in `anvil/api/v1/`.
- [X] T026 [US3] Verify each test module is independently runnable — for each module, run `python -m pytest tests/e2e/api/test_*.py -v` in isolation (not as a suite) and confirm it self-seeds data and passes without other modules having run first.

**Checkpoint**: All tests produce clear failure messages and pass when run in isolation.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Cleanup, verification, vault enrichment, and quality gates.

- [X] T027 Move the 3 existing tests from `tests/e2e/test_endpoints.py` into the appropriate new modules (test_health_ops.py: health + list_datasets go into test_datasets.py: list_datasets, test_experiments.py: list_experiments) and delete `tests/e2e/test_endpoints.py` — no loss of coverage
- [X] T028 Run `lsp_diagnostics` on all new files in `tests/e2e/api/` — confirm clean (no errors, `tests/` is exempt from docstring/lint strictness per existing ruff config)
- [ ] T029 Run `make test` locally and confirm all tests pass. Verify coverage gate (`fail_under = 23`) still passes. Report the new coverage %. **SC-002 baseline (validates the 90s guess)**: capture the measured lifecycle test runtime (from T021) and the full-suite runtime; if either materially exceeds its target, set the SC-002 threshold to the measured value plus headroom and update spec.md SC-002 + plan.md Performance Goals to reflect the validated number rather than the initial guess.
- [ ] T030 Run `make lint` + `make typecheck` — confirm both pass (test files are exempt via existing per-file-ignores, but no regressions in production code)
- [ ] T031 Run the full suite 3 consecutive times and confirm deterministic pass/fail results (no flakes)
- [ ] T032 Write session log to `docs/vault/Sessions/2026-06-21-api-e2e-suite.md` per vault enrichment protocol
- [ ] T033 Write discovery notes in `docs/vault/Discoveries/` for any real integration bugs found during test implementation (do NOT silently fix unrelated code)
- [ ] T034 Run `make vault-audit` — confirm 0 errors before committing vault changes

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies within Phase 1 — T002 through T008 should be implemented sequentially within the single conftest.py file
- **US1 (Phase 2)**: ALL 14 modules depend on Phase 1 completion (they import from conftest.py). Modules are mutually independent.
- **US4 (Phase 3)**: Depends on Phase 1 completion (uses factories). Best started after Phase 2 proves the factories are correct.
- **US2 (Phase 4)**: Depends on Phase 2 completion (needs tests to exist before verifying CI)
- **US3 (Phase 5)**: Depends on Phase 2 completion (reviews existing tests)
- **Polish (Phase 6)**: Depends on all prior phases

### Within Each User Story

- Phase 2 tasks T009-T020 are ALL [P] — can be implemented in parallel as independent test modules
- Phase 3 (T021) depends on Phase 1 but can be parallel with Phase 2
- Phase 4 (T022-T024) depends on Phase 2
- Phase 5 (T025-T026) depends on Phase 2

### Parallel Opportunities

- **All 14 per-router modules** can be implemented simultaneously (T009 through T020) — this is the biggest parallel opportunity
- Within each module, test functions are independent and can be developed in any order
- T021 (lifecycle) can start as soon as Phase 1 is done, even before Phase 2 finishes
- T022-T024 and T025-T026 can run in parallel once Phase 2 is done

---

## Parallel Example: Phase 2 (US1 — 14 Router Modules)

```bash
# Launch all 14 per-router test modules in parallel:
Task: "Implement test_health_ops.py in tests/e2e/api/test_health_ops.py"
Task: "Implement test_compute.py in tests/e2e/api/test_compute.py"
Task: "Implement test_pages.py in tests/e2e/api/test_pages.py"
Task: "Implement test_corpora.py in tests/e2e/api/test_corpora.py"
Task: "Implement test_datasets.py in tests/e2e/api/test_datasets.py"
Task: "Implement test_training.py in tests/e2e/api/test_training_router.py"
Task: "Implement test_experiments.py in tests/e2e/api/test_experiments.py"
Task: "Implement test_registry.py in tests/e2e/api/test_registry_api.py"
Task: "Implement test_inference.py in tests/e2e/api/test_inference_api.py"
Task: "Implement test_eval.py in tests/e2e/api/test_eval.py"
Task: "Implement test_governance.py in tests/e2e/api/test_governance.py"
Task: "Implement test_content.py in tests/e2e/api/test_content.py"
```

---

## Implementation Strategy

### MVP First (Phase 1 + Phase 2 — User Story 1)

1. Complete Phase 1: Setup (conftest.py with all factories)
2. Complete Phase 2: US1 — all 14 per-router modules (parallel)
3. **STOP and VALIDATE**: Run `make test` — all 14 routers covered
4. MVP complete: developer can self-verify all APIs

### Incremental Delivery

1. Setup + US1 (P1) → **MVP**: Core developer self-verification
2. US4 (P2) → Lifecycle integration confidence
3. US2 (P1) → CI automation verification
4. US3 (P2) → Debugging polish
5. Polish → Cleanup, vault, gates

### Parallel Team Strategy

With multiple implementers:
1. One agent/developer: Phase 1 (conftest.py — critical path)
2. Up to 14 parallel agents: Phase 2 modules (T009-T020)
3. One agent: Phase 3 (lifecycle test) — can start after Phase 1
4. One agent: Phases 4-6 (CI, review, polish)

---

## Notes

- [P] tasks = different files, no dependencies — can run simultaneously
- [Story] label maps task to specific user story
- Each user story is independently completable and testable
- Tests do NOT need separate test tasks — the implementation IS the test suite
- Commit after each task or logical group
- Stop at MVP checkpoint (end of Phase 2) to validate full coverage