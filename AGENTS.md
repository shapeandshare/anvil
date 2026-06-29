# anvil — Agent Guidelines

**Last updated**: 2026-06-28 (constitution v1.8.0: Article XI Simplicity First / Boring Technology + ADR-041; sonarcloud-tooling + content-repository-016-mvp; scripts-python-over-bash + package-module-migration, testing-guide consolidation; OWASP remediation spec 017 + ADRs 035/036; whole-API e2e test suite 017)

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
| `make sonar-scan` | Run SonarCloud analysis (`brew install sonar-scanner` + `SONAR_TOKEN` req.) |
| `make sonar-scan-docker` | Run SonarCloud analysis via Docker (no local install) |
| `make sonar-status` | Fetch quality gate status from SonarCloud API |
| `make sonar-issues` | Fetch open bugs/vulnerabilities/code smells |
| `make sonar-measures` | Fetch quality metrics (coverage, duplications, ratings) |
| `make sonar-mcp` | Start SonarCloud MCP server for OpenCode/Claude integration (Docker) |
| `make sonar-full` | Run tests with coverage + SonarCloud analysis |
| `make ux-lint` | Run deterministic UX lint (mechanical S4 gate) |
| `make ux-review` | Run AI UX review (requires UX_API_KEY) |

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

### Testing

Test suites live under `tests/` — unit tests in `tests/unit/`, e2e HTTP tests in `tests/e2e/`. The `client` fixture (defined in `tests/conftest.py`) provides an `httpx.AsyncClient` connected to the FastAPI app with a clean in-memory SQLite database per test session.

| Test file | What it tests |
|-----------|---------------|
| `tests/unit/core/test_engine.py` | Autograd (Value backward + operations), Tokenizer (encode/decode roundtrip), LlamaModel param count, training loop (loss decreases) |
| `tests/e2e/test_setup.py` | Package imports resolve (`import anvil`, `import anvil.core.engine`) |
| `tests/e2e/test_endpoints.py` | HTTP API endpoints return 200 with correct JSON |

**Writing tests:**

Unit test pattern — create `tests/unit/<module>/test_<name>.py`:
```python
"""Unit tests for <module name>."""


def test_<behavior>():
    result = <function>()
    assert result == <expected>
```

e2e HTTP test pattern — add to `tests/e2e/test_<name>.py`:
```python
"""e2e tests for <endpoint>."""

import pytest


@pytest.mark.asyncio
async def test_<endpoint>(client):
    r = await client.get("/v1/<endpoint>")
    assert r.status_code == 200
    assert "<key>" in r.json()
```

Coverage is reported via `pytest --cov=anvil --cov-report=term-missing`. Current coverage: ~41% (TDD mandate targets 100%).

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

12. **Python over Bash for scripts** — Any new CI or utility script SHOULD be
    written in Python, not bash. Python is testable, type-checkable, and
    consistent with the rest of the codebase. Shell scripts are reserved for
    bootstrap/early-setup scenarios where the Python runtime is not guaranteed
    (e.g., Makefile helpers that must run before the venv exists). Scripts in
    ``scripts/ci/`` and ``scripts/release/`` use snake_case filenames, the
    ``if __name__ == "__main__":`` pattern, and stdlib-only dependencies.

    **Beyond "Python over bash"** — business logic for CI tooling MUST live in
    importable package modules under ``anvil/``, exposed via CLI entry points
    (``anvil-vault``), NOT as standalone scripts with duplicated code. The
    ``scripts/`` directory holds only **thin wrapper scripts** that delegate to
    ``anvil-vault`` via ``subprocess``. This makes the logic testable via
    ``pytest``, type-checkable via ``mypy --strict``, and avoids duplicating
    ``_read_version()`` / ``_parent_version()`` across files.

    Rationale: the 015-graph-health-subsumption spec established this pattern
    (FR-004: CI gate logic belongs in the package), and the version-utils
    refactor (2026-06-21) confirmed that standalone scripts inevitably
    duplicate shared helpers. Every CI job that calls ``anvil-vault`` must
    ``pip install .`` (or ``make setup``) first — this is acceptable overhead
    for correctness and maintainability.

    Correct:
    ```python
    # scripts/ci/check_version.py — thin wrapper
    def main() -> None:
        subprocess.run(["anvil-vault", "check-version"])
    ```

    Incorrect:
    ```python
    # scripts/ci/check_version.py — duplicated logic
    def _read_version(): ...  # same as 3 other files
    def main(): ...
    ```

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

