# anvil — Agent Guidelines

**Last updated**: 2026-06-14

## Project Overview

anvil is a pip-installable Python package for training and experimenting with small LLMs from scratch. Inspired by Karpathy's microgpt.py, it has evolved into a standalone engine with RoPE, SwiGLU MLP, RMSNorm, and safetensors export — wrapped in a FastAPI web server, MLflow experiment tracking, and an iOS-modern UI. The system follows a layered architecture: Repository → Service → God Class → Routes/CLI.

## Design System

This project uses a visual design system defined in @DESIGN.md.

Follow strictly the rules defined in @DESIGN.md for all UI generation. Do not invent colors, fonts, spacing values, or component styles outside the design system. Match component states (hover, focus, active, disabled, pressed) to patterns defined in @DESIGN.md.

The design system is implemented via CSS custom properties in `anvil/api/static/css/tokens.css` (source of truth for token values), with components in `components.css`, layout archetypes in `archetypes.css`, and utilities in `utilities.css`. Always reference these tokens rather than raw values — a systemic restyle must be a token edit.

## Quick Reference

### Commands

| Command | Purpose |
|---------|---------|
| `make setup` | Create venv, install deps from lock file, init DB |
| `make run` | Start all background services (web + MLflow) |
| `make stop` | Stop all background services |
| `make train` | Run training from CLI |
| `make test` | Run full test suite |
| `make lint` | Run ruff → black --check → isort --check → pylint |
| `make format` | Auto-format (black + isort) |
| `make typecheck` | Run mypy/pyright |
| `make clean` | Remove artifacts |

### Project Structure

```
anvil/          # Python package (implicit namespace)
├── core/          # Stdlib-only training engine
├── db/            # async SQLAlchemy + repositories
├── services/      # Business logic
├── api/           # FastAPI + Jinja2 + SSE
├── storage/       # FileStore abstraction
└── supervisor/    # Process manager
```

## Agent Behavioral Principles

1. **Constitution First** — Read `CONSTITUTION.md` before writing any code. All work must comply.
2. **TDD Always** — Write tests before implementation (Red-Green-Refactor). 100% coverage required.
3. **Vault Enrichment** — Record discoveries in `docs/vault/` during sessions. Enrich vault at session end.
4. **ADR for Decisions** — Every significant architecture decision gets an ADR in `docs/vault/Decisions/`.
5. **Layer Discipline** — Repositories access DB only. Services consume repositories. God class exposes services. Routes call god class. No shortcuts.
6. **Implicit Namespace** — No `__init__.py` except for public API exports. All internal imports relative.
7. **Async Throughout** — Web, DB, storage layers are async. Core engine is sync (exception).
8. **No Circular Imports** — Restructure modules architecturally if circular deps appear.

## Vault Enrichment Protocol

### During a session:
- When you discover a non-obvious constraint, write a discovery note to `docs/vault/`
- When you make an architecture decision, write or update an ADR in `docs/vault/Decisions/`

### At session end:
- Update `docs/vault/Sessions/` with a session log
- Update any notes that are stale
- Ensure all wikilinks resolve

## Architecture Rules

- Core engine (`anvil/core/`) has ZERO pip dependencies
- All file paths use relative imports within the package
- Constants grouped together in dedicated modules
- Imports at top of file only (no inline imports)
- Classes for all logic (no loose functions)
- Strict explicit typing on all function signatures

