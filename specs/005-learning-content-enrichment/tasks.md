# Tasks: Learning Content Enrichment

**Input**: Design documents from `specs/005-learning-content-enrichment/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Tests**: Test tasks are included for backend endpoints (per spec FRs and Constitution Article IV — TDD Mandatory).

**Organization**: Tasks grouped by user story (7 stories, 3 P1 + 4 P2). Each story is independently implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- Include exact file paths in descriptions

## Path Conventions

- All paths relative to repository root
- Python package: `microgpt/`
- Widget JS: `microgpt/api/static/js/widgets/`
- Widget HTML: `microgpt/api/templates/partials/concept-widgets/`
- Lesson templates: `microgpt/api/templates/archetypes/`
- CSS: `microgpt/api/static/css/`
- Examples: `examples/`
- Tests: `tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Review design artifacts and verify no new dependencies needed

- [X] T001 Review all design artifacts in `specs/005-learning-content-enrichment/` — plan.md, spec.md, research.md, data-model.md, 4 contract files, quickstart.md
- [X] T002 [P] Verify existing test suite passes with `make test` — confirms no regressions before starting
- [X] T003 [P] Verify existing lint passes with `make lint`

**Checkpoint**: Design reviewed, baseline tests pass. No new pip dependencies needed.

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Add `backward_graph()` method to InferenceService in `microgpt/services/inference.py` — runs forward pass on input text, computes loss, calls `loss.backward()`, then traverses Value graph capturing `.data`, `.grad`, `.local_grads` per node. Capped at 400 nodes.
- [X] T005 [P] Add `loss_breakdown()` method to InferenceService in `microgpt/services/inference.py` — tokenizes input, runs forward pass per position, computes per-token cross-entropy + running average + random-guess baseline (`-log(1/vocab_size)`)
- [X] T006 [P] Add `model_params()` method to InferenceService in `microgpt/services/inference.py` — iterates `GPT.state_dict`, extracts shape/param count per named matrix, categorizes into embedding/attention/mlp/output groups
- [X] T007 Add routes for new endpoints in `microgpt/api/v1/inference.py` — `POST /v1/inference/backward-graph`, `POST /v1/inference/loss-breakdown`, `GET /v1/inference/model-params`
- [X] T008 [P] Add contract tests for backward-graph endpoint in `tests/e2e/test_inference_widgets.py` — verify response has `nodes`, `edges`, `metadata`; verify `.grad` is populated (non-zero) after backward pass; verify node count ≤ 400
- [X] T009 [P] Add contract tests for loss-breakdown endpoint in `tests/e2e/test_inference_widgets.py` — verify per-token losses are positive; verify `len(losses) == len(tokens) - 1`; verify `random_baseline` matches `-log(1/vocab_size)`; verify `average_loss` == mean of per-token losses
- [X] T010 [P] Add contract tests for model-params endpoint in `tests/e2e/test_inference_widgets.py` — verify response has `groups` array; verify sum of `num_params` across groups == `total_params`; verify all 4 categories present (embedding, attention, mlp, output)

**Checkpoint**: Backend endpoints functional and tested. User story implementation can begin in parallel.

---

## Phase 3: User Story 1 — Interactive Backpropagation Lesson (Priority: P1) 🎯 MVP

**Goal**: A learner can navigate to `/v1/learn/autograd`, scroll through 5 steps, and see a real computation graph showing `.data`, `.grad`, and `_local_grads` for each Value node after a backward pass.

**Independent Test**: Navigate to `/v1/learn/autograd`, type text in the widget, see computation graph rendered on canvas with node values and gradient annotations. No training required — uses demo model.

### Implementation for User Story 1

