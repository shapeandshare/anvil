# Implementation Plan: Fine-Tuning Dataset Preparation

**Branch**: `053-fine-tuning-dataset-preparation` | **Date**: 2026-06-28 | **Spec**: [053 spec](053%20Fine-Tuning%20Dataset%20Preparation%20-%20spec.md)
**Input**: Feature specification from `docs/vault/Specs/053 Fine-Tuning Dataset Preparation/053 Fine-Tuning Dataset Preparation - spec.md`

## Summary

Add a preparation layer that turns raw instruction examples (JSONL) into a properly formatted
fine-tuning dataset: supervised prompt→response (SFT) pairs with chat template rendering,
and optional preference pairs. Introduces two new entities — `FineTuneDataset` and `ChatTemplate` —
extending the existing dataset domain with async job processing, configurable batch sizes,
skip-and-continue error handling, and audit trail.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI, async SQLAlchemy + aiosqlite, Jinja2 (existing stack); no new runtime deps
**Storage**: `LocalFileStore` at `data/datasets/<id>/prepared/`; SQLite (anvil-state.db) for metadata
**Testing**: pytest with `client` fixture (httpx.AsyncClient); e2e HTTP tests in `tests/e2e/`
**Target Platform**: macOS/Linux server (same as project)
**Project Type**: Web service (FastAPI) + library (pip-installable package)
**Performance Goals**: Async job completes within seconds for typical datasets (hundreds–thousands of records); configurable batch sizes (default 1000)
**Constraints**: FR-003 — template rendering is text (no heavy ML deps); tokenizer-dependent checks behind `[finetune]` extra
**Scale/Scope**: Medium — hundreds to tens of thousands of records (confirmed Q4 clarification)

## Constitution Check

*GATE: Must pass before Phase 1 design. Re-check after Phase 1 design.*

**Simplicity First gate (Article XI — hard MUST)**: Confirm this plan favors
the simplest, most boring solution that meets the requirement:

- [x] **Simplest viable** (§11.1) — reuses existing `ModelImportJob` async pattern, existing
      `SampleRepository.add_bulk()` batching, existing `CurationOperation` audit trail, and
      existing `LocalFileStore`. The only new infrastructure is the two ORM entities and the
      service class — no new dependencies, no new framework.
- [x] **Boring over novel** (§11.2) — no novel/experimental dependency. ChatTemplate is a plain
      SQLAlchemy ORM entity. Template rendering is text string manipulation via the existing
      tokenizer factory (`TokenizerFactory.create_tokenizer()`).
- [x] **YAGNI** (§11.3) — no speculative generality. Skip-and-continue with summary report
      (not pause-on-resume). Separate ChatTemplate entity justified by known future variants
      (confirmed Q2 clarification). Async job pattern is the existing project convention.
- [x] **Reuse first** (§11.4) — reuses: `LocalFileStore`, `TokenizerFactory`, `DatasetRepository`,
      `CurationOperation` model, `ModelImportJob` async pattern, existing `asyncio.create_task()`
      background worker pattern, SSE streaming pattern from training if needed.
- [x] **Testable** (§11.6) — all paths testable via pytest with client fixture. Preparation can
      be tested with small JSONL fixtures (in-memory). Skip-and-continue error paths are
      explicitly testable by feeding malformed records.

> No deviations from simplest viable solution — no Complexity Tracking table needed.

## Project Structure

### Documentation (this feature)

```text
docs/vault/Specs/053 Fine-Tuning Dataset Preparation/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
# Web application — existing project structure

anvil/
├── db/
│   ├── models/
│   │   ├── chat_template.py              # NEW — ChatTemplate ORM
│   │   └── fine_tune_dataset.py          # NEW — FineTuneDataset ORM
│   └── repositories/
│       ├── chat_templates.py             # NEW — ChatTemplateRepository
│       └── fine_tune_datasets.py         # NEW — FineTuneDatasetRepository
├── services/
│   ├── finetuning/                       # NEW domain sub-package
│   │   ├── __init__.py                   # Bare docstring
│   │   ├── chat_template_service.py      # NEW — ChatTemplate CRUD
│   │   ├── dataset_preparation_service.py # NEW — async preparation worker
│   │   ├── preparation_job.py            # NEW — preparation job runner
│   │   └── preparation_result.py         # NEW — PreparationResult value object
│   └── _shared/
│       ├── fine_tune_dataset_status.py   # NEW — FineTuneDatasetStatus enum
│       └── chat_template_status.py       # NEW — ChatTemplateStatus enum (if needed)
├── api/
│   └── v1/
│       ├── fine_tune_datasets.py         # NEW — API routes
│       ├── schemas_fine_tune_datasets.py # NEW — Pydantic schemas
│       └── router.py                     # MODIFIED — register new sub-router
├── workbench.py                          # MODIFIED — wire new services
└── _resources/
    └── migrations/versions/
        └── 006_add_fine_tune_datasets.py # NEW — migration

tests/
├── unit/
│   └── services/
│       └── finetuning/
│           ├── test_chat_template_service.py
│           └── test_dataset_preparation_service.py
└── e2e/
    └── test_fine_tune_datasets.py        # NEW — HTTP API tests
```

**Structure Decision**: New domain sub-package `anvil/services/finetuning/` (per Article X — domain-driven decomposition). Follows the same pattern as `datasets/`, `training/`, `inference/`. New ORM models co-located in `anvil/db/models/` with sibling files. New API routes get their own file (matching `datasets.py` pattern), registered via `router.py`.

## Complexity Tracking

> No deviations from simplest viable solution. All choices reuse existing patterns. Table reserved.