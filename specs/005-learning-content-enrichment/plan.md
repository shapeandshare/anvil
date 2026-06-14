# Implementation Plan: Learning Content Enrichment

**Branch**: `005-learning-content-enrichment` | **Date**: 2026-06-13 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification for 7 new learning features: autograd backprop visualization, progressive code stubs (train1/train3/train4), cross-entropy loss deep-dive, model parameter anatomy, Adam optimizer interactive lesson, FAQ section, residual connections & RMSNorm explanations

## Summary

Enrich the microgpt-workbench learning arc from 5 lessons to 9+ by adding interactive scroll-driven lessons with live computation graph visualization (autograd), per-token loss breakdown, parameter anatomy explorer, real logged optimizer state visualization, and progressive training scripts. Fill 3 empty stubs in the 6-stage curriculum (Constitution Article II compliance). Add a static FAQ and enrich existing attention lessons with RMSNorm/residual explanations. All widgets use the existing demo model for data — no training required to explore.

## Technical Context

**Language/Version**: Python 3.11+ (backend), JavaScript ES6+ (frontend widgets)
**Primary Dependencies**: FastAPI, Jinja2, aiofiles (all existing); no new pip dependencies
**Storage**: Demo model at `data/models/demo/model.json` (existing); optimizer state captured in-memory during training runs
**Testing**: pytest (existing) + coverage for new backend endpoints
**Target Platform**: macOS ARM (Apple Silicon) primary, Linux secondary
**Project Type**: Python web application (FastAPI + Jinja2 templates + educational JS widgets)
**Performance Goals**: All lesson widgets respond to user input within 1 second (existing demo model); computation graph capped at 400 nodes (existing limit)
**Constraints**: Core engine (`microgpt/core/`) must remain stdlib-only; progressive scripts (train1/train3/train4) must be independently runnable with zero pip dependencies; all lesson widgets fall back to demo model when no trained model exists
**Scale/Scope**: 7 new learning features across P1 (3) and P2 (4); 3 backend endpoint additions; 3 code stubs to implement; ~300 lines total backend delta

**NEEDS CLARIFICATION**: None. All design decisions are covered by the spec, constitution, and research.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Check | Notes |
|---------|-------|-------|
| **I — Zero-Dependency Core** | ✅ PASS | train1/train3/train4 scripts use only stdlib. Core engine unchanged. No new pip deps. |
| **II — Educational Clarity** | ✅ PASS | This feature IS the fulfillment of Article II. train1/train3/train4 stubs are being implemented. All new code includes WHY comments. |
| **III — Seeded Reproducibility** | ✅ PASS | Progressive scripts use `random.seed(42)` (existing pattern). |
| **IV — TDD Mandatory** | ⚠️ CONDITIONAL | Tests required for new backend endpoints (loss-breakdown, model-params, optimizer-state). Progressive scripts need test coverage. FAILS if tests are skipped. |
| **V — Async-First** | ✅ PASS | New endpoints follow existing async pattern. Core engine remains sync. |
| **VI — Implicit Namespace** | ✅ PASS | No new packages created. No `__init__.py` changes needed. |
| **VII — Layered Architecture** | ✅ PASS | New service methods on existing InferenceService. No DB primitives leak. |
| **VIII — Whimsy Without Compromise** | ✅ PASS | Widget visualizations can include decorative elements. FAQ uses existing theme. |
| **IX — Pit of Success** | ✅ PASS | Demo model fallback ensures all widgets work without training. |

**Gate Result**: CONDITIONAL PASS — TDD requirement noted. Must write tests for new backend endpoints.

## Project Structure

### Documentation (this feature)

```text
specs/005-learning-content-enrichment/
├── plan.md                        # This file
├── spec.md                        # Feature specification
├── research.md                    # Phase 0: Research findings
├── data-model.md                  # Phase 1: Data model
├── quickstart.md                  # Phase 1: Implementation quickstart
├── checklists/
│   └── requirements.md            # Quality checklist
├── contracts/                     # API contracts
│   ├── autograd-graph.md          # Computation graph contract
│   ├── loss-breakdown.md          # Loss endpoint contract
│   ├── model-params.md            # Parameter anatomy contract
│   └── optimizer-state.md         # Optimizer state contract
└── tasks.md                       # Phase 2: Task breakdown (created by /speckit.tasks)
```

### Source Code (changes by module)

