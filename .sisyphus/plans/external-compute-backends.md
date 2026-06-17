# Plan: Pluggable External Compute Backends for anvil

> **Status**: DECISION-READY (not yet approved). Full-fidelity plan grounded in (a) cross-referenced vendor research [Modal, SkyPilot, Metaflow, ZenML, MLOps landscape], (b) codebase mapping of anvil's service/CLI/DB/API/test layers, (c) the anvil Constitution v1.2.0, and (d) an Oracle architecture review.
>
> **Author**: Sisyphus | **Date**: 2026-06-16

---

## 0. TL;DR — What We're Building & The Core Decisions

We add an **opt-in, swappable "compute backend" layer** so anvil can run training on external compute (starting with **Modal** serverless GPU), while keeping **MLflow + safetensors → Hugging Face Hub** as the portable, lock-in-free spine. Each backend doubles as a `/v1/learn` lesson.

**The four load-bearing design decisions (Oracle-validated):**

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | **String-key registry + thin `Protocol`** (NOT a ZenML-style ABC hierarchy) | anvil's service layer uses zero ABCs; mirrors the existing `engine_backend` string dispatch + `client_factory` injection. `Protocol` gives `mypy --strict` safety without inheritance. |
| D2 | **Normalized `ComputeResult` value object** replaces "return a model object" | The real seam is *local in-process model* vs *remote artifact URI*. Unify both behind one typed result. |
| D3 | **Submit-then-poll for remote** (NOT a blocking `run_in_executor` await) | Remote jobs outlive the request; poll for status, emit SSE `submitted`/`status`/`metrics`/`complete`. |
| D4 | **Capability-scoped fallback** | Implicit "GPU→CPU" still silently falls back (Art IX). Explicit "I chose Modal" that fails → **visible error**, never silent local downgrade. |

**Scope of Phase 1 (this plan):** the abstraction + adapt BOTH existing local engines (`stdlib`, `torch`) behind it + ONE remote backend (`modal`) + one `/v1/learn` lesson. SkyPilot/Metaflow are explicitly **deferred** (Section 9).

---

## 1. Why (Problem Statement)

anvil trains locally only. The user wants full model-lifecycle management on external compute, supporting many vendors/paradigms as pluggable modules, minimizing vendor lock-in, with each backend teachable as a lesson.

**Cross-referenced landscape (validated against official docs + reputable MLOps sources):**

- **Compute layer**: Modal (serverless GPU, `@app.function`+`.remote()`/`.starmap()` fan-out, `CloudBucketMount` S3, `modal.Secret`), SkyPilot (18+ clouds, one portable Apache-2 YAML, `sky jobs launch`, managed spot), raw IaaS (RunPod/Lambda/Hetzner).
- **Orchestration layer**: Metaflow (`FlowSpec`/`foreach`, `@batch`/`@kubernetes`, flow≠compute), Prefect/Dagster/Flyte, ZenML (pluggable stack components — the *pattern* we mirror, not adopt).
- **Tracking/registry layer**: MLflow (anvil already has this), HF Hub (free registry, anvil already exports safetensors).
- **Serving layer** (currently MISSING in anvil): BentoML/KServe/Ray Serve — flagged as the biggest true lifecycle gap; **out of scope here**, noted for the roadmap.

**Critical caveat that shapes sequencing (do not skip):** `train_torch` (anvil/core/torch_engine.py) runs a **single-example, per-token Python loop** on tiny models (`n_embd=16`, `n_layer=1`). It is **not batched/vectorized** → currently **CPU-bound, not GPU-bound**. Remote GPU is **pedagogically valuable** (teaches the lifecycle) but **compute-wasteful** until the engine is vectorized. This plan therefore treats remote backends as a *teaching + orchestration* vehicle, and lists engine vectorization as a separate prerequisite for GPU payoff (Section 9).

---

## 2. Constitution Compliance Map

