---
title: 004 Frontend Refactor - quickstart
type: quickstart
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/004 Frontend Refactor/
related:
  - '[[004 Frontend Refactor]]'
created: ~
updated: ~
---
# Quickstart: Systemic Frontend Refactor

## Prerequisites

- Python 3.11+ (backend unchanged)
- Modern browser (Chrome/Firefox/Safari — ES6+, EventSource, IntersectionObserver, Canvas)

## Development Setup

```bash
# 1. Ensure the project is set up
make setup

# 2. Start the development server
make run
# Opens at http://localhost:8080

# 3. Verify current frontend routes
open http://localhost:8080/v1/training-page
open http://localhost:8080/v1/experiments-page
open http://localhost:8080/v1/datasets-page
```

## Frontend Architecture Overview

```
microgpt/api/
├── templates/           # Jinja2 HTML templates (kept as-is, refactored in-place)
│   ├── base.html        # App shell — nav, theme toggle, store boundary
│   ├── archetypes/      # Archetype templates
│   │   ├── concept.html
│   │   ├── training.html
│   │   ├── experiment.html
│   │   └── playground.html
│   └── partials/        # Reusable partials
└── static/
    ├── css/
    │   ├── tokens.css    # Design tokens (CSS custom properties)
    │   ├── base.css      # Reset, typography, shell
    │   ├── archetypes.css
    │   ├── components.css
    │   └── utilities.css
    └── js/
        ├── core.js       # Shell, nav, theme, cross-page state
        ├── sse.js        # SSE connection manager
        ├── chart.js      # Canvas loss chart
        ├── scroll-scene.js # IntersectionObserver scroll scene
        ├── graph-view.js   # Computation graph renderer
        └── widgets/      # Concept widgets
```

## Implementation Phases

| Phase | What | Deliverables |
|-------|------|--------------|
| 1 | Tokens + shell | `tokens.css`, `base.css`, `core.js`, refactored `base.html` |
| 2 | Archetype B (live training) | `sse.js`, `chart.js`, `training.html`, `components.css` |
| 3 | ScrollScene + attention page | `scroll-scene.js`, `concept.html`, `partials/scroll-scene.html` |
| 4 | Remaining concept pages | Widget files in `js/widgets/` and `partials/concept-widgets/` |
| 5 | Run history (Archetype C) | `experiment.html`, chart replay integration |
| 6 | Cross-page state | URL params + sessionStorage wiring |
| 7 | Cross-cutting audit | a11y, reduced-motion, mobile, perf verification |

## Key Files to Reference

| File | What It Defines |
|------|----------------|
| `spec.md` | Feature specification with all clarifications |
| `data-model.md` | Entity relationships, state machines, data flows |
| `contracts/sse-lifecycle.md` | SSE connection manager API |
| `contracts/scroll-scene.md` | ScrollScene primitive API |
| `contracts/design-tokens.md` | CSS custom property definitions |
| `contracts/chart-primitive.md` | LossChart canvas component API |
| `research.md` | Technology decisions and rationale |

## Running Tests

```bash
make test        # Backend tests (no frontend test framework yet)
make lint        # Python linting (ruff, black, isort, pylint)
make typecheck   # Python type checking
```