# Implementation Plan: Demo Data Bootstrap Guard

**Branch**: `015-demo-data-bootstrap` | **Date**: 2026-06-19 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/015-demo-data-bootstrap/spec.md`

## Summary

Add a first-run guard to the demo data bootstrap process so bundled corpora and datasets are created only on first startup of a fresh environment, with an ops-menu button to manually re-trigger. The guard detects prior bootstrap by checking for entities with `origin="bundled"` in the database. Three touchpoints: (1) FastAPI lifespan handler (skip if already bootstrapped), (2) new API endpoint + ops menu button (manual re-trigger), (3) CLI command (conditional banner).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI, SQLAlchemy[asyncio], Jinja2 (all existing — no new deps)
**Storage**: SQLite via async SQLAlchemy (`data/anvil-state.db`) — demo entities use `origin="bundled"`
**Testing**: pytest + pytest-asyncio (existing); no CLI integration tests yet
**Target Platform**: Linux/macOS server (FastAPI web app)
**Project Type**: Web application (FastAPI + Jinja2 templates + inline JS)
**Performance Goals**: Startup guard check < 100ms (simple `SELECT count(*)`); bootstrap completes in < 30s on fresh install; re-bootstrap (when already done) < 5s
**Constraints**: Must not block app startup (best-effort); must not crash on failure; must follow existing ops-page JS/endpoint patterns
**Scale/Scope**: Single-user/small-team development tool; no concurrent user concerns beyond debouncing the ops button

## Constitution Check

*GATE: Pass before Phase 0. Re-check after Phase 1 design.*

| Article | Check | Status |
|---------|-------|--------|
| **Article I — Zero-Dependency Core** | Changes in web/DB layer, not core engine | ✅ No impact |
| **Article IV — TDD Mandatory** | Tests for: guard, endpoint, CLI banner | ✅ Test plan defined |
| **Article V — Async-First** | New endpoint async; lifespan handler async | ✅ Compliant |
| **Article VII — Layered Architecture** | Endpoint → workbench.demo() → DemoBootstrapService | ✅ Compliant |
| **Article IX — Pit of Success** | Failure logged, not crash; UI re-trigger available | ✅ Compliant |
| **Article X — Domain-Driven** | Uses existing sub-packages; no structural changes | ✅ No impact |
| **One class per file** | New methods in existing classes | ✅ No new classes |
| **Pydantic over dataclass** | BootstrapResult is BaseModel | ✅ Compliant |
| **No type-error suppression** | `mypy --strict` must pass | ✅ Verify after edits |

**Result**: PASS — no violations. Changes are purely behavioral.

## Project Structure

### Documentation (this feature)

```text
specs/015-demo-data-bootstrap/
├── spec.md
├── plan.md                        # This file
├── research.md                    # Phase 0 — resolved unknowns
├── data-model.md                  # Phase 1 — entity definitions
├── quickstart.md                  # Phase 1 — implementation summary
├── contracts/
│   └── rebootstrap-api.md         # Phase 1 — API contract
└── tasks.md                       # Created by /speckit.tasks
```

### Source Code Changes (4 files)

```text
anvil/
├── api/
│   ├── app.py                     # [EDIT] Add origin-based guard around bootstrap_all()
│   ├── v1/
│   │   └── health_ops.py          # [EDIT] Add POST /v1/demo/bootstrap endpoint
│   └── templates/
│       └── operations.html        # [EDIT] Add button + JS handler in System Actions
└── cli.py                         # [EDIT] Conditional banner in bootstrap_datasets_main
```

**Structure Decision**: Single web application using existing project layout. All changes are surgical edits to 4 existing files. No new modules, packages, or dependencies.

## Complexity Tracking

No Constitution violations exist. No complexity justification needed.