- [X] T011 Create `AutogradWidget` in `microgpt/api/static/js/widgets/autograd.js` — canvas-based computation graph renderer. Constructor takes container. `_fetch(text)` calls `POST /v1/inference/backward-graph`. `_renderOutput(data)` renders nodes as rounded rectangles with `.data` value, `.grad` gradient, and operation type label. Color-coded by op type (input=green, add=blue, mul=orange, pow=purple, log=amber, exp=red, relu=cyan). Edges drawn as arrows from parent to child with `_local_grads` annotated inline.
- [X] T012 Create Autograd widget HTML partial in `microgpt/api/templates/partials/concept-widgets/autograd.html` — canvas element with text input and hint text
- [X] T013 [P] Register `AutogradWidget` in WIDGET_CLASSES and add script tag in `microgpt/api/templates/archetypes/concept.html`
- [X] T014 Define `AUTOGRAD_STEPS` (5 steps) in `microgpt/api/v1/router.py`:
  - Step 1: "What is Autograd?" — Value class wraps scalars, tracks operations
  - Step 2: "Building the Graph" — every operation (add, mul, etc.) creates child Value nodes
  - Step 3: "Topological Sort" — ordering nodes for backward pass
  - Step 4: "Chain Rule" — gradients flow backward, multiplying local gradients
  - Step 5: "Gradient Accumulation" — branching paths sum at shared nodes
- [X] T015 Add route handler `GET /v1/learn/autograd` and entry to `LEARNING_ARC` in `microgpt/api/v1/router.py`
- [X] T016 Add Autograd widget CSS to `microgpt/api/static/css/components.css` — `.autograph-canvas` sizing, `.autograd-legend` for op type colors, `.grad-value` styling

**Checkpoint**: US1 complete — autograd lesson renders live computation graphs with gradient information. Demo model provides data without training.

---

## Phase 4: User Story 2 — Progressive Code Walkthrough (Priority: P1)

**Goal**: A learner can run `python examples/train1.py`, `train3.py`, and `train4.py` and see each build one additional concept — MLP + manual gradients, single-head attention, multi-head GPT.

**Independent Test**: Run `python examples/train1.py` → trains a 2-layer MLP with manually computed gradients, prints decreasing loss. Run `train3.py` → trains single-head attention, prints decreasing loss. Run `train4.py` → trains multi-head GPT, prints decreasing loss. All use only Python stdlib.

### Implementation for User Story 2

- [X] T017 Implement `examples/train1.py` — 2-layer MLP (input → hidden with ReLU → output). Define manual numerical gradients (finite differences) and analytic gradients (chain rule by hand). Verify they match within tolerance. Train with SGD. Print loss per step. Stdlib only.
- [X] T018 Implement `examples/train3.py` — Single-head causal self-attention with learned position embeddings, RMSNorm, residual connections, single transformer block. Train with SGD. Print loss per step. Reuse `linear()`, `softmax()`, `rmsnorm()` from `microgpt/core/engine.py`. Stdlib only.
- [X] T019 Implement `examples/train4.py` — Multi-head GPT (n_head divisible into n_embd) with learned embeddings, RMSNorm, multi-head attention, residual MLP, single transformer layer. Train with SGD. Print loss per step. Reuse `GPT.forward()` from `microgpt/core/engine.py`. Stdlib only.
- [X] T020 [P] Add unit tests for progressive scripts in `tests/unit/core/test_examples.py` — verify train1: loss decreases, numerical gradients match analytic gradients within 1e-4 tolerance; verify train3: loss decreases, output shape correct; verify train4: loss decreases, param count consistent with `GPT.num_params()`

**Checkpoint**: US2 complete — all 6 training scripts (train0 through train5) are now working, fulfilling Constitution Article II.

---

## Phase 5: User Story 3 — Cross-Entropy Loss Deep-Dive (Priority: P1)

**Goal**: A learner can navigate to `/v1/learn/loss`, type text into a widget, and see per-token cross-entropy values with the random-guess baseline marked.

**Independent Test**: Navigate to `/v1/learn/loss`, type "emma", see 5 per-token loss bars (one for each predicted character), an average loss line, and a baseline indicator at `-log(1/27) ≈ 3.3`. No training required.

### Implementation for User Story 3