13. **Simplicity First (Boring Technology)** — Favor the simplest, most boring
    solution that fully satisfies the requirement. Proven reliability and
    obviousness outrank cleverness, novelty, and speculative flexibility. This
    is a hard MUST gate (Constitution Article XI), enforced at merge review.

    Rules:
    - **Simplest viable solution** — choose the simplest approach that meets the
      requirement. Complexity is never the default; justify it with a concrete,
      present need, never a hypothetical future one.
    - **Boring over novel** — prefer mature, well-understood, widely-used
      technology and patterns. A novel/experimental dependency, framework,
      library, or pattern MUST NOT be introduced unless a simpler proven
      alternative was evaluated and explicitly rejected in an ADR or the plan's
      Complexity Tracking table. Pairs with Article I and "Lean dependencies".
    - **YAGNI** — build only what the current requirement needs. No speculative
      generality, premature abstraction, or config knobs without a present
      consumer. Add the abstraction when the *second* concrete use case arrives.
    - **Reuse before introducing** — reuse existing libraries, patterns, and
      abstractions in the codebase before adding new ones; a second parallel way
      to do the same thing is reject-worthy.
    - **Justify every deviation** — any solution more complex than the simplest
      viable alternative MUST be recorded in the Complexity Tracking table
      (`.specify/templates/plan-template.md`) with the simpler alternative and
      why it was rejected. Unrecorded complexity fails the Constitution Check.
    - **Untested paths are not done** — an approach that cannot be, or has not
      been, tested MUST NOT be treated as complete. Prefer a simpler, testable
      approach over a complex one whose correctness cannot be shown. Pairs with
      Principle 2 (TDD).

    Correct (boring, present-need only):
    ```python
    # One supported strategy today → a plain function, no plugin registry.
    def chunk_lines(corpus: str) -> list[str]:
        return corpus.splitlines()
    ```

    Incorrect (speculative generality for one caller):
    ```python
    # No second strategy exists yet — premature abstraction (violates YAGNI).
    class ChunkerFactory:
        def __init__(self, plugins: dict[str, type[Chunker]]): ...
        def build(self, name: str) -> Chunker: ...
    ```

14. **No Lazy Imports** — All ``import`` and ``from ... import`` statements MUST
    appear at the **top of the file** (module level, before any class/function
    definition). Indented imports inside function or method bodies are
    forbidden, with exactly three exceptions:

    Exceptions (verified by ``check_import_placement.py``):
    - ``TYPE_CHECKING`` blocks — ONLY for genuine circular import cycles that
      cannot be resolved by restructuring. The ``if TYPE_CHECKING:`` line MUST
      carry a ``# cycle:`` comment documenting the cycle.
    - ``try`` / ``except ImportError`` — ONLY for optional third-party
      dependencies not listed in the package's core dependencies. The
      ``except`` line MUST name ``ImportError`` specifically.
    - ``# import-placement:allow`` — Last-resort escape hatch on the line
      immediately preceding the import. MUST include a justification comment.

    **Internal (project-own) modules MUST NEVER be lazy-imported.** If a module
    is needed, import it at the top of the file — even if that means
    restructuring code to avoid circular imports. Deferred imports are
    complexity, not simplicity (Principle 13 / Constitution Article XI).

    Enforced by ``check_import_placement.py`` — zero violations allowed.
    Run via ``make lint``. This replaces the old "imports at top by default"
    guideline.