| Article | Requirement | How this plan complies |
|---------|-------------|------------------------|
| I — Zero-Dep Core | `anvil/core/` stdlib-only | Backends live in `anvil/services/compute/`. **No core changes.** Local backends *call* existing `train()`/`train_torch()`, never modify them. |
| II — Educational Clarity | Readability > perf | Each backend is a small, readable adapter; each becomes a `/v1/learn` lesson. |
| III — Seeded Reproducibility | Deterministic, log config | Backends pass through seed/config; remote runs log full config to MLflow. |
| IV — TDD Mandatory | Tests first, 100% cov, mypy strict | Section 7 lists test files written **before** impl; all vendor I/O behind injected factories → 100% coverage with no cloud calls. |
| V — Async-First | web/service/db async | `TrainingService` stays async; remote = submit-then-poll async; sync compute stays in `run_in_executor`. |
| VI — Implicit Namespace | `__init__.py` only for public API | New `anvil/services/compute/` package: no `__init__.py` side-effect wiring; explicit imports. |
| VII — Layered | Repo→Service→God→Routes/CLI | Backends are Service-layer plain classes. DB writes stay in repositories. MLflow/export/persistence stay in the existing `on_complete` owner (route/CLI). |
| VIII — iOS Polish | Polished UI | Backend selector + lesson follow existing `training.html`/`concept.html` patterns + DESIGN.md tokens. |
| IX — Pit of Success | Default works; silent fallback | Default `compute_backend=auto` → local always works. **Capability-scoped fallback** (D4): implicit upgrades fall back silently; explicit remote selection fails visibly. |
| Constraints | Reversible Alembic; deps in optional-deps; ADR; mypy strict | `modal` goes in `[project.optional-dependencies]`; one reversible migration; one ADR; mypy strict throughout. |

**ADR required** (Constitution "Additional Constraints"): `docs/vault/Decisions/ADR-XXXX-pluggable-compute-backends.md` documenting D1–D4 and the `modal` optional dependency.

---

## 3. Architecture

### 3.1 The Abstraction (D1 + D2)

New package `anvil/services/compute/`:

```
anvil/services/compute/
├── result.py          # ComputeResult value object + ComputeStatus enum (D2)
├── protocol.py        # ComputeBackendProtocol (PEP 544, typing-only, NO ABC) (D1)
├── registry.py        # string-key registry: name -> backend factory (D1)
├── errors.py          # ComputeBackendUnavailable, RemoteSubmissionError (degraded-mode style)
├── local.py           # LocalStdlibBackend, LocalTorchBackend (adapt existing engines)
└── modal_backend.py   # ModalBackend (opt-in; imports modal lazily)
```

**`ComputeResult` (result.py)** — the unifying seam:

```python
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from anvil.core.engine import LlamaModel

class ComputeStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    SUBMITTED = "submitted"   # remote, not yet finished
    RUNNING = "running"

@dataclass
class ComputeResult:
    status: ComputeStatus
    # LOCAL path: in-process model present, export happens locally
    model: LlamaModel | None = None
    final_loss: float | None = None
    samples: list[str] = field(default_factory=list)
    uchars: list[str] = field(default_factory=list)
    # REMOTE path: artifacts already produced in cloud/S3
    artifact_uris: dict[str, str] = field(default_factory=dict)  # e.g. {"safetensors": "s3://..."}
    remote_job_id: str | None = None
    exported_remotely: bool = False  # if True, skip local export
    error_message: str | None = None
    # provenance
    engine: str = "stdlib"     # stdlib | torch  (the compute ENGINE)
    backend: str = "local"     # local | modal   (the EXECUTION location)
```

**`ComputeBackendProtocol` (protocol.py)** — typing only, satisfies mypy strict without inheritance:

```python
from __future__ import annotations
from typing import Protocol, Callable, Awaitable
from anvil.services.compute.result import ComputeResult

ProgressCallback = Callable[[int, float], None]
StopCheck = Callable[[], bool]

class ComputeBackendProtocol(Protocol):
    name: str
    def is_available(self) -> bool: ...
    async def run(
        self,
        docs: list[str],
        config: dict,
        *,
        progress_callback: ProgressCallback,
        stop_check: StopCheck,
    ) -> ComputeResult: ...
    # Remote backends additionally implement poll/cancel (duck-typed, optional):
    # async def poll(self, job_id: str) -> ComputeResult: ...
    # async def cancel(self, job_id: str) -> None: ...
```

**`registry.py`** — mirrors the existing `engine_backend` string dispatch:

```python
from __future__ import annotations
from typing import Callable
from anvil.services.compute.protocol import ComputeBackendProtocol

# factory takes injected dependencies (client_factory etc.) for testability
_REGISTRY: dict[str, Callable[..., ComputeBackendProtocol]] = {}

def register(name: str, factory: Callable[..., ComputeBackendProtocol]) -> None: ...
def get_backend(name: str, **deps) -> ComputeBackendProtocol: ...
def available_backends() -> list[str]: ...  # for UI dropdown + lesson
```

