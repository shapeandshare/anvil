---
title: Implementation Plan — Learning Architecture Differences
type: plan
tags:
  - type/spec
created: '2026-06-28'
updated: '2026-06-28'
---
# Implementation Plan: Learning Arc — Architecture Differences

**Branch**: `049-learning-architecture-differences` | **Date**: 2026-06-28 | **Spec**: [[049 Learning Architecture Differences - spec]]
**Input**: Feature specification from `docs/vault/Specs/049 Learning Architecture Differences/049 Learning Architecture Differences - spec.md`

## Summary

Add one explorable learning module on architecture differences as a single-page accordion-style page in anvil's learning arc. The module explains tokenization, attention variants, parameter scaling, and context length differences between anvil's char-level mini-Llama and larger architectures (TinyLlama-class and beyond), paired with the architecture allow-list rationale (FR-032). Cross-linked from the catalog eligibility flags (041) with anchor-ID targeting. Content-only — no new widgets, JS, or database changes.

## Technical Context

**Language/Version**: Python 3.11+ (existing repo convention)  
**Primary Dependencies**: FastAPI, Jinja2, existing widget JS framework — no new dependencies  
**Storage**: N/A — static content page  
**Testing**: pytest (existing); SC-005 NMRG — pre-existing tests pass unmodified  
**Target Platform**: Web (FastAPI + Jinja2, served via Uvicorn)  
**Project Type**: Web application — content-only feature  
**Performance Goals**: N/A — static content  
**Constraints**: 
- Must use accordion/single-page pattern (FR-025 UX), NOT carousel
- Must support anchor-ID targeting from 041 cross-links (FR-025a UX)
- Must follow existing learning content conventions in `anvil/api/v1/learning.py`  
- No new JavaScript widget files needed — content-only, prose + tables  
**Scale/Scope**: 1 accordion page, 1 new Jinja2 template, ~5 accordion sections

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Applicable Articles**:

| Article | Applies | Reasoning |
|---------|---------|-----------|
| I — Zero-Dependency Core | No | Content-only; no changes to `anvil/core/` |
| II — Educational Clarity | Yes | Learning content must prioritize readability and educational value |
| IV — TDD Mandatory | Yes | Tests must exist; SC-005 (NMRG) ensures pre-existing tests pass |
| V — Async-First | No | Content pages are synchronous template renders |
| VI — `__init__.py` Policy | No | No new Python packages |
| VII — Layered Architecture | No | Content lives in route layer; no service/repo changes |
| VIII — iOS-Grade Polish | Yes | UI must match existing polish with accordion sections |
| IX — Pit of Success | No | No optional capabilities involved |
| X — Domain-Driven Decomposition | No | No new package boundaries |
| XI — Simplicity First | Yes | Must choose simplest approach; reuse existing FAQ accordion pattern |

**Simplicity First gate (Article XI — hard MUST)**: Confirm this plan favors the simplest, most boring solution that meets the requirement:

- [x] **Simplest viable** (§11.1) — single accordion page reusing existing `.faq-item` / `.faq-question` / `.faq-answer` CSS and `toggleFaq()` JS; no new carousel, no interactive widgets
- [x] **Boring over novel** (§11.2) — no novel dependencies or frameworks; using existing Jinja2 + FAQ accordion pattern already proven in codebase
- [x] **YAGNI** (§11.3) — only 1 page with ~5 sections; no speculative content or future interactivity
- [x] **Reuse first** (§11.4) — reusing existing `LEARNING_ARC` navigation, `_arc_context()`, FAQ accordion CSS/JS, and `base.html` template
- [x] **Testable** (§11.6) — page is verifiable via e2e HTTP test; accordion behavior testable via Playwright

**Complexity Tracking**: No deviations from simplest viable solution — all patterns are reused from existing code.

## Project Structure

### Documentation (this feature)

```text
docs/vault/Specs/049 Learning Architecture Differences/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (N/A — no contracts)
├── 049 Learning Architecture Differences.md  # Spec overview
└── 049 Learning Architecture Differences - spec.md  # Feature spec (with clarifications)
```

### Source Code (repository root)

