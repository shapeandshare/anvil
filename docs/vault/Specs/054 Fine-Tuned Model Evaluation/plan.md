# Implementation Plan: Fine-Tuned Model Evaluation

**Branch**: `054-fine-tuned-model-evaluation` | **Date**: 2026-07-01 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `docs/vault/Specs/054 Fine-Tuned Model Evaluation/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Provide side-by-side comparison of a fine-tuned model against its base — qualitative samples on
identical prompts and quantitative metrics (eval loss / perplexity) with a base→fine-tuned metric
delta. Reuses the existing eval service (`InferenceService` computation, `TrackingService` for MLflow
recording) and surfaces results via a dedicated eval-compare UI launched from the Models page. Applies
to native warm-start (039) and external/adapter (044/045) models alike, dispatching on the recorded
tokenizer family (043). Runs as an async job with SSE streaming.

## Technical Context

**Language/Version**: Python 3.11+ (PEP 604, `StrEnum`, `from __future__ import annotations`)  
**Primary Dependencies**: FastAPI, async SQLAlchemy + aiosqlite, Jinja2, MLflow (existing — no new deps)  
**Storage**: SQLite (anvil-state.db, WAL mode) via async SQLAlchemy; MLflow for eval dataset records; `LocalFileStore` for model artifacts  
**Testing**: pytest + pytest-asyncio (existing); TDD mandate (Constitution Article IV)  
**Target Platform**: Linux server / macOS (localhost); web UI in any browser via FastAPI + Jinja2  
**Project Type**: Web service (pip-installable Python package) with training engine  
**Performance Goals**: Eval run on typical held-out set (<100 prompts) completes within 60s on CPU; SSE streams per-sample progress in real time  
**Constraints**: No new runtime dependencies (Constitution Article I + XI); must reuse existing eval service (`InferenceService.loss_breakdown`, `TrackingService` MLflow pattern)  
**Scale/Scope**: Single-user workbench; eval dataset sizes <10k records per spec scope

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Simplicity First gate (Article XI — hard MUST)**: Confirm this plan favors
the simplest, most boring solution that meets the requirement:

- [x] **Simplest viable** (§11.1) — the chosen approach extends the existing eval service
      (`InferenceService.loss_breakdown`) and MLflow recording pattern (`TrackingService`) rather
      than building a new evaluation framework. The `EvaluationRun` ORM is the minimal new entity
      needed to persist eval results (no such table exists today).
- [x] **Boring over novel** (§11.2) — all technologies are existing project stack (FastAPI,
      SQLAlchemy, Jinja2, MLflow). No new dependencies introduced. SSE streaming reuses the
      existing training SSE pattern.
- [x] **YAGNI** (§11.3) — no speculative generality. Benchmark-suite / standardized-eval harnesses
      are explicitly out of scope for v1. The `EvaluationRun` data model stores only what is needed
      for the base-vs-fine-tuned comparison described in the spec (lineage-complete, not full
      experiment-tracking; references MLflow run rather than duplicating hardware/config).
- [x] **Reuse first** (§11.4) — reuses `InferenceService.loss_breakdown()` for per-sample loss
      computation; reuses `TrackingService.start_run()`/`log_metric()`/`finish_run()` for MLflow
      recording; reuses MLflow-backed eval-dataset infra (`POST /eval-datasets`) for prompt set
      input; reuses existing SSE stream pattern for async progress; reuses `ExternalModel` and
      `LoRAAdapter` ORMs for model/adapter references (no new FKs to raw model tables).
- [x] **Testable** (§11.6) — new ORM models (`EvaluationRun`, `MetricDelta`) are testable via
      standard repository pattern. SSE endpoint testable via `httpx.AsyncClient` SSE support.
      API endpoints testable via existing e2e fixtures. Dispatches (tokenizer, adapter) testable
      via unit tests.

> Any deviation from the simplest viable solution MUST be recorded in the
> Complexity Tracking table below (§11.5), or this gate fails.

## Project Structure

### Documentation (this feature)

```text
docs/vault/Specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
anvil/
├── db/
│   ├── models/
│   │   └── evaluation_run.py    # NEW: EvaluationRun + MetricDelta ORM models
│   └── repositories/
│       └── evaluation_runs.py   # NEW: EvaluationRunRepository
├── services/
│   ├── evaluation/              # NEW: domain sub-package for evaluation logic
│   │   ├── __init__.py          # bare docstring-only (Article VI)
│   │   ├── evaluation_service.py   # NEW: orchestration: run eval, stream SSE, persist
│   │   └── evaluator.py         # NEW: per-sample inference + metric computation
│   └── tracking/
│       └── tracking.py          # EXTEND: add eval-specific MLflow tag helpers
├── api/
│   └── v1/
│       ├── eval.py              # EXTEND: POST /eval/fine-tuned, GET /eval/fine-tuned/{id}, SSE
│       └── schemas_eval.py      # EXTEND: request/response Pydantic models for eval-compare
├── api/
│   └── templates/
│       └── eval_compare.html    # NEW: dedicated eval-compare Jinja2 view
├── api/
│   └── static/
│       └── js/
│           └── eval.js          # NEW: SSE client for eval progress streaming

tests/
├── unit/
│   └── evaluation/
│       ├── test_evaluation_run_orm.py     # NEW: ORM model tests
│       ├── test_evaluation_repository.py  # NEW: repository tests
│       └── test_evaluator.py              # NEW: per-sample eval logic tests
└── e2e/
    └── test_evaluation.py      # NEW: end-to-end HTTP + SSE tests
```

**Structure Decision**: Standard anvil layered architecture (Repository → Service → God Class → Routes),
with a new `services/evaluation/` domain sub-package (plural noun per §10.4). No nesting exceeds 2 levels.
New models co-locate in `db/models/` with existing ORM models; new views in `api/templates/` per convention.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
