---
title: Tasks — Learning Fine-Tuning Concepts
type: tasks
tags:
  - type/spec
created: '2026-06-28'
updated: '2026-06-28'
---
# Tasks: Learning Arc — Fine-Tuning Concepts

**Input**: Design documents from `docs/vault/Specs/048 Learning Fine-Tuning Concepts/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: No test tasks — this is a content-only feature. SC-004 (NMRG) requires pre-existing tests pass unmodified.

**FR-026 note**: "Each shippable fine-tuning capability MUST ship with its corresponding learning content" is
a policy constraint on future specs (039 warm-start, 044 PEFT/LoRA). This spec (048) provides the conceptual
framing pages. When 039/044 are implemented, each must include its own learning content tasks.

**Organization**: Tasks are grouped by implementation dependency order within the single user story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1 = single learner story)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Understanding Existing Patterns)

**Purpose**: Review existing code to identify exact insertion points and patterns before making changes.

- [X] T001 Review `LEARNING_ARC` list in `anvil/api/v1/learning.py` around line 168-174 to confirm exact insertion point after `"export"` entry (line 173)
- [X] T002 Review route handler pattern (`export_concept_page` at lines 2098-2105, an 8-line handler) in `anvil/api/v1/learning.py` to confirm exact handler signature: `@router.get` decorator → `async def ...(request) -> HTMLResponse` → docstring → `return ...TemplateResponse(request, "archetypes/concept.html", {"steps": ..._STEPS, **_arc_context("...")})`
- [X] T003 Review `WIDGET_CLASSES` registration in `anvil/api/templates/archetypes/concept.html` (map at lines 90-107; script includes at lines 70-86; widget-rendering loop at lines 26-36 that turns `step.widget` into `<div class="concept-widget" data-widget="...">`; auto-instantiation at lines 109-116). Note: the inline script block (line 87) carries a CSP nonce — `lora.js` is an EXTERNAL script include, so no nonce needed for it
- [X] T004 Review a SYNTHETIC (no-API) widget — `anvil/api/static/js/widgets/governance.js` or `memory-divergence.js` — as the precedent for `lora.js` (purely client-side math, no `fetch`/`apiFetch`). Confirm constructor + prototype pattern exposing `window.XxxWidget`

---

## Phase 2: Foundational (Step Data Arrays)

**Purpose**: Define the content data that route handlers will reference — MUST be complete before routes can be added.

- [X] T005 [P] Define `FINE_TUNING_INTRO_STEPS` array (5 steps) in `anvil/api/v1/learning.py`:
- [X] T006 [P] Define `WARMSTART_VS_LORA_STEPS` array (6 steps) in `anvil/api/v1/learning.py`:
- [X] T007 [P] Define `FINETUNE_VS_PROMPT_VS_RAG_STEPS` array (5 steps) in `anvil/api/v1/learning.py`:
  - Step 1: Fine-tuning — best for domain specialization, data available, behavior change needed
  - Step 2: Prompt engineering — best for quick tasks, no training data, zero setup
  - Step 3: Retrieval-Augmented Generation (RAG) — best for knowledge grounding, dynamic data
  - Step 4: Comparison table as inline HTML `<table>` — rows per approach, columns for strengths/weaknesses/use-cases
  - Step 5: Summary — decision guide combining all three approaches

**Checkpoint**: All three step arrays defined — content is ready for route integration.

---

## Phase 3: User Story 1 — Learner Progresses Into Fine-Tuning Concepts (Priority: P1) 🎯 MVP

**Goal**: Learner can navigate to three new fine-tuning concept pages as an ordered progression continuing from the existing from-scratch lessons.

**Independent Test**: Open `/v1/learn` — verify 3 new entries appear after "Model Export" in the numbered lesson list. Open each page — verify prev/next navigation. Open `/v1/learn/warmstart-vs-lora` — verify LoRA widget renders with rank slider.

### Tests for User Story 1 (follow existing convention in `tests/e2e/api/test_pages.py`) ⚠️

> **NOTE**: The codebase convention (Constitution Article IV — TDD) is one `test_learn_<name>` e2e route test per lesson. These NEW routes require NEW tests. SC-004 NMRG only means *pre-existing* tests stay unmodified — it does not exempt new public routes from coverage.

- [ ] T008 [P] [US1] Add `test_learn_fine_tuning_intro` in `tests/e2e/api/test_pages.py` — GET `/v1/learn/fine-tuning-intro` asserts 200, `text/html`, and the lesson title appears in body (follow `test_learn_export` pattern, lines 223-229)
- [ ] T009 [P] [US1] Add `test_learn_warmstart_vs_lora` in `tests/e2e/api/test_pages.py` — GET `/v1/learn/warmstart-vs-lora` asserts 200, title in body, AND `'data-widget="lora"' in r.text` (follow `test_learn_chunking` pattern with widget assertion, lines 232-240)
- [ ] T010 [P] [US1] Add `test_learn_finetune_vs_prompt_vs_rag` in `tests/e2e/api/test_pages.py` — GET `/v1/learn/finetune-vs-prompt-vs-rag` asserts 200, title in body, and `'<table'` present (comparison table)

### Implementation for User Story 1

- [X] T011 [US1] Add 3 `LEARNING_ARC` entries after `"export"` entry (line 173) in `anvil/api/v1/learning.py` — keys: `fine-tuning-intro`, `warmstart-vs-lora`, `finetune-vs-prompt-vs-rag` with paths and descriptions per data-model.md
- [X] T012 [P] [US1] Add `fine_tuning_intro_page` route handler in `anvil/api/v1/learning.py` after `export_concept_page` (after line 2105) — renders `concept.html` with `FINE_TUNING_INTRO_STEPS` and `_arc_context("fine-tuning-intro")`
- [X] T013 [P] [US1] Add `warmstart_vs_lora_page` route handler in `anvil/api/v1/learning.py` — renders `concept.html` with `WARMSTART_VS_LORA_STEPS` and `_arc_context("warmstart-vs-lora")`
- [X] T014 [P] [US1] Add `finetune_vs_prompt_vs_rag_page` route handler in `anvil/api/v1/learning.py` — renders `concept.html` with `FINETUNE_VS_PROMPT_VS_RAG_STEPS` and `_arc_context("finetune-vs-prompt-vs-rag")`
- [X] T015 [P] [US1] Create LoRA interactive widget in `anvil/api/static/js/widgets/lora.js` — IIFE exposing `window.LoraWidget`; constructor `LoraWidget(container)` + prototype methods; rank slider (1-16); canvas rendering of synthetic matrix W, approximation A×B, difference heatmap, reconstruction error display. Model after `governance.js`/`memory-divergence.js` (purely client-side, no `fetch`/`apiFetch`). Use `window.AnvilBase` helpers (`token()`, `initReducedMotion()`) for theme + reduced-motion. NOTE: widget auto-instantiates because the `WARMSTART_VS_LORA_STEPS` steps carry `"widget": "lora"`, which the concept.html loop (lines 26-36) renders as `<div class="concept-widget" data-widget="lora">`
- [X] T016 [US1] Register LoRA widget in `anvil/api/templates/archetypes/concept.html` — add `<script src="/static/js/widgets/lora.js"></script>` to the script includes block (after line 86, before the nonce'd inline `<script>` at line 87) and add `lora: window.LoraWidget,` to the `WIDGET_CLASSES` map (lines 90-107). Depends on T015
- [X] T017 [P] [US1] Add widget CSS classes in `anvil/api/static/css/components.css` — `.lora-controls`, `.lora-canvas`, `.lora-info`, `.coming-soon-badge` following existing `.widget-*` pattern
- [X] T018 [P] [US1] Add "Coming soon" badge implementation — forward-link badges in step bodies (T006-T007) where 039/044 capabilities are referenced, using the `.coming-soon-badge` class from T017

**Checkpoint**: All three fine-tuning concept pages functional with navigation, widget, "coming soon" forward links, and passing e2e route tests (T008-T010).

---

## Phase 4: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and compliance checks.

- [X] T019 Verify `make test` passes — pre-existing tests unmodified (SC-004 NMRG) AND new tests T008-T010 pass
- [X] T020 Verify `make lint` passes on `anvil/api/v1/learning.py`
- [X] T021 Verify new pages render at `/v1/learn/fine-tuning-intro`, `/v1/learn/warmstart-vs-lora`, `/v1/learn/finetune-vs-prompt-vs-rag` with correct prev/next navigation, and confirm all 3 appear in `/v1/learn` index between "Model Export" and "Chunking Strategies"
- [X] T022 [P] **UX compliance gate**: run `make ux-lint` on changed UI files (`concept.html`, `components.css`, `lora.js`) — must pass GATE: PASS before merge

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately; review tasks are parallelizable
- **Foundational (Phase 2)**: Depends on Setup (Phase 1) — step data arrays needed before routes
- **User Story (Phase 3)**: Depends on Foundational (Phase 2) — step data and LEARNING_ARC entries must exist before routes and widget can be connected
- **Polish (Phase 4)**: Depends on User Story completion

### Within User Story 1

- Tests (T008-T010) target the new routes — write FIRST (TDD); they FAIL until routes exist
- `LEARNING_ARC` entries (T011) must be added before routes (T012-T014) resolve in the index
- Route handlers (T012-T014) reference the step arrays from Phase 2 (T005-T007)
- Widget registration (T016) depends on widget creation (T015)
- CSS (T017) is independent; "coming soon" badges (T018) depend on T017's `.coming-soon-badge` class and the step bodies (T006-T007)

### Parallel Opportunities

| Task IDs | Why Parallel |
|----------|-------------|
| T001-T004 | All read-only reviews of different files |
| T005-T007 | Independent step arrays — no interdependencies |
| T008-T010 | Independent e2e tests in `test_pages.py` — write all three at once |
| T012-T014 | Independent route handlers in `learning.py` — can write all three at once (after T011) |
| T015, T017 | Widget JS and CSS in different files — fully parallel |

### Critical Sequencing (NOT parallel)

- T011 (arc entries) before T012-T014 take effect in the index page
- T015 (widget JS) before T016 (registration)
- T017 (CSS `.coming-soon-badge`) before T018 (badge usage)
- All implementation before T019-T022 (validation)

---

## Parallel Example: User Story 1

```bash
# Wave 1 — TDD: write failing tests first (after Phase 1 + 2 complete):
Task: "Add test_learn_fine_tuning_intro in tests/e2e/api/test_pages.py"
Task: "Add test_learn_warmstart_vs_lora in tests/e2e/api/test_pages.py"
Task: "Add test_learn_finetune_vs_prompt_vs_rag in tests/e2e/api/test_pages.py"

