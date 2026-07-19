# Implementation Plan: Play → Inference (Rename) + New Chat Page

**Branch**: `001-inference-chat-split` | **Date**: 2026-07-19 | **Spec**: [spec](085%20Inference%20Chat%20Split%20-%20spec.md)

## Summary

Two-part feature: (1) Rename the existing "Play" nav label to "Inference" with zero UX changes to the playground page, and (2) build a new conversational Chat page with streaming text generation, model selector, temperature control, cancel support, and conversation export.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: FastAPI, Jinja2, SSE (all existing — no new deps)  
**Storage**: In-memory (ephemeral chat conversations); existing SQLite + LocalFileStore for model metadata  
**Testing**: pytest (unit + e2e HTTP), Playwright (browser tests) — all existing  
**Target Platform**: Web (macOS/Linux server, any modern browser)  
**Project Type**: Web application (FastAPI + Jinja2 templates + vanilla JS)  
**Performance Goals**: First character streams within 1 second (SC-001); uninterrupted character-level streaming  
**Constraints**: Zero new runtime dependencies; Article XI (Simplicity First) — reuse existing SSE, inference, and template patterns; Article VI (async-first); Article IV (TDD)  
**Scale/Scope**: Single-user session; ephemeral conversations; no multi-tenancy or persistence  

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Simplicity First gate (Article XI — hard MUST)**:

- [x] **Simplest viable** (§11.1) — Nav rename is a one-line change. Chat page reuses existing inference service, SSE pattern, Jinja2 archetype pattern, and model loading. No new frameworks or patterns introduced.
- [x] **Boring over novel** (§11.2) — SSE is already used for training metrics. Jinja2 + vanilla JS already established. No novel dependencies.
- [x] **YAGNI** (§11.3) — No speculative persistence, no multi-modal, no system prompts. Only what the spec requires.
- [x] **Reuse first** (§11.4) — Reuses `InferenceService.generate()`, `GET /v1/inference/models`, existing `archetypes/*.html` pattern, existing `dom.js` / `apiFetch` helpers, existing SSE infrastructure.
- [x] **Testable** (§11.6) — All chat interactions testable via Playwright browser tests + e2e HTTP tests against the streaming endpoint.

**Other constitutional articles**:

| Article | Check | Notes |
|---------|-------|-------|
| I — Zero-Dep Core | ✅ Not affected | Chat is UI/inference layer, not core engine |
| IV — TDD Mandatory | ✅ Tests first | Tests written before implementation per spec |
| V — Async-First | ✅ All async | FastAPI handlers, service calls already async |
| VI — `__init__.py` | ✅ Not affected | No new Python packages needed |
| VII — Layered Arch | ✅ Followed | Route → service → god class discipline |
| VIII — iOS-Grade Polish | ✅ Chat UI polished | Chat messages, streaming, model selector follow existing design tokens |
| IX — Pit of Success | ✅ Demo auto-selects | Demo model pre-selected, graceful degradation |
| X — Domain Decomposition | ✅ Not affected | Chat reuses existing inference domain |

> **Gate status**: PASS — all articles satisfied. No Complexity Tracking entries needed.

## Project Structure

### Documentation (this feature)

```text
docs/vault/Specs/085 Inference Chat Split/
├── 085 Inference Chat Split - spec.md       # Feature specification
├── 085 Inference Chat Split - plan.md       # This file
├── 085 Inference Chat Split - research.md   # Phase 0 — pattern analysis
├── 085 Inference Chat Split - data-model.md # Phase 1 — in-memory chat data structures
├── 085 Inference Chat Split - quickstart.md # Phase 1 — implementation steps
└── contracts/                               # Phase 1 — API contracts
    └── chat-stream.md
```

### Source Code (repository root)

```text
anvil/
├── api/
│   ├── templates/
│   │   └── archetypes/
│   │       ├── playground.html     # UNCHANGED — still at /v1/inference-page
│   │       └── chat.html           # NEW — conversational chat page
│   ├── static/
│   │   └── css/
│   │       └── components.css      # CHANGED — add chat message styles
│   └── v1/
│       ├── pages.py                # CHANGED — add /v1/chat-page route
│       ├── inference.py            # CHANGED — add streaming chat endpoint
│       └── inference_schemas.py    # UNCHANGED — streaming endpoint uses query params, not request body
├── services/
│   └── inference/
│       └── inference.py            # CHANGED — add streaming generate method
└── base.html                       # CHANGED — "Play" → "Inference", add "Chat" tab

tests/
├── e2e/
│   ├── test_pages.py               # CHANGED — add chat page test, update nav test
│   └── api/
│       └── test_chat.py            # NEW — streaming endpoint tests
├── browser/
│   ├── test_navigation_smoke.py    # CHANGED — add chat nav entry
│   └── test_chat_ux.py             # NEW — Playwright chat interaction tests
└── unit/
    └── services/
        └── inference/
            └── test_chat.py        # NEW — unit tests for chat service method
```

**Structure Decision**: Standard single-project web app layout. Chat page follows the same pattern as every other page route (route in `pages.py`, template in `archetypes/`, inline JS in template). No new Python package directories needed — the feature fits entirely within existing modules.

## Complexity Tracking

> No violations to justify. All approaches are the simplest viable option. This table is intentionally empty.