## Active Technologies
## Active Technologies
- Python 3.11+ + Existing project deps (FastAPI, SQLAlchemy, aiofiles) + `pathspec` (lightweight gitignore pattern matching, pure Python, no binary deps) (002-directory-corpus-ingestion)
- SQLite via async SQLAlchemy for corpus metadata; filesystem via existing `LocalFileStore` or reference to original directory paths (002-directory-corpus-ingestion)
- FastAPI, SQLAlchemy (async), MLflow, Jinja2, pytest (all existing — no new deps) (002-model-registry-tracking)
- SQLite (async SQLAlchemy) for metadata, local filesystem (`data/models/`) for model artifacts (002-model-registry-tracking)
- Python 3.11+ + FastAPI, SQLAlchemy (async), aiofiles, pathspec (all existing) (003-dataset-curation)
- SQLite via async SQLAlchemy (metadata); local filesystem via existing `LocalFileStore` (sample content, curation artifacts) (003-dataset-curation)
- JavaScript (ES6+), Python 3.11+ (backend FastAPI) + Zero JS libraries currently; refactor maintains lean dependency ethos — native EventSource, IntersectionObserver, CSS custom properties, Canvas API. A single encoding library for computation graph layout (e.g., dagre) may be justified for FR-014. (004-frontend-refactor)
- localStorage for theme preference, URL search params for shareable state (run ID, model config), sessionStorage for ephemeral UI state (004-frontend-refactor)
- Python 3.11+ + FastAPI, SQLAlchemy (async) + aiosqlite, Alembic, Jinja2; **CHANGED**: `mlflow>=3.1,<4` (was `>=2.16,<3`); **NEW**: `nvidia-ml-py>=12,<13` in `gpu` optional extra; custom `MPSMetricsCollector` via `ioreg`/IOKit (no sudo); new service modules: `tracking.py`, `mlflow_inputs.py`, `mlflow_capabilities.py`, `metrics_collectors.py`; source-keyed registry consolidation (dataset-<id>/corpus-<id>/default-source) (005-mlflow-experiment-tracking)
- SQLite via async SQLAlchemy (app metadata: `data/anvil.db`); MLflow tracking via the supervisor-managed `mlflow server` (SQLite backend `mlruns/mlflow.db`, artifacts under `mlruns/`), reached over HTTP. (005-mlflow-experiment-tracking)
- App metadata in SQLite (`data/anvil.db`, async SQLAlchemy + Alembic). MLflow data via the supervisor-managed `mlflow server` (SQLite backend `mlruns/mlflow.db`, artifacts under `mlruns/`), reached over HTTP. (005-mlflow-experiment-tracking)
- Python 3.11+ (backend), JavaScript ES6+ (frontend widgets) + FastAPI, Jinja2, aiofiles (all existing); no new pip dependencies (005-learning-content-enrichment)
- Demo model at `data/models/demo/model.json` (existing); optimizer state captured in-memory during training runs (005-learning-content-enrichment)
- Demo model at `data/models/demo/model.json` (existing); optimizer state captured in-memory during training runs (005-learning-content-enrichment)
- Python 3.11+ (stdlib for core engine, async for web layer) (006-llama-engine-evolution)
- Local filesystem (`data/models/`) for model artifacts; SQLite via async SQLAlchemy for metadata (006-llama-engine-evolution)
- **RoPE** (half-split/rotate_half): Replaced learned `wpe` position embeddings with Rotary Position Encoding, matching HuggingFace Llama convention (dim i paired with i + head_dim/2). Precomputed cos/sin tables at `block_size x head_dim//2`. (006-llama-engine-evolution)
- **SwiGLU MLP**: Replaced ReLU-based `fc1`/`fc2` (4x expansion) with SiLU-gated `gate`/`up`/`down` projections. `intermediate_size = int(8 * n_embd/3)` preserves parameter count parity (~8n²). (006-llama-engine-evolution)
- **Learned RMSNorm weights**: Added learned scale parameters (`rms_1`, `rms_2`, `rms_final`) initialized to `1.0`, replacing hardcoded RMSNorm. (006-llama-engine-evolution)
- **Safetensors export**: Primary artifact format via `SafetensorsExportService` in `anvil/services/export.py`. Converts anvil internal state dict to HF-convention tensor names, generates `model.safetensors` + `config.json` + `tokenizer.json`. (006-llama-engine-evolution)
- Python 3.11+ + Existing project deps — no new pip dependencies. Key modules: `CorpusService`, `CorpusLoader`, `DatasetService`, `DatasetImportService`, `LocalFileStore` (opencode/misty-panda)
- SQLite via async SQLAlchemy (app metadata); filesystem (`data/demo/`) for source data; existing `data/datasets/` for imported sample conten (opencode/misty-panda)

## Recent Changes
- 002-directory-corpus-ingestion: Added Python 3.11+ + Existing project deps (FastAPI, SQLAlchemy, aiofiles) + `pathspec` (lightweight gitignore pattern matching, pure Python, no binary deps)
- 002-model-registry-tracking: Added FastAPI, SQLAlchemy (async), MLflow, Jinja2, pytest (all existing — no new deps)
- 005-mlflow-experiment-tracking: MLflow bumped to `>=3.1,<4`; added `nvidia-ml-py>=12,<13` in `gpu` extra; new `tracking.py`, `mlflow_inputs.py`, `mlflow_capabilities.py`, `metrics_collectors.py` services; custom MPS metrics collector (`MPSMetricsCollector`/`MPSSamplerThread`); source-keyed registry consolidation.
