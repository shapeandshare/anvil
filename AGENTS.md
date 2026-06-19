# anvil — Agent Guidelines

**Last updated**: 2026-06-19 (013-responsible-data-governance)

## Project Overview

anvil is a pip-installable Python package for training and experimenting with small LLMs from scratch. It has evolved into a standalone engine with RoPE, SwiGLU MLP, RMSNorm, and safetensors export — wrapped in a FastAPI web server, MLflow experiment tracking, and an iOS-modern UI. The system follows a layered architecture: Repository → Service → God Class → Routes/CLI.

## Design System

This project uses a visual design system defined in @DESIGN.md.

Follow strictly the rules defined in @DESIGN.md for all UI generation. Do not invent colors, fonts, spacing values, or component styles outside the design system. Match component states (hover, focus, active, disabled, pressed) to patterns defined in @DESIGN.md.

The design system is implemented via CSS custom properties in `anvil/api/static/css/tokens.css` (source of truth for token values), with components in `components.css`, layout archetypes in `archetypes.css`, and utilities in `utilities.css`. Always reference these tokens rather than raw values — a systemic restyle must be a token edit.

## Quick Reference

### Commands

| Command | Purpose |
|---------|---------|
| `make setup` | Create venv, install deps from lock file via uv, init DB |
| `make run` | Start all background services (web + MLflow) |
| `make stop` | Stop all background services |
| `make train` | Run training from CLI |
| `make test` | Run full test suite |
| `make lint` | Run ruff → black --check → isort --check → pylint |
| `make format` | Auto-format (black + isort) |
| `make typecheck` | Run mypy/pyright |
| `make clean` | Remove artifacts |
| `make vault-audit` | Run vault audit + graph health (report only) |
| `make vault-audit-apply` | Run vault audit with safe auto-fixes |
| `make vault-audit-diff` | Preview audit auto-fixes (no changes) |
| `make vault-audit-fast` | Mechanical audit only (skip graph-health) |

### Project Structure

```
anvil/          # Python package (implicit namespace)
├── core/          # Stdlib-only training engine
├── db/            # async SQLAlchemy + repositories
│   ├── models/        # ORM models (domain sub-package)
│   └── repositories/  # Repository pattern (domain sub-package)
├── services/      # Business logic — decomposed into domain sub-packages
│   ├── compute/       # Compute backend abstraction
│   ├── chunking/      # Text chunking strategies
│   ├── training/      # Training orchestration, export, memory estimation
│   ├── datasets/      # Corpora, datasets, import, curation, export
│   ├── inference/     # Inference, loaded model, demo provider
│   ├── tracking/      # MLflow experiment tracking, metrics
│   ├── demo/          # Demo data bootstrap on first run
│   └── _shared/       # Cross-domain types (internal, underscore-prefixed)
├── api/           # FastAPI + Jinja2 + SSE
│   └── v1/           # API v1 route definitions (domain sub-package)
├── storage/       # FileStore abstraction
└── supervisor/    # Process manager
```

## Agent Behavioral Principles

1. **Constitution First** — Read `.specify/memory/constitution.md` before writing any code. All work must comply.
2. **TDD Always** — Write tests before implementation (Red-Green-Refactor). 100% coverage required.
3. **Vault Enrichment** — Record discoveries in `docs/vault/` during sessions. Enrich vault at session end.
4. **ADR for Decisions** — Every significant architecture decision gets an ADR in `docs/vault/Decisions/`.
5. **Layer Discipline** — Repositories access DB only. Services consume repositories. God class exposes services. Routes call god class. No shortcuts.
6. **`__init__.py` Ownership Policy** — This is an implicit namespace package codebase. The `anvil/` package root has `anvil/__init__.py` to expose the public API (e.g., `__version__`). For every sub-directory that is a fully-owned Python package level (a directory containing `.py` modules that forms a complete, authoritative part of the `anvil.*` namespace), a **bare `__init__.py`** MUST exist to assert ownership and designate it as a regular package. This means:
   - Authoritative levels (fully owned by the `anvil` project) get a bare `__init__.py` — a docstring-only file describing the package's purpose. No re-exports, no imports.
   - Data-only directories (`static/`, `templates/`, `data/`, `_resources/`, and similar non-Python-package directories) MUST NOT have `__init__.py`.
   - All internal imports MUST continue to use direct module paths: `from .module import X`, not `from . import X` where `X` is a re-export.
   - No `__init__.py` may re-export symbols for internal consumption.
   - This is enforced at merge review — adding or removing `__init__.py` at a package level requires justification that the level is (or is not) a fully-owned authoritative namespace level.
