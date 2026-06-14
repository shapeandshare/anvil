# Implementation Plan: Directory Corpus Ingestion

**Branch**: `002-directory-corpus-ingestion` | **Date**: 2026-06-11 | **Spec**: `specs/002-directory-corpus-ingestion/spec.md`
**Input**: Feature specification from `specs/002-directory-corpus-ingestion/spec.md`

## Summary

Add support for ingesting entire source code directories as training corpora for microgpt. Currently only single `.txt` files (one-doc-per-line) are supported via `input.txt`. This feature adds: (1) a Corpus abstraction that groups files from a directory, (2) a CorpusLoader that walks directories with gitignore-style filtering, (3) three chunking strategies (line-as-doc, fixed-size windowed, file-as-doc) configurable per-corpus, and (4) training run selection of directory corpora via a new `corpus_id` FK on `TrainingConfig` (replaces existing `dataset_id`).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Existing project deps (FastAPI, SQLAlchemy, aiofiles) + `pathspec` (lightweight gitignore pattern matching, pure Python, no binary deps)
**Storage**: SQLite via async SQLAlchemy for corpus metadata; filesystem via existing `LocalFileStore` or reference to original directory paths
**Testing**: pytest + pytest-asyncio; TDD with 100% coverage enforcement
**Target Platform**: macOS ARM / Linux — no platform-specific code needed (stdlib pathlib)
**Project Type**: Python package (`anvil-workbench`) — new modules under `anvil/services/`, `anvil/db/models/`, `anvil/db/repositories/`, `anvil/api/v1/`
**Performance Goals**: Ingest 100 source files (200 lines avg) in under 30s (file I/O bound); no performance regression on existing training flows
**Constraints**:
- Core engine (`anvil/core/`) MUST NOT be modified — all changes in services/db/api layers
- Existing Dataset model and upload flow MUST remain backward compatible
- `input.txt` fallback MUST continue to work for users who don't use corpora
- No new heavy dependencies — `pathspec` only (pure Python, <100KB)
**Scale/Scope**: Single-user local tool; directories up to ~10,000 files; no live sync or git clone support in v1
**Unknowns (NEEDS CLARIFICATION)**: None — resolved via user choice of option A (all three chunking strategies, per-corpus config), librarian prior art research, and existing project patterns

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Gates derived from CONSTITUTION.md:**

1. ✅ **Zero-Dependency Core** (`core/` must remain stdlib-only) — CorpusLoader lives in `services/`, not `core/`. No changes to `core/engine.py` or `core/autograd.py`. `pathspec` is a service-layer dep only.
2. ✅ **TDD Mandatory** — Tests before code; 100% coverage on new modules (CorpusRepository, CorpusLoader, chunking logic, API endpoints, CLI commands).
3. ✅ **Async-First** — Directory walking and file reading are I/O bound; use `asyncio.to_thread()` or `aiofiles` for file ops. Service layer async. Core engine remains sync (unchanged).
4. ✅ **Implicit Namespace** — New modules follow PEP 420. `__init__.py` only for directories that export a public API surface (db/repositories/, db/models/, services/).
5. ✅ **Layered Architecture** — Repository → Service → God Class → Routes. `CorpusRepository` for DB access. `CorpusService` for business logic. `MicroGPTWorkbench` god class exposes all. Routes call god class.
6. ✅ **Educational Clarity** — Chunking logic should be readable and well-commented. Each strategy is a clearly named function/class.
7. ✅ **Whimsy Without Compromise** — Corpus browser UI in the existing retro terminal style (ls-like file listings in datasets.html). Not a priority for v1 but follow the pattern.

**All gates pass. No violations to justify.**

## Project Structure

### Documentation (this feature)

```text
specs/002-directory-corpus-ingestion/
├── spec.md               # Feature specification (complete)
├── plan.md               # This file — implementation plan
├── research.md           # Phase 0 output (technology decisions)
├── data-model.md         # Phase 1 output (Corpus + CorpusFile entities)
├── quickstart.md         # Phase 1 output (CLI usage guide)
├── contracts/            # Phase 1 output (API contracts for new endpoints)
│   └── corpora.md        # New corpus API contracts
└── tasks.md              # Phase 2 output (/speckit.tasks)
```

### Source Code — New & Modified Files

```text
# NEW modules
microgpt/
├── services/
│   ├── corpora.py                    # CorpusService — orchestration logic
│   ├── corpus_loader.py              # CorpusLoader — directory walk + chunking
│   └── chunking/
│       ├── __init__.py               # Exports Chunker interface
│       ├── base.py                   # Abstract Chunker base class
│       ├── line_chunker.py           # LineAsDocChunker
│       ├── window_chunker.py         # FixedSizeWindowChunker (configurable overlap)
│       └── file_chunker.py           # FileAsDocChunker
├── db/
│   ├── models/
│   │   ├── corpus.py                 # NEW: Corpus + CorpusFile ORM models
│   │   └── training_config.py        # MODIFY: rename dataset_id → corpus_id (FK)
│   └── repositories/
│       ├── corpora.py                # NEW: CorpusRepository
│       └── datasets.py               # UNCHANGED (backward compat)
├── api/
│   └── v1/
│       ├── corpora.py                # NEW: Corpus CRUD + ingest endpoints
│       └── router.py                 # MODIFY: add corpus routes

# EXISTING files to modify
├── services/
│   ├── training.py                   # MODIFY: _load_docs() → accept corpus_id param
│   └── __init__.py                   # MODIFY: export new services
├── cli.py                            # MODIFY: add `anvil corpus` subcommand
├── db/
│   ├── models/
│   │   ├── __init__.py               # MODIFY: export Corpus, CorpusFile
│   │   └── training_config.py        # MODIFY: rename dataset_id → corpus_id
│   └── repositories/
│       └── __init__.py               # MODIFY: export CorpusRepository
├── api/v1/
│   └── router.py                     # MODIFY: include corpus router
└── api/
    ├── app.py                        # MODIFY: if needed for startup
    └── templates/
        ├── datasets.html             # MODIFY: add corpus view section
        └── training.html             # MODIFY: corpus selector in training form

# TESTS (TDD — write before code)
tests/
├── unit/
│   ├── services/
│   │   ├── test_corpus_loader.py     # NEW: walk, filter, chunk tests
│   │   ├── test_chunking.py          # NEW: all 3 chunker strategies
│   │   └── test_corpora.py           # NEW: corpus CRUD service tests
│   ├── db/
│   │   ├── test_corpus_repository.py # NEW: corpus DB tests
│   │   └── test_training_config.py   # MODIFY: corpus_id FK tests
│   └── api/
│       └── test_corpora.py           # NEW: corpus API endpoint tests
└── e2e/
    └── test_corpus_lifecycle.py      # NEW: ingest → train → verify e2e

migrations/
└── versions/
    └── 002_add_corpus_tables.py      # NEW: Corpus + CorpusFile tables + migration
```

**Structure Decision**: Follows the existing layered architecture exactly. New modules slot into existing service/db/api layers. Core engine untouched. Chunking is extracted into its own sub-module under `services/` for clarity and testability.

## Complexity Tracking

> Not applicable — all Constitution Check gates pass. No violations to justify.