# Wave 2 — implementation (after T011 LEARNING_ARC entries added):
Task: "Add 3 route handlers after line 2105 in anvil/api/v1/learning.py"
Task: "Create lora.js widget in anvil/api/static/js/widgets/lora.js"
Task: "Add widget + badge CSS in anvil/api/static/css/components.css"

# Wave 3 — wiring:
Task: "Register lora.js in concept.html (script include + WIDGET_CLASSES)"
Task: "Add coming-soon badges to step bodies"
```

---

## Implementation Strategy

### MVP (Single Phase)

This feature has ONE user story — the entire feature IS the MVP:

1. Complete Phase 1: Review patterns
2. Complete Phase 2: Define step data arrays
3. Write tests (T008-T010) — they FAIL (routes don't exist yet)
4. Complete Phase 3 implementation: arc entries, routes, widget, CSS, badges
5. Validate: tests now PASS, verify pages render
6. Deploy

### Sequential Implementation Order

1. All T001-T004 (parallel reviews)
2. All T005-T007 (parallel step definitions)
3. T008-T010 (parallel failing tests — TDD)
4. T011 (LEARNING_ARC entries) → then T012-T014 + T015 + T017 in parallel
5. T016 (widget registration) + T018 (badges)
6. T019-T022 (validation)

---

## Notes

- [P] tasks = different files, no dependencies
- [US1] label maps task to the single user story
- **New routes get new e2e tests** (T008-T010) per codebase convention + Constitution Article IV (TDD). SC-004 NMRG means *pre-existing* tests stay unmodified — verified: `test_pages.py` uses per-lesson `in r.text` assertions (no count/`len()` checks), and `test_related_lessons.py` iterates `LEARNING_ARC` dynamically requiring `/v1/learn/` paths — the new entries satisfy this
- Widget JS (`lora.js`) does NOT require a backend API — uses synthetic matrix math (precedent: `governance.js`, `memory-divergence.js`, `architecture.js`)
- No changes needed to `pages.py` — cross-linking new lessons from workspace pages is optional enrichment, out of scope
- Commit after each logical group of tasks