### 3.2 Resolution + Fallback Logic (D4)

New helper, e.g. `anvil/services/compute/resolve.py` (or inside registry):

```
resolve_backend(config) -> (backend_name, engine, device, fallback_note)
```

**Input contract (resolves the UI/`use_gpu` question — Momus blocker #1):** the browser/CLI sends a SINGLE field `compute_backend` whose value is one of: `auto` | `local-cpu` | `local-gpu` | `modal`. **The `use_gpu` boolean is RETIRED end-to-end** (removed from the `training.html` payload, the `POST /v1/training/start` body parsing at `anvil/api/v1/training.py` ~L54, and the CLI). Local GPU-vs-CPU is now expressed by the explicit backend value, not a separate toggle. The CLI `--gpu` flag (Section 4.2) is kept ONLY as a convenience alias that maps to `compute_backend=local-gpu` (and `--device` still overrides the resolved device string).

Rules:
- `compute_backend` absent or `"auto"`: pick `torch`+GPU if torch and an accelerator are available, else `stdlib`+CPU. **device GPU→CPU silent fallback preserved** (implicit capability — Art IX OK).
- `compute_backend == "local-cpu"`: force `stdlib` engine on CPU.
- `compute_backend == "local-gpu"`: prefer `torch` on the detected accelerator; if torch/accelerator unavailable → **silently fall back to CPU** (implicit capability downgrade — Art IX OK; this is "GPU missing → CPU", NOT "cloud → local").
- `compute_backend == "modal"` (EXPLICIT remote): if `ModalBackend.is_available()` is False (modal not installed / not authed) → **DO NOT silently fall back**. Mark run failed, emit SSE `error` with actionable message ("Modal selected but not installed: `pip install anvil[modal]` and run `modal token new`"). This is the D4 line — explicit remote selection never silently downgrades to local.

> **Backend-selector option labels** (Section 6.1) map 1:1 to these values: `Auto` → `auto`, `Local (CPU)` → `local-cpu`, `Local (GPU)` → `local-gpu`, `Modal (cloud GPU)` → `modal`. The `Local (GPU)` option renders disabled (with tooltip) when no accelerator is detected.

### 3.3 The Execution Seam in `TrainingService` (D2 + D3)

Refactor `TrainingService.start_training()` (anvil/services/training.py) to orchestrate **phases** instead of the current boolean dispatch at ~line 222:

```
1. load docs (unchanged, run_in_executor)
2. resolve backend  (new: resolve_backend(config))
3. backend.run(...) returns ComputeResult
     - LocalBackend: wraps existing train()/train_torch() in run_in_executor,
       returns ComputeResult(status=COMPLETED, model=..., ...)  [synchronous-ish, as today]
     - ModalBackend: submits job, emits SSE 'submitted', polls async loop,
       emits periodic 'status'/'metrics', returns ComputeResult(status=COMPLETED, artifact_uris=..., exported_remotely=True)
4. emit SSE events throughout (existing queue contract preserved)
5. call on_complete(result, config)   <-- SIGNATURE CHANGES: ComputeResult, not model
```

**`on_complete` contract change (D2):** today `on_complete(model, config, final_loss, samples, uchars)`. New: `on_complete(result: ComputeResult, config: dict)`. The two callers (anvil/cli.py ~line 187, anvil/api/v1/training.py ~line 190) update to:
- If `result.model is not None` (local): export safetensors locally + MLflow log + DB persist (existing logic, just unwrap from `result`).
- If `result.exported_remotely` (remote): MLflow logging ALREADY happened inside the Modal job (set `MLFLOW_TRACKING_URI`, called `log_artifact`/`log_model` → presigned upload to S3 via proxy-mode server). Local `on_complete` **skips local export** and does **metadata-only** `register_source_model(...)` with the existing `runs:/<run_id>/model` source — zero artifact transfer. See **Q-B correction (Section 8)** for why "register raw S3 URIs" is mechanically unsupported. `result.artifact_uris` carries the `runs:/` reference for provenance.

### 3.4 `engine_backend` column semantics (Oracle catch — critical)

The `Experiment.engine_backend` column is `String(16)` and today means the *compute engine* (`stdlib`/`torch`). Vendor-qualified values risk **(a) semantic muddle** and **(b) length overflow**.

**Decision:** Add **two** columns via one reversible Alembic migration (`011_add_compute_columns.py`):
- `execution_backend: str | None = mapped_column(String(32), nullable=True)` — holds `local|modal`. `engine_backend` keeps meaning `stdlib|torch`. (Avoids the `String(16)` overflow and keeps analytics clean.) Default existing rows to `"local"`.
- `remote_job_id: str | None = mapped_column(String(128), nullable=True)` — the cloud job handle for remote runs; NULL for local. Enables orphan reconciliation (Section 10) via the existing `find_orphaned` pattern.

`ExperimentRepository` gains `set_remote_job_id(experiment_id, job_id)` and reuses `mark_finished`/`mark_failed` for status transitions, following the existing repository conventions.

---

## 4. Configuration & CLI

### 4.1 New env vars (anvil/config.py `get_config()`)

| Env var | Default | Meaning |
|---------|---------|---------|
| `ANVIL_COMPUTE_BACKEND` | `"auto"` | auto \| local-cpu \| local-gpu \| modal |
| `ANVIL_MODAL_GPU` | `"T4"` | GPU type for Modal functions |
| `ANVIL_MODAL_TIMEOUT` | `"3600"` | Modal function timeout (s) |
| `ANVIL_REMOTE_S3_BUCKET` | `""` | artifact bucket for remote runs |

Credentials (`MODAL_TOKEN_ID/SECRET`, AWS keys, remote `MLFLOW_TRACKING_URI`) are **NOT** anvil config — they live in `modal.Secret` / environment, and must **never** be logged into SSE/DB (Section 8 Q-E). `get_config()` reads only the bucket name + tuning knobs.

### 4.2 CLI (`anvil/cli.py` `train()`)

Add `--backend {auto,local-cpu,local-gpu,modal}` (argparse) before `parse_known_args()` (~line 115). Maps to `config["compute_backend"]`. `--gpu` is kept ONLY as a convenience alias → `compute_backend=local-gpu` (and is mutually exclusive with an explicit `--backend`); `--device` still overrides the resolved device string. **`use_gpu` is removed from the config dict** — `resolve_backend()` is the single source of truth.

`make train` invocation style unchanged (`python -c "from anvil.cli import train; train()"`). Remote tools that need `python -m anvil train` (research showed SkyPilot/Modal patterns) → add a minimal `anvil/__main__.py` delegating to `cli.train()` **only when** we add SkyPilot (deferred). Not needed for Modal (uses `.remote()`, not a CLI shell).

---

## 5. Modal Backend (the one remote backend in Phase 1)

`anvil/services/compute/modal_backend.py` — validated against Modal docs:

- **Lazy import**: `import modal` inside methods/`is_available()`, guarded by try/except → `is_available()` returns False if not installed. (Keeps base install clean; Art I/IX.)
- **Image**: `modal.Image.debian_slim("3.11").uv_pip_install("torch","mlflow").add_local_dir("anvil","/root/anvil")`. (`boto3`/S3 creds NOT needed in MLflow proxy mode — see Q-B.)
- **Function**: `@app.function(gpu=ANVIL_MODAL_GPU, timeout=..., secrets=[Secret.from_name("anvil-mlflow")])`. Inside: `from anvil.core.torch_engine import train_torch; train_torch(docs, device="cuda", ...)`, then `SafetensorsExportService().export(model, tmpdir, uchars)` to the job's OWN temp dir, then `mlflow.set_tracking_uri(MLFLOW_TRACKING_URI); mlflow.log_artifact(...)` — MLflow proxy-mode server issues a presigned URL and the files upload straight to S3 (no S3 creds in Modal). Returns `runs:/<run_id>/model` provenance. (Q-B-corrected: log FROM the job, not register S3 URIs after.)
- **MLflow server prerequisite**: the central tracking server must run in **proxy artifact mode** (`mlflow server --artifacts-destination s3://<bucket>/mlflow-artifacts`). Document in the ADR + ops page. For purely local Modal testing this falls back to the existing local `mlruns/` server (the Modal job then logs to the URI reachable from the job).
- **Submit-then-poll (D3)**: `.spawn()` returns a handle; poll `handle` status in an async loop, translate to SSE `status`/`metrics`, fetch final result → `ComputeResult(exported_remotely=True, artifact_uris={...})`.
- **Testability (Art IV)**: the Modal app + function are constructed via an **injected runner factory** (`runner_factory: Callable`), so tests pass a `FakeModalRunner` returning canned job states. No real cloud calls; 100% coverage achievable.
- **Fan-out (future)**: `.starmap()` for hyperparameter sweeps — noted, not Phase 1.

---

## 6. UI & Learn Lesson

### 6.1 Backend selector (`training.html`)

Replace the GPU toggle checkbox (`anvil/api/templates/archetypes/training.html` ~lines 113–121) with a `<select id="compute_backend">` whose options map 1:1 to the resolve contract (Section 3.2): `Auto` → `auto`, `Local (CPU)` → `local-cpu`, `Local (GPU)` → `local-gpu`, `Modal (cloud GPU)` → `modal`. JS `startTraining()` (~line 1028) sends `compute_backend: select.value` and **no longer sends `use_gpu`**. Backend route (`anvil/api/v1/training.py` ~line 54) reads `compute_backend` (string) and **stops reading `use_gpu`**. Populate options + availability from `GET /v1/compute/backends` (new route, see below) so `Local (GPU)` and `Modal (cloud GPU)` render **disabled with a tooltip** when unavailable (iOS polish, Art VIII).

**`GET /v1/compute/backends` response shape** (so the dropdown can disable+tooltip): returns `[{"value": "auto", "label": "Auto", "available": true, "reason": null}, {"value": "local-gpu", "label": "Local (GPU)", "available": false, "reason": "No accelerator detected"}, {"value": "modal", "label": "Modal (cloud GPU)", "available": false, "reason": "modal not installed"}, ...]`. (Note: `registry.available_backends()` is extended to return these dicts, not bare strings.)

### 6.2 SSE additions

Existing events `metrics|complete|error` preserved. Add `submitted` (remote job accepted) and `status` (remote state transitions). Frontend `sse.js` adds two listeners; degrade gracefully if absent.

### 6.3 `/v1/learn` lesson — "Training in the Cloud"

Follow the data-driven pattern in `anvil/api/v1/router.py`:
- Add `CLOUD_COMPUTE_STEPS = [...]` (steps: "Why external compute?", "Local vs serverless", "Modal: submit & poll", "Artifacts in S3", "MLflow as the portable spine", "Lock-in & portability").
- Add entry to `LEARNING_ARC`.
- Add route `@router.get("/learn/cloud-compute")` rendering `concept.html` with `_arc_context("cloud-compute")`.
- Optional widget `anvil/api/static/js/widgets/cloud-compute.js` (`window.CloudComputeWidget`) animating submit→poll→artifact flow (pure frontend, no API needed, like `DataFlowWidget`); register in `concept.html`.

---

## 7. TDD Plan (tests FIRST — Art IV, 100% coverage)

Written before implementation, mirroring anvil's conventions (Fake clients + `client_factory`/runner injection; `patch("subprocess.run")` n/a for Modal; `monkeypatch` for lazy-import availability; `tempfile` for artifacts).

| Order | Test file | Covers |
|-------|-----------|--------|
| 1 | `tests/unit/services/compute/test_result.py` | `ComputeResult`/`ComputeStatus` construction, local vs remote shapes |
| 2 | `tests/unit/services/compute/test_registry.py` | register/get/available; unknown key raises |
| 3 | `tests/unit/services/compute/test_resolve.py` | auto→stdlib/torch; GPU→CPU silent fallback; explicit modal-unavailable → failure (D4) |
| 4 | `tests/unit/services/compute/test_local_backend.py` | stdlib & torch adapters return correct `ComputeResult(model=...)`; matches legacy tuple |
| 5 | `tests/unit/services/compute/test_modal_backend.py` | `is_available()` False when modal absent (monkeypatch import); submit→poll→result via `FakeModalRunner`; degraded/error paths; secrets never in result |
| 6 | `tests/unit/services/test_training_phases.py` | refactored `start_training` phases; SSE event sequence incl. `submitted`/`status`; `on_complete(ComputeResult)` for both local & remote |
| 7 | `tests/unit/api/test_compute_backends_route.py` | `GET /v1/compute/backends` availability flags |
| 8 | `tests/unit/db/test_execution_backend_column.py` | new column + repo writes `execution_backend` |
| 9 | `tests/unit/api/test_training_start_backend_select.py` | `compute_backend` flows route→service; explicit modal-unavailable returns visible error |

`make test` (100% `fail_under`) + `make typecheck` (mypy strict) + `make lint` must pass. Every Modal/cloud touchpoint behind injected callables → no network in tests.

---

## 8. Open Decisions for YOU (the "we will decide" items)

| ID | Question | Recommended default | Alternatives |
|----|----------|---------------------|--------------|
| Q-A | Phase 1 remote backend = **Modal** only? | **Yes — Modal** (lowest effort, validated, Python-native, `.remote()` no CLI needed) | SkyPilot first (more portable, but needs `__main__.py` + YAML + cloud creds) |
| Q-B | Remote artifact handling | **Remote-job-logs-directly** (Modal job sets `MLFLOW_TRACKING_URI`, calls `mlflow.log_artifact()`/`log_model()` itself → presigned-URL upload to S3; local process does metadata-only `register_model("runs:/<run_id>/model")`). **CORRECTED from v1** — see note below. | Local-download-then-register (download S3→local→`log_artifact`; needed only if we refuse to log from inside Modal) |

> **Q-B correction (verified against MLflow 3.x docs + anvil's code):** v1 of this plan said "register S3 URIs in MLflow." That is **mechanically unsupported**: `mlflow.log_artifact()` requires a LOCAL path, and `register_model` accepts only `runs:/`/`models:/` URIs, **never a raw `s3://`**. anvil's `TrackingService` confirms this — every `client.log_artifact(run_id, path)` call passes a local path and `register_source_model` uses `source=f"runs:/{run_id}/{artifact_path}"`. The clean, download-free pattern is to **log from inside the Modal job**: run MLflow tracking server with `--artifacts-destination s3://…` (proxy mode → Modal needs NO S3 creds, server issues presigned URLs); the Modal function sets `MLFLOW_TRACKING_URI` + exports safetensors to its own temp dir + calls `mlflow.log_artifact()` (uploads straight to S3); a valid `runs:/<run_id>/model` URI then exists, so the local `on_complete` does metadata-only `register_model(...)` with zero artifact transfer. This means `ComputeResult.exported_remotely=True` for remote runs signals "MLflow logging already happened inside the job; local `on_complete` skips export + does registry-only," NOT "register an S3 URI."
| Q-C | `engine_backend` overload fix | **Add `execution_backend` column** (clean, needs 1 migration) | Encode `local:torch` in existing col (no migration, but `String(16)` overflow risk + muddy analytics) |
| Q-D | `on_complete` signature change | **Change to `(ComputeResult, config)`** (Oracle-recommended seam) | Keep model-based + bolt-on remote special case (leaky) |
| Q-E | Build engine vectorization first? | **No — build abstraction first** as teaching vehicle; vectorize later (separate plan) | Vectorize first so GPU actually pays off (delays the lifecycle lesson) |
| Q-F | Include the `/v1/learn` lesson in Phase 1? | **Yes** (it's the stated "cover lessons" goal) | Defer lesson to Phase 2 |

---

## 9. Sequencing & Deferred Work

**Phase 1 (this plan):** abstraction (`ComputeResult` + Protocol + registry + resolve) → adapt `LocalStdlibBackend` + `LocalTorchBackend` → `ModalBackend` → `execution_backend` + `remote_job_id` columns + migration → backend selector UI → cloud-compute lesson → ADR. **Both local engines behind the abstraction is mandatory** (Oracle: prevents a remote-only leaky abstraction).

**Phase 2 (deferred, separate plans):**
- **SkyPilot backend** (multi-cloud; needs `anvil/__main__.py`, task YAML, S3 `file_mounts`, `sky jobs launch`). Add only after the abstraction survives Modal.
- **Metaflow orchestration** (`foreach` sweeps; orchestration ≠ compute — likely a `RemoteTrainingCoordinator` service, not bloating `TrainingService`).
- **Engine vectorization** (batch over sequence dim — the true unlock for GPU payoff; the honest prerequisite before remote GPU is cost-effective).
- **Serving layer** (BentoML/KServe — the biggest *true* lifecycle gap; entirely separate).

---

## 10. Risks & Guardrails (Oracle-flagged)

| Risk | Guardrail in this plan |
|------|------------------------|
| Remote jobs outlive web request/process | **Phase 1 scope decision:** the migration in Section 3.4 adds BOTH `execution_backend: String(32)` AND `remote_job_id: String(128) NULL` to `Experiment`; `ExperimentRepository` persists `remote_job_id` on submit and `status` transitions on poll. The async poll loop lives inside the same `start_training` task (in-memory queue is acceptable for Phase 1 since the FastAPI background task owns the run); the DB row is the durable record of `remote_job_id`+`status` so a restarted process can reconcile orphaned remote runs (reusing the existing `find_orphaned` pattern). Full out-of-process resumption (poll loop surviving a server restart) is **explicitly deferred to Phase 2**. |
| Secrets leakage | `MLFLOW_TRACKING_URI`/creds via `modal.Secret`/env only; **never** logged into SSE payloads or DB columns. Test asserts no secret in `ComputeResult`/events. |
| 100% coverage w/o cloud | All vendor I/O behind injected runner/client factories + Fake implementations. |
| Export ambiguity | Decide Q-B ONCE; do not support both ad-hoc. |
| `engine_backend` overflow/muddle | Separate `execution_backend` column (Q-C). |
| Silent fallback hiding intent | D4: explicit remote selection fails visibly; only implicit capability upgrades fall back. |
| async/sync boundary | Local stays `run_in_executor`; remote is async submit-poll — never block the executor on a cloud call. |

---

## 11. Definition of Done (Phase 1)

- [ ] ADR written in `docs/vault/Decisions/`.
- [ ] `modal` in `[project.optional-dependencies]` (`anvil[modal]`); base install unchanged.
- [ ] Abstraction (`result.py`, `protocol.py`, `registry.py`, `resolve.py`, `errors.py`) + both local backends + `modal_backend.py`.
- [ ] `on_complete` migrated to `ComputeResult`; both callers (cli.py, api/v1/training.py) updated.
- [ ] `execution_backend` + `remote_job_id` columns + reversible migration `011_*`; existing rows default `execution_backend="local"`.
- [ ] `use_gpu` retired end-to-end (training.html payload, `POST /v1/training/start` parsing, config dict); `resolve_backend()` is the single source of truth.
- [ ] Backend selector UI (4-value contract) + `GET /v1/compute/backends` (dict shape w/ availability) + SSE `submitted`/`status`.
- [ ] `/v1/learn/cloud-compute` lesson (+ optional widget).
- [ ] All 9 test files; `make test` 100% coverage, `make typecheck` strict, `make lint` pass.
- [ ] Default path (no selection) trains locally exactly as before (regression).
- [ ] Explicit `modal` without install → clear, actionable error (D4), verified by test.
- [ ] All Section 11.5 QA scenarios pass.
- [ ] Vault session log updated; wikilinks resolve.

---

## 11.5 Final Verification — Executable QA Scenarios (Phase 1)

Each scenario is independently runnable with a concrete tool, steps, and expected result. These are acceptance gates beyond the unit tests in Section 7.

### QA-1 — Default path regression (Art IX do-nothing path)
- **Tool**: shell / `make train`
- **Steps**: With a clean checkout (no `modal` installed), run `make train` (no `--backend`). 
- **Expected**: Training completes on CPU exactly as before; an `Experiment` row is written with `engine_backend="stdlib"`, `execution_backend="local"`, `remote_job_id=NULL`; final loss + samples logged to MLflow. No errors.

### QA-2 — Backend selector flow (web, happy path local)
- **Tool**: Playwright (`/playwright` skill) against `make run` on `http://localhost:8080/v1/training-page`
- **Steps**: Load training page → confirm a `#compute_backend` `<select>` exists with options `Auto / Local (CPU) / Local (GPU) / Modal (cloud GPU)` → select `Local (CPU)` → start training → observe SSE.
- **Expected**: `POST /v1/training/start` body contains `compute_backend:"local-cpu"` and **no `use_gpu` key** (verify via devtools/network); SSE emits `metrics…` then `complete`; loss chart renders; run appears in experiments list with `execution_backend="local"`.

### QA-3 — `GET /v1/compute/backends` availability shape
- **Tool**: `curl` / httpx
- **Steps**: `curl localhost:8080/v1/compute/backends` on a machine without `modal` installed and (if applicable) no GPU.
- **Expected**: JSON array of dicts; `modal` entry `{"available": false, "reason": "modal not installed"}`; `local-gpu` entry `available:false` with a non-null `reason` when no accelerator; `auto` and `local-cpu` `available:true`. UI renders unavailable options disabled with the `reason` as tooltip.

### QA-4 — Explicit Modal-unavailable fails visibly (D4)
- **Tool**: shell + httpx (or Playwright)
- **Steps**: Without `modal` installed, `POST /v1/training/start` with `{"compute_backend":"modal", ...}` (or select `Modal (cloud GPU)` in UI if not disabled).
- **Expected**: Run does **NOT** silently execute locally. SSE emits an `error` event with actionable text (`pip install anvil[modal]` + `modal token new`); the `Experiment` row is marked `status="failed"` with that `error_message`; `execution_backend="modal"`. (Contrast QA-5.)

### QA-5 — Implicit GPU→CPU fallback stays silent (Art IX)
- **Tool**: shell
- **Steps**: On a machine with no accelerator, run training with `compute_backend="local-gpu"` (or `--gpu`).
- **Expected**: Training completes successfully on CPU **without error** (silent capability downgrade); `Experiment.engine_backend` reflects the actual engine used (`stdlib`), device `cpu`. This confirms the line between QA-4 (visible) and QA-5 (silent).

### QA-6 — Remote submit→poll lifecycle (Modal, mocked runner)
- **Tool**: `pytest tests/unit/services/compute/test_modal_backend.py` + `tests/unit/services/test_training_phases.py`
- **Steps**: With `FakeModalRunner` injected, drive a remote run through submit→poll→complete.
- **Expected**: SSE event ORDER is `submitted` → ≥1 `status`/`metrics` → `complete`; `ComputeResult.exported_remotely=True` with `artifact_uris` populated; `Experiment.remote_job_id` persisted on submit; `mark_finished` called on completion; **no secret value** (`MLFLOW_TRACKING_URI`, tokens) appears in any SSE payload or DB column (asserted).

### QA-7 — `/v1/learn/cloud-compute` lesson renders
- **Tool**: Playwright / `curl`
- **Steps**: Load `http://localhost:8080/v1/learn/cloud-compute`; confirm it appears in the `/v1/learn` index (`LEARNING_ARC`).
- **Expected**: Page renders via `concept.html` with the 6 defined steps; prev/next arc navigation works; if the widget is included, `CloudComputeWidget` mounts and animates without console errors.

### QA-8 — Orphan reconciliation (remote durability, Phase 1 bound)
- **Tool**: `pytest tests/integration` (extend existing `test_orphan_reconciliation.py` pattern)
- **Steps**: Create an `Experiment` with `execution_backend="modal"`, `status="running"`, a `remote_job_id`; run the orphan-reconciliation pass.
- **Expected**: The run is discovered via `find_orphaned`; reconciliation logic can read `remote_job_id` to query/mark state. (Full out-of-process poll resumption is Phase 2 — this only verifies the DB record is sufficient for reconciliation.)

---

## 12. Appendix — Source Provenance

- **Modal**: docs.modal.com — `@app.function(gpu=)`, `.remote()`/`.starmap()`/`.spawn()`, `CloudBucketMount`, `modal.Secret`, scale-to-zero pricing (T4 $0.59/hr … A100-80GB $2.50/hr).
- **SkyPilot**: docs.skypilot.co, Apache-2 — 18+ clouds, portable task YAML, `sky jobs launch`, managed spot + `job_recovery`, S3 `file_mounts`. No native MLflow (pass via env).
- **Metaflow**: docs.metaflow.org, Apache-2 — `FlowSpec`/`foreach`, `@batch`/`@kubernetes`, S3 datastore. Complements MLflow (call `mlflow.*` in steps).
- **ZenML**: docs.zenml.io, Apache-2 — three-class flavor pattern; verdict = **mirror the swappability idea, do NOT adopt** (too broad; anvil uses no ABCs).
- **MLOps landscape**: Google/MS/AWS whitepapers, ml-ops.org — canonical stages (data→train→track→register→deploy→monitor→govern); serving layer (BentoML/KServe) is anvil's true gap; OSS-portable stack (MLflow+HF Hub) = lowest lock-in.
- **anvil internals**: cli.py (`AnvilWorkbench`, `train()`), services/training.py (phase seam ~L222, `on_complete`), services/tracking.py (`client_factory`+degraded-mode style), db/models/training_config.py (`Experiment.engine_backend String(16)`), api/v1/router.py (`LEARNING_ARC` lesson registry), training.html (selector site), conftest.py + pyproject (`fail_under=100`, `asyncio_mode=auto`).
- **Oracle review**: validated D1–D4, flagged `engine_backend` overflow/overload, remote-lifecycle ≠ local-lifecycle, secrets, coverage-without-cloud.
