---
title: "Session: Spec 054 Fine-Tuned Model Evaluation — spec, plan, design, implementation"
type: session-log
tags:
  - type/session-log
  - domain/training
  - domain/mlops
  - status/draft
created: '2026-07-01'
updated: '2026-07-01'
aliases:
  - spec-054-fine-tuned-model-evaluation
status: draft
source: agent
---

# Session: Spec 054 Fine-Tuned Model Evaluation — Full Implementation

**Date**: 2026-07-01
**Trigger**: Implement spec 054: side-by-side comparison of a fine-tuned model against its base, with qualitative samples and quantitative metrics.

## Summary

Complete spec-driven development cycle for spec 054: clarification → plan → tasks → analyze → implement. The full backend (ORM, migration, repository, service, API, God Class) and UI (template, SSE, Models page integration) were built, with real in-memory SQLite integration tests.

## Artifacts Created

- `docs/vault/Specs/054 Fine-Tuned Model Evaluation/054 Fine-Tuned Model Evaluation - spec.md` — full spec with 6 FRs, 8 SCs, known capability gaps
- `docs/vault/Specs/054 Fine-Tuned Model Evaluation/plan.md` — constitution-checked implementation plan
- `docs/vault/Specs/054 Fine-Tuned Model Evaluation/research.md` — industry research + codebase verification
- `docs/vault/Specs/054 Fine-Tuned Model Evaluation/data-model.md` — EvaluationRun, MetricDelta, EvalSample entity definitions
- `docs/vault/Specs/054 Fine-Tuned Model Evaluation/contracts/api.md` — typed API contracts
- `docs/vault/Specs/054 Fine-Tuned Model Evaluation/quickstart.md` — setup-to-run flow
- `docs/vault/Specs/054 Fine-Tuned Model Evaluation/tasks.md` — 39 tasks

## Source Files Created

- `anvil/services/evaluation/__init__.py` — domain sub-package
- `anvil/services/evaluation/evaluator.py` — per-prompt generate + loss
- `anvil/services/evaluation/evaluation_service.py` — async SSE orchestration, module-level shared queues/tasks
- `anvil/services/_shared/evaluation_status.py` — EvaluationRunStatus enum
- `anvil/db/models/evaluation_run.py` — EvaluationRun, MetricDelta, EvalSample ORMs (3 classes, 1 file per tight-coupling exception)
- `anvil/db/repositories/evaluation_runs.py` — full CRUD
- `anvil/_resources/migrations/versions/010_add_evaluation_runs.py` — Alembic migration (3 tables, 4 indexes, 2 constraints)
- `anvil/api/v1/schemas_eval.py` — extended with 6 Pydantic models
- `anvil/api/v1/eval.py` — extended with 5 endpoints (POST, SSE stream, GET detail, GET samples, GET list)
- `anvil/api/templates/eval_compare.html` — side-by-side comparison view with SSE live updates
- `tests/unit/evaluation/test_evaluation_run_orm.py`
- `tests/unit/evaluation/test_evaluation_repository.py`
- `tests/unit/evaluation/test_evaluator.py`
- `tests/unit/tracking/test_tracking_eval.py`
- `tests/e2e/test_evaluation.py`

## Key Discoveries

- `InferenceService.loss_breakdown` returns **losses only, not text** — text samples come from `InferenceService.generate`. Critical for correctly specifying FR-035.
- `InferenceService.load_model` does NOT resolve `ExternalModel.id` directly (uses filesystem experiment artifacts + MLflow registry names). FR-006 was added to mandate an explicit resolution path.
- No held-out split capability exists in `FineTuneDataset` / `Dataset` / `Sample` — FR-004 path (b) is net-new seeded work, deferred for v1.
- The existing training SSE pattern uses module-level `_tasks` / `_queues` dicts and `asyncio.create_task` — mirrored for evaluation.
- `ExternalModelRepository.get()` (not `get_by_id()`) is the correct method name.

## Critical Bugs Found & Fixed During Review

1. **Session use-after-close** — background eval worker used request-scoped session after request returned. Fixed: worker opens its own `AsyncSessionLocal()`.
2. **Cross-request queue invisibility** — POST and SSE-GET got different service instances. Fixed: module-level `_QUEUES`/`_TASKS`.
3. **Session leak / Article VII violation** — `_get_eval_service()` bypassed God Class. Fixed: routes now use `Depends(get_workbench)`.
4. **ORM/migration index mismatch** — `ix_evaluation_runs_created_at` missing from ORM model. Added `__table_args__`.
5. **Broken test mocks** — AsyncMock chaining returned coroutines, not values. Rewrote as real in-memory SQLite integration tests.

## Verification

- 46 tests pass (38 unit + 8 e2e)
- ruff: All checks passed
- mypy --strict: 463 files, 0 errors
- App import: OK
- NMRG: pre-existing tests pass

## Related Specs

- [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|038 Fine-Tuning Arc (umbrella)]]
- [[Specs/045 Adapter Inference Export/045 Adapter Inference Export|045 Adapter Inference Export]]
- [[Specs/043 Subword Tokenizer Abstraction/043 Subword Tokenizer Abstraction|043 Subword Tokenizer Abstraction]]
- [[Reference/FineTuningArchitectureDecisions|Fine-Tuning Architecture Decisions]]