- [X] T021 Create `LossWidget` in `microgpt/api/static/js/widgets/loss.js` — bar chart rendering per-token loss as vertical bars. Highlights tokens with high loss (red) vs low loss (green). Shows average loss as dashed horizontal line. Shows random-guess baseline as dotted line with annotation. `_fetch(text)` calls `POST /v1/inference/loss-breakdown`.
- [X] T022 Create Loss widget HTML partial in `microgpt/api/templates/partials/concept-widgets/loss.html` — text input + canvas for bar chart + statistics display
- [X] T023 [P] Register `LossWidget` in WIDGET_CLASSES and add script tag in `microgpt/api/templates/archetypes/concept.html`
- [X] T024 Define `LOSS_STEPS` (5 steps) in `microgpt/api/v1/router.py`:
  - Step 1: "What is Loss?" — measuring prediction error
  - Step 2: "Cross-Entropy" — `-log(p(target))` formula
  - Step 3: "Softmax Connection" — logits → probabilities sum to 1
  - Step 4: "Reading the Curve" — smooth decline = stable learning, plateaus = need more capacity, oscillations = LR too high
  - Step 5: "The Baseline" — why `-log(1/27) ≈ 3.3` is random guessing
- [X] T025 Add route handler `GET /v1/learn/loss` and entry to `LEARNING_ARC` in `microgpt/api/v1/router.py`
- [X] T026 Add Loss widget CSS to `microgpt/api/static/css/components.css` — `.loss-bar` colors, `.baseline-line` styling

**Checkpoint**: US3 complete — loss lesson explains the primary training feedback signal with interactive per-token visualization.

---

## Phase 6: User Story 4 — Model Parameter Anatomy (Priority: P2)

**Goal**: A learner can navigate to `/v1/learn/parameters` and see a visual breakdown of all 4,192 parameters organized by matrix group, with interactive sliders for `n_embd` and `n_layer`.

**Independent Test**: Navigate to `/v1/learn/parameters`, see treemap or stacked bar of wte/wpe/attention/mlp/lm_head groups with counts and percentages. Change `n_embd` from 16 to 32 and observe total params increase. No training required.

### Implementation for User Story 4

- [X] T027 Create `ParamsWidget` in `microgpt/api/static/js/widgets/params.js` — renders parameter breakdown as stacked horizontal bar or treemap. Color-coded by category (embedding=blue, attention=cyan, mlp=orange, output=purple). Shows shape, count, percentage per group. Includes `n_embd` and `n_layer` sliders that call `GET /v1/inference/model-params` with updated values and re-render.
- [X] T028 Create Params widget HTML partial in `microgpt/api/templates/partials/concept-widgets/params.html` — canvas for visualization + slider controls + stats table
- [X] T029 [P] Register `ParamsWidget` in WIDGET_CLASSES and add script tag in `microgpt/api/templates/archetypes/concept.html`
- [X] T030 Define `PARAMS_STEPS` (5 steps) in `microgpt/api/v1/router.py`:
  - Step 1: "Where Parameters Live" — overview of state_dict structure
  - Step 2: "Token Embeddings (WTE)" — one vector per token in vocabulary
  - Step 3: "Position Embeddings (WPE)" — one vector per position in context
  - Step 4: "Attention Weights" — Q/K/V/O projections per layer
  - Step 5: "MLP & Output" — fc1/fc2 transformations + lm_head projection
- [X] T031 Add route handler `GET /v1/learn/parameters` and entry to `LEARNING_ARC` in `microgpt/api/v1/router.py`
- [X] T032 Add Params widget CSS to `microgpt/api/static/css/components.css`

**Checkpoint**: US4 complete — parameter anatomy visualizes where 4,192 params live and how architecture choices affect model capacity.

---

## Phase 7: User Story 5 — Adam Optimizer Interactive Lesson (Priority: P2)

**Goal**: A learner can see per-parameter momentum (m) and adaptive learning rate (v) evolving during training, captured from real training runs.

**Independent Test**: Start a training run from the training dashboard. The Adam lesson SSE stream receives `optimizer_state` events with m/v/grad per parameter. After training, navigate to Adam lesson and see m/v curves.

### Implementation for User Story 5

