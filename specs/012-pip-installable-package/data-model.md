# Phase 1 Data Model: Pip-Installable Package

**Feature**: `009-pip-installable-package` | **Date**: 2026-06-18

This feature is packaging/build/ops oriented; it introduces **no new database entities or schema changes**. The "entities" below are build-and-runtime artifacts and their relationships, derived from the spec's Key Entities and the Phase 0 decisions. They define what must exist, their attributes, validation rules, and lifecycle.

---

## Entity: Installable Artifact (wheel)

The single built, installable representation of anvil.

| Attribute | Value / Rule |
|---|---|
| Format | Python wheel (`.whl`), built via PEP 517 (`python -m build` / `uv build`) |
| Name | `anvil` (distribution name unchanged — no public index in this feature) |
| Version | From `pyproject.toml [project] version` (currently `0.1.0`); discoverable post-install via `importlib.metadata.version("anvil")` and `GET /v1/health` |
| Supported runtime | `requires-python = ">=3.11"` — pip MUST refuse install on < 3.11 |
| Required dependencies | All base deps from `[project] dependencies` (FastAPI, uvicorn, SQLAlchemy, aiosqlite, alembic, pydantic, jinja2, mlflow, safetensors, numpy, …) |
| Optional dependencies | `[gpu]` (torch, nvidia-ml-py), `[compute]` (modal), `[dev]` — NOT installed by default |
| Bundled non-code resources | `anvil/_resources/alembic.ini`, `anvil/_resources/migrations/**`, `anvil/data/demo/**`, `anvil/api/static/**`, `anvil/api/templates/**` |

**Validation rules**:
- VR-A1: Inspecting the wheel (`unzip -l`) MUST show all bundled non-code resources (FR-003, SC-003).
- VR-A2: The wheel metadata MUST list every base runtime dependency (FR-002).
- VR-A3: The base wheel MUST NOT pull torch/nvidia-ml-py/modal (FR-014, SC-009 lean-install).
- VR-A4: Installing on Python < 3.11 MUST fail fast with a clear message (FR-006).

**Lifecycle**: `source → build (builder stage) → .whl in /dist → pip install into runtime image → importable + console scripts available`.

---

## Entity: Packaged Resource Set

The relocated runtime resources that make the wheel self-contained.

| Resource | New location (in package) | Resolved at runtime by |
|---|---|---|
| Alembic config | `anvil/_resources/alembic.ini` | `anvil/db/migration.py` via `importlib.resources` |
| Alembic migrations | `anvil/_resources/migrations/{env.py,script.py.mako,scripts/,versions/}` | `MigrationService` `script_location` override (absolute path) |
| Demo/seed content | `anvil/data/demo/{small,medium,large}/**` | `anvil/services/demo_bootstrap.py` via `importlib.resources` |
| Static assets | `anvil/api/static/**` | `anvil/api/app.py` (`HERE`-relative — already correct) |
| Templates | `anvil/api/templates/**` | `anvil/api/app.py` (`HERE`-relative — already correct) |

**Validation rules**:
- VR-R1: No runtime resource may be resolved relative to CWD; all MUST resolve from the installed package (FR-003).
- VR-R2: Migrations MUST apply with `upgrade heads` (a merge revision exists) (research finding).
- VR-R3: Relocation MUST NOT introduce `__init__.py` into migration dirs (Constitution Art. VI; research Decision 2).

---

## Entity: Container Image

A reproducible, isolated environment that installs the artifact.

| Attribute | Value / Rule |
|---|---|
| Base | `python:3.11-slim` |
| Build strategy | Multi-stage: `builder` (builds wheel) + `runtime` (installs wheel only) |
| Source presence in runtime | NONE — only the `.whl` is copied from builder (FR-007, Q1) |
| User | Non-root |
| Workspace | Writable working dir for `data/`, `logs/`, `mlruns/` (FR-011) |
| Exposed ports | 8080 (web), 5001 (in-process MLflow) |
| Launch command | `anvil` (console script) (FR-009) |

**Validation rules**:
- VR-I1: Runtime stage MUST contain no anvil source tree (only installed package) (FR-007).
- VR-I2: Rebuild after a code change MUST reflect the new artifact (stale-image edge case).

