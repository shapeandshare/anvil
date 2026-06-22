# Implementation Plan: Bootstrap Demo Datasets

**Branch**: `009-bootstrap-datasets` | **Date**: 2026-06-14 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/009-bootstrap-datasets/spec.md`

## Summary

Replace the hardcoded training fallback (downloads `names.txt` from an external URL) and the hardcoded `DEMO_CORPUS` in the inference service with curated, in-repo demo data. Organize as directories of text files under `data/demo/` (corpus format, primary) and standalone `.txt` files (dataset format, secondary) across 3 sizes × 4 domains. Add a bootstrap command to import demo data into the database via existing corpus/dataset ingestion pipelines.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: Existing project deps — no new pip dependencies. Key modules: `CorpusService`, `CorpusLoader`, `DatasetService`, `DatasetImportService`, `LocalFileStore`  
**Storage**: SQLite via async SQLAlchemy (app metadata); filesystem (`data/demo/`) for source data; existing `data/datasets/` for imported sample content  
**Testing**: pytest (existing) — add tests for bootstrap CLI command and training fallback behavior  
**Target Platform**: Linux/macOS (development), macOS (primary dev environment — Apple Silicon)  
**Project Type**: Python pip-installable package with FastAPI web service and CLI  
**Performance Goals**: Bootstrap completes in <5 seconds; total demo data <500 KB in repo  
**Constraints**: Zero new pip dependencies; all content must be public-domain, generated, or permissively-licensed; must not break existing tests  
**Scale/Scope**: ~10 source files across 3 sizes × 4 domains; 2 code paths to modify (training fallback, inference `DEMO_CORPUS`); 1 new CLI command

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Check | Notes |
|---------|-------|-------|
| I — Zero-Dependency Core | ✅ PASS | Demo data files are not in `anvil/core/`. No changes to core engine. |
| II — Educational Clarity | ✅ PASS | Demo data files will have header comments explaining source and purpose. |
| III — Seeded Reproducibility | ✅ PASS | Static data files are deterministic by nature. |
| IV — TDD Mandatory | ✅ PASS | Bootstrap command and training fallback changes will have tests. |
| V — Async-First | ✅ PASS | Bootstrap reuses existing async corpus ingestion pipeline. |
| VI — Implicit Namespace | ✅ PASS | No new `__init__.py` files needed for internal wiring. |
| VII — Layered Architecture | ✅ PASS | Reuses existing Repository → Service → God Class → Routes/CLI layering. |
| VIII — Whimsy Without Compromise | ✅ PASS | Demo data can include whimsical content (emoji names, fun facts) without compromising functionality. |
| IX — Pit of Success | ✅ PASS | Default do-nothing path (no corpus_id/dataset_id specified) auto-uses demo data. Fallback is graceful, not a crash. |

**No violations. All gates pass.**

## Project Structure

### Documentation (this feature)

```text
specs/009-bootstrap-datasets/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (repository root)

```text
data/
└── demo/
    ├── small/
    │   ├── names/              # Corpus: directory of .txt name files
    │   │   ├── first-names.txt
    │   │   └── README.md
    │   ├── hello-world/        # Corpus: tiny code snippets
    │   │   ├── hello.py
    │   │   ├── factorial.py
    │   │   └── README.md
    │   └── presidents.txt      # Dataset: single .txt upload
    ├── medium/
    │   ├── alice/              # Corpus: Alice in Wonderland excerpt
    │   │   ├── chapter-01.txt
    │   │   └── README.md
    │   └── math-facts.txt      # Dataset: structured math records
    └── large/
        └── metamorphosis/      # Corpus: Kafka novella (public domain)
            ├── part-01.txt
            ├── part-02.txt
            └── README.md

anvil/
├── cli.py                      # [MODIFY] Add bootstrap-datasets subcommand
├── services/
│   ├── training.py             # [MODIFY] Remove fallback download, use default demo
│   ├── inference.py            # [MODIFY] Replace DEMO_CORPUS with curated demo data
│   └── demo_bootstrap.py       # [NEW] Bootstrap service for importing demo data
├── api/
│   └── v1/
│       └── router.py           # [MODIFY] Add bootstrap-datasets endpoint (optional)

tests/
├── test_bootstrap.py           # [NEW] Tests for demo data bootstrapping
└── services/
    └── test_training.py        # [MODIFY] Tests for updated training fallback
```

**Structure Decision**: Single-project layout. Demo data lives under `data/demo/` as static text files organized by size/domain. New `demo_bootstrap.py` service handles import. Existing `cli.py` gets a new subcommand. Training fallback and inference `DEMO_CORPUS` are modified in-place.

## Complexity Tracking

No Constitution violations to justify.