```text
# New / Modified files
microgpt/
├── core/
│   └── engine.py                          # [MODIFY] Add forward_with_optimizer() for optimizer state capture
├── services/
│   └── inference.py                       # [MODIFY] Add loss_breakdown(), model_params(), backward_graph() methods
├── api/
│   ├── v1/
│   │   ├── router.py                      # [MODIFY] Add LEARNING_ARC entries, lesson routes, step definitions
│   │   └── inference.py                   # [MODIFY] Add new inference endpoints
│   ├── templates/
│   │   ├── archetypes/
│   │   │   └── concept.html               # [MODIFY] Add WIDGET_CLASSES entries + script tags
│   │   └── partials/
│   │       └── concept-widgets/           # [NEW] Widget HTML partials
│   │           ├── autograd.html
│   │           ├── loss.html
│   │           ├── params.html
│   │           └── adam.html
│   └── static/
│       ├── js/
│       │   └── widgets/                   # [NEW] Widget JS implementations
│       │       ├── autograd.js
│       │       ├── loss.js
│       │       ├── params.js
│       │       └── adam.js
│       └── css/
│           ├── components.css             # [MODIFY] Add widget-specific CSS
│           └── archetypes.css             # [MODIFY] Add FAQ page layout

examples/
├── train1.py                              # [REWRITE] MLP + manual gradients + SGD
├── train3.py                              # [REWRITE] Single-head attention
└── train4.py                              # [REWRITE] Multi-head GPT

tests/
├── unit/
│   └── core/
│       └── test_examples.py               # [NEW] Tests for progressive scripts
└── e2e/
    └── test_inference_widgets.py           # [NEW] Tests for new inference endpoints
```

**Structure Decision**: The project uses a single-package layout (`microgpt/`). New learning features add files within existing directories (services/inference.py, api/v1/, templates/, static/js/widgets/). No new packages or modules at the top level.

## Complexity Tracking

No Constitution violations. All gate conditions pass (conditional on TDD).

---

## Phase 0: Research (Complete)

Research completed via 3 parallel background agents. Full findings in [research.md](research.md).

### Key Findings

| Topic | Decision | Rationale |
|-------|----------|-----------|
| Computation graph format | Extend existing `forward_graph()` to include `.grad` and `_local_grads` | Minimal delta (~8 lines); existing graph traversal code handles node/edge building |
| Backward pass trigger | New `backward_graph()` endpoint that runs forward → computes loss → calls `backward()` → traverses graph | `.grad` is 0 without backward pass; separate endpoint prevents breaking existing forward-only use |
| Optimizer state capture | Modify `train()` to return m/v buffers; add new SSE event type `optimizer_state` in `progress_callback` | Chosen by user (Option B); real logged data is more authentic than synthetic |
| Widget framework | Follow existing pattern: constructor takes container, `_render()` builds HTML, `_fetch()` calls API | 5 existing widgets prove this pattern works; reuses WIDGET_CLASSES registry, scroll-scene lifecycle |
| Lesson registration | Add to `LEARNING_ARC` in router.py + step arrays + route handlers | Follows existing pattern for 5 current lessons |
| Demo model fallback | All widgets call `load_model(None)` which returns demo model | Existing pattern ensures widgets work without training |
| Progressive scripts | Reuse helpers from `engine.py` (linear, softmax, rmsnorm) but implement unique logic per stage | Constitution Article II: each script adds one concept without hiding earlier ones; calling shared helpers is acceptable for the boilerplate (data loading, printing) |

## Phase 1: Design & Contracts

### Data Model

Full data model at [data-model.md](data-model.md). Key entities:

- **ComputationGraph**: nodes (Value data, grad, local_grads, op type) + edges (parent→child) + global stats (total nodes, max depth)
- **LossBreakdown**: per-token cross-entropy values + token labels + running average + random-guess baseline
- **ParameterBreakdown**: named matrix groups (wte, wpe, lm_head, attention, MLP) with shape, param count, percentage
- **OptimizerSnapshot**: per-parameter momentum (m) + adaptive LR (v) + gradient (grad) at a given training step

### API Contracts

Full contracts at [contracts/](contracts/). Four new endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `POST /v1/inference/backward-graph` | POST | Returns computation graph with `.grad` and `_local_grads` after running forward + backward on a prompt |
| `POST /v1/inference/loss-breakdown` | POST | Returns per-token cross-entropy loss for input text |
| `GET /v1/inference/model-params` | GET | Returns named parameter breakdown with shapes and counts |
| `SSE event: optimizer_state` | (in training stream) | Returns per-parameter m/v values at each training step |

### Quickstart

See [quickstart.md](quickstart.md) for day-1 implementation plan with exact file paths, estimated line counts, and execution order.

---

## Phase 2: Tasks (deferred to `/speckit.tasks`)

Command ends after Phase 2 planning. Ready for task generation.