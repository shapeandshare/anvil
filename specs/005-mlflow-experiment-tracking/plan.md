# Implementation Plan: MLflow Experiment & Data Lifecycle Tracking

**Branch**: `005-mlflow-experiment-tracking` | **Date**: 2026-06-13 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/005-mlflow-experiment-tracking/spec.md`

## Summary

Complete and correct the workbench's partial MLflow integration, now layered on the post-`main` codebase (dual stdlib/torch engine, GPU detection, async CLI, `mlflow` declared at 2.x). The feature: (1) **bumps MLflow to 3.x** (`>=3.1,<4`) and adds `nvidia-ml-py`; (2) routes ALL MLflow access through a single `TrackingService` whose canonical destination is the **HTTP tracking-server URI** from `get_config()`, removing four hardcoded literals; (3) attaches dataset/corpus **input lineage** (content digests) to every run; (4) creates the `Experiment` lifecycle record at run **start** with statuses `running`/`finished`/`failed`, plus startup **orphan reconciliation**; (5) tracks **CLI** training too; (6) records **backend+device** (`stdlib`/`torch`, `cpu`/`cuda`/`mps`) as run params; (7) captures **system metrics** including a **custom MPS collector** alongside CUDA; (8) **auto-registers every successful run as a new version of a source-keyed registered model** (1 dataset/corpus → 1 registered model → N versions) and **deprecates the local registry**; (9) adds first-class **managed evaluation datasets** (`mlflow.genai`, enabled by the 3.x bump).

Technical approach: a single async `TrackingService` (`anvil/services/tracking.py`) owns URI resolution, run lifecycle, lineage, metrics, artifacts, source-keyed registration, and genai datasets; blocking MLflow calls run via `run_in_executor`. Helper modules: `MlflowInputResolver` (FR-005 source→lineage decision + digest), `mlflow_capabilities` (genai detection), and a `metrics_collectors` module housing the custom MPS sampler. Orphan reconciliation and `enable_system_metrics_logging()` hook into the FastAPI `lifespan`. Web + CLI training both call `TrainingService` → `TrackingService`.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI, SQLAlchemy (async) + aiosqlite, Alembic, Jinja2, `psutil`; **CHANGED**: `mlflow` `>=2.16,<3` → **`>=3.1,<4`** (core dep); **NEW**: `nvidia-ml-py` added to the **`gpu` optional extra** (CUDA metrics; opt-in per Article I); torch is the existing optional `gpu` extra (drives the torch backend)
**Storage**: App metadata in SQLite (`data/microgpt.db`, async SQLAlchemy + Alembic). MLflow data via the supervisor-managed `mlflow server` (SQLite backend `mlruns/mlflow.db`, artifacts under `mlruns/`), reached over HTTP.
**Testing**: pytest + pytest-asyncio (`asyncio_mode=auto`); httpx `AsyncClient`+`ASGITransport`; **100% coverage enforced (`fail_under=100`)**
**Target Platform**: Local-first LAN server; macOS/Apple Silicon (MPS) is the primary dev platform, Linux/CUDA also supported; single host
**Project Type**: Single Python package (web service + CLI), layered: Repository → Service → God Class → Routes/CLI
**Performance Goals**: Tracking overhead must not perceptibly slow training; per-step metric logging is best-effort/non-blocking; system-metric sampling at MLflow's default interval
**Constraints**: Core engine (`anvil/core/`) MUST remain stdlib-only — all MLflow/psutil/pynvml code lives in services/api, never in `core/` (the torch backend already lives in `core/torch_engine.py` and is import-guarded). Async throughout except core; imports at top of file; classes for logic; no circular imports; implicit namespace.
**Scale/Scope**: Single-process, single-rank training; tens–hundreds of experiments; small custom-JSON model artifacts

**Key resolved unknowns** (detail in [research.md](./research.md)):
- MLflow **3.x mandate** re-enables `mlflow.genai` managed datasets (US6); current pin `>=2.16,<3` MUST be bumped.
- Canonical destination = **HTTP server URI** (`http://127.0.0.1:5000`); clients never open sqlite directly; required for genai + avoids concurrent-write contention.
- **Source-keyed auto-registration**: registered-model name derived from a stable per-source key; create-or-reuse + `create_model_version` on each successful run; failed runs register nothing.
- **MPS metrics**: MLflow system metrics cover CUDA (via `nvidia-ml-py`) only; a custom collector samples MPS utilization (via `ioreg`/IOKit `AGXAccelerator → PerformanceStatistics`, stdlib `subprocess`, **no `sudo`/no new dep**) and memory and logs to the run. (`psutil`/`torch.mps` cannot provide GPU utilization — torch.mps is memory-only.)
- Orphan reconciliation: `search_runs("attributes.status = 'RUNNING'")` → `set_terminated(run_id, "KILLED")`.
- **Article IX (Pit of Success)**: tracking + GPU are opt-in layers; tracking-server-down → untracked run + non-blocking warning (never error/block); GPU-unavailable → silent CPU fallback; `TrackingService` operates in a degraded no-op mode rather than propagating `TrackingUnavailable` to fail a run.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Authoritative constitution: root `CONSTITUTION.md` v1.1.0 (mirrored in `.specify/memory/constitution.md`). Compliance:

| Article | Compliance | Status |
|---|---|---|
| I. Zero-Dependency Core | All MLflow/psutil/pynvml confined to services/api; `core/` untouched (torch already isolated + guarded); `nvidia-ml-py` placed in the `gpu` extra (opt-in layer) | PASS |
| III. Seeded Reproducibility | Run params (incl. resolved engine/device) + dataset/corpus digests logged for exact reproduction | PASS |
| IV. TDD Mandatory (100% coverage) | Tasks ordered test-first; injected client factory makes MLflow deterministic | PASS (enforced in tasks) |
| V. Async-First | Service async; blocking MLflow/pynvml calls via `run_in_executor`; MPS sampler on a thread | PASS |
| VI. Implicit Namespace | No new `__init__.py`; relative imports | PASS |
| VII. Layered Architecture | New `TrackingService` + helpers in services; routes/CLI call it; repositories handle Experiment lifecycle | PASS |
| **IX. Pit of Success** | Tracking + GPU are opt-in layers that **degrade silently**: tracking-server-down → untracked run with a non-blocking warning (FR-009, reframed); GPU requested-but-absent → CPU fallback, params record the resolved device (FR-011); GPU/genai deps absent → graceful no-op (FR-022/031). No `raise`/error solely for an absent optional dependency. | PASS |

**Gate result: PASS.** Deprecating the local registry reduces complexity. The one notable new build effort — the custom MPS metrics collector (spec Q4 → B) — is justified by FR-020/SC-006 and isolated in a dedicated module; recorded in Complexity Tracking. ADRs to be written as **ADR-004** (MLflow 3.x + HTTP-server canonical URI) and **ADR-005** (source-keyed registry consolidation), following the existing ADR-001/002/003.

## Project Structure

### Documentation (this feature)