7. **Relative Imports Only** — Never use absolute `anvil.` prefixed imports from within the `anvil/` package itself. Every internal import must use relative paths (`from .module import X`, `from ..parent.module import Y`). This includes lazy imports inside function bodies. Absolute `anvil.X` imports are valid only from code outside the package (`tests/`, `examples/`). This rule is enforced at merge review — violating imports are reject-worthy.
8. **Domain-Driven Package Decomposition** — Package boundaries follow domain (bounded context) boundaries. When a package reaches 12+ peer `.py` modules, evaluate whether it mixes multiple domains and split accordingly. Result/error/value types tightly coupled to one service co-locate in that service's domain sub-package — they do NOT live at the parent level. See Constitution Article X for full rules.
9. **Async Throughout** — Web, DB, storage layers are async. Core engine is sync (exception).
10. **Forward References via PEP 563** — Never use string-literal forward references (`"MyClass"`) in type annotations. Instead, add `from __future__ import annotations` (PEP 563) at the top of the file, which defers all annotation evaluation to strings automatically. When a forward-referenced name is defined in another module (cross-module), pair PEP 563 with `TYPE_CHECKING` imports: guard the import under `if TYPE_CHECKING:` so it's only visible to the type checker. This avoids circular import issues at runtime while keeping annotations clean.

   Correct:
   ```python
   from __future__ import annotations
   from typing import TYPE_CHECKING

   if TYPE_CHECKING:
       from .other_module import OtherClass

   class MyClass:
       def get(self) -> OtherClass:  # no quotes needed
           ...
   ```

   Incorrect:
   ```python
   class MyClass:
       def get(self) -> "OtherClass":  # string literal — DO NOT USE
           ...
   ```

11. **Prefer Enumerations over Magic Strings** — Any parameter, field, or value that represents one of a fixed, known set of possibilities MUST use a Python `enum` rather than magic strings, ad-hoc string constants, `Literal[...]` types, or dict-based choice mappings. Rationale: enums provide type safety, discoverability (IDE autocomplete), single-source-of-truth values, and exhaustiveness checking.

    Rules:
    - Use `StrEnum` (Python 3.11+ stdlib) for string-valued enumerations. Use `IntEnum` for integer-valued. Use `auto()` when values are irrelevant.
    - Enum member names use `UPPER_CASE`. Values use `"lower_case"` (snake_case strings).
    - Define enums in the domain sub-package they belong to (co-located with the service that primarily consumes them). Cross-domain enums go in `anvil/services/_shared/`.
    - Enums may share a file with their primary class per the one-class-per-file exception (see Constitution Article X). Standalone enums get their own file named `<thing>.py` (e.g., `compute_status.py`).
    - Enum values are the single source of truth — never duplicate the string literal elsewhere. Import and use the enum member.
    - When a function or method accepts an enum value, type the parameter with the enum class, not `str`.

    Correct:
    ```python
    from enum import StrEnum

    class ChunkingStrategy(StrEnum):
        LINE = "line"
        WINDOWED = "windowed"
        FILE = "file"

    def chunk(corpus: str, strategy: ChunkingStrategy) -> list[str]:
        ...
    ```

    Incorrect:
    ```python
    def chunk(corpus: str, strategy: str) -> list[str]:
        if strategy not in ("line", "windowed", "file"):
            ...
    ```

## Vault Enrichment Protocol

### During a session:
- When you discover a non-obvious constraint, write a discovery note to `docs/vault/`
- When you make an architecture decision, write or update an ADR in `docs/vault/Decisions/`

### At session end:
- Update `docs/vault/Sessions/` with a session log
- Update any notes that are stale
- Ensure all wikilinks resolve
- Run `make vault-audit` — it must report 0 errors before committing vault changes

### Vault Conventions
- All tags MUST come from `docs/vault/_meta/tags.md` — controlled vocabulary only
- Every note MUST have frontmatter: `title`, `type`, `tags`, `created`, `updated`
- Notes follow `draft → reviewed → canonical` status lifecycle; agents never set `canonical`
- No orphans — every note should have inbound wikilinks (MOCs and session logs exempt)
- Use templates from `docs/vault/_meta/templates/` for new notes

## Architecture Rules

