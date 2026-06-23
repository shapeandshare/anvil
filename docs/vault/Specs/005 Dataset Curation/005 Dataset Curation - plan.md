---
title: 005 Dataset Curation - plan
type: plan
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/005 Dataset Curation/
related:
  - '[[005 Dataset Curation]]'
created: ~
updated: ~
---
# Implementation Plan: Dataset Curation

**Branch**: `005-dataset-curation` | **Date**: 2026-06-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/docs/vault/Specs/005 Dataset Curation/spec.md`

## Summary

Add feature-rich dataset curation to the anvil platform: users can create, import (TXT/CSV/JSONL/JSON), curate (dedup, filter, regex replace, individual edit/delete), view quality metrics, export (TXT/CSV/JSONL), and use curated datasets directly for training. Extends the existing Dataset model and bridges directory-sourced corpora for curation.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI, SQLAlchemy (async), aiofiles, pathspec (all existing)
**Storage**: SQLite via async SQLAlchemy (metadata); local filesystem via existing `LocalFileStore` (sample content, curation artifacts)
**Testing**: pytest (existing); test for new dataset service methods, API routes, UI functionality
**Target Platform**: Linux/MacOS server (web service, single-user desktop-style)
**Project Type**: Web service (FastAPI backend + Jinja2 frontend)
**Performance Goals**: 100K-sample import <30s (file parsing only); 10K-sample export <10s; curation ops <2s for 10K samples; 1M samples must succeed with streaming
**Constraints**: Single-user; SQLite-bound (concurrent write limitations); local filesystem storage; up to 1M sample ceiling
**Scale/Scope**: Single concurrent user; up to 1M samples per dataset; ~20-30 dataset entities active

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

No constitution violations — project constitution has no defined gates.

## Project Structure

### Documentation (this feature)

```text
docs/vault/Specs/005 Dataset Curation/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
# Web application structure (frontend + backend)
microgpt/
├── db/
│   ├── models/
│   │   ├── curation.py        # New: Sample, CurationOperation, ImportSource models
│   │   └── __init__.py
│   └── repositories/
│       ├── datasets.py        # Extend DatasetRepository (sample CRUD, curation ops)
│       └── __init__.py
├── services/
│   ├── datasets.py            # Extend DatasetService (import, export, curation)
│   ├── dataset_curation.py    # New: curation operations engine (dedup, filter, replace)
│   ├── dataset_import.py      # New: multi-format import with validation + streaming
│   └── dataset_export.py      # New: multi-format export
├── api/
│   └── v1/
│       ├── datasets.py        # Extend: add curation, import, export endpoints
│       └── router.py          # Register new routes
│   └── templates/
│       ├── datasets.html       # Extend: add curation UI, quality dashboard
│       └── dataset_detail.html # New: individual dataset curation page
├── storage/
│   ├── interface.py           # Existing FileStore ABC
│   └── local.py               # Existing LocalFileStore
└── supervisor/                # Unchanged

tests/
├── unit/
│   ├── test_dataset_service.py    # New: curation engine, import, export tests
│   └── test_dataset_api.py        # New: API endpoint tests
├── integration/
│   └── test_dataset_curation.py   # New: full curation workflow integration tests
└── fixtures/
    └── datasets/                  # Test data files
```

**Structure Decision**: Extended existing microgpt package structure (Web application - Option 2) following project conventions: Repository → Service → API. New curation services are separate modules co-located with existing `services/datasets.py`.

## Complexity Tracking

Not needed — no constitution violations.

## Phase 0: Research

See [research.md](./research.md) for findings from Phase 0 research agents.

## Phase 1: Design

See [data-model.md](./data-model.md) for data model, and [contracts/](./contracts/) for API contracts.

---

**Phase 0 ✅** — Research complete. All design decisions documented in research.md. Key findings: hybrid SQLite+filesystem storage, import atomicity via transactions, immutable curation operation log, corpus bridge via existing chunking, API envelope pattern from corpora, no HTMX (vanilla JS).

**Constitution Re-check ✅** — No violations. No constitution gates defined.

**Phase 1 ✅** — Design artifacts generated. Data model (4 entities: Dataset extended, Sample, CurationOperation, ImportSource), API contracts (12 endpoints), quickstart guide.

---

**Main Branch Sync ✅** — Merged origin/main (fast-forward, no conflicts). 2 new commits incorporated:
- `feat(ui): clean minimalist theme (#6)` — CSS palette changed to indigo/green; no functional spec impact
- `feat: progressive walkthrough (#7)` — New `training.html` page with corpus selector, SSE streaming, progressive walkthrough. Training API extended with progressive endpoints. Spec updated: User Story 5 dataset selector placement clarified, FR-025 references existing training.html, assumptions updated.