```text
specs/005-mlflow-experiment-tracking/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── tracking-service.md   # Internal service seam
│   └── http-api.md           # External HTTP API deltas
└── tasks.md             # Phase 2 (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
microgpt/
├── core/                          # UNTOUCHED (engine.py stdlib; torch_engine.py already isolated)
├── gpu.py                         # reuse detect_gpu()/resolve_device() for device params + MPS detection
├── config.py                      # EDIT: mlflow_uri → canonical HTTP server URI; add mlflow_backend_store_uri (abs sqlite)
├── db/
│   ├── models/training_config.py  # EDIT: Experiment lifecycle (run_name, statuses, corpus_id, input_digest, input_role)
│   └── repositories/experiments.py # EDIT: create_running, mark_finished, mark_failed, find_orphaned
├── services/
│   ├── tracking.py                # NEW: TrackingService — sole MLflow seam
│   ├── mlflow_inputs.py           # NEW: MlflowInputResolver (FR-005) + content digest
│   ├── mlflow_capabilities.py     # NEW: genai/version capability detection
│   ├── metrics_collectors.py      # NEW: custom MPS accelerator-metrics sampler (FR-020/031)
│   ├── training.py                # EDIT: emit run lifecycle via TrackingService; device/backend params
│   ├── experiments.py             # EDIT: read via canonical URI
│   └── models.py                  # DEPRECATE: stop local-registry writes; transition helper
├── supervisor/services.py         # EDIT: backend-store + tracking URI from get_config()
├── api/
│   ├── app.py                     # EDIT: lifespan → enable system metrics + reconcile orphans
│   └── v1/
│       ├── training.py            # EDIT: delegate to TrackingService; Experiment at start; source-keyed auto-register on success
│       ├── experiments.py         # EDIT: canonical URI; expose run_name/status/digest
│       ├── registry.py            # EDIT: redirect/retire local-registry writes → MLflow registry
│       ├── eval_datasets.py       # NEW: managed eval dataset endpoints (genai)
│       └── router.py              # EDIT: register eval_datasets router
└── cli.py                         # EDIT: train() creates a tracked run via TrackingService; --dataset

migrations/versions/
└── 0XX_experiment_lifecycle.py    # NEW: Alembic autogen for Experiment changes

tests/  (mirrors existing tests/unit, tests/integration, tests/e2e, tests/test_api layout)
└── … per-story test files (see tasks.md)

docs/vault/Decisions/
├── ADR-00X-mlflow-3x-and-canonical-uri.md          # NEW
└── ADR-00Y-source-keyed-registry-consolidation.md  # NEW
```

**Structure Decision**: Single-package layered structure (existing). All MLflow logic concentrates behind `TrackingService`; the custom MPS sampler is isolated in `metrics_collectors.py`. Core engine stays dependency-free. DB change via Alembic autogen per `make db-revision`.

## Implementation Phases (high-level; tasks come from /speckit.tasks)

Ordered by spec priority, each independently testable:

1. **Foundation**: bump `mlflow>=3.1,<4` + add `nvidia-ml-py`; `TrackingService` skeleton + capability detection; canonical HTTP-server URI in config/supervisor/all clients (remove 4 hardcodes). → US2, FR-006/008/009/026/031.
2. **Run lifecycle record**: `Experiment` at start; statuses `running`/`finished`/`failed` + `run_name`; Alembic migration; repository methods. → FR-010/011/015/016.
3. **Provenance/lineage**: `MlflowInputResolver` + digests; `log_input` for dataset/corpus/validation/metadata. → US1, FR-001–005.
4. **Metrics + device params**: per-step loss on consistent axis + distinct `final_loss`; backend/device params (extend existing GPU-param logging). → US3, FR-012/013/014/011.
5. **CLI tracking**: route `cli.train()` through `TrackingService`; add `--dataset`. → US2/US3, FR-008.
6. **Failure & orphans**: fail on exception; startup reconciliation. → US4, FR-015/016/028.
7. **System metrics + MPS collector**: enable MLflow system metrics (CUDA via nvidia-ml-py) + custom MPS sampler. → US5, FR-020/031.
8. **Source-keyed registry consolidation**: auto-register every successful run as a version of the input-source registered model; default-source model; deprecate local registry + redirect `POST /v1/registry/models`; transition existing rows; ADR. → FR-017/018/019/027/029/030.
9. **Managed evaluation datasets**: `mlflow.genai` create/append/query; graceful fallback. → US6, FR-021/022/023.

## Complexity Tracking

| Added Complexity | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Custom MPS accelerator-metrics collector (`metrics_collectors.py`) | Spec Q4→B / FR-020 require accelerator metrics on ALL accelerators incl. MPS; MLflow covers CUDA only | CUDA-only scope (rejected by user); dropping MPS metrics would make SC-006 unachievable on the primary dev platform |

## Post-Design Constitution Re-check

After Phase 1 (data-model + contracts): still PASS. Design adds one service + three helper modules (no new layers), reuses repository/migration patterns, keeps `core/` stdlib-only, confines MLflow/psutil/pynvml to services/api, and removes a parallel registry. The MPS collector is the only net-new subsystem and is isolated + capability-gated. No further justification required.
