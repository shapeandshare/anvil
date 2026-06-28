---
title: Implementation Plan — Learning Fine-Tuning Concepts
type: plan
tags:
  - type/spec
created: '2026-06-28'
updated: '2026-06-28'
---
# Implementation Plan: Learning Arc — Fine-Tuning Concepts

**Branch**: `048-learning-fine-tuning-concepts` | **Date**: 2026-06-28 | **Spec**: [[048 Learning Fine-Tuning Concepts - spec]]
**Input**: Feature specification from `docs/vault/Specs/048 Learning Fine-Tuning Concepts/048 Learning Fine-Tuning Concepts - spec.md`

## Summary

Add three explorable learning pages about fine-tuning concepts as the next rung of anvil's learning ladder. Pages are individual entries in `LEARNING_ARC` (after "Model Export"), following the existing step-based carousel pattern in `anvil/api/v1/learning.py`. Includes a new interactive widget (`lora.js`) for the LoRA low-rank intuition page. The fine-tune vs prompt vs RAG page presents trade-offs in a comparison table. Unshipped capability links use "Coming soon" badges.

## Technical Context

**Language/Version**: Python 3.11+ (existing repo convention)  
**Primary Dependencies**: FastAPI, Jinja2, existing widget JS framework — no new dependencies  
**Storage**: N/A — static content pages  
**Testing**: pytest (existing); SC-004 NMRG — pre-existing tests pass unmodified  
**Target Platform**: Web (FastAPI + Jinja2, served via Uvicorn)  
**Project Type**: Web application — content-only feature  
**Performance Goals**: N/A — static content  
**Constraints**: Must follow existing learning content pattern in `anvil/api/v1/learning.py` (step arrays, `_arc_context` navigation, `concept.html` template); new widget JS must integrate with existing `widget-base.js` framework  
**Scale/Scope**: 3 concept pages, 1 new widget JS file (`anvil/api/static/js/widgets/lora.js`)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Applicable Articles**:

| Article | Applies | Reasoning |
|---------|---------|-----------|
| I — Zero-Dependency Core | No | Content-only; no changes to `anvil/core/` |
| II — Educational Clarity | Yes | Learning content must prioritize readability and educational value |
| IV — TDD Mandatory | Yes | Tests must exist; SC-004 (NMRG) ensures pre-existing tests pass |
| V — Async-First | No | Content pages are synchronous template renders |
| VI — `__init__.py` Policy | No | No new Python packages |
| VII — Layered Architecture | No | Content lives in route layer; no service/repo changes |
| VIII — iOS-Grade Polish | Yes | UI must match existing explorable-explanation style with same polish |
| IX — Pit of Success | No | No optional capabilities involved |
| X — Domain-Driven Decomposition | No | No new package boundaries |
| XI — Simplicity First | Yes | Must choose simplest approach; no speculative widgets or abstractions |

**Simplicity First gate (Article XI — hard MUST)**: Confirm this plan favors the simplest, most boring solution that meets the requirement:

- [x] **Simplest viable** (§11.1) — following existing `*_STEPS` + `concept.html` pattern is the simplest approach; no new templates or service layers needed
- [x] **Boring over novel** (§11.2) — reusing existing widget framework (widget-base.js) with a new widget class; no novel dependencies
- [x] **YAGNI** (§11.3) — only the 3 pages and 1 widget specified; no speculative content or future interactivity
- [x] **Reuse first** (§11.4) — reusing `concept.html`, `_arc_context()`, `LEARNING_ARC` pattern, and widget registration system
- [x] **Testable** (§11.6) — pages are verifiable via e2e HTTP tests; widget behavior is verifiable via browser tests

**Complexity Tracking**: No deviations from simplest viable solution — all patterns are existing.

## Project Structure

### Documentation (this feature)

```text
docs/vault/Specs/048 Learning Fine-Tuning Concepts/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (N/A - no contracts)
├── 048 Learning Fine-Tuning Concepts.md  # Spec overview
└── 048 Learning Fine-Tuning Concepts - spec.md  # Feature spec (with clarifications)
```