- [X] T033 Add `optimizer_state_callback` parameter to `train()` in `microgpt/core/engine.py` — called after Adam update, passes `(step, m, v, grads)` arrays. Optional parameter, defaults to None. Captures optimizer state at configurable interval (default: every 10 steps).
- [X] T034 Extend `TrainingService` in `microgpt/services/training.py` — wire `optimizer_state_callback` to emit new `optimizer_state` SSE event type with `{"step": N, "params": [{"index": i, "m": m[i], "v": v[i], "grad": p.grad}]}` payload. Only for CPU training path; no optimizer state events for GPU path.
- [X] T035 Create `AdamWidget` in `microgpt/api/static/js/widgets/adam.js` — dual line chart showing m (momentum) and v (adaptive LR) curves over training steps for a selected parameter. Includes beta1/beta2 sliders that show how momentum and adaptive LR response curves change. Shows LR decay annotation `lr_t = lr * (1 - step/num_steps)`. Listens for `optimizer_state` SSE events when training is active, or loads from stored experiment data.
- [X] T036 Create Adam widget HTML partial in `microgpt/api/templates/partials/concept-widgets/adam.html` — canvas for dual chart + beta1/beta2 sliders + parameter selector dropdown
- [X] T037 [P] Register `AdamWidget` in WIDGET_CLASSES and add script tag in `microgpt/api/templates/archetypes/concept.html`
- [X] T038 Define `ADAM_STEPS` (5 steps) in `microgpt/api/v1/router.py`:
  - Step 1: "What is Adam?" — why plain SGD is slow
  - Step 2: "Momentum (m)" — rolling average of gradients
  - Step 3: "Adaptive LR (v)" — per-parameter learning rate scaling
  - Step 4: "Bias Correction" — m_hat and v_hat warmup
  - Step 5: "LR Decay" — linear schedule `lr_t = lr * (1 - step/num_steps)`
- [X] T039 Add route handler `GET /v1/learn/adam` and entry to `LEARNING_ARC` in `microgpt/api/v1/router.py`
- [X] T040 Add Adam widget CSS to `microgpt/api/static/css/components.css`

**Checkpoint**: US5 complete — Adam optimizer internals visualized from real training data with interactive parameter controls.

---

## Phase 8: User Story 6 — FAQ & Reference Section (Priority: P2)

**Goal**: A learner can navigate to `/v1/learn/faq` and find answers to common questions about model understanding, hallucinations, relation to ChatGPT, training speed, dataset customization, and production scaling.

**Independent Test**: Navigate to `/v1/learn/faq`, see 7 questions with expandable answers. No model, API, or training required — pure static content.

### Implementation for User Story 6

- [X] T041 Create FAQ page template in `microgpt/api/templates/archetypes/faq.html` — extends base.html. Accordion-style layout with question headers and expandable answer sections. Styled consistently with existing panels.
- [X] T042 Add route handler `GET /v1/learn/faq` and entry to `LEARNING_ARC` in `microgpt/api/v1/router.py`
- [X] T043 Add FAQ CSS to `microgpt/api/static/css/archetypes.css` — `.faq-item`, `.faq-question`, `.faq-answer`, `.faq-answer--open` accordion styles

**Checkpoint**: US6 complete — FAQ addresses 7 common questions, making the learning platform self-contained.

---

## Phase 9: User Story 7 — Residual Connections & RMSNorm (Priority: P2)

**Goal**: The existing attention lesson is enriched with 2 additional steps explaining residual connections (the "add-back" pattern) and RMSNorm (input values → RMS computation → scale factor → normalized output).

**Independent Test**: Navigate to `/v1/learn/attention`, scroll past the 5 existing steps to find 2 new steps explaining residuals and RMSNorm. Visualizations show the residual stream and normalization computation.

### Implementation for User Story 7

- [X] T044 Extend `ATTENTION_STEPS` array in `microgpt/api/v1/router.py` — add 2 new steps after existing step 5:
  - Step 6: "Residual Connections" — the `x = [a + b for a, b in zip(x, x_residual)]` pattern; visualization showing gradient highway; why this makes deep networks trainable
  - Step 7: "RMSNorm" — input vector values, `ms = sum(xi*xi)/len(x)`, `scale = (ms+1e-5)^-0.5`, normalized output; contrast with LayerNorm
- [X] T045 [P] Update the attention widget in `microgpt/api/static/js/widgets/attention.js` — add optional rendering mode for residual stream visualization when step key matches "residual". Uses existing per-token embedding data from the attention endpoint (`POST /v1/inference/attention`) to illustrate the `x = [a + b for a, b in zip(x, x_residual)]` pattern. RMSNorm step uses a schematic diagram showing: input vector → RMS computation (`sqrt(mean(x²))`) → scale factor → normalized output. No new backend data needed.