15. **Solid Comment Separators** — Section-comment separators MUST use
    solid ``#`` lines, not dashes. This means:

    .. code-block:: python

       ####################################################################
       # Section header
       ####################################################################

    Not:

    .. code-block:: python

       # ------------------------------------------------------------------
       # Section header
       # ------------------------------------------------------------------

    Rationale: solid ``#`` lines are visually unambiguous — they cannot be
    confused with docstring section underlines (``---``\ , ``===``) or
    horizontal rules. The line length should match the surrounding context
    (``# `` prefix + header text length is a good reference point).

    Enforced at merge review — any new or edited comment separator using
    dashes instead of solid ``#`` must be corrected.

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
- Imports at the TOP of the file only — see Principle 14 (No Lazy Imports). Enforced by ``check_import_placement.py`` via ``make lint``. Zero violations allowed.
- One class per file. Classes for all logic (no loose functions)
- Favor Pydantic `BaseModel` over `dataclasses.dataclass`
- `mypy --strict` enforced. Plus `enable_error_code = ["ignore-without-code", "possibly-undefined", "redundant-cast", "redundant-expr"]` and `warn_unused_ignores = true` in `pyproject.toml`. No type-error suppression (`# type: ignore`, `cast()`, `Any` abuse). Strict explicit typing on all function signatures.
- **Domain-Driven Package Decomposition**: Package boundaries follow domain boundaries. Result/error/value types tightly coupled to one service co-locate in that service's domain sub-package. Cross-domain types go in `_shared/`. Domain sub-packages use plural nouns; internal sub-packages use underscore prefix. Max 2 levels of nesting. See Constitution Article X.
- **Enums over magic strings**: See Principle 11 in Agent Behavioral Principles above.
- **Simplicity First (boring over complex/untested)**: Choose the simplest, most boring solution that meets the requirement; reuse before introducing; no speculative abstraction (YAGNI); record any justified complexity in the plan's Complexity Tracking table. Untested/untestable approaches are not "done". See Principle 13 above and Constitution Article XI.

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
- Python 3.11+ (existing repo convention) + Stdlib only — `ux_lint.py` (re/ sys/ os/), `ux_review.py` (stdlib + urllib for OpenAI-compatible API calls) (025-ux-rules-integration)
- N/A — flat files on disk (025-ux-rules-integration)
- OpenCode skills: `ux-review` (audit UI), `ux-generate` (generate compliant UI) at `.opencode/skills/` (025-ux-rules-integration)
- Python 3.11+ + FastAPI, async SQLAlchemy + aiosqlite, Jinja2, MLflow (sidecar). Backup archiving uses **stdlib only** (`tarfile`, `hashlib`, `shutil`, `tempfile`, `sqlite3`) — no new third-party deps. (027-deployment-backup-restore)
- SQLite (app DB at `data/anvil-state.db` in WAL mode; MLflow DB at `mlruns/mlflow.db`). Persistent state under `data/` and `mlruns/`. Backup archives at `data/backups/` (new, configurable via `ANVIL_BACKUP_DIR`). (027-deployment-backup-restore)
- Python 3.11+ (matches repo; uses `StrEnum`, PEP 604 unions, PEP 563 `from __future__ import annotations`) + `httpx>=0.27,<1` (transport — already a direct dep), `pydantic>=2,<3` (DTOs — already a dep). No new runtime dependencies. (026-client-sdk)
- N/A — the SDK is a stateless HTTP client; the only persisted state is an in-memory session cookie + optional API key held on the client instance. (026-client-sdk)
- Python 3.11+ + FastAPI + Jinja2 (existing project stack — no new deps) (opencode/lucky-canyon)
- N/A — static content defined as structured data in a Python module (opencode/lucky-canyon)
- Python 3.11+ (repo standard; `StrEnum`, PEP 604 unions, PEP 563 `from __future__ import annotations`) + FastAPI, async SQLAlchemy + aiosqlite, Alembic, Jinja2, uvicorn, MLflow (sidecar). **No new runtime dependencies** — boot file uses stdlib `json`; global registry uses the existing async SQLAlchemy/Alembic stack (or stdlib `sqlite3` for the host-level store — see research.md F). (opencode/witty-meadow)
- Per-instance SQLite app DB (WAL) under each workspace; a host-level global registry SQLite DB at `~/.anvil/registry.db`; per-workspace `instance.json` boot file (JSON on disk). (opencode/witty-meadow)
- Python 3.11+ (PEP 604 unions, `StrEnum`, `from __future__ import annotations`) + FastAPI, async SQLAlchemy + aiosqlite, Jinja2, `safetensors`, `numpy` (existing); `transformers`/`tokenizers` (new — behind `[finetune]` extra only) (043-subword-tokenizer-abstraction)
- `LocalFileStore` (model artifacts + co-located tokenizer files); SQLite (app DB for metadata) (043-subword-tokenizer-abstraction)
- Python 3.11+ + `huggingface_hub` (behind `[finetune]` extra for HF source); existing (040-external-model-registry)
- SQLite (anvil-state.db, WAL mode) via async SQLAlchemy + existing Alembic migrations; (040-external-model-registry)
- Python 3.11+ + FastAPI, async SQLAlchemy, Jinja2, MLflow (existing — no new deps) (039-model-warm-start)
- MLflow Model Registry — lineage via tags (039-model-warm-start)
- Python 3.11+ (existing repo convention) + FastAPI, Jinja2, existing widget JS framework — no new dependencies (opencode/cosmic-eagle)
- N/A — static content pages (opencode/cosmic-eagle)
- Python 3.11+ + FastAPI, async SQLAlchemy, Jinja2, MLflow (existing — no new deps) (014-model-warm-start)
- MLflow Model Registry (registered_models / model_versions tables) — lineage via tags (014-model-warm-start)
- Python 3.11+ + FastAPI, async SQLAlchemy + aiosqlite, Jinja2 (existing stack); no new runtime deps (053-fine-tuning-dataset-preparation)
- `LocalFileStore` at `data/datasets/<id>/prepared/`; SQLite (anvil-state.db) for metadata (053-fine-tuning-dataset-preparation)

## Recent Changes
- 025-ux-rules-integration: Added Python 3.11+ (existing repo convention) + Stdlib only — `ux_lint.py` (re/ sys/ os/), `ux_review.py` (stdlib + urllib for OpenAI-compatible API calls)
- 025-ux-rules-integration: Added OpenCode skills `ux-review` and `ux-generate` for UI compliance; UX ruleset at `docs/ux-rules.md`
- 039-model-warm-start: Model warm-start via optional `base_model_ref`;
  torch engine warm-start parity; registry lineage
- 040-external-model-registry: External model import; HuggingFace Hub &
  local-file ModelSource; async job-based import; `finetune` extra
