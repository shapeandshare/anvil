# Tasks: HuggingFace Model Browser & Curated Catalog

**Input**: Design documents from `docs/vault/Specs/041 HuggingFace Model Browser/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/
**Branch**: `041-huggingface-model-browser`

**Tests**: Unit tests and e2e tests are included per Constitution Article IV (TDD Mandatory) and Article XI §11.6 (testable paths).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1)
- Include exact file paths in descriptions

## Path Conventions

- **Project root**: `/Users/joshburt/.local/share/opencode/worktree/5354809a525912e5a56a6d4a6e81ccf9f89efdf3/hidden-forest`
- **Package**: `anvil/`
- **Tests**: `tests/`

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization — register the bundled catalog file, create new sub-package skeleton

- [ ] T001 [P] Register `"data/curated-models.yaml"` in `[tool.setuptools.package-data]` in `pyproject.toml`
- [ ] T002 [P] Create `anvil/services/inference_hub/__init__.py` with bare docstring: `"""HF Hub integration — guarded behind the ``[finetune]`` extra."""`
- [ ] T002a [P] Add `pyyaml>=6,<7` to `[project.dependencies]` in `pyproject.toml` (currently only a transitive dep; the catalog loader runs at base install). Per FR-007b / constitution lean-dependency rule.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Pydantic models and catalog data that ALL user story tasks depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T003 [P] Create `anvil/services/inference/model_browser_types.py` with Pydantic models: `ResourceEnvelope` (with a `field_validator` ensuring `min_vram_per_backend` contains a `cpu` key), `CatalogEntry`, `CuratedCatalog`. **Do NOT define a `RunnableArchitecture` enum** — reuse spec 040's `_ALLOWED_ARCHITECTURES`, `_ACCEPTED_FORMATS` (`anvil/services/model_import/model_import_service.py`) and `RunnableStatus` (`anvil/services/_shared/runnable_status.py`).
- [ ] T004 [P] Create `anvil/data/curated-models.yaml` with initial entries: TinyLlama 1.1B Chat, TinyLlama 1.1B base, and 1-2 other TinyLlama-class models with documented resource envelopes per the schema in `contracts/catalog-format.md`. `min_vram_per_backend` keys MUST use `DeviceType` strings (`cpu`/`cuda`/`mps`).

**Checkpoint**: Foundation ready — Pydantic models load, YAML parses and validates

---

## Phase 3: User Story 1 — Learner Browses and Picks a Model That Fits (Priority: P1) 🎯 MVP

**Goal**: A learner opens the HF view at `/v1/hf-browser`, browses the curated catalog, sees eligibility badges based on their machine's resources, searches HF Hub, inspects a model card, and imports a model.

**Independent Test**: Open `/v1/hf-browser`, confirm the curated catalog renders with eligibility badges on each card, search for "TinyLlama", inspect a result's card, click import, confirm the import job is created via spec 040.

### Tests for User Story 1

- [ ] T005 [P] [US1] Unit test: YAML catalog parsing and validation through Pydantic `CuratedCatalog` (including the `min_vram_per_backend` must-contain-`cpu` validator) in `tests/unit/services/inference/test_model_browser_types.py`
- [ ] T006 [P] [US1] Unit test: `check_eligibility(envelope, gpu, ram_total_gb)` pure function — cover CPU-only (RAM only), CUDA (RAM+VRAM pass/fail), MPS (best-effort proxy), and allow-list/format comparison against spec 040 constants — in `tests/unit/services/inference/test_model_browser.py`
- [ ] T007 [US1] Write failing e2e test for `/v1/hf-browser` page returning 200 in `tests/e2e/test_hf_browser.py`
- [ ] T008 [US1] Write failing e2e test for `GET /v1/hf-browser/search?q=<query>` JSON endpoint in `tests/e2e/test_hf_browser.py`

### Implementation for User Story 1

**Service layer:**

- [ ] T009 [US1] Implement `ModelBrowserService` in `anvil/services/inference/model_browser.py` with:
  - `load_catalog()` — load and validate YAML via Pydantic (uses PyYAML; cache parsed result in memory)
  - `check_eligibility(envelope, gpu, ram_total_gb) -> bool` — **pure function** per `data-model.md`: RAM check always; VRAM check only when `gpu.available`; CPU-only skips VRAM; MPS is best-effort
  - `runnable_status(entry) -> RunnableStatus` — compare `entry.architecture` against the **imported** `_ALLOWED_ARCHITECTURES` from spec 040 → `RUNNABLE` / `TRACK_ONLY` (no local constant)
  - `is_catalog_model(hf_id)` — check membership against loaded catalog
  - Service gathers detection inputs by calling `detect_gpu()` (`anvil/gpu.py`) and `psutil.virtual_memory()` and passing values into the pure function

- [ ] T010 [US1] Implement `HubClient` in `anvil/services/inference_hub/hub_client.py` with:
  - Lazy `from huggingface_hub import HfApi` (behind `[finetune]` extra) — follow the existing guard pattern in `anvil/services/model_import/hf_source.py`
  - `search_models(query, limit=20)` — wrapped `HfApi.list_models()` with 5-min in-memory TTL cache
  - `get_model_info(hf_id)` — wrapped `HfApi.model_info()` with 30-min in-memory TTL cache
  - Graceful 429 handling: return cached data if available, else user-friendly error in response

- [ ] T011 [US1] Wire `ModelBrowserService` into `AnvilWorkbench` in `anvil/workbench.py`:
  - Add `self._model_browser: ModelBrowserService | None = None` to `__init__` (follow the existing lazy-property pattern, e.g. `model_imports`)
  - Add `@property def model_browser(self) -> ModelBrowserService` with lazy init
  - **No `workbench.compute.device` exists** — the service itself calls `detect_gpu()` + `psutil`; do NOT invent a compute property

**API layer:**

- [ ] T012 [US1] Create route `GET /v1/hf-browser` in `anvil/api/v1/pages.py`:
  - Inject workbench via `Depends(get_workbench)`
  - Build template context: `catalog` (each entry annotated with computed `eligible` + `runnable_status`), `allow_list` (from spec 040 constant), `accepted_format`, `host_backend`, `host_ram_gb`, `lesson_049_available`, `hf_available`
  - Add `"/v1/hf-browser"` to `PAGE_PREFIXES` in `anvil/api/auth.py` (same step group as T016)
  - Render `hf_browser.html` template

- [ ] T013 [P] [US1] Create search JSON API route at `GET /v1/hf-browser/search` in `anvil/api/v1/hf_browser_api.py`:
  - Accept `q` query param (string, required) and optional `limit` query param (int, default 20, max 50)
  - Return `{"results": [...], "cached": bool, "error": null | str}`
  - Handle `[finetune]` extra not installed → return `503` with `EXTRA_MISSING` code per `contracts/api-browser.md`
  - Register this router in `anvil/api/v1/router.py`

> **Note**: There is NO new import endpoint. Import reuses the existing `POST /v1/models/import` (spec 040). See `contracts/api-import.md`. (Former T014 deleted.)

**UI layer:**

- [ ] T015 [US1] Create Jinja2 template `anvil/api/templates/hf_browser.html`:
  - Extends `base.html`
  - Search bar at top, curated catalog card grid below, detail panel on card selection
  - Each card shows: model name, params, architecture, **eligibility badge** (green check / yellow warning) computed against host RAM/VRAM
  - "Import" button issues a client-side `POST /v1/models/import` with `{source:"huggingface", identifier:<hf_id>}` (NO architecture field), then optionally polls `GET /v1/models/import/{job_id}/status`
  - Non-allow-list models shown as **track-but-not-run**; show architecture-differences lesson link ONLY when `lesson_049_available` is true (otherwise omit / "coming soon" — never a broken link)
  - Accepted weight format displayed in the model detail panel (from `accepted_format` context)
  - Offline banner when `hf_available` is false or HF API unreachable
  - Follows design system tokens from `anvil/api/static/css/tokens.css`

- [ ] T016 [US1] Register the HF browser route in auth middleware: add `"/v1/hf-browser"` to `PAGE_PREFIXES` tuple in `anvil/api/auth.py`
- [ ] T017 [US1] Add navigation link: insert `<a href="/v1/hf-browser" class="tab-item">` in the `nav-bar__tabs` div in `anvil/api/templates/base.html`

**Checkpoint**: At this point, User Story 1 should be fully functional — browse curated catalog, see eligibility badges, search HF Hub, inspect models, import via the existing spec 040 route.

---

## Phase 4: Polish & Cross-Cutting Concerns

**Purpose**: Improvements, UX compliance, and final validation

- [ ] T018 [P] Run diagnostics and fix any LSP errors on all changed files
- [ ] T019 [P] **UX compliance gate**: run `make ux-lint` on all changed UI/template/CSS files — must pass GATE: PASS before merge
- [ ] T020 Run full test suite (`make test`) — all tests pass, including pre-existing tests (NMRG per SC-005)
- [ ] T021 Run `make lint`, `make typecheck` — zero new violations

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS User Story 1
- **User Story 1 (Phase 3)**: Depends on Foundational phase completion — all tasks within US1 follow the pattern: tests write first → models → service → route → template → registration
- **Polish (Phase 4)**: Depends on User Story 1 completion

### Within User Story 1

- Tests (T005-T008) MUST be written and FAIL before implementation
- Models/types before services (T009 depends on T003)
- Services before routes (T012/T013 depend on T011)
- Core service before HF Hub client (T010 is independent — parallel with T009)
- Template before route registration (T015 before T016/T017)
- Route + template complete before e2e tests pass

### Parallel Opportunities

| Tasks | Why Parallel |
|-------|-------------|
| T001 ↔ T002 ↔ T002a | Different files / different pyproject sections, no dependencies |
| T003 ↔ T004 | Different files (models file vs YAML data file) |
| T005 ↔ T006 | Different test files (types vs service) |
| T007 ↔ T008 | Different e2e test scenarios |
| T009 ↔ T010 | ModelBrowserService vs HubClient — different responsibilities, no shared state at impl time |
| T016 ↔ T017 | Different files (auth.py vs base.html) |

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "Unit test for Pydantic models in tests/unit/services/inference/test_model_browser_types.py"
Task: "E2E test for page render in tests/e2e/test_hf_browser.py"

# Launch models + catalog + service + client in parallel:
Task: "Pydantic models in model_browser_types.py"
Task: "curated-models.yaml data file"
Task: "ModelBrowserService in model_browser.py"
Task: "HubClient in inference_hub/hub_client.py"

# Launch all routes + template together after service wiring:
Task: "Page route (GET /v1/hf-browser) + search API route (GET /v1/hf-browser/search)"
Task: "Jinja2 template (import button reuses existing POST /v1/models/import)"
Task: "Auth registration + Nav link"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

This feature has a single User Story (P1). The full feature IS the MVP.

1. Complete Phase 1: Setup (register package-data, create sub-package)
2. Complete Phase 2: Foundational (Pydantic models + catalog YAML)
3. Write tests (T005-T008) — they MUST fail initially (Red)
4. Implement service layer (T009-T011)
5. Implement routes + template (T012-T017)
6. Tests pass (Green)
7. Phase 4: Polish + compliance gates
8. **STOP and VALIDATE**: SC-001 through SC-006 verified

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Write failing tests → Red wave
3. Implement services → Green wave
4. Implement UI → Full feature visible
5. Polish + gates → Merge-ready

---

## Notes

- [P] tasks = different files, no dependencies
- [US1] label maps task to User Story 1 for traceability
- User Story 1 should be independently completable and testable
- Verify tests fail before implementing (Red-Green-Refactor)
- Commit after each logical task group
- Avoid: vague tasks, same file conflicts
- Import action reuses the existing `POST /v1/models/import` route — no new endpoint; `ModelBrowserService` does NOT implement import logic
- Allow-list / accepted-format / runnable-status constants are imported from spec 040 — never duplicated
- Eligibility uses `detect_gpu()` + `psutil` — there is no `workbench.compute.device` property
- PyYAML must be promoted to a declared core dependency (T002a) before relying on it