**Checkpoint**: US7 complete — attention lesson now covers all key transformer components: tokens → embeddings → causal attention → multi-head → residuals → RMSNorm.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Tests, documentation, and quality verification across all stories

### Tests

- [X] T046 [P] Add end-to-end test for all lesson page routes in `tests/e2e/test_lesson_routes.py` — verify `GET /v1/learn/autograd`, `/v1/learn/loss`, `/v1/learn/parameters`, `/v1/learn/adam`, `/v1/learn/faq` all return 200 with valid HTML
- [X] T047 [P] Add optimizer state capture test in `tests/unit/core/test_engine.py` — verify `train()` with `optimizer_state_callback` parameter calls the callback with correct per-step m/v/grad arrays; verify `len(m) == len(v) == len(model.params)`
- [X] T053 [P] Add demo model fallback test for FR-019 in `tests/e2e/test_inference_widgets.py` — verify backward-graph, loss-breakdown, and model-params endpoints return valid responses when called without `model_id` (i.e., use demo model fallback). Verify response contains `model.is_demo == true`.
- [X] T054 [P] Add OOV character handling test for FR-020 in `tests/e2e/test_inference_widgets.py` — verify backward-graph, loss-breakdown, and attention endpoints return HTTP 400 with descriptive error message when input contains a character not in the model's vocabulary (e.g., "hello ☺ world"). Verify error message includes the invalid character.
- [X] T055 [P] Add widget JS smoke tests — verify each new widget JS file (autograd.js, loss.js, params.js, adam.js) can be loaded in a browser context without errors. Navigate to each lesson page with Playwright or in a headless browser via pytest, capture console errors. File: `tests/e2e/test_widget_smoke.py`. Note: this is a minimal smoke test; full widget unit tests would require a JS test framework.

### Documentation & Quality

- [X] T048 Enrich vault documentation in `docs/vault/` — add session log for this feature to `docs/vault/Sessions/2026-06-13-learning-content-enrichment.md`; add ADR for computation graph visualization approach if none exists
- [X] T049 [P] Run `make lint` and `make typecheck` — fix any new issues introduced
- [X] T050 [P] Run `make test` — verify all tests pass (existing + new)
- [X] T051 [P] Run `make format` — auto-format all changed files
- [X] T052 Update `microgpt/api/v1/router.py` LEARNING_ARC ordering — ensure new lessons appear in logical pedagogical order: Tokenization → Embeddings → Parameters → Autograd → Attention → Loss → Sampling → Adam → Training Loop → FAQ

**Checkpoint**: All 7 user stories complete. Full test suite passes. Lint + typecheck clean. Vault enriched.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup. BLOCKS US1, US3, US4, US5 (which need backend endpoints)
- **US1 (Phase 3)**: Depends on Foundational (needs `backward_graph()` endpoint)
- **US2 (Phase 4)**: No backend dependencies — can run in parallel with Phase 2 (standalone Python scripts)
- **US3 (Phase 5)**: Depends on Foundational (needs `loss_breakdown()` endpoint)
- **US4 (Phase 6)**: Depends on Foundational (needs `model_params()` endpoint)
- **US5 (Phase 7)**: Depends on Foundational + T033 (needs `optimizer_state_callback` in engine.py)
- **US6 (Phase 8)**: No backend dependencies — can run in parallel with any phase (static content)
- **US7 (Phase 9)**: Depends on Foundational (uses existing attention endpoint, just new lesson steps)
- **Polish (Phase 10)**: Depends on all user stories complete

### User Story Dependencies

- **US1 (P1)**: Depends on Foundational Phase 2 (T004, T007)
- **US2 (P1)**: NO dependencies on other phases — independent Python scripts
- **US3 (P1)**: Depends on Foundational Phase 2 (T005, T007)
- **US4 (P2)**: Depends on Foundational Phase 2 (T006, T007)
- **US5 (P2)**: Depends on Foundational Phase 2 (T033, T034)
- **US6 (P2)**: NO dependencies — static content
- **US7 (P2)**: NO backend dependencies — just router.py changes

### Parallel Opportunities

