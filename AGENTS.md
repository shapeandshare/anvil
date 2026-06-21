# anvil — Agent Guidelines

**Last updated**: 2026-06-20 (data-fundamentals-lesson + banner-cta-pattern + theme-gallery-expansion + ui-layout-overhaul + nine-new-themes + unicorn-theme + prism-vibrancy + unicorn-mascot-flying-sprites + content-repository-016-mvp + concurrent-isolated-ingestion-us2)

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
10. **Forward References via PEP 563** — Never use string-literal forward references (`"MyClass"`) in type annotations. Instead, add `from __future__ import annotations` (PEP 563) at the top of the file, which defers all annotation evaluation to strings automatically. For cross-module type references, default to a normal top-level import (the project's layered architecture should resolve cross-module dependencies without cycles). Use `TYPE_CHECKING`-guarded imports ONLY to break a genuine runtime circular import that cannot be resolved without violating another rule — the most common case is a bidirectional SQLAlchemy ORM relationship. See Constitution Additional Constraints for the full exception discipline, including the four conditions (annotations marker, genuine cycle, annotation-only usage, one-line cycle comment). A script (`scripts/ci/check_guarded_imports.py`) enforces that guarded symbols stay annotation-only.

   Permitted (genuine unavoidable cycle):
   ```python
   from __future__ import annotations
   from typing import TYPE_CHECKING

   if TYPE_CHECKING:
       from .other_module import OtherClass  # TYPE_CHECKING-only: breaks cycle

   class MyClass:
       def get(self) -> OtherClass:  # no quotes needed
           ...
   ```

   Incorrect — add a normal top-level import instead (no cycle):
   ```python
   from __future__ import annotations
   from typing import TYPE_CHECKING

   if TYPE_CHECKING:
       from .other_module import OtherClass  # REMOVE — only needed if genuine cycle

   class MyClass:
       def get(self) -> OtherClass:
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
    - At boundaries (DB reads, API input, config files) where callers pass raw strings, the boundary method should accept ``str | MyEnum`` and convert via ``isinstance(x, str): x = MyEnum(x)``. Internal methods stay strictly typed with the enum.

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

    Boundary pattern (DB field → service method):
    ```python
    # At the boundary: accept either and convert
    def ingest(
        chunking_strategy: ChunkingStrategy | str = ChunkingStrategy.WINDOWED,
    ) -> None:
        if isinstance(chunking_strategy, str):
            chunking_strategy = ChunkingStrategy(chunking_strategy)
        # Now chunking_strategy is strictly ChunkingStrategy
        _do_chunk(chunking_strategy)

    # Internal: strictly typed
    def _do_chunk(strategy: ChunkingStrategy) -> None:
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
- Python 3.11+ (helper scripts, refactors); YAML (GitHub Actions); Markdown (governance/docs); POSIX sh + GNU make (gate orchestration, existing `shared/*.mk`) + Existing dev tooling only — `ruff`, `black`, `isort`, `pylint`, `mypy` (strict), `pytest` + `pytest-cov`, `commitizen`, `uv`; GitHub Actions (`actions/checkout@v4`, `astral-sh/setup-uv` or `actions/setup-python@v5`); existing `scripts/ci/vault_audit.py` + `graph_health/`. **No new runtime or dev dependency is required.** (013-dx-harness-hardening)
- N/A — no new persistence. (Coverage baseline stored as a config value in `pyproject.toml`; gate config stored in workflow YAML.) (013-dx-harness-hardening)
- Python 3.11+ (backend), TypeScript 5.x (CDK infrastructure), JavaScript ES6+ (frontend unchanged) + FastAPI (existing), SQLAlchemy[asyncio] (existing), `boto3` (new, SaaS extra), `redis-py` (new, SaaS extra), `aws-jwt-verify` (new, SaaS extra), `aws-cdk-lib` (dev only, infra package) (opencode/mighty-tiger)
- RDS PostgreSQL (SaaS), SQLite (local), S3 (SaaS), local filesystem (local), ElastiCache Redis (SaaS, for SSE) (opencode/mighty-tiger)
- Python 3.11+ + PyYAML (existing), networkx (optional via `anvil[vault-health]` extra) (015-graph-health-subsumption)
- Filesystem — vault health reports written to `_meta/audit/` under vault dir (legacy behavior preserved) (015-graph-health-subsumption)
- Python 3.11+ (backend), JavaScript ES6+ (frontend, no build step / no framework) + FastAPI, Jinja2, async SQLAlchemy (all existing). **No new runtime dependencies** — themes are vanilla JS + CSS; signal instrumentation is stdlib (`math.isnan`) + existing Pydantic. (015-theme-engine)
- Client-side only — `localStorage` for theme preference (`theme` key extended) and light/dark choice; `sessionStorage` not required. No DB schema change, no Alembic migration (per spec Assumption: server-side per-user persistence out of scope for v1). (015-theme-engine)
- Python 3.11+ + FastAPI, SQLAlchemy[asyncio], Jinja2 (all existing — no new deps) (opencode/crisp-rocket)
- SQLite via async SQLAlchemy (`data/anvil-state.db`) — demo entities use `origin="bundled"` (opencode/crisp-rocket)
- Python 3.11+ + FastAPI, async SQLAlchemy + aiosqlite, Alembic, Jinja2, MLflow (016-lakefs-content-repo)
- SQLite (`data/anvil-state.db`) for metadata; content-addressed blobs on the filesystem via `LocalFileStore` (`data/content/`); LakeFS reserved for SaaS mode (016-lakefs-content-repo)

## Recent Changes
- 002-directory-corpus-ingestion: Added Python 3.11+ + Existing project deps (FastAPI, SQLAlchemy, aiofiles) + `pathspec` (lightweight gitignore pattern matching, pure Python, no binary deps)
- 002-model-registry-tracking: Added FastAPI, SQLAlchemy (async), MLflow, Jinja2, pytest (all existing — no new deps)
- 005-mlflow-experiment-tracking: MLflow bumped to `>=3.1,<4`; added `nvidia-ml-py>=12,<13` in `gpu` extra; new `tracking.py`, `mlflow_inputs.py`, `mlflow_capabilities.py`, `metrics_collectors.py` services; custom MPS metrics collector (`MPSMetricsCollector`/`MPSSamplerThread`); source-keyed registry consolidation.
- py-typed-marker: Added `anvil/py.typed` (PEP 561 typed marker) and declared it in `[tool.setuptools.package-data]` so the package advertises inline type annotations.
- 010-numpy-docstrings: Added NumPy-style docstring convention section to AGENTS.md, enabled ruff `D` (pydocstyle) rules with `convention = "numpy"` in `pyproject.toml`, and added full NumPy-style docstrings across all modules (~100 files). New per-file ignores for `tests/`, `examples/`, `scripts/`, `anvil/_resources/migrations/` for D rules.
- 011-enum-convention: Added "Prefer Enumerations over Magic Strings" as Agent Behavioral Principle 11 in AGENTS.md, with rules for StrEnum usage, naming conventions, domain placement, and correct/incorrect examples. Added cross-reference in Architecture Rules.
- 012-ddd-services-restructure: Decomposed `anvil/services/` from 29 flat `.py` modules into 6 domain sub-packages (`datasets/`, `training/`, `tracking/`, `inference/`, `demo/`, `_shared/`). All imports rewritten across 65 files. +449/−317 lines, zero behavioral delta. See Constitution Article X and ADR-022.
- 013-responsible-data-governance: Added provenance columns to Dataset/Corpus, `license_catalog` and hash-chained `audit_events` tables, `provenance.json` manifest, `AuditService` (sha256 chain), `GovernanceService` (acceptable-use gate), and Article VII God-Class refactor (`AnvilWorkbench` session-bound, `get_workbench` dep). Alembic migration 014. See `specs/010-responsible-data-governance/` and ADR-023.
- 014-demo-data-bootstrap: Added first-run guard to demo data bootstrap (origin-based detection via `count_by_origin("bundled")` in repository layer), conditional startup skip, `POST /v1/demo/bootstrap` ops-menu re-trigger endpoint with `asyncio.Lock` concurrency protection, and CLI banner conditional. Also fixed stale monkeypatch paths in test_bootstrap.py (`anvil.services.demo_bootstrap` → `anvil.services.demo.demo_bootstrap`) and provenance manifest injection pattern (`_svc_with_provenance` helper). See `specs/014-demo-data-bootstrap/` and `docs/vault/Discovery/provenance-manifest-mocking-technique.md`.
- 014-saas-architecture (**spec + decision-record only — NOT yet implemented**): Authored the three-mode SaaS operating model (local / SaaS user / SaaS developer) sharing one `anvil` package behind five abstraction interfaces (`FileStore`, `EventBus`, `JobQueue`, `ComputeBackend`, `LogsReader`). Binding decisions **AD-1..AD-16** in `specs/014-saas-architecture/spec.md`: AWS Batch-on-EC2 compute, app-managed Cognito OIDC/JWT, Postgres-source-of-truth + append-only `job_events` + reconciler, asset-free CFN with digest-pinned images, two-tier RBAC with a **read-wide/write-narrow cluster-admin** (`is_cluster_admin`), usage metering, single-image/two-entrypoints, observability (CloudWatch Logs viewer + OTel→X-Ray + Prometheus/Grafana/Alertmanager), private MLflow behind a `/v1/mlflow-proxy/` reverse proxy, multi-cluster CLI registry, and HA/backup-DR posture. SaaS-only code is confined to `anvil/_saas/` with optional `[aws]`/`[monitoring]`/`[monitoring-aws]`/`saas` extras — **local mode is unchanged and has zero new dependencies**. See ADR-030 and `docs/vault/Reference/SaaSArchitecture.md` (+ 77 diagrams). When implementation begins, update the Active Technologies section above.
- release-workflow-ci-fix: Configured the `BUMP_PAT` repository secret and fixed the `Release` workflow (`.github/workflows/release.yml`). `commitizen bump` creates a commit, so git author identity (`github-actions[bot]`) MUST be configured *before* the bump step (was previously only set in the later bump-PR step → `fatal: empty ident name not allowed`). Added `--no-tag` to `cz bump` to avoid a local tag colliding with the explicit tag from merged `main`, and changed the bump-PR step to `git commit --amend` the commit `cz bump` already made (instead of `git add` + `git commit`, which would stage nothing). See `docs/vault/Discoveries/release-workflow-git-identity-and-cz-commit.md`.
- theme-gallery-expansion: Grew the behavioral theme engine (ADR-031) from 4 to **17 themes** via the documented 3-step contract (no engine/manager/registry/SSE change) — added Tide, Bloom, Tectonic, Glacier, Reactor, Hyperspace, Mainframe, Hologram, Storm Front, Ember Drift, Resonance, Inkwash, Stained Glass. Diversified the driving signal (loss / throughput / instability) and maximized dual light+dark (9 of 17). `Resonance` is the first theme to use the reserved opt-in WebAudio layer. Reworked the theme picker into a **scrollable 2-column grid with full keyboard navigation + live preview** (Arrows move, Enter commits, Escape/click-away reverts) using a `persist:false` apply for preview — all in `theme-manager.js` + `base.css`, with CI guards in `tests/system/test_theme_engine.py::TestPickerKeyboardNavigation`. Reusable pattern in `docs/vault/Reference/theme-picker-grid-keyboard-nav.md`; see ADR-031 addendum and `docs/vault/Sessions/2026-06-19-theme-gallery-expansion.md`.
- ui-layout-overhaul: App-shell layout chrome — footer removed, `.app-shell` is the scroll container (`overflow-y:auto`) so the nav scrolls with content, and `.nav-bar` is a **floating rounded box inset from the screen edges** (margin + `--radius-lg` + 1px `--glass-border` + solid `--surface`, **no drop shadow**). The atmospheric accent `radial-gradient` lives on `.app-shell` (not `.app-main`) so the page background reads continuously around the floating nav box. `DESIGN.md` reconciled (app-shell layers, Ambient background, Navigation Bar + new Theme Picker component, reduced-transparency exemption, nav drop-shadow Do/Don't) — note the prior "glass nav with fade-mask" description was a stale divergence; the shipped nav is the solid floating box. See `docs/vault/Sessions/2026-06-20-ui-layout-overhaul.md`.
- theme-square-grid-fixes: Replaced rigid orthogonal grid overlays in two themes. **Stained Glass** (`stainedglass.css`): swapped the 90px square-grid mask+blur for three `repeating-linear-gradient` came layers at 40°/-35°/18° with non-harmonic spacings (87/72/105px), creating irregular polygonal panes. **Hologram** (`hologram.css`): replaced the 44px orthogonal cyan grid with an SVG data-URI hexagonal wireframe (flat-top, R=20, seamless 60×34.64px tile, 4 hexes/tile). Both preserve their original signal-response behavior (`--lumin`/`--focus` dimming, `data-glass` milestone flash, scanline overlay, chromatic ghosting). See `docs/vault/Discoveries/css-grid-overlay-replacement-techniques.md`.
- nine-new-themes: Added **9 new behavioral themes** (17→26 total) in a single batch: Pulse (throughput/heartbeat, light/dark), Solar Flare (gradient-norm/coronal, single), Deep Sea (loss/bioluminescent, light/dark), Static (loss-volatility/CRT noise, single), Vinyl (throughput/turntable wobble, light/dark), Echo (gradient-norm+milestone/sonar, single), Prism (loss+milestone/spectrum, light/dark), Loom (throughput/weave, light/dark), Ash (loss/embers, single). Diversified the category mix — 4 of 9 are single-mode, 5 dual light+dark. First themes to use: loss-volatility (rolling stddev window=8), CSS `hsl()` with dynamic hue-shift (Prism), FractalNoise SVG filter (Static), CSS `rotate()` on `.app-main` (Vinyl), and expanding-ring `::after` animations (Echo). All 18 files written per the 3-step contract; no engine changes. CI `THEME_IDS` list updated. See `docs/vault/Reference/theme-creation-guide.md` and `docs/vault/Sessions/2026-06-20-nine-new-themes.md`.
- unicorn-theme: Added **Unicorn** theme (26→27 total), a whimsical magical theme with dual light/dark mode. Loss drives `--magic` (rainbow gradient overlay), throughput drives `--twinkle` (16-position starfield). Milestones shift hue by 51° (rainbow order) with a saturate burst; divergence fades to monochrome. See `docs/vault/Sessions/2026-06-20-unicorn-theme-and-prism-vibrancy.md`.
- prism-vibrancy: Boosted the **Prism** theme's visual punch — doubled rainbow opacity range (`0.02-0.17` → `0.05-0.33`), tightened HSL lightness (60-70% → 48-60%) for punchier bands, added 8th gradient stop and `filter: saturate(1.3)`, raised flash peak to 0.65 opacity + `saturate(1.8) brightness(1.3)`, intensified monochrome divergence state. Accent colors brightened across the board.
- data-fundamentals-lesson: Moved inline "Understanding Datasets & Corpora" content from `datasets.html` into a new learning lesson (`/v1/learn/data-fundamentals`) as Lesson 1 in the arc, with a custom template (`archetypes/data-fundamentals.html`) featuring the visual pipeline diagram hero + carousel steps. See `docs/vault/Sessions/2026-06-20-data-fundamentals-learning-lesson.md`.
- banner-cta-pattern: Added `.section-card--banner` CSS class (gradient bg, no shadow, compact padding) and deployed CTA cross-reference banners across 6 operational pages — Datasets → Data Fundamentals, Training → Training Loop, Playground → Sampling, Models → Export, Experiments → Loss, Operations → Cloud Compute. See `docs/vault/Discoveries/learning-lesson-cta-banner-pattern.md`.
- unicorn-mascot-flying-sprites: Made the **Unicorn** theme pop in two presence tiers. (1) *Session-gated JS* — rewrote `anvil/api/static/js/themes/unicorn.js` to inject a managed `document.body` overlay (`pointer-events:none`, the first theme to do live DOM sprite injection) with inline-SVG floating unicorns (googly wiggling eyes) and 6-band rainbows flying across, driven by loss/throughput/milestone/divergence; rAF loop now compacts node arrays each frame (fixed an unbounded leak), seeds transforms at spawn (no `(0,0)` flash), and `burst()` gates on `reducedMotion`; teardown leaves zero trace. (2) *Always-on CSS* — added `[data-skin="unicorn"] .app-shell::after`, a side-profile prancing unicorn as a `background-image` data-URI SVG that trails a rainbow from its rear and flies across the viewport re-entering at a new height each pass (composed `left` 14s / `top` 17s / `transform` 1.1s; the non-harmonic X/Y periods give the "different spot" loop with no JS). Discovered that a theme's `mapping()` only binds while a signal-bus session is attached, so always-on decoration MUST be CSS, not the JS module. Data-URI SVG encoding (`%23` for `#`, `%25` for every `%`) + in-SVG `prefers-reduced-motion` self-gating. No engine/registration/`base.html`/test changes (Unicorn was already wired). See `docs/vault/Reference/css-data-uri-animated-svg-sprite.md`, `docs/vault/Discoveries/theme-presence-tiers-css-vs-session-gated-js.md`, and `docs/vault/Sessions/2026-06-20-unicorn-mascot-flying-sprites.md`. **Follow-up**: the always-on `.app-shell::after` prancing mascot was subsequently removed at user request (to be re-added later); the session-gated JS sprite overlay, sparkle field, and theme registration remain. Implementation preserved in git history.
- content-repository-016-mvp: Implemented the US1 MVP of the versioned **Content Repository** (spec 016, ADR-033) — reproducibility-by-reference end-to-end (create corpus → register source → open isolated ingest session → stage → per-batch validate → accept/atomic-fold → freeze immutable version → pin in a training run via `content_version_id` → re-resolve byte-identically). **Local mode is pure-Python and content-addressed** (no LakeFS, no new runtime dependency, no managed sidecar): blobs at `data/content/blobs/<aa>/<sha256>`, session-scoped staging, canonical HEAD, and an `asyncio.Lock`-serialized atomic acceptance — all behind the `VersionedContentStore` ABC so a future SaaS `LakeFSVersionedContentStore` slots in unchanged (014/AD-17). Added 10 ORM models + reversible migration `002_add_content_repository`, 7 repositories, the `VersionedContentStore` interface + `LocalVersionedContentStore`, `ValidationService`/`CorpusService`/`IngestionService`/`LineageService`, a 21-endpoint `/v1/content` router, workbench accessors (with `content_dir` now read from config), and training-data resolution via the existing chunkers. The reproducibility anchor is a content-addressed **manifest digest** (sha256 of canonical-JSON sorted entries). Three test layers: unit (digest/blob/VCS contract via a fake), real store+service e2e, and HTTP-API integration (ASGI, no lifespan) — 69 tests. A critical QA pass found/fixed ~16 real integration bugs the fake-only tests had masked (broken workbench wiring + store constructor, empty-version accept, ambiguous ORM relationship, unnamed-constraint migration failure, async expired-object/lazy-load greenlet errors, missing endpoint commits, a revert unique-constraint violation, and `create`/`stage` endpoint signature mismatches). See `specs/016-lakefs-content-repo/` and `docs/vault/Decisions/ADR-033-content-repository-substrate.md`.
- concurrent-isolated-ingestion-us2: Implemented US2 — concurrent isolated content injection (spec 016). Five integration tests verifying: zero cross-visibility between concurrent sessions (SC-003), serialized atomic acceptance via asyncio.gather (FR-010), producer scoping via staging-key isolation (FR-007/036), revert correctness (FR-011), and abandoned-session retention (FR-025). Added app-level `_assert_session_scope` guard in `IngestionService.stage()` and an `AuthzContext` management-action authorization seam (`anvil/services/content/authz.py`) with a FastAPI `require_content_auth` dependency — the documented injection points for future SaaS multi-principal RBAC. Fixed a pre-existing indentation bug where `_assert_session_scope` was at module level instead of inside the class. 74 content tests pass (42 unit + 32 integration). See `docs/vault/Decisions/ADR-033-content-repository-substrate.md`.