- Core engine (`anvil/core/`) has ZERO pip dependencies
- All file paths use relative imports within the package
- Constants grouped together in dedicated modules
- Imports at top of file by default. Lazy/conditional imports allowed ONLY for runtime capability detection (e.g. platform-specific GPU support, optional dependency probing) — reviewed case by case
- One class per file. Classes for all logic (no loose functions)
- Favor Pydantic `BaseModel` over `dataclasses.dataclass`
- `mypy --strict` enforced. Plus `enable_error_code = ["ignore-without-code", "possibly-undefined", "redundant-cast", "redundant-expr"]` and `warn_unused_ignores = true` in `pyproject.toml`. No type-error suppression (`# type: ignore`, `cast()`, `Any` abuse). Strict explicit typing on all function signatures.
- **Domain-Driven Package Decomposition**: Package boundaries follow domain boundaries. Result/error/value types tightly coupled to one service co-locate in that service's domain sub-package. Cross-domain types go in `_shared/`. Domain sub-packages use plural nouns; internal sub-packages use underscore prefix. Max 2 levels of nesting. See Constitution Article X.
- **Enums over magic strings**: See Principle 11 in Agent Behavioral Principles above.

## Packaging Conventions

### `py.typed` Marker (PEP 561)

The top-level `anvil/` package MUST ship a `py.typed` marker file to declare that
the package distributes inline PEP 484 type annotations. This enables type
checkers (mypy, pyright, pytype) to use the annotations directly without
generating or looking for stub files.

Rules:
- The marker is a **zero-byte file** at `anvil/py.typed`. No content.
- It MUST be listed in `[tool.setuptools.package-data]` in `pyproject.toml`:
  ```toml
  [tool.setuptools.package-data]
  anvil = [
      "py.typed",
      ...
  ]
  ```
- A single `py.typed` at the top-level package root covers all subpackages — no
  need to place it in sub-packages (`anvil/core/`, `anvil/db/`, etc.).
- When adding a new distributed package under the `anvil` namespace, ensure
  `py.typed` is included at that package's root if it lives alongside `anvil`
  (not under it) in the distribution layout.

## Docstring Convention

Every module, package, class, method, function, and constant MUST have a full NumPy-style docstring. This is enforced by ruff (`[tool.ruff.lint.pydocstyle] convention = "numpy"`).

### Template

```python
"""Short description on one line.

Extended description with more detail about behavior, edge
cases, side effects, and usage notes. Leave a blank line
between the short and long description.

Parameters
----------
param_name : type
    Description of the parameter. Start with capital letter.
param2 : type, optional
    Description. Defaults to ``None``.

Returns
-------
type
    Description of the return value. Use ``backticks`` for
    inline code references.

Raises
------
SomeException
    Description of when/why this is raised.
"""
```

### Specifics by entity

| Entity | Required sections |
|--------|-----------------|
| **Module** | Short description; longer description of public API if helpful |
| **Class** | Short description; `Parameters` in `__init__` (not class docstring) |
| **Method** | Short description; `Parameters`, `Returns` (if not None), `Raises` (if applicable) |
| **Function** | Short description; `Parameters`, `Returns`, `Raises` (if applicable) |
| **Constant** | Inline comment or module-level docstring section |
| **Property** | Short description in docstring (no Parameters needed) |

