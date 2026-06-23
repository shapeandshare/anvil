---
title: 012 Pip Installable Package - research
type: research
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/012 Pip Installable Package/
related:
  - '[[012 Pip Installable Package]]'
created: ~
updated: ~
---
# Phase 0 Research: Pip-Installable Package

**Feature**: `009-pip-installable-package` | **Date**: 2026-06-18

This document consolidates the research that resolves the Technical Context unknowns. Each entry: **Decision**, **Rationale**, **Alternatives considered**. Findings are grounded in the existing codebase (explore agents) and authoritative external sources (librarian agents).

---

## Codebase findings (the problem, precisely located)

- **torch is NOT required for the functional end product.** The default training engine is the stdlib `anvil/core/engine.py`; `resolve_backend()` falls back to `engine="stdlib", device="cpu"` whenever torch is absent. Every `torch` import in the codebase is guarded (`try/except ImportError`, lazy, or string-flag). Base `pip install anvil` runs the full web workbench + default training with no torch. → torch stays in `[project.optional-dependencies] gpu`.
- **Three packaging gaps (the core work):**
  1. `anvil/db/migration.py:15` → `ALEMBIC_INI = Path(__file__).resolve().parent.parent.parent / "alembic.ini"` resolves to the **repo root**, which is absent in a wheel.
  2. `alembic.ini:2` → `script_location = migrations` is **CWD-relative**; `migrations/` lives at repo root, outside `anvil/`.
  3. `anvil/services/demo_bootstrap.py:27` → `DEMO_DIR = Path("data/demo")` is **CWD-relative**; `data/demo/` lives at repo root.
- **Already-correct pieces:** `anvil/api/app.py` resolves static + templates via `HERE = Path(__file__).parent` (package-relative — works in a wheel). `anvil/__init__.py` already falls back to `importlib.metadata.version("anvil")` when `pyproject.toml` is absent (works when installed). `migrations/env.py` imports `from anvil.db.base import Base` (package-aware).
- **Health endpoint exists:** `GET /v1/health` returns `{"status":"healthy","version":...,"system":...,"gpu":...}` — ideal for the compose healthcheck and system tests.
- **Phantom entry point:** `anvil-migrate-registry = "anvil.cli:migrate_registry"` references a function that does NOT exist in `cli.py`. Calling it fails at runtime.
- **Migration heads:** `migrations/versions/` contains a merge revision (`12a4027155f0_merge_002b_and_006_heads.py`) → migrations must be applied with `upgrade heads` (plural), which `MigrationService.upgrade()` already does.
- **Existing Dockerfile** copies the source tree and runs `make setup`/`make run` — it never installs a wheel, so it cannot catch the gaps above. It must be rewritten.
- **Build tooling:** project already uses `uv` (`uv sync`, `uv venv`) and `setuptools` build backend. `make clean` already removes `build dist *.egg-info`.

---

## Decision 1 — Relocate runtime resources INTO the package

**Decision**: Move `migrations/` + `alembic.ini` → `anvil/_resources/` (i.e. `anvil/_resources/migrations/`, `anvil/_resources/alembic.ini`), and `data/demo/` → `anvil/data/demo/`.

**Rationale**: setuptools only bundles files **inside the package directory** into a wheel by default. CWD-relative resources can never resolve for an installed user. Relocating makes them addressable via `importlib.resources.files("anvil")` independent of CWD, and portable to zipapp/PyInstaller. Directly satisfies FR-003, FR-003a, FR-005, FR-007. Precedent: **IBM/mcp-context-forge PR #310** (identical bug: alembic outside package → missing from wheel → moved inside, `script_location = mcpgateway:alembic`); **OpenStack Neutron** uses `package:resource` script locations in production.