```text
anvil/
├── api/
│   ├── v1/
│   │   └── learning.py                 # Add: ARCHITECTURE_DIFFERENCES_STEPS, LEARNING_ARC entry, route
│   ├── templates/
│   │   └── archetypes/
│   │       └── architecture-differences.html  # NEW: accordion template
│   └── static/
│       └── css/
│           └── components.css           # Add: .arch-diff-* section styles (optional - may reuse existing)
└── tests/
    └── e2e/
        └── api/
            └── test_pages.py            # Add: e2e test for /v1/learn/architecture-differences
```

**Structure Decision**: Single-project structure — all changes within or alongside existing files. No new Python modules, packages, or services.

## Phase 0: Research

Research goals (all resolved via codebase exploration — no NEEDS CLARIFICATION items):

1. **Accordion template pattern**: Use existing `.faq-item` / `.faq-question` / `.faq-answer` CSS pattern from `components.css` + `toggleFaq()` JS from `faq-common.html` → **RESOLVED**
2. **LEARNING_ARC insertion point**: Insert after existing 048 entries (after `"finetune-vs-prompt-vs-rag"`), before `"chunking"` → **RESOLVED**
3. **Anchor ID support**: Accordion sections use `id` attributes matching step keys; JS opens section on page load when URL hash matches → **RESOLVED**
4. **Cross-link target from 041**: Link anchors to the allow-list section key (e.g., `#allow-list`) → **RESOLVED** (from clarification Q2)
5. **Content structure**: 5 accordion sections — Tokenization, Attention, Parameters, Context, Allow-List → **RESOLVED**

### Research Tasks

The following were resolved via codebase exploration:

1. **Accordion pattern analysis**: `faq.html` + `components.css` (`.faq-item`, `.faq-question`, `.faq-answer`) + `faq-common.html` (`toggleFaq()`) provide a full accordion pattern; reusable with new template
2. **LEARNING_ARC insertion geometry**: 048 entries end at line ~191 of `learning.py`; 049 entry goes after `"finetune-vs-prompt-vs-rag"` and before `"chunking"` 
3. **Template rendering pattern**: `architecture-context` template extends `base.html`, reuses `concept-lesson-header` for arc navigation, renders steps as FAQ-style accordion panels

## Complexity Tracking

> **No violations** — all chosen approaches are the simplest viable solution (existing patterns reused throughout).

---

## Phase 0 & Phase 1 Completion

**Phase 0 — Research**: Complete. See `research.md` for full decision log.

| Unknown | Status | Decision |
|---------|--------|----------|
| Accordion template pattern | Resolved | Reuse `.faq-item` CSS + `toggleFaq()` JS; new template extends `base.html` |
| LEARNING_ARC insertion | Resolved | After `"finetune-vs-prompt-vs-rag"`, before `"chunking"` |
| Anchor ID support | Resolved | Accordion items use `id={{ step.key }}`; JS checks `window.location.hash` on load |
| Cross-link target | Resolved | Anchor to allow-list section (key: `allow-list`) |
| Content sections | Resolved | 5 sections: tokenization, attention, parameters, context, allow-list |

**Phase 1 — Design**: Complete.

| Artifact | Path |
|----------|------|
| Data model | `docs/vault/Specs/049 Learning Architecture Differences/data-model.md` |
| Quickstart | `docs/vault/Specs/049 Learning Architecture Differences/quickstart.md` |
| Agent context | Updated `AGENTS.md` via `update-agent-context.sh` |

**Contracts**: N/A — no new external interfaces (all changes are internal content).

### Constitution Check Re-Evaluation (Post-Design)

*Re-checked after Phase 1 design — all gates PASS.*

| Article | Status | Rationale |
|---------|--------|-----------|
| I — Zero-Dependency Core | ✅ PASS | No changes to `anvil/core/` |
| II — Educational Clarity | ✅ PASS | Learning content follows existing educational style |
| IV — TDD Mandatory | ✅ PASS | New e2e route test added per codebase convention; pre-existing tests unmodified (SC-005 NMRG) |
| V — Async-First | ✅ PASS | No new async code or data flow changes |
| VI — __init__.py Policy | ✅ PASS | No new Python packages |
| VII — Layered Architecture | ✅ PASS | Content in route layer only |
| VIII — iOS-Grade Polish | ✅ PASS | Uses existing design system tokens + FAQ accordion pattern |
| IX — Pit of Success | ✅ PASS | No optional capabilities involved |
| X — DDD | ✅ PASS | No new package boundaries |
| XI — Simplicity First | ✅ PASS | All 6 sub-gates pass; Complexity Tracking shows zero deviations |