### Source Code (repository root)

```text
anvil/
├── api/
│   ├── v1/
│   │   └── learning.py                 # Add: FINE_TUNING_STEPS, LEARNING_ARC entries, routes
│   └── static/
│       └── js/
│           └── widgets/
│               └── lora.js             # NEW: LoRA low-rank intuition widget
│   └── templates/
│       └── archetypes/
│           └── concept.html            # Add lora.js to widget script includes & WIDGET_CLASSES
```

**Structure Decision**: Single-project structure — all changes within existing files in `anvil/api/`. No new Python modules, packages, or services.

## Phase 0: Research

Research goals (all resolved via spec clarification — no NEEDS CLARIFICATION items):

1. **Insertion point**: After "Model Export" in `LEARNING_ARC`, as individual entries — **RESOLVED** (FR-024b)
2. **Widget scope**: Full interactive widget for LoRA page — **RESOLVED** (FR-024c)
3. **Forward links**: "Coming soon" badges for unshipped capabilities — **RESOLVED** (Edge Cases)
4. **Decision page format**: Comparison table — **RESOLVED** (SC-003)
5. **Page ordering**: (1) What fine-tuning is, (2) Warm-start vs PEFT/LoRA, (3) Fine-tune vs prompt vs RAG — **RESOLVED**

<research-required>
### Research Tasks

The following require codebase exploration to resolve for precise implementation steps:

1. **Widget pattern analysis**: Understand widget-base.js API, existing widget implementations, registration pattern
2. **LEARNING_ARC insertion geometry**: Find exact `LEARNING_ARC` entries around "Model Export" key and positions
3. **Route handler pattern**: Confirm exact handler signature and template context structure
</research-required>

## Complexity Tracking

> **No violations** — all chosen approaches are the simplest viable solution (existing patterns reused throughout).

---

## Phase 0 & Phase 1 Completion

**Phase 0 — Research**: Complete. See `research.md` for full decision log.

| Unknown | Status | Decision |
|---------|--------|----------|
| Widget system pattern | Resolved | Follow existing constructor + prototype from widget-base.js |
| LoRA widget type | Resolved | Slider-based rank visualization, no backend API needed |
| Page content structure | Resolved | 3 pages: 5/6/5 steps respectively; LoRA widget on page 2 |
| Navigation integration | Resolved | Insert after "export" in LEARNING_ARC, individual entries |
| "Coming soon" links | Resolved | Inline badge, no dead links |

**Phase 1 — Design**: Complete.

| Artifact | Path |
|----------|------|
| Data model | `docs/vault/Specs/048 Learning Fine-Tuning Concepts/data-model.md` |
| Quickstart | `docs/vault/Specs/048 Learning Fine-Tuning Concepts/quickstart.md` |
| Agent context | Updated `AGENTS.md` via `update-agent-context.sh` |

**Contracts**: N/A — no new external interfaces (all changes are internal content).

### Constitution Check Re-Evaluation (Post-Design)

*Re-checked after Phase 1 design — all gates PASS.*

| Article | Status | Rationale |
|---------|--------|-----------|
| I — Zero-Dependency Core | ✅ PASS | No changes to `anvil/core/` |
| II — Educational Clarity | ✅ PASS | Learning content follows existing educational style |
| IV — TDD Mandatory | ✅ PASS | New e2e route tests (T008-T010) added per codebase convention; pre-existing tests unmodified (SC-004 NMRG) |
| V — Async-First | ✅ PASS | No new async code or data flow changes |
| VI — __init__.py Policy | ✅ PASS | No new Python packages |
| VII — Layered Architecture | ✅ PASS | Content in route layer only |
| VIII — iOS-Grade Polish | ✅ PASS | Uses existing concept.html with same polish level |
| IX — Pit of Success | ✅ PASS | No optional capabilities involved |
| X — DDD | ✅ PASS | No new package boundaries |
| XI — Simplicity First | ✅ PASS | All 6 sub-gates pass; Complexity Tracking shows zero deviations |
