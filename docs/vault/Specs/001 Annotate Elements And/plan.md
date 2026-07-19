# Implementation Plan: Visual Feedback Annotation

**Branch**: `001-annotate-elements-and` | **Date**: 2026-07-18 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `docs/vault/Specs/001 Annotate Elements And/spec.md`

## Summary

Add a visual feedback annotation tool to the anvil web UI. Users enter an annotation mode from any page, capture a viewport screenshot via client-side DOM rendering, then mark broken UI elements by clicking, draw circles/freehand shapes, and attach text notes. Annotations are submitted as a single feedback report viewable in an admin feedback dashboard. Reports include full JSON export for automated agent consumption.

## Technical Context

**Language/Version**: Python 3.11+ (backend) + Vanilla JavaScript ES2020 (frontend — no transpiler/bundler)  
**Primary Dependencies**: Existing stack (FastAPI, Jinja2, async SQLAlchemy, aiosqlite) + `html-to-image` (vendored locally at `anvil/api/static/js/lib/` — the strict CSP `script-src 'self' 'nonce-…'` blocks external CDN scripts on app routes)  
**Storage**: LocalFileStore at `data/feedback/{report_id}/screenshot.png`; SQLite `anvil-state.db` via new `FeedbackReport` + `FeedbackAnnotation` DB models  
**Testing**: pytest (unit + API) + Playwright (browser e2e for annotation canvas interactions)  
**Target Platform**: Modern web browser (Chrome 90+, Safari 15+, Firefox 90+)  
**Project Type**: Web application (monolith — FastAPI server + Jinja2 templates + vanilla JS)  
**Performance Goals**: Annotation mode activates in <500ms; screenshot capture completes in <3s on a typical page; annotation overlay operates at 60fps  
**Constraints**: Zero new npm/Python runtime dependencies (JS vendored into `static/js/lib/`); CSP forbids external CDN scripts on app routes; no server-side screenshot processing; client-side only capture  
**Scale/Scope**: Single-page viewport capture only (no full-page scrolling); supports ~50 annotations per report; ~1000 feedback reports before admin review needed

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Simplicity First gate (Article XI — hard MUST)**:

- [x] **Simplest viable** (§11.1) — Client-side DOM capture via `html-to-image` is the simplest approach for viewport screenshots. No server-side headless browser needed.
- [x] **Boring over novel** (§11.2) — Uses existing project stack (FastAPI, Jinja2, SQLAlchemy, LocalFileStore). Only new frontend dependency is `html-to-image` (vendored, 4.5M weekly downloads, battle-tested).
- [x] **YAGNI** (§11.3) — No speculative generality: annotation tools limited to element click, circles, and freehand. No full-page capture, no video recording, no collaboration features.
- [x] **Reuse first** (§11.4) — Reuses existing LocalFileStore, Repository pattern, service layer, CSS token system, nav-bar pattern, modal component, and toast notification system.
- [x] **Testable** (§11.6) — Each annotation tool is independently testable via Playwright. API endpoints follow existing e2e patterns. Screenshot capture testable with known DOM fixtures.

> Any deviation from the simplest viable solution MUST be recorded in the Complexity Tracking table below (§11.5), or this gate fails.

**Additional gates**:
- [x] **Article IV (TDD)** — Tests written before implementation (Red-Green-Refactor). New DB model + repository + service + API endpoints all get unit tests.
- [x] **Article V (Async-First)** — `FeedbackService` methods are async. API routes use async handlers. `LocalFileStore` operations are async. Consistent with existing async patterns.
- [x] **Article VI (`__init__.py`)** — New `feedback/` service sub-package gets bare `__init__.py`. No re-exports.
- [x] **Article VII (Layered Architecture)** — New `FeedbackService` follows existing service pattern. New `FeedbackRepository` follows Repository pattern. API routes call service via God Class.
- [x] **Article VIII (iOS-Grade Polish)** — Annotation overlay uses existing CSS tokens, spring animations, `prefers-reduced-motion` support, and `:focus-visible` patterns.
- [x] **Article IX (Pit of Success)** — Annotation mode gracefully degrades if screenshot capture fails (toast + retry). No crash on missing canvas support.
- [x] **Article X (Domain-Driven Package Decomposition)** — New `feedback/` service sub-package follows DDD boundary. Result types co-located in the sub-package. Max 2 levels of nesting.
- [x] **UI compliance** — All templates and CSS comply with `docs/ux-rules.md`. S4/S3 findings resolved before merge.

## Project Structure

### Documentation (this feature)

```text
docs/vault/Specs/001 Annotate Elements And/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output — technology decisions
├── data-model.md        # Phase 1 output — DB entities and relationships
├── quickstart.md        # Phase 1 output — implementation quickstart guide
├── contracts/           # Phase 1 output — API contracts
│   └── feedback-api.md
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
anvil/
├── api/
│   ├── static/
│   │   ├── css/
│   │   │   └── feedback.css        # NEW — annotation overlay + feedback dashboard styles
│   │   └── js/
│   │       ├── annotation.js       # NEW — annotation mode, canvas, drawing tools
│   │       └── lib/
│   │           └── html-to-image.js  # NEW — vendored DOM-capture library (CSP requires local)
│   ├── templates/
│   │   ├── feedback.html           # NEW — feedback dashboard template
│   │   ├── partials/
│   │   │   └── annotation-toolbar.html  # NEW — annotation toolbar partial
│   │   └── base.html               # MODIFY — add Feedback nav tab + annotation.js script
│   └── v1/
│       ├── feedback.py             # NEW — feedback API routes
│       └── pages.py                # MODIFY — add /feedback-page route
├── db/
│   ├── models/
│   │   └── feedback_report.py      # NEW — FeedbackReport ORM model
│   └── repositories/
│       └── feedback_repository.py  # NEW — FeedbackRepository
├── services/
│   └── feedback/
│       ├── __init__.py             # NEW — bare docstring
│       └── feedback_service.py     # NEW — FeedbackService
├── storage/
│   └── local.py                    # MODIFY — no changes needed (LocalFileStore handles any path)
└── workspace/
    └── workspace_paths.py          # MODIFY — add feedback_dir property

tests/
├── unit/
│   └── services/
│       └── test_feedback_service.py  # NEW — unit tests
└── e2e/
    └── test_feedback.py            # NEW — e2e HTTP + browser tests
```

**Structure Decision**: Web application (monolith) — new files follow existing patterns for each layer. No architectural changes to the project structure.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

No complexity deviations — all choices follow existing patterns with minimal additions.