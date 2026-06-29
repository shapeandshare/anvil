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

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Pydantic models and catalog data that ALL user story tasks depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T003 [P] Create `anvil/services/inference/model_browser_types.py` with Pydantic models: `ResourceEnvelope`, `CatalogEntry`, `CuratedCatalog`, `RunnableArchitecture` (StrEnum with `LLAMA_FOR_CAUSAL_LM = "LlamaForCausalLM"`)
- [ ] T004 [P] Create `anvil/data/curated-models.yaml` with initial entries: TinyLlama 1.1B Chat, TinyLlama 1.1B base, and 1-2 other TinyLlama-class models with documented resource envelopes per the schema in `contracts/catalog-format.md`

**Checkpoint**: Foundation ready — Pydantic models load, YAML parses and validates

---

## Phase 3: User Story 1 — Learner Browses and Picks a Model That Fits (Priority: P1) 🎯 MVP

**Goal**: A learner opens the HF view at `/v1/hf-browser`, browses the curated catalog, sees eligibility badges based on their machine's resources, searches HF Hub, inspects a model card, and imports a model.

**Independent Test**: Open `/v1/hf-browser`, confirm the curated catalog renders with eligibility badges on each card, search for "TinyLlama", inspect a result's card, click import, confirm the import job is created via spec 040.

### Tests for User Story 1

- [ ] T005 [P] [US1] Unit test: YAML catalog parsing and validation through Pydantic `CuratedCatalog` in `tests/unit/services/inference/test_model_browser_types.py`
- [ ] T006 [P] [US1] Unit test: `RunnableArchitecture` enum membership and allow-list comparison in `tests/unit/services/inference/test_model_browser_types.py`
- [ ] T007 [US1] Write failing e2e test for `/v1/hf-browser` page returning 200 in `tests/e2e/test_hf_browser.py`
- [ ] T008 [US1] Write failing e2e test for `GET /v1/hf-browser/search?q=<query>` JSON endpoint in `tests/e2e/test_hf_browser.py`

### Implementation for User Story 1

**Service layer:**

- [ ] T009 [US1] Implement `ModelBrowserService` in `anvil/services/inference/model_browser.py` with:
  - `load_catalog()` — load and validate YAML via Pydantic
  - `check_eligibility(catalog_entry, detected_device)` — pure function comparing `ResourceEnvelope` against host; also validates accepted weight format (`safetensors`)
  - `get_allow_list()` — return `RunnableArchitecture` values
  - `is_catalog_model(hf_id)` — check membership against loaded catalog
  - `accepted_format()` — return `"safetensors"` string for UI display

- [ ] T010 [US1] Implement `HubClient` in `anvil/services/inference_hub/hub_client.py` with:
  - Lazy `from huggingface_hub import HfApi` (behind `[finetune]` extra)
  - `search_models(query, limit=20)` — wrapped `HfApi.list_models()` with 5-min in-memory TTL cache
  - `get_model_info(hf_id)` — wrapped `HfApi.model_info()` with 30-min in-memory TTL cache
  - Graceful 429 handling: return cached data if available, else user-friendly error in response

- [ ] T011 [US1] Wire `ModelBrowserService` into `AnvilWorkbench` in `anvil/workbench.py`:
  - Add `self._model_browser: ModelBrowserService | None = None` to `__init__`
  - Add `@property def model_browser(self) -> ModelBrowserService` with lazy init
  - Wire device detection: pass `self.compute.device` (from `anvil/services/compute/resolve.py`) as the detected device to eligibility checks

**API layer:**

- [ ] T012 [US1] Create route `GET /v1/hf-browser` in `anvil/api/v1/pages.py`:
  - Inject workbench via `Depends(get_workbench)`
  - Pass catalog, allow-list, host device, hf_available flag to template context
  - Render `hf_browser.html` template

- [ ] T013 [P] [US1] Create search JSON API route at `GET /v1/hf-browser/search` in `anvil/api/v1/hf_browser_api.py`:
  - Accept `q` query param (string) and optional `limit` query param (int, default 20, max 50)
  - Return `{"results": [...], "cached": bool, "error": null | str}`
  - Handle `[finetune]` extra not installed → return `503` with `EXTRA_MISSING` code per `contracts/api-browser.md`

- [ ] T014 [P] [US1] Create import trigger route at `POST /v1/hf-browser/import` in `anvil/api/v1/hf_browser_api.py` (per `contracts/api-import.md`):
  - Accept `{"hf_id": str, "architecture": str}` body
  - Delegate to `workbench.model_import` (spec 040) — return `202 Accepted`

**UI layer:**

- [ ] T015 [US1] Create Jinja2 template `anvil/api/templates/hf_browser.html`:
  - Extends `base.html`
  - Search bar at top, curated catalog card grid below, detail panel on card selection
  - Each card shows: model name, params, architecture, **eligibility badge** (green check / yellow warning)
  - "Import" button on each card (calls POST /v1/hf-browser/import)
  - Non-allow-list models shown as **track-but-not-run** with a link to the architecture-differences lesson (`/v1/learn/architecture-differences`, spec 049)
  - Accepted weight format (`safetensors`) displayed in the model detail panel
  - Offline banner when `hf_available` is false or HF API unreachable
  - Follows design system tokens from `anvil/api/static/css/tokens.css`

- [ ] T016 [US1] Register the HF browser route in auth middleware: add `"/v1/hf-browser"` to `PAGE_PREFIXES` tuple in `anvil/api/auth.py`
- [ ] T017 [US1] Add navigation link: insert `<a href="/v1/hf-browser" class="tab-item">` in the `nav-bar__tabs` div in `anvil/api/templates/base.html`

**Checkpoint**: At this point, User Story 1 should be fully functional — browse curated catalog, see eligibility badges, search HF Hub, inspect models, import via spec 040.

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
| T001 ↔ T002 | Different files, no dependencies |
| T003 ↔ T004 | Different files (models file vs YAML data file) |
| T005 ↔ T006 | Different test files (same file OK — different classes) |
| T007 ↔ T008 | Different e2e test scenarios |
| T009 ↔ T010 | ModelBrowserService vs HubClient — different responsibilities, no shared state at impl time |
| T013 ↔ T014 | Different route handlers in same file — can be written together |
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
Task: "Page route + search API route (GET) + import route (POST)"
Task: "Jinja2 template"
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
8. **STOP and VALIDATE**: SC-001 through SC-005 verified

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
- Import action delegates entirely to spec 040 — ModelBrowserService does NOT implement import logic