---
title: "Session: Spec 053 Fine-Tuning Dataset Preparation — clarification, plan, implementation"
type: session-log
tags:
  - type/session-log
  - domain/training
  - domain/database
created: '2026-06-28'
updated: '2026-06-28'
aliases:
  - spec-053-fine-tuning-dataset-preparation
status: draft
source: agent
---

# Session: Spec 053 Fine-Tuning Dataset Preparation — Clarification, Plan, Implementation

**Date**: 2026-06-28
**Trigger**: Implement spec 053: turn raw instruction examples into chat-template–rendered
fine-tuning datasets (SFT + preference pairs) tracked through the existing dataset governance.

## What was done

### Spec clarification & cleanup (speckit.clarify)
- Resolved 5 ambiguities: lifecycle states (`preparing→ready|failed`), ChatTemplate as separate entity, JSONL input format, medium scale (async with batches), skip-and-continue error handling
- Caught and corrected spec dependency inaccuracy: spec 043 provides only the *tokenizer abstraction*, not chat-template handling — this spec introduces `ChatTemplate` as a new concept (FT-AD-3 only covers encode/decode)
- Added FR-005 (deterministic template resolution a→b→c), FR-004 (job status API), generalized FR-002 to all input shapes (SFT instruction/response + messages array, preference chosen/rejected)
- Added missing edge cases: concurrency (one active prep per dataset → 409), empty input (`total=0` → ready, not failed)
- Added SC-006 (default template fallback with warning)

### Implementation plan (speckit.plan)
- 5 design artifacts generated: plan.md, research.md, data-model.md, contracts/, quickstart.md
- Architecture decision: reuses `ModelImportJob` async pattern (submit → asyncio.create_task → poll), `SampleRepository.add_bulk()` for batching, `CurationOperation` for audit trail

### Implementation (speckit.implement) — 42 tasks, all complete

**New modules created:**
- `anvil/db/models/chat_template.py`, `fine_tune_dataset.py` — ORM models
- `anvil/db/repositories/chat_templates.py`, `fine_tune_datasets.py` — async repo layer
- `anvil/services/finetuning/` — domain sub-package (ChatTemplateService, DatasetPreparationService, preparation_job, preparation_result)
- `anvil/api/v1/schemas_fine_tune_datasets.py`, `fine_tune_datasets.py` — API endpoints
- `anvil/_resources/migrations/versions/006_add_fine_tune_datasets.py` — Alembic migration

**Wiring:** `anvil/workbench.py` (ftd_repo), `anvil/api/v1/router.py` (route registration)

### Bugs caught during critical review (6 real bugs)
- G1: Worker hardcoded template string instead of resolving via FR-005
- G2: summary_json never persisted
- G3: Rendered output discarded (no JSONL file written)
- G4: Fatal error left job stuck in PREPARING (never set FAILED)
- G5: `_samples_to_records` read non-existent `Sample.content` field (text lives in FileStore)
- G6: Preference records dispatched through SFT render path

## Key discoveries

### ChatTemplate is a new concept, not from spec 043
FT-AD-3 only defines the encode/decode **tokenizer abstraction** (spec 043). Chat template handling
(rendering prompts/responses for instruction tuning) is introduced here. The `ChatTemplate` entity
stores the template string in a dedicated `chat_templates` table; the model's tokenizer (FT-AD-3)
is used only for tokenizer-family validation, not for template management.

### FileStore async generator vs async-iterable discrepancy
The abstract `FileStore.get()` is typed as `async def get() -> AsyncIterator[bytes]`, but the
concrete `LocalFileStore` implements it as an `async def` with `yield` (an async generator).
This causes `mypy` to refuse `async for chunk in store.get(path)` when the parameter is typed as
`FileStore` (abstract) vs `LocalFileStore` (concrete). Consumers must type-hint with the concrete
class to pass mypy's strict mode.

### Sample text lives in FileStore, not on the ORM row
`Sample` has no `content` field. Text is stored in `LocalFileStore("data/datasets")` at
`{dataset_id}/{import_source_id}/{index}.txt`. The `Sample.file_path` holds this relative path.
Preparation jobs must read via the store, not via the ORM.

## Files changed
- New: 18 source files (models, repos, services, API, migration)
- Modified: 2 files (workbench.py, router.py)
- New tests: 8 test files with 53 new tests (46 unit + 7 e2e)
- Tests: 51/51 passing (NMRG preserved: 14 pre-existing failures, 136 baseline passes)