- US2 (progressive scripts) and US6 (FAQ) can run entirely in parallel with Foundational phase and all other stories — zero backend dependencies
- US1, US3, US4 backend endpoints (T004, T005, T006) are marked [P] — can run in parallel during Phase 2
- Tests within a phase marked [P] can run in parallel
- US7 can start as soon as Phase 2's T007 (route setup) is done

---

## Parallel Example: Phase 2 Foundational (Backend Endpoints)

```bash
# Launch all 3 service methods in parallel (different methods, same file)
Task: "Add backward_graph() to microgpt/services/inference.py"
Task: "Add loss_breakdown() to microgpt/services/inference.py"
Task: "Add model_params() to microgpt/services/inference.py"

# Then add routes (depends on service methods existing)
Task: "Add routes in microgpt/api/v1/inference.py"

# Then launch all contract tests in parallel
Task: "Contract tests for backward-graph in tests/e2e/test_inference_widgets.py"
Task: "Contract tests for loss-breakdown in tests/e2e/test_inference_widgets.py"
Task: "Contract tests for model-params in tests/e2e/test_inference_widgets.py"
```

## Parallel Example: Zero-Dependency Stories

```bash
# US2 (progressive scripts) and US6 (FAQ) have NO backend dependencies
# Run these immediately, even during Foundational phase:
Task: "Implement train1.py in examples/train1.py"
Task: "Implement train3.py in examples/train3.py"
Task: "Implement train4.py in examples/train4.py"
Task: "Create FAQ page in microgpt/api/templates/archetypes/faq.html"
```

## Parallel Example: Widget + Lesson Registration (per story)

```bash
# For each US, widget JS, widget HTML, CSS, and router changes are independent:
Task: "Create AutogradWidget in microgpt/api/static/js/widgets/autograd.js"
Task: "Create autograd.html widget partial"
Task: "Register in concept.html WIDGET_CLASSES"
Task: "Define AUTOGRAD_STEPS + route + LEARNING_ARC in router.py"
```

---

## Implementation Strategy

### MVP First (US1 + US3 — P1 Backend + Lessons)

1. Complete Phase 1: Setup — review design, verify baseline
2. Complete Phase 2: Foundational — all 3 backend endpoints
3. Complete Phase 3: US1 — Autograd lesson (uses backward_graph)
4. Complete Phase 5: US3 — Loss lesson (uses loss_breakdown)
5. **STOP and VALIDATE**: Test both lessons independently
6. Complete US2 (progressive scripts) — zero backend deps, can even start during Phase 1

### Incremental Delivery

1. **Phase 1-2** → Backend foundation ready (3 endpoints, 3 contracts)
2. **US1** → Autograd backprop lesson → Deploy/Demo (P1 MVP!)
3. **US3** → Loss lesson → Deploy/Demo (P1 complete!)
4. **US2** → Progressive code walkthrough → Deploy/Demo (Constitution compliance!)
5. **US4** → Parameter anatomy → Deploy/Demo
6. **US5** → Adam optimizer → Deploy/Demo
7. **US6 + US7** → FAQ + residual enrichments → Deploy/Demo (all stories complete!)
8. **Phase 10** → Polish, tests, vault → Feature complete

### Total Task Count

| Phase | Tasks | [P] Parallel | Story |
|-------|-------|-------------|-------|
| 1 — Setup | 3 | 2 | — |
| 2 — Foundational | 7 | 4 | — |
| 3 — US1 (Autograd) | 6 | 1 | [US1] |
| 4 — US2 (Code) | 4 | 1 | [US2] |
| 5 — US3 (Loss) | 6 | 1 | [US3] |
| 6 — US4 (Params) | 6 | 1 | [US4] |
| 7 — US5 (Adam) | 8 | 1 | [US5] |
| 8 — US6 (FAQ) | 3 | 0 | [US6] |
| 9 — US7 (Residuals) | 2 | 1 | [US7] |
| 10 — Polish | 10 | 5 | — |
| **Total** | **55** | **17** | **7 stories** |

## Notes

- [P] tasks = different files, no dependencies — safe to run in parallel
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Tests in Phase 2 must fail before implementation (TDD)
- US2 and US6 have zero backend dependencies — can start immediately
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently