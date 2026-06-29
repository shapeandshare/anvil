---
title: Tasks — Learning Architecture Differences
type: tasks
tags:
  - type/spec
created: '2026-06-28'
updated: '2026-06-28'
---
# Tasks: Learning Arc — Architecture Differences

**Input**: Design documents from `docs/vault/Specs/049 Learning Architecture Differences/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: This is a content+UI feature. One new e2e route test per the codebase convention (Constitution Article IV — TDD). SC-005 (NMRG) only means *pre-existing* tests stay unmodified — it does not exempt new public routes from coverage.

**Organization**: Tasks are grouped by implementation dependency order within the single user story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1 = single learner story)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Understanding Existing Patterns)

**Purpose**: Review existing code to identify exact insertion points, template patterns, and accordion/CSS conventions before making changes.

- [X] T001 Review `LEARNING_ARC` list in `anvil/api/v1/learning.py` around lines 168-195 to confirm exact insertion point after `"finetune-vs-prompt-vs-rag"` entry (line ~191), before `"chunking"` (line ~193)
- [X] T002 Review route handler pattern in `anvil/api/v1/learning.py` — examine `finetune_vs_prompt_vs_rag_page` (the last 048 handler, around line 2362) to confirm handler signature: `@router.get` decorator → `async def ...(request) -> HTMLResponse` → docstring → `return ...TemplateResponse(request, "archetypes/concept.html", {"steps": ..._STEPS, **_arc_context("...")})` — note this spec uses a DIFFERENT template (`architecture-differences.html`)
- [X] T003 Review the accordion/FAQ pattern in `anvil/api/templates/archetypes/faq.html` and `anvil/api/static/css/components.css` (`.faq-item`, `.faq-question`, `.faq-answer`, `.faq-toggle` classes around lines 800-870) to understand the collapsible section pattern to reuse in the new template
- [X] T004 Review the FAQ accordion JS pattern — `toggleFaq()` function in `anvil/api/templates/archetypes/faq.html` or `anvil/api/templates/partials/faq-common.html`. Note: the new template will embed an inline version with CSP nonce
- [X] T005 Review existing e2e test pattern in `tests/e2e/api/test_pages.py` — look at `test_learn_finetune_vs_prompt_vs_rag` or similar for the exact assertion pattern (200, content-type, title in body) to replicate

---

## Phase 2: Foundational (Content Step Data)

**Purpose**: Define the content data that the route handler and template will reference — MUST be complete before routes and template can be connected.

- [X] T006 Define `ARCHITECTURE_DIFFERENCES_STEPS` array (5 sections) in `anvil/api/v1/learning.py`:
  - Section `tokenization`: explain char-level vs subword/BPE tokenization, vocabulary size differences, fine-tuning implications
  - Section `attention`: explain multi-head vs grouped-query vs multi-query attention, KV cache implications, weight portability
  - Section `parameters`: explain parameter scaling (4K vs 1.1B+), n_embd/n_layer scaling, fine-tuning method implications
  - Section `context`: explain context window differences (anvil default `block_size=16` vs 4K-128K), RoPE extrapolation, char-level vs subword effective context. VERIFY the anvil value against `anvil/core/engine.py` (`block_size: int = 16`) before writing — do NOT hardcode a guessed number
  - Section `allow-list`: LlamaForCausalLM + safetensors allow-list, why the boundary exists, GGUF as deferred/planned (specs 050-052)
  - Each section uses key/title/body dict format matching existing `*_STEPS` convention
  - Body content as HTML prose (paragraphs, `<ul>`, `<code>`, `<b>` tags allowed)
  - **ACCURACY GATE (FR-032)**: All taught factual values MUST match the code single source of truth. Verify before writing: allow-list = `_ALLOWED_ARCHITECTURES` (`{LlamaForCausalLM}`) and format = `_ACCEPTED_FORMATS` (`{safetensors}`) in `anvil/services/model_import/model_import_service.py`; default model params (`n_embd=16`, `n_layer=1`, `n_head=4`, `block_size=16`) and RoPE theta (10000.0) in `anvil/core/engine.py`. Do NOT hardcode guessed numbers (e.g. context length is 16, not 32)

**Checkpoint**: `ARCHITECTURE_DIFFERENCES_STEPS` defined — content ready for route and template integration.

---

## Phase 3: User Story 1 — Learner Understands How Architectures Differ (Priority: P1) 🎯 MVP

**Goal**: Learner can explore a single-page accordion module explaining how model architectures differ (tokenization, attention, parameters, context, allow-list) and understands why anvil supports a limited architecture set.

**Independent Test**: Open `/v1/learn/architecture-differences` — verify page renders with arc navigation (prev/next + "Back to Learning Index"). Verify all 5 accordion sections display. Open `/v1/learn/architecture-differences#allow-list` — verify allow-list section auto-opens. Also verify "Architecture Differences" entry appears in `/v1/learn` index between "Fine-Tune vs Prompt vs RAG" and "Chunking Strategies".

### Tests for User Story 1 (follow existing convention in `tests/e2e/api/test_pages.py`) ⚠️

> **NOTE**: The codebase convention (Constitution Article IV — TDD) is one `test_learn_<name>` e2e route test per lesson. This NEW route requires a NEW test. SC-005 NMRG only means *pre-existing* tests stay unmodified — it does not exempt new public routes from coverage.

- [X] T007 [P] [US1] Add `test_learn_architecture_differences` in `tests/e2e/api/test_pages.py` — GET `/v1/learn/architecture-differences`:
  - Asserts `r.status_code == 200`
  - Asserts `"text/html" in r.headers["content-type"]`
  - Asserts all 5 section titles appear in `r.text`: `"Tokenization Differences"`, `"Attention Variants"`, `"Parameter Scaling"`, `"Context Length"`, `"Architecture Allow-List"`
  - Asserts arc navigation links present (either prev or next lesson name in body)
  - Asserts anchor ID `id="allow-list"` present for cross-linking from 041

### Implementation for User Story 1

- [X] T008 [US1] Add `"architecture-differences"` entry to `LEARNING_ARC` in `anvil/api/v1/learning.py` after `"finetune-vs-prompt-vs-rag"` entry, before `"chunking"` entry — key: `"architecture-differences"`, title: `"Architecture Differences"`, path: `"/v1/learn/architecture-differences"`, desc: `"How model architectures differ — tokenization, attention variants, parameter scaling, context length — and what those differences mean for fine-tuning."`
- [X] T009 [P] [US1] Add `architecture_differences_page` route handler in `anvil/api/v1/learning.py` after `finetune_vs_prompt_vs_rag_page` — `@router.get("/learn/architecture-differences", response_class=HTMLResponse)` → `async def architecture_differences_page(request: Request) -> HTMLResponse` → docstring → `return ...TemplateResponse(request, "archetypes/architecture-differences.html", {"steps": ARCHITECTURE_DIFFERENCES_STEPS, **_arc_context("architecture-differences")})`
- [X] T010 [P] [US1] Create accordion template in `anvil/api/templates/archetypes/architecture-differences.html` — extends `base.html`, imports `archetypes.css`, renders:
  - `.concept-lesson-header` block with arc navigation (title, "Back to Learning Index", prev/next links — reuse same pattern as `concept.html` lines 13-23)
  - Introduction paragraph (single `<p>` setting context: "anvil trains a char-level mini-Llama. This page explains how production architectures differ and what that means for fine-tuning.")
  - Accordion section loop: for each step, render a `.faq-item.section-card` with `id="{{ step.key }}"` containing `.faq-question.section-card__header` with `.section-card__title` and `.faq-toggle`, plus `.faq-answer.section-card__content` with `{{ step.body | safe }}`
  - Inline `<script nonce="{{ request.state.csp_nonce }}">` block with:
    - `toggleFaq()` function (same logic as FAQ template: toggle `aria-expanded`, toggle `.faq-answer` display between `none` and `block`, toggle `.faq-toggle` text between `[+]` and `[-]`)
    - Auto-open IIFE: checks `window.location.hash`, finds matching `.faq-item` by ID, calls `toggleFaq()` via `setTimeout(..., 100)` (allows DOM to settle)
  - `didyouknow_banner` block (same as `concept.html`/`faq.html`)

**Checkpoint**: Architecture differences page functional with accordion sections, arc navigation, auto-open anchor support, and passing e2e route test (T007).

---

## Phase 4: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and compliance checks.

- [X] T011 Verify `make test` passes — pre-existing tests unmodified (SC-005 NMRG) AND new test T007 passes
- [X] T012 Verify `make lint` passes on `anvil/api/v1/learning.py` (no new Python code beyond steps array and route)
- [X] T013 Verify new page renders at `/v1/learn/architecture-differences` with correct prev/next navigation (previous: "Fine-Tune vs Prompt vs RAG", next: "Chunking Strategies"), verify entry appears in `/v1/learn` index between those entries
- [X] T014 Verify anchor auto-open: navigate to `/v1/learn/architecture-differences#allow-list` — confirm allow-list section is open on page load
- [X] T015 [P] **UX compliance gate**: run `make ux-lint` on changed UI files (`architecture-differences.html`) — must pass GATE: PASS before merge
- [X] T016 [US1] Add cross-link FROM 041 external model detail to 049: in `anvil/api/templates/archetypes/models.html` or the external model detail rendering code, display a link to `/v1/learn/architecture-differences#allow-list` when a model has `runnable_status: "track_only"`. This ensures the "not eligible / unknown architecture" flag in the catalog (041) links into the architecture-differences module per FR-025a. (Requires coordination with 041 template changes; the anchor target `#allow-list` is already supported by T010.)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately; review tasks T001-T005 are parallelizable
- **Foundational (Phase 2)**: Depends on Setup (Phase 1) — step data array needed before routes
- **User Story (Phase 3)**: Depends on Foundational (Phase 2) — step data (T006) and LEARNING_ARC entry (T008) must exist before route (T009) and template (T010) can be connected
- **Polish (Phase 4)**: Depends on User Story completion

### Within User Story 1

- Test (T007) targets the new route — write FIRST (TDD); it FAILS until route exists
- `LEARNING_ARC` entry (T008) must be added before route (T009) resolves in the index
- Route handler (T009) references step array from Phase 2 (T006)
- Template (T010) is independent from route handler — can be written in parallel, but both must exist for the route to render
- Template depends on understanding the accordion pattern (T003, T004)

### Parallel Opportunities

| Task IDs | Why Parallel |
|----------|-------------|
| T001-T005 | All read-only reviews of different files/patterns |
| T007, T008 | Test and arc entry — different files, no interdependencies |
| T009, T010 | Route handler and template — different files, can write in parallel (after T006, T008) |
| T016 | Independent from other Polish tasks — can run in parallel with T011-T015

### Critical Sequencing (NOT parallel)

- T006 (step data) before T009 (route handler references it)
- T008 (arc entry) before T009 (route won't appear in navigation without it)
- T003+T004 (accordion pattern review) before T010 (template uses the pattern)
- T007 (failing test) can be written before any implementation (TDD)
- All implementation before T011-T016 (validation)

---

## Parallel Example: User Story 1

```bash
# Wave 1 — TDD: write failing test first (after Phase 1 + 2 complete):
Task: "Add test_learn_architecture_differences in tests/e2e/api/test_pages.py"

# Wave 2 — implementation in parallel (after T006 step data + T008 arc entry):
Task: "Add architecture_differences_page route handler in anvil/api/v1/learning.py"
Task: "Create architecture-differences.html accordion template in anvil/api/templates/archetypes/"

# Wave 3 — validation:
Task: "Run make test to verify both pre-existing and new tests pass"
Task: "Manually verify page renders and accordion auto-open works"
```

---

## Implementation Strategy

### MVP (Single Phase)

This feature has ONE user story — the entire feature IS the MVP:

1. Complete Phase 1: Review existing patterns (T001-T005)
2. Complete Phase 2: Define step data (T006)
3. Write test (T007) — it FAILS (route doesn't exist yet)
4. Add LEARNING_ARC entry (T008)
5. Complete Phase 3 implementation: route handler (T009) + template (T010) — write both in parallel
6. Validate: tests now PASS, verify accordion + anchor auto-open
7. Deploy

### Sequential Implementation Order

1. All T001-T005 (parallel reviews)
2. T006 (step data definition)
3. T007 (failing test — TDD)
4. T008 (LEARNING_ARC entry)
5. T009 + T010 (route handler + template — parallel)
6. T011-T016 (validation cross-links and compliance)

---

## Notes

- [P] tasks = different files, no dependencies
- [US1] label maps task to the single user story
- **New route gets a new e2e test** (T007) per codebase convention + Constitution Article IV (TDD). SC-005 NMRG means *pre-existing* tests stay unmodified — verified: `test_pages.py` uses per-lesson `in r.text` assertions (no count/`len()` checks), and `test_related_lessons.py` iterates `LEARNING_ARC` dynamically requiring `/v1/learn/` paths — the new entry satisfies this
- No new JS widget files needed — this is a content-only page using the existing FAQ accordion pattern
- Template reuses existing `.faq-item`, `.faq-question`, `.faq-answer`, `.faq-toggle` CSS from `components.css` — no CSS changes needed unless accordion-specific overrides are required
- No changes needed to `pages.py` — cross-linking the new lesson from workspace pages is optional enrichment, out of scope
- Commit after each logical group of tasks