---

## Entity: Local Orchestration Stack (compose)

The single-service composition that brings the installed package online.

| Attribute | Value / Rule |
|---|---|
| Services | One: `anvil` (MLflow in-process, Q2) |
| Ports | `8080:8080`, `5001:5001` |
| Runtime workspace | Persistent **named volume** (Q4, FR-011a) |
| Healthcheck | HTTP poll of `/v1/health` until `status: healthy` |
| Spec format | Compose Spec (no `version:` key) |

**Validation rules**:
- VR-O1: `docker compose up --wait` MUST report healthy before tests run.
- VR-O2: Workspace state MUST persist across restarts for normal use (FR-011a).
- VR-O3: System tests MUST reset the volume (`down -v`) before a run for a fresh first-run (Q4, FR-011a).

---

## Entity: Console Commands (post-install surface)

Every documented CLI must work after a wheel install (FR-005, FR-007, SC-004).

| Command | Function | Must-pass check |
|---|---|---|
| `anvil` | `anvil.cli:serve` | starts web on 8080 |
| `anvil-train` | `anvil.cli:train` | runs a CLI training step (stdlib engine) |
| `anvil-corpus` | `anvil.cli:corpus_main` | `anvil-corpus list` exits 0 |
| `anvil-stop` | `anvil.cli:stop` | stops servers |
| `anvil-bootstrap-datasets` | `anvil.cli:bootstrap_datasets_main` | `--dry-run` scans bundled demo, exits 0 |
| `anvil-db` | `anvil.cli:db_main` | `anvil-db current` reports a revision |
| ~~`anvil-migrate-registry`~~ | ~~`anvil.cli:migrate_registry`~~ | **REMOVED** — phantom (no implementation) (Decision 8) |

**Validation rules**:
- VR-C1: Every entry point remaining in `[project.scripts]` MUST be importable and runnable (FR-007).
- VR-C2: The phantom `anvil-migrate-registry` MUST be removed before release (no crashing entry points).

---

## Entity: Runtime Workspace

Predictable on-disk location for generated state (created on first use).

| Path (CWD/workspace-relative) | Purpose | Env override |
|---|---|---|
| `data/anvil-state.db` | App SQLite DB | `ANVIL_STATE_DB_PATH` |
| `logs/` | Logs + PID files | `ANVIL_LOG_DIR` |
| `mlruns/mlflow.db` + `mlruns/` | MLflow backend + artifacts | (derived) |

**Validation rules**:
- VR-W1: On first launch, the DB MUST be auto-created and migrated to HEAD (FR-005, FR-010).
- VR-W2: Demo content MUST be auto-bootstrapped on first launch (FR-003a).
- VR-W3: If the workspace is non-writable, a clear actionable error MUST surface (edge case).

---

## Entity: System Test Suite

The acceptance gate executed against the running instance.

| Attribute | Value / Rule |
|---|---|
| Location | `tests/system/test_installed_runtime.py` |
| Client | `httpx` against `http://localhost:8080`; `docker compose exec` for CLI checks |
| Result | Single pass/fail; failures identify the broken aspect (FR-013, SC-008) |
| Coverage | health, primary pages + assets, static serving, DB init, demo bootstrap, CLI tools |

**Validation rules**:
- VR-T1: Suite MUST return an unambiguous pass/fail and not depend on prior state (fresh volume) (FR-013, Q4).
- VR-T2: Suite MUST NOT invoke the removed phantom command.

---

## State transitions (end-to-end loop)

```
[source tree]
   │  build (builder stage)
   ▼
[anvil-<ver>.whl]  ──VR-A*──▶ validated artifact
   │  pip install into clean runtime image (no source)
   ▼
[container image]  ──VR-I*──▶ installed, source-free
   │  docker compose up --wait (named volume reset for tests)
   ▼
[running instance]  ──first launch──▶ auto-migrate DB + bootstrap demo (VR-W1/W2)
   │  pytest tests/system (httpx + exec)
   ▼
[PASS/FAIL]  ──VR-T*──▶ functional-end-product gate
```
