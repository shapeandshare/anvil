# Implementation Plan: Systemic Frontend Refactor — microGPT Learning Tool

**Branch**: `004-frontend-refactor` | **Date**: 2026-06-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/004-frontend-refactor/spec.md`

## Summary

Systemic refactor of the microGPT Learning Tool frontend: replace the ANSI/terminal aesthetic with a proper editorial design system, introduce 4 page archetypes (concept/explainer, live training, run history, playground), build scroll-driven concept pages, a live SSE training dashboard with 6-state connection management, canvas-based loss charts (replacing ASCII art), a computation graph view sourced from real engine data, light/dark mode with design tokens, and cross-page state continuity via URL params + session storage. All existing 9 Jinja2 pages are retrofitted into the archetype set.

## Technical Context

**Language/Version**: JavaScript (ES6+), Python 3.11+ (backend FastAPI)  
**Primary Dependencies**: Zero JS libraries currently; refactor maintains lean dependency ethos — native EventSource, IntersectionObserver, CSS custom properties, Canvas API. A single encoding library for computation graph layout (e.g., dagre) may be justified for FR-014.  
**Storage**: localStorage for theme preference, URL search params for shareable state (run ID, model config), sessionStorage for ephemeral UI state  
**Testing**: pytest (backend). Frontend testing: manual for now (no JS test framework in stack). New frontend modules should be structured for future testability.  
**Target Platform**: Modern browsers (ES6+, EventSource, IntersectionObserver, CSS custom properties, Canvas API)  
**Project Type**: Web application — Jinja2 templates with extracted JS modules, multiple independently-served pages with client-side state continuity via URL params. Not a single-page app, but enhanced with extracted client-side behavior.  
**Performance Goals**: 100ms input responsiveness (SC-002), no unbounded DOM growth past 10,000 step points, throttled paint cadence (rAF or fixed interval)  
**Constraints**: Zero new JS dependencies without explicit justification against Principle 4 (dependency-lean ethos); WCAG AA contrast in both modes; prefers-reduced-motion honored; mobile collapse for all sticky layouts  
**Scale/Scope**: 9 existing Jinja2 templates → 4 archetypes, 5 concept widgets, 1 SSE lifecycle, 1 computation graph view, 1 shared shell. Single-user dev tool.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Status: PASS (no violations)**

The project constitution (`.specify/memory/constitution.md`) contains only template placeholders — no real constitutional gates have been defined for this project. No violation to evaluate.

## Project Structure

### Documentation (this feature)

```text
specs/004-frontend-refactor/
├── plan.md              # This file (/speckit.plan command output)
├── spec.md              # Feature specification with clarifications
├── research.md          # Phase 0 — technology decisions
├── data-model.md        # Phase 1 — entities, state machines, data flows
├── quickstart.md        # Phase 1 — developer quickstart for this feature
├── contracts/           # Phase 1 — API contracts, component interfaces
│   ├── sse-lifecycle.md
│   ├── scroll-scene.md
│   ├── design-tokens.md
│   └── chart-primitive.md
└── tasks.md             # Phase 2 — (/speckit.tasks command)
```

### Source Code (repository root)

```text
microgpt/api/                   # Existing API module — routes stay unchanged
├── app.py                      # FastAPI app factory (minor changes for new endpoints)
├── v1/
│   ├── router.py               # Route definitions (add computation graph endpoint)
│   ├── training.py             # SSE stream endpoint (unchanged)
│   └── ...                     # Other route modules (unchanged)
├── templates/                  # Jinja2 templates — REFACTORED
│   ├── base.html               # App shell: nav, theme toggle, page frame, store boundary
│   ├── archetypes/
│   │   ├── concept.html        # Archetype A — ScrollScene concept page
│   │   ├── training.html       # Archetype B — Live training dashboard (REPLACES existing)
│   │   ├── experiment.html     # Archetype C — Run history list + detail
│   │   └── playground.html     # Archetype D — Sandbox/widget composition
│   └── partials/
│       ├── scroll-scene.html   # ScrollScene reusable partial (pinned visual + steps)
│       ├── streaming-chart.html # Live/replay chart component
│       ├── concept-widgets/    # Per-concept interactive widgets
│       │   ├── tokenization.html
│       │   ├── embedding.html
│       │   ├── attention.html
│       │   ├── sampling.html
│       │   └── training-loop.html
│       └── graph-view.html     # Computation graph view partial
└── static/
    ├── css/
    │   ├── tokens.css          # Design token definitions (CSS custom properties)
    │   ├── base.css            # Reset, base typography, shell layout
    │   ├── archetypes.css      # Per-archetype layout styles
    │   ├── components.css      # Reusable component styles
    │   ├── utilities.css       # Utility classes
    │   └── code.css            # Code/token/mono rendering (carried over from terminal theme)
    ├── js/
    │   ├── core.js             # Shell init, theme toggle, nav, cross-page state
    │   ├── sse.js              # SSE connection manager (6 states, reconnect, backoff)
    │   ├── chart.js            # Canvas-based loss chart (append-only, throttle, downsample)
    │   ├── scroll-scene.js     # IntersectionObserver scroll-triggered state machine
    │   ├── graph-view.js       # Computation graph renderer (canvas/SVG)
    │   └── widgets/            # Per-concept interactive widgets
    │       ├── tokenization.js
    │       ├── embedding.js
    │       ├── attention.js
    │       ├── sampling.js
    │       └── training-loop.js
    └── assets/
        └── unicorn.svg         # Mascot (unchanged)
```

**Structure Decision**: Option 2 (Web application — frontend component structure extracted from inline template JS into organized `static/js/` and `static/css/` directories). Routes remain in `anvil/api/v1/` as-is. The existing monolithic template-per-route pattern is replaced by an archetype + partials pattern with extracted JS modules.

## Complexity Tracking

Not applicable — no Constitution Check violations to justify.