**Alternatives considered**:
- *Repo-root + `MANIFEST.in`*: rejected — `MANIFEST.in` only affects the sdist, not the wheel; installed users get nothing.
- *`data-files` entries*: rejected — land in unpredictable `*.data/` install prefixes, break `importlib.resources` and zipapp portability (setuptools discussion #4105).

---

## Decision 2 — Resolve Alembic config + script_location via `importlib.resources` (no new `__init__.py`)

**Decision**: In `anvil/db/migration.py`, resolve the bundled `alembic.ini` and set `script_location` to an **absolute filesystem path** derived at runtime:
```python
import importlib.resources as ir
_RES = ir.files("anvil").joinpath("_resources")
ALEMBIC_INI = str(_RES.joinpath("alembic.ini"))          # via as_file if needed
# in _build_config: alembic_cfg.set_main_option("script_location", str(_RES.joinpath("migrations")))
```
Keep `alembic.ini`'s `script_location` value but override it programmatically so it always points at the packaged migrations dir. The env URL is already overridden at runtime (existing behavior).

**Rationale**: Using an absolute path from `importlib.resources` means Alembic receives a real directory and does NOT need package-import discovery — so **no `__init__.py` is required** inside `anvil/_resources/migrations/` or `versions/`, preserving Constitution Article VI (implicit namespace). For a normal (non-zip) wheel install, `files()` yields a real path directly; `as_file()` provides a context-managed fallback for zip-imported cases.

**Alternatives considered**:
- *`script_location = anvil:_resources/migrations` (package:resource syntax)*: works and is idiomatic Alembic, but historically nudges toward adding `__init__.py` to the versions package → conflicts with Art. VI. Kept as the documented fallback only if runtime testing shows the absolute-path approach fails under a specific install mode.
- *Fully programmatic `Config()` with no ini file*: viable, but the existing `alembic.ini` also carries logging config; bundling it is lower-risk than re-deriving logging in code.

---

## Decision 3 — Resolve demo/seed dir via `importlib.resources`

**Decision**: In `anvil/services/demo_bootstrap.py`, replace `DEMO_DIR = Path("data/demo")` with a package-relative resolver:
```python
import importlib.resources as ir
def _demo_dir() -> Path:
    with ir.as_file(ir.files("anvil").joinpath("data", "demo")) as p:
        return Path(p)
```
Resolve lazily (function/cached) rather than at import time so tests can monkeypatch if needed.

**Rationale**: Makes first-run bootstrap (`anvil-bootstrap-datasets` and the app-startup bootstrap) work from the installed package, satisfying FR-003a. The service reads `.txt` files and stores content in the DB; a resolved real path keeps the existing `Path`-based walking logic unchanged.

**Alternatives considered**: Reading each file via `files(...).joinpath(...).read_text()` — cleaner for single files but the service walks a directory tree; a resolved directory path minimizes code churn.

---

## Decision 4 — `pyproject.toml` package-data declaration

**Decision**: Add explicit package-data and enable inclusion:
```toml
[tool.setuptools.packages.find]
include = ["anvil*"]

[tool.setuptools.package-data]
anvil = [
    "_resources/alembic.ini",
    "_resources/migrations/*.py",
    "_resources/migrations/*.mako",
    "_resources/migrations/scripts/*.py",
    "_resources/migrations/versions/*.py",
    "data/demo/**/*.txt",
    "data/demo/**/*.md",
    "api/static/**/*",
    "api/templates/**/*",
]
```
Keep `requires-python = ">=3.11"` (drives pip fail-fast on unsupported runtimes — FR-006) and keep `torch`/`nvidia-ml-py` in `[gpu]`, `modal` in `[compute]` (FR-014).

**Rationale**: Explicit globs guarantee non-code resources land in the wheel rather than relying on implicit discovery (which covers Python files only). Static/templates are added explicitly even though they currently work, to remove fragility (spec FR-004/SC-003).

**Alternatives considered**: `include-package-data = true` + `MANIFEST.in` — rejected as primary because MANIFEST governs sdist; explicit `package-data` is the deterministic wheel mechanism.

---

## Decision 5 — Multi-stage Dockerfile (build wheel → install wheel into clean image)

**Decision**: Two-stage build.
- **builder** (`python:3.11-slim`): copy source, `pip install build` (or use `uv build`), run `python -m build --wheel --outdir /dist`.
- **runtime** (`python:3.11-slim`, NO source COPY): `COPY --from=builder /dist/*.whl /wheels/`, `pip install --no-cache-dir /wheels/*.whl` (pulls deps), create non-root user, `WORKDIR /workspace` (writable), `EXPOSE 8080 5001`, `CMD ["anvil"]`.

**Rationale**: Installing only the `.whl` into a source-free runtime is the only way to genuinely exercise "pip installable by a user" and surface the packaging gaps (Q1 clarification, FR-007). `python -m build` is the standard PEP 517 front-end; `anvil` console script is the documented launch command (FR-009). Non-root + dedicated workspace satisfies FR-011 and the read-only-workspace edge case.

**Alternatives considered**:
- *Single-stage `pip install .` from copied source*: rejected (Q1) — leaves source present, weaker isolation, can mask missing package-data.
- *`uv build`*: acceptable equivalent; `python -m build` chosen for tool-agnostic reproducibility, with `uv` allowed in the builder for speed.

---

## Decision 6 — docker compose: single service, in-process MLflow, named volume, healthcheck

**Decision**: `compose.yaml` (Compose Spec, no `version:` key), one `anvil` service: `build` from the Dockerfile runtime target, `ports: "8080:8080","5001:5001"`, a **named volume** mounted at the runtime workspace, and a `healthcheck` polling `http://localhost:8080/v1/health` (`interval`, `retries`, `start_period`). MLflow runs in-process (current behavior) — no separate service (Q2).

**Rationale**: Matches Q2 (single container, in-process MLflow on 5001) and Q4 (persistent named volume for normal use). `/v1/health` is a real endpoint returning `status: healthy`. Healthcheck enables `docker compose up --wait`.

**Alternatives considered**: Separate MLflow service (Q2 rejected — deployment-architecture change, deferred); ephemeral workspace by default (Q4 rejected — persistent volume chosen, with test-time reset).

---

## Decision 7 — System tests: pytest + httpx, orchestrated up/wait/test/down -v

**Decision**: New `tests/system/test_installed_runtime.py`. A Makefile `test-system` target: `docker compose down -v` (reset → fresh first-run per Q4) → `docker compose up -d --build --wait` → `pytest tests/system` → `docker compose down -v`. Tests use `httpx` against `http://localhost:8080`:
- `GET /v1/health` → 200, `status == "healthy"`.
- Each primary page (`/`, `/v1/training-page`, `/v1/datasets-page`, `/v1/experiments-page`, `/v1/models-page`, `/v1/inference-page`, `/v1/operations-page`, `/v1/learn`) → 200 + a referenced static asset resolves (no missing-asset failure).
- A representative static asset under `/static/...` → 200.
- DB init + demo bootstrap: `GET /v1/corpora` (or `/v1/datasets`) shows the bundled demo content present.
- CLI tools run inside the container via `docker compose exec`: `anvil-db current` (DB stamped), `anvil-corpus list`, `anvil-bootstrap-datasets --dry-run`. Each exits 0.

**Rationale**: Smoke/system depth "just enough" to prove a functional end product (spec test-depth clarification, FR-012/FR-013). `down -v` before each run guarantees first-run init (auto-migrate + bootstrap) is exercised (Q4, FR-011a). Phantom `anvil-migrate-registry` is **excluded** from tests.

**Alternatives considered**: `pytest-docker` plugin — viable but adds a dev dep; a Makefile + httpx keeps deps lean (Constitution). TestClient in-process — rejected: would not exercise the installed wheel/container (defeats the feature).

---

## Decision 8 — Fix the phantom `anvil-migrate-registry` entry point

**Decision**: Remove the `anvil-migrate-registry = "anvil.cli:migrate_registry"` line from `[project.scripts]` (no implementation exists; registry migration is a one-off historical script under `migrations/scripts/`). FR-007 requires "every documented command-line tool MUST be functional" — a console script that errors on invocation violates this.

**Rationale**: A declared entry point that crashes fails FR-005/FR-007 and SC-004. Removing it is the minimal correct fix; re-introducing real functionality is out of scope.

**Alternatives considered**: Implement a real `migrate_registry` — rejected as scope creep (registry migration is unrelated to pip-installability and already handled by a historical script).

---

## Decision 9 — Version discoverability (FR-015)

**Decision**: Rely on the existing `anvil.__version__` (already uses `importlib.metadata.version("anvil")` when installed). Optionally add a tiny `anvil --version` flag to `serve()`/a top-level parser; the version is also already surfaced at `GET /v1/health` (`"version"`). System tests assert `/v1/health` reports the expected version.

**Rationale**: FR-015 ("a maintainer MUST be able to determine the version") is already satisfiable via `python -c "import anvil; print(anvil.__version__)"` and `/v1/health`. A CLI `--version` is a low-cost nicety, marked optional.

**Alternatives considered**: A dedicated `anvil-version` console script — rejected as unnecessary surface area.

---

## Open items intentionally deferred (not blocking)

- Whether to add `anvil --version` CLI flag (nice-to-have; version already exposed).
- Exact static-asset chosen per page for the missing-asset assertion (a planning/impl detail for `/speckit.tasks`).
- Public-index publishing, CI, full e2e suites — explicitly out of scope per spec.