- One-line docstrings are acceptable ONLY for trivial properties or obvious getters.
- If a method/function returns `None` and has no side effects worth documenting, omit `Returns`.
- Use `` ``backticks`` `` for parameter names, types, and code references within prose.

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
- Python 3.11+ (pyproject.toml config), YAML (GitHub Actions workflows), Shell (CI scripts) + `commitizen` (new dev dependency), GitHub Actions (`actions/checkout@v4`, `actions/cache@v4`), `gh` CLI (GitHub CLI, pre-installed on GitHub runners) (007-automated-semver-release)
- `pyproject.toml` (version source), `CHANGELOG.md` (changelog), git tags (release markers), GitHub Releases API (release artifacts) (007-automated-semver-release)
- Python 3.11+ (stdlib for migration service, async for web layer) + Alembic >=1.13 (existing), SQLAlchemy[asyncio] >=2.0 (existing), aiosqlite >=0.20 (existing) (008-auto-db-schema)
- SQLite via async SQLAlchemy (`data/anvil-state.db`, configurable via `ANVIL_STATE_DB_PATH`) (008-auto-db-schema)
- Python 3.11+ (`requires-python = ">=3.11"`) + setuptools (build backend), `build`/`uv build` (wheel build), FastAPI, SQLAlchemy[asyncio], Alembic, MLflow (in-process), Jinja2 — all existing. No new runtime deps. New dev-only: `build` (or reuse `uv build`), `pytest` + `httpx` (existing) for system tests. (009-pip-installable-package)
- SQLite via async SQLAlchemy (`data/anvil-state.db`); MLflow SQLite (`mlruns/mlflow.db`); demo/seed files bundled in package, imported into DB on first run. (009-pip-installable-package)
- `anvil/services/` decomposed into domain sub-packages: `datasets/`, `training/`, `tracking/`, `inference/`, `demo/`, `_shared/`. 29 flat modules → 6 domain directories. (012-ddd-services-restructure)
- Python 3.11+ + stdlib-only hashlib/json for hash-chained audit trail; no new runtime deps. (013-responsible-data-governance)
- `anvil/workbench.py` — Session-bound AnvilWorkbench God Class exposing all DB-backed services as lazy accessors (datasets, corpora, audit, governance, demo). `get_workbench` FastAPI dependency. (013-responsible-data-governance)
- `anvil/services/governance/` — New domain sub-package: `AuditService` (sha256 hash-chaining, raises on failure), `GovernanceService` (acceptable-use gate, license catalog, provenance assignment). Broad OSI/CC license seed idempotently seeded at startup. (013-responsible-data-governance)
- `anvil/db/models/audit_event.py`, `anvil/db/models/license_entry.py` — ORM models for hash-chained audit trail and approved-license catalog. `Dataset`/`Corpus` gain 5 provenance columns (source_description, license_id FK, attribution_text, origin, parent_provenance_ref). (013-responsible-data-governance)
- Bundled provenance via `anvil/data/demo/provenance.json` — machine-readable manifest with source, license, attribution per demo item. Validated at bootstrap; invalid items are skipped. (013-responsible-data-governance)
- SQLite via async SQLAlchemy (`data/anvil-state.db`) for app metadata including provenance columns, `audit_events`, and `license_catalog` tables. (013-responsible-data-governance)

## Recent Changes
- 002-directory-corpus-ingestion: Added Python 3.11+ + Existing project deps (FastAPI, SQLAlchemy, aiofiles) + `pathspec` (lightweight gitignore pattern matching, pure Python, no binary deps)
- 002-model-registry-tracking: Added FastAPI, SQLAlchemy (async), MLflow, Jinja2, pytest (all existing — no new deps)
- 005-mlflow-experiment-tracking: MLflow bumped to `>=3.1,<4`; added `nvidia-ml-py>=12,<13` in `gpu` extra; new `tracking.py`, `mlflow_inputs.py`, `mlflow_capabilities.py`, `metrics_collectors.py` services; custom MPS metrics collector (`MPSMetricsCollector`/`MPSSamplerThread`); source-keyed registry consolidation.
- py-typed-marker: Added `anvil/py.typed` (PEP 561 typed marker) and declared it in `[tool.setuptools.package-data]` so the package advertises inline type annotations.
- 010-numpy-docstrings: Added NumPy-style docstring convention section to AGENTS.md, enabled ruff `D` (pydocstyle) rules with `convention = "numpy"` in `pyproject.toml`, and added full NumPy-style docstrings across all modules (~100 files). New per-file ignores for `tests/`, `examples/`, `scripts/`, `anvil/_resources/migrations/` for D rules.
- 011-enum-convention: Added "Prefer Enumerations over Magic Strings" as Agent Behavioral Principle 11 in AGENTS.md, with rules for StrEnum usage, naming conventions, domain placement, and correct/incorrect examples. Added cross-reference in Architecture Rules.
- 012-ddd-services-restructure: Decomposed `anvil/services/` from 29 flat `.py` modules into 6 domain sub-packages (`datasets/`, `training/`, `tracking/`, `inference/`, `demo/`, `_shared/`). All imports rewritten across 65 files. +449/−317 lines, zero behavioral delta. See Constitution Article X and ADR-022.
- 013-responsible-data-governance: Added provenance columns to Dataset/Corpus, `license_catalog` and hash-chained `audit_events` tables, `provenance.json` manifest, `AuditService` (sha256 chain), `GovernanceService` (acceptable-use gate), and Article VII God-Class refactor (`AnvilWorkbench` session-bound, `get_workbench` dep). Alembic migration 014. See `specs/010-responsible-data-governance/` and ADR-023.
