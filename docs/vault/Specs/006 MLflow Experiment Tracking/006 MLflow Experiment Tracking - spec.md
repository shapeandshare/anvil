---
title: 006 MLflow Experiment Tracking - spec
type: spec
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/006 MLflow Experiment Tracking/
related:
  - '[[006 MLflow Experiment Tracking]]'
created: ~
updated: ~
---
# Feature Specification: MLflow Experiment & Data Lifecycle Tracking

**Feature Branch**: `006-mlflow-experiment-tracking`
**Created**: 2026-06-13
**Status**: Draft
**Input**: User description: "MLflow Integration Spec: Dataset + Corpus LLM Trainer — route as much of the trainer's dataset, corpus, training, and evaluation lifecycle through MLflow as the API surface genuinely supports, and explicitly not invent abstractions MLflow doesn't have."

## Clarifications

### Session 2026-06-13

- Q: MLflow is imported but not declared in any dependency file (version unconstrained). What version should be pinned, and is the managed-evaluation-dataset capability (MLflow 3.x) first-class or fallback-only? → A: Pin `mlflow>=3.1` as an explicit dependency; managed evaluation datasets (US6 / FR-021) are a first-class supported path, with capability detection as a safety net rather than the primary mode.
- Q: What is the relationship between a tracked run and the existing local model registry (`RegisteredModel`/`ModelVersion`)? → A: Adopt the tracking store's own model registry as the single source of truth for registered models and deprecate the separate local model registry; trained models are promoted/registered through the tracking layer, eliminating the two-system contradiction risk.
- Q: There are three divergent tracking-URI literals (config default with `./`, supervisor without `./`, hardcoded API values). What is the single canonical source of the tracking destination? → A: `MICROGPT_MLFLOW_URI` resolved via `get_config()` is the one canonical source; the supervisor-managed tracking server and all clients (training, experiments, registry) MUST derive their URI from it, and all hardcoded literals are removed.
- Q: How are hard-killed/crashed runs (no exception handler runs, e.g. OOM or process kill) marked, given only `pending → completed` transitions exist today? → A: On service startup, reconcile orphaned runs — any run still in a running/pending state with no live owning process is marked failed/terminated (reason: "interrupted/terminated"), so the run list self-heals without manual cleanup.

### Session 2026-06-13 (rebase on `main` — corrections to earlier assumptions)

The feature branch was synchronized with `main`, which merged a torch engine, GPU detection, inference/eval endpoints, an async CLI, and an explicit MLflow dependency. These merged changes affect earlier decisions; the spec is corrected as follows:

- **A PyTorch engine now exists alongside the stdlib engine.** `main` added `anvil/core/torch_engine.py` (opt-in via `--gpu`/`use_gpu`, with GPU detection); the stdlib autograd engine remains the CPU default. However, training still does **not** use `mlflow.pytorch` autolog/flavor and models still serialize to **custom JSON**. So the "custom artifact, no standard flavor" stance (FR-025) holds; only the "not PyTorch" wording is corrected (see updated Context + Assumptions).
- **Model registration to MLflow happens automatically on completion; the local registry is written only via a manual endpoint.** *(Corrected after codebase verification — an earlier draft incorrectly claimed both systems are written on every completed run.)* `main`'s web training path (`api/v1/training.py` lines ~139–155) **auto-registers** each completed model into the MLflow Model Registry under a per-run name `anvil-experiment-{id}` (one throwaway registered model per run). The local `RegisteredModel`/`ModelVersion` tables are written **only** by the manual `POST /v1/registry/models` endpoint (via `ModelRegistryService.register_model()`) — **NOT** automatically on completion. So the dual-system contradiction this feature targets (FR-019, SC-008) is **latent** (it materializes whenever a user manually registers a run that MLflow already auto-registered), not an unconditional every-run duplication. The consolidation decision is unchanged and now also covers replacing the per-run `anvil-experiment-{id}` auto-register with source-keyed registration.

### Session 2026-06-13 (rebase on `main` #2 — Constitution Article IX "Pit of Success")

`main` added **Article IX — Pit of Success** to `.specify/memory/constitution.md` (authoritative; v1.1.0) + ADR-003. It mandates that optional capabilities (per Article I, **experiment tracking and GPU are opt-in layers**) MUST silently fall back when their runtime dependency is unavailable — *"never crash, never error, never block ... No `raise` or error response MAY be emitted solely because an optional capability's runtime dependency is absent."* This overrides parts of the earlier spec:

- **Tracking-destination unavailability is now graceful-degrade, NOT a hard error (reverses FR-009 / US2-AC4).** If the tracking server is unreachable at run start, training MUST proceed (the base capability) with a clear non-blocking **warning**; the run is not blocked and no error is raised solely due to tracking being down. Tracking simply degrades (run not recorded) and the user is notified.
- **GPU device resolution is silent-fallback.** When `--gpu`/`use_gpu` is requested but no accelerator (or torch) is available, the run silently uses CPU; the recorded `engine_backend`/`device` (FR-011) reflect the **resolved** device, and no error is raised (matches existing `resolve_device()`).
- **GPU dependency placement.** `nvidia-ml-py` (CUDA system metrics) is an opt-in GPU dependency and belongs in the **`gpu` optional extra** alongside `torch` (Article I), not core deps; absence degrades GPU-metric capture silently (FR-031).

### Session 2026-06-13 (MLflow 3.x mandate)

- Q: `main` shipped `mlflow>=2.16,<3` (2.x), which lacks `mlflow.genai` managed datasets — does the project accept 2.x (US6 gated/deferred) or require 3.x? → A: **The project MUST require MLflow 3.x.** Double-check confirmed `pyproject.toml` currently pins `mlflow>=2.16,<3` (commit `3f139bf`); this feature MUST bump it to `mlflow>=3.1,<4`. This **re-establishes managed evaluation datasets (US6 / FR-021) as a first-class supported path** (reverting the 2.x correction above), with runtime capability detection retained only as a safety net. Changing the pin from what `main` shipped is an explicit, intended deliverable of this feature.
- Q: Should the one canonical tracking destination be the HTTP tracking-server URI or a direct sqlite file URI? → A: **The HTTP server URI (`http://127.0.0.1:5000`) is canonical.** The supervisor-managed `mlflow server` AND all clients derive their URI from `MICROGPT_MLFLOW_URI`; the sqlite database is the server's backend-store only (passed via `--backend-store-uri`), never opened directly by clients. This is required for `mlflow.genai` managed datasets (US6), avoids multi-process SQLite write contention for concurrent runs, and fully supports the Model Registry.
- Q: Should model registration be automatic or explicit, and how are registered models keyed? → A: **Auto-register on every successful experiment, keyed to the INPUT SOURCE (dataset or corpus), not the experiment.** One registered model per source; each successful experiment trained on that source is added as a new **version** under that source's registered model (1 source → many experiments → many versions → 1 registered model). Creating a new dataset/corpus produces a new registered model; all successful runs from that source register as versions under it. Failed runs do NOT create versions. Runs with no explicit dataset/corpus (default input) register under a dedicated default-source registered model.
- Q: Should the compute backend/device a run used be recorded? → A: **Yes — record the resolved engine backend (`stdlib`/`torch`) and device (`cpu`/`cuda`/`mps`) as run parameters/tags on every run**, so provenance and run-to-run comparisons account for where the run executed (CPU vs GPU), not just hyperparameters.
- Q: What is the scope of accelerator (GPU) utilization capture, given MLflow's built-in system metrics cover NVIDIA only and not Apple Silicon MPS? → A: **Accelerator utilization MUST be captured on ALL accelerator types present, including MPS.** Add `nvidia-ml-py` for CUDA (via MLflow's built-in system metrics), AND implement a **custom MPS accelerator-metrics collector** (utilization and memory) that logs to the run, since MLflow's system metrics do not cover MPS. CPU/memory are always captured regardless of accelerator.

## Context *(what already exists)*

This is **not** a greenfield integration. The workbench already has partial MLflow wiring and rich data entities. This feature **completes and corrects** that integration rather than introducing it.

What exists today:

- **Training already creates an MLflow run** when started from the web API: hyperparameters are logged as params, per-step loss is logged as a metric, and the final model file + generated samples are logged as artifacts. A local `Experiment` record stores the linking `mlflow_run_id`.
- **An MLflow tracking server is managed by the supervisor** as a background service (default local SQLite backend on a dedicated port), and a tracking URI is exposed via configuration (`MICROGPT_MLFLOW_URI`).
- **Datasets** are first-class entities with metadata (vocabulary size, document/sample counts, total size, curation version, status) plus curation history (operations, import sources, per-sample provenance).
- **Corpora** are first-class entities representing a directory of source files, ingested and chunked into training documents, with file-level metadata (language, line/char/chunk counts, size).
- **A local model registry** (`RegisteredModel` / `ModelVersion`, created by migration `006_add_model_registry`) versions trained models in DB tables + on the filesystem, written **only** via the manual `POST /v1/registry/models` endpoint. Separately, the web training path **automatically** registers each completed model into the MLflow Model Registry (`create_registered_model` + `create_model_version(source="runs:/<run_id>/model.json")`) under a per-run name `anvil-experiment-{id}`. The two systems are therefore written on **different triggers** (MLflow on every completion; the local registry only on manual request) but can hold contradictory records for the same run. **This feature deprecates the local registry in favor of the tracking store's own model registry** (see FR-019).
- **The training engine is custom (a from-scratch transformer on a stdlib autograd engine), with an optional PyTorch backend.** `anvil/core/engine.py` (stdlib, CPU default) and `anvil/core/torch_engine.py` (opt-in via `--gpu`/`use_gpu` + GPU detection) coexist. Neither path uses a standard MLflow model flavor or autolog; models serialize to **custom JSON** in both cases.
- **An MLflow dependency is declared** in `pyproject.toml` as `mlflow>=2.16,<3` (MLflow **2.x**) — but **this feature MUST raise it to `mlflow>=3.1,<4`** (MLflow 3.x mandate; see Clarifications), because 2.x lacks the `mlflow.genai` managed-dataset API required by US6. `psutil` is declared; `torch` is an optional `gpu` extra; **`nvidia-ml-py` MUST be added to the `gpu` optional extra** (not core deps) for CUDA accelerator metrics (FR-031), with a custom MPS collector for Apple Silicon (FR-020).

What is incomplete, inconsistent, or missing today (the problems this feature solves):

- The MLflow tracking URI is **hardcoded in four+ places** (`api/v1/training.py`, `api/v1/experiments.py`, `api/v1/registry.py`, `supervisor/services.py`) as `sqlite:///./mlruns/mlflow.db`, while `config.py`'s `MICROGPT_MLFLOW_URI` value is **dead code that no client reads**. The `main` merge worsened this by adding a fresh hardcoded literal in `training.py`. Runs can land in a different store than the server reads.
- **Dataset and corpus lineage is not attached to runs.** A run records hyperparameters but not *which dataset or corpus version fed it*, so experiments are not reproducible from the tracking record alone.
- **CLI-initiated training is not tracked at all** — only the web API path creates MLflow runs. The async CLI `train()` goes through `TrainingService` but creates no MLflow run (prints step/loss to stdout only).
- **System/host resource utilization is not captured**, so runs cannot be compared on resource cost.
- **Run failure is not reliably reflected** in the tracking record; status is free-form and only ever set `pending → completed`, so a crashed run may appear unfinished rather than failed.
- Two parallel model-record systems exist — the **MLflow Model Registry** (written automatically on every completed run as `anvil-experiment-{id}`) and the **local `RegisteredModel`/`ModelVersion` tables** (written only via the manual `POST /v1/registry/models` endpoint) — which can hold duplicated/contradictory model records for the same run. Additionally, the per-run MLflow auto-register pollutes the registry with one throwaway registered model per experiment. This feature resolves both problems by consolidating on the tracking store's model registry as the single source of truth, keyed per input source.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reproducible run provenance: every training run records its data inputs (Priority: P1)

A researcher starts a training run against a chosen dataset or corpus. When they later inspect that run in the experiment tracker, they can see exactly which dataset/corpus (and which version of it) fed the run, alongside the hyperparameters, so they can reproduce or audit the result without guessing.

**Why this priority**: Provenance is the core value of experiment tracking. Without it, comparing runs is unreliable and reproducibility is impossible. This is the single highest-value gap in the current integration.

**Independent Test**: Start a run against a known dataset, then open that run's record and confirm the dataset appears as a labeled input with an identity (digest/version) and a source reference. Repeat against a corpus. Delivers reproducible provenance even if nothing else is added.

**Acceptance Scenarios**:

1. **Given** a dataset selected for a run, **When** the run starts, **Then** the run record shows that dataset as a labeled "training" input with a stable identity and a source reference.
2. **Given** a corpus selected for a run, **When** the run starts, **Then** the run record shows that corpus as a labeled "corpus" input with a stable identity and a source reference.
3. **Given** the same dataset content used by two runs, **When** both runs are inspected, **Then** both reference the **same** dataset identity (digest), confirming they trained on identical data.
4. **Given** a dataset whose content has changed since a prior run, **When** a new run uses it, **Then** the new run references a **different** identity than the prior run.
5. **Given** a run uses both a curated dataset and a holdout/validation split, **When** the run is inspected, **Then** training and validation inputs are distinguishable by their labels.

---

### User Story 2 - Consistent, configurable tracking destination (Priority: P1)

An operator configures where experiment data is stored (the tracking destination) once, in one place. Every training run — regardless of how it was started — records to that same destination, and the experiment-browsing UI reads from the same destination, so runs are never "lost" in a mismatched store.

**Why this priority**: A split between where runs are written and where they are read makes the entire tracking feature appear broken. This must be correct before provenance or metrics have any value.

**Independent Test**: Point the tracking destination at a known location via configuration, start a run, and confirm the run is visible both in the tracking UI and in the workbench's experiment list — and that no run appears in any other default location.

**Acceptance Scenarios**:

1. **Given** a configured tracking destination, **When** a run is started from the web UI, **Then** the run is recorded at the configured destination, not a hardcoded default.
2. **Given** the same configured destination, **When** a run is started from the CLI, **Then** it is recorded at the same destination as web-started runs.
3. **Given** a configured destination, **When** the experiment-browsing view loads, **Then** it reads runs from that same destination.
4. **Given** the configured destination is unreachable at run start, **When** a run is attempted, **Then** training still proceeds and the user receives a clear, non-blocking warning that the run will not be tracked (graceful degradation per Constitution Article IX — no hard error, no block).

---

### User Story 3 - Live and historical training metrics (Priority: P1)

A user watches training progress in real time and later compares completed runs. Loss is recorded per step so the tracker charts a curve, and a final summary metric is recorded at completion so runs can be ranked and compared.

**Why this priority**: Metrics are the primary reason to track experiments. The current integration logs loss per step but lacks a reliable, comparable completion summary and does not guarantee the step axis is consistent across metrics.

**Independent Test**: Run a short training job, watch the live loss curve update, then open the completed run and confirm a per-step loss series plus a final-loss summary value are present and chartable.

**Acceptance Scenarios**:

1. **Given** a training run in progress, **When** each step completes, **Then** the loss for that step is recorded against a consistent step axis.
2. **Given** a completed run, **When** it is inspected, **Then** a final summary loss value is recorded distinctly from the per-step series.
3. **Given** two completed runs, **When** compared side by side, **Then** their loss curves are overlaid on a shared step axis.
4. **Given** an evaluation/validation metric is produced, **When** it is recorded, **Then** it shares the same step axis as training loss so curves align.

---

### User Story 4 - Failure and lifecycle integrity (Priority: P2)

When a training run crashes or is interrupted, its tracking record reflects a failed/terminated state rather than appearing as a perpetually-running or successful run, so users can trust the run list at a glance.

**Why this priority**: Trustworthy run state is essential for triage but is secondary to having provenance and metrics at all. A wrong status is misleading; missing provenance is disqualifying.

**Independent Test**: Force a training run to raise an error mid-loop and confirm the run's recorded status becomes "failed" and the error context is captured, while a normally-completing run shows "finished".

**Acceptance Scenarios**:

1. **Given** a run that raises an error mid-training, **When** the run terminates, **Then** its tracking status is recorded as failed.
2. **Given** a run that completes normally, **When** it finishes, **Then** its status is recorded as finished.
3. **Given** a failed run, **When** inspected, **Then** the failure reason is captured in the record.
4. **Given** a run that fails, **When** the local experiment record is examined, **Then** its status agrees with the tracking record (no contradiction between the two systems).
5. **Given** a run whose process was hard-killed (OOM/kill/power loss) while still marked running, **When** the service next starts, **Then** that orphaned run is reconciled to a failed/terminated status with an interruption reason in both records.

---

### User Story 5 - System resource utilization per run (Priority: P3)

A user comparing runs can see host resource utilization (CPU, memory, and GPU where available) captured automatically for each run, so cost/efficiency can be compared alongside accuracy.

**Why this priority**: Useful for optimization and capacity decisions but not required for core reproducibility or comparison. Lowest priority among the included stories.

**Independent Test**: Start a run and confirm host CPU/memory utilization series appear on the run record without any per-run manual instrumentation.

**Acceptance Scenarios**:

1. **Given** system metrics capture is enabled, **When** a run executes, **Then** host CPU and memory utilization are recorded as time series on the run.
2. **Given** a CUDA host, **When** a run executes, **Then** GPU utilization/memory are recorded (via MLflow built-in system metrics).
3. **Given** an Apple Silicon (MPS) host, **When** a run executes, **Then** MPS utilization/memory are recorded via the custom collector.
4. **Given** a machine without an accelerator, **When** a run executes, **Then** the run still records CPU/memory metrics without error.

---

### User Story 6 - Reusable, curated evaluation sets (Priority: P3)

A user maintains a named evaluation set that grows over time and is reusable across many runs, so that successive models are judged against a consistent, queryable benchmark rather than ad-hoc data.

**Why this priority**: Valuable for disciplined evaluation but optional; additive on top of per-run lineage. Enabled by the mandated MLflow 3.x pin (FR-026), which provides the `mlflow.genai` managed-dataset API. Note: the existing `POST /v1/eval/perplexity` endpoint is unrelated — it computes perplexity over a raw text string and does not manage evaluation datasets.

**Independent Test**: Create a named evaluation set, add records to it, then query it back by name and confirm the records persist and are retrievable independently of any single run.

**Acceptance Scenarios**:

1. **Given** the tracking destination supports managed evaluation datasets, **When** a user creates a named evaluation set, **Then** it persists and is retrievable by name across sessions.
2. **Given** an existing evaluation set, **When** records are appended, **Then** the set grows without losing prior records.
3. **Given** the tracking destination does **not** support managed evaluation datasets (capability unavailable), **When** a user attempts to create one, **Then** the system degrades gracefully to per-run input lineage and informs the user, rather than failing the run.

---

### Edge Cases

- **Non-tabular corpus**: When a corpus cannot be represented as a structured table (e.g., raw source files), the run still records corpus provenance via a metadata-only input plus the actual files captured as run artifacts.
- **Capability gating by tracking-store version**: When the configured tracking destination lacks managed evaluation-dataset support, those features are disabled and the system falls back to per-run lineage without error.
- **Missing data selection**: When a run is started with neither a dataset nor a corpus selected, the system follows existing behavior (default dataset) and records whichever input actually fed the run.
- **Both dataset and corpus referenced**: When a configuration references both, the system records the input that actually fed training and labels it accordingly (no phantom inputs for unused references).
- **Tracking destination temporarily unavailable mid-run**: The training itself should not be silently corrupted; the user is informed that tracking data for that run may be incomplete.
- **CLI-started run hard-killed**: Orphan reconciliation (FR-028) runs on **web service startup**. A CLI-started run that is hard-killed is therefore reconciled to `failed`/`terminated` the next time the web service boots (not instantly), since the short-lived CLI process has no long-running startup hook of its own.
- **Concurrent runs**: Multiple simultaneous runs each produce a distinct, correctly-attributed run record without cross-contamination of metrics or inputs. Per-run **params, metrics, inputs, and artifacts** are always run-scoped (logged against an explicit `run_id`) and never cross-contaminate. *Known limitation*: **process-global system-metrics logging** (`enable_system_metrics_logging`) and **startup orphan reconciliation** assume a single training process — concurrent in-process runs may share/duplicate host system-metric series, and reconciliation cannot distinguish a genuinely-live concurrent run from an orphan (see the FR-028 liveness model). Multi-process/multi-instance concurrency is out of scope (see Assumptions).
- **Duplicate model records**: With the local model registry deprecated, registered models exist in exactly one system (the tracking store's registry); a successful run must not produce a parallel local registry entry.
- **Repeated runs on one source**: Multiple successful experiments on the same dataset/corpus MUST append versions to that source's single registered model — never create a second registered model for the same source (FR-029).
- **Source renamed between runs**: Renaming a dataset/corpus MUST NOT fork its registered model; versions continue accumulating under the stable per-source identity (FR-029).
- **No explicit source (default input)**: A successful run with neither dataset nor corpus registers a version under the dedicated default-source registered model (FR-029).
- **Failed/interrupted run**: A run that fails, is interrupted, or is reconciled as orphaned MUST NOT create a registered-model version (FR-030).
- **Pre-existing local registry entries**: When models already exist in the deprecated local registry at upgrade time, the system must follow a defined transition path (migrate or clearly mark as legacy) rather than silently orphaning or duplicating them.
- **Very large model artifacts**: Model artifacts are captured deliberately and named predictably, never auto-captured in a way that produces unusable or oversized default artifacts.

## Requirements *(mandatory)*

### Functional Requirements

**Provenance & lineage**

- **FR-001**: System MUST record, on every training run, the dataset or corpus that fed it as a labeled input with a stable content-derived identity and a source reference.
- **FR-002**: System MUST distinguish input roles using clear labels (at minimum: training, validation, corpus) so multiple inputs on one run are unambiguous.
- **FR-003**: System MUST derive input identity such that identical data content yields the same identity and changed content yields a different identity across runs.
- **FR-004**: System MUST capture corpus provenance even when the corpus is not representable as structured tabular data, using a metadata-only input plus the source files captured as run artifacts.
- **FR-005**: System MUST centralize the decision of how a given corpus is represented (lineage input vs. metadata-only + artifacts) in a single, testable place so the choice is consistent across entry points.

**Tracking destination consistency**

- **FR-006**: System MUST resolve the tracking destination from a single canonical configuration source (`MICROGPT_MLFLOW_URI` via the central config accessor), and that destination MUST be the **HTTP tracking-server URI** (default `http://127.0.0.1:5000`). All clients (training, experiment-browsing, model registration) MUST talk to the running server via this URI; clients MUST NOT open the sqlite database directly. The sqlite database is the server's backend-store only (passed to `mlflow server --backend-store-uri`). All hardcoded URI literals MUST be removed.
- **FR-007**: The experiment-browsing experience MUST read runs from the same canonical destination that runs are written to.
- **FR-008**: System MUST record runs to the configured destination regardless of whether training was started from the web interface or the CLI.
- **FR-009**: When the configured tracking destination is unavailable at run start, System MUST **degrade gracefully per Constitution Article IX**: training proceeds (the base capability) and the user receives a clear, **non-blocking warning** that this run will not be tracked. System MUST NOT raise an error or block training solely because the tracking server (an opt-in capability) is unreachable. (Tracking is best-effort; the warning surfaces the degraded state without failing the run.)

**Run lifecycle & metrics**

- **FR-010**: System MUST wrap each training job as a single tracked run with a human-meaningful run name and a retrievable run identifier. The default run name follows the pattern `<source-slug>-<UTC-timestamp>` (e.g. `corpus-2-20260613T154500Z`), where `<source-slug>` is the input-source key from FR-029; callers MAY override the name.
- **FR-011**: System MUST record resolved hyperparameters as run parameters once per run after configuration is finalized, AND MUST record the **resolved** compute backend (`stdlib`/`torch`) and device (`cpu`/`cuda`/`mps`) as run parameters/tags so the execution environment is part of the run's provenance. Per Constitution Article IX, when GPU is requested but unavailable the resolved values reflect the actual CPU fallback (no error is raised); the params record what actually ran, not what was requested.
- **FR-012**: System MUST record per-step training loss against a consistent step axis so a loss curve can be charted.
- **FR-013**: System MUST record a final summary loss metric at completion, distinct from the per-step series.
- **FR-014**: When evaluation/validation metrics are produced, System MUST record them on the same step axis as training loss so curves align.
- **FR-015**: System MUST record a run's terminal status as failed when training raises an error, and finished when it completes normally, capturing the failure reason on failure.
- **FR-016**: The local experiment record and the tracking-store run record MUST agree on terminal status (no contradiction between the two systems).
- **FR-028**: System MUST reconcile orphaned runs on service startup: any run persisted in a running/pending (non-terminal) state at startup MUST be marked failed/terminated with a reason indicating interruption, in BOTH the local experiment record and the tracking-store run record. This covers hard kills, OOM, and power loss where no in-process handler can run. **Liveness model (single-process assumption)**: the system does NOT track per-run owning PIDs/heartbeats; under the single-process model (see Assumptions), any non-terminal run found at web startup is by definition orphaned, because a genuinely-live run would be owned by the process that is now (re)starting. Consequently, reconciliation MUST NOT be run in a deployment where another instance may legitimately own in-flight runs — concurrent **multi-instance** operation is out of scope (a PID/heartbeat-based liveness check is a deferred enhancement, not part of this feature).

**Artifacts & model handling**

- **FR-017**: System MUST capture the trained model artifact and associated non-model files (e.g., generated samples, vocabulary/config) on the tracking run, with predictable naming.
- **FR-018**: System MUST NOT auto-capture model artifacts in a way that produces unusable or unintended defaults; artifact capture is deliberate and controlled. (Intentional negative-constraint complement to FR-017 — retained to forbid MLflow flavor/autolog default-artifact behavior.)
- **FR-019**: System MUST use the tracking store's own model registry as the single source of truth for registered models, and MUST deprecate the separate local model registry (`RegisteredModel` / `ModelVersion`) so two contradictory model-record systems no longer coexist. Registration MUST be **automatic on every successful experiment**: on successful completion the system MUST create-or-reuse a registered model **keyed to the run's input source (the dataset or corpus that fed it)** and add the run's model artifact (FR-017) as a new **version** under that registered model. Thus one input source maps to exactly one registered model that accumulates one version per successful experiment on that source.
- **FR-029**: The registered-model identity MUST be derived from a **stable per-source key** based on the source's **immutable database id** (NOT its mutable name), using the slug scheme: `dataset-<id>` for a dataset, `corpus-<id>` for a corpus, and the literal `default-source` for runs with no explicit dataset/corpus. This guarantees: (a) re-running on the same source appends versions to the same registered model rather than creating duplicates; and (b) renaming the source does not fork its registered model. No successful run is left unregistered.
- **FR-030**: Only **successful** experiments create registered-model versions; failed, interrupted, or orphaned runs MUST NOT create a version. Registration MUST happen on both web- and CLI-initiated successful runs (consistent with FR-008).
- **FR-027**: System MUST retire the local model-registration write path (`RegisteredModel`/`ModelVersion`) so it no longer records a parallel registry. The existing `POST /v1/registry/models` endpoint MUST either be removed or redirected to target the same source-keyed MLflow registered model (manual promotion remains possible but is no longer the only path, since registration is automatic per FR-019). A migration/transition path for any models already in the local registry MUST be defined during planning.

**System metrics**

- **FR-020**: System MUST capture host resource utilization (CPU and memory) per run automatically. It MUST also capture **accelerator utilization and memory for ALL accelerator types present, including both CUDA and Apple Silicon MPS**. CUDA metrics are captured via MLflow's built-in system metrics (requiring `nvidia-ml-py`); since MLflow does NOT cover MPS, the System MUST provide a **custom MPS accelerator-metrics collector** that logs MPS utilization/memory to the run. Machines without any accelerator MUST still record CPU/memory without error.
- **FR-031**: System MUST declare `nvidia-ml-py` (for CUDA accelerator metrics) in the **`gpu` optional-dependency extra** alongside `torch` (per Constitution Article I — GPU is an opt-in layer), NOT in core dependencies. System MUST implement the custom MPS collector behind a capability check so that hosts lacking a given accelerator type (or the optional GPU deps) degrade gracefully — no errors, CPU/memory still recorded (Article IX).

**Managed evaluation datasets (first-class under the mandated MLflow 3.x pin)**

- **FR-021**: System MUST support managed, persistent, named evaluation datasets as a first-class path: creating such a set, appending records over time, and querying it back by name across sessions. This is available because the tracking layer is pinned to MLflow 3.x (FR-026), which provides the `mlflow.genai` managed-dataset API.
- **FR-022**: Where managed evaluation datasets are unavailable at runtime (e.g., a misconfigured store, or a tracking server older than the mandated 3.x baseline), System MUST degrade gracefully to per-run input lineage and inform the user, **without failing runs**. This is a safety net, not the expected primary mode.

**Compatibility & scope guardrails**

- **FR-023**: System MUST detect the tracking-store capability level at startup (including whether `mlflow.genai` managed datasets exist for the installed MLflow version) and enable/disable capability-gated features accordingly. Under the mandated 3.x baseline the capability is expected to be present.
- **FR-026**: System MUST pin the tracking library to **MLflow 3.x** by changing `pyproject.toml` from the currently-shipped `mlflow>=2.16,<3` to `mlflow>=3.1,<4`. This bump is a required deliverable (it enables FR-021/US6); the feature MUST NOT remain on the 2.x pin.
- **FR-024**: System MUST NOT introduce a bespoke "corpus store" abstraction in the tracking layer; corpus support MUST be composed from the tracking store's native input-lineage and artifact capabilities (and managed-dataset capabilities only when on MLflow 3.x) so all data remains inspectable through standard tracking tooling.
- **FR-025**: System MUST treat the model as a custom (non-standard-flavor) JSON artifact, and MUST NOT assume a HuggingFace/Transformers or PyTorch model flavor or autologging hook — even on the GPU/torch backend, where the model is still serialized to custom JSON rather than a PyTorch flavor.

### Key Entities *(include if feature involves data)*

- **Training Run**: A single execution of a training job. Bridges the local experiment record and the tracking-store run via a shared run identifier. Carries parameters, metric series, inputs, artifacts, terminal status, and resource-utilization series.
- **Dataset Input**: A reference, attached to a run, to a curated dataset that fed training. Has a stable content-derived identity, a source reference, and a role label. Maps from the existing Dataset entity (with its vocabulary size, sample/document counts, and curation version).
- **Corpus Input**: A reference, attached to a run, to a corpus of source documents that fed training. Has a stable identity, a source reference (root path / ingestion identity), and a role label. When non-tabular, represented as metadata + source-file artifacts. Maps from the existing Corpus entity.
- **Run Parameters**: The resolved, flattened hyperparameter set for a run (e.g., layers, embedding width, heads, block size, steps, learning rate, schedule coefficients, sampling temperature, plus the dataset/corpus selection), plus the resolved **compute backend** (`stdlib`/`torch`) and **device** (`cpu`/`cuda`/`mps`).
- **Metric Series**: Time-indexed measurements on a run, primarily per-step training loss, a final summary loss, and (when available) evaluation metrics aligned on the same step axis.
- **Run Artifact**: A file captured against a run — the trained model file, generated text samples, and any vocabulary/config needed to interpret the model.
- **Registered Model**: A model entry in the tracking store's model registry (the single source of truth), **keyed to an input source** (a dataset or corpus, by stable identifier). It accumulates one **version** per successful experiment trained on that source, each version linked to its originating run and based on that run's model artifact (FR-017). One source → one registered model → many versions. A dedicated default-source registered model covers runs with no explicit dataset/corpus. Replaces the deprecated local `RegisteredModel`/`ModelVersion` entities.
- **Resource-Utilization Series**: Automatically captured host CPU/memory utilization over the run's duration, plus accelerator utilization/memory for any accelerator present — CUDA (via MLflow built-in system metrics) and MPS (via the custom collector).
- **Managed Evaluation Set** (capability-gated): A named, persistent, growable collection of evaluation records that exists independently of any single run and is queryable by name.
- **Tracking Destination**: The single configured location where runs are written and from which they are read; capability level is detected at startup.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: When the tracking destination is reachable, 100% of training runs (web- and CLI-initiated) produce a tracking record at the configured destination; 0% land in an unconfigured/default location. When it is unreachable, 100% of runs still complete (untracked) with a non-blocking warning and 0% raise a tracking-related error (Article IX).
- **SC-002**: 100% of training runs record the dataset or corpus that fed them as a labeled input with a content-derived identity and source reference.
- **SC-003**: Given two runs that used identical data content, an observer can confirm they share the same input identity in under 30 seconds of inspection, with no access to the underlying files.
- **SC-004**: 100% of runs that raise an error are recorded with a failed terminal status, and the local and tracking-store status agree in 100% of cases.
- **SC-005**: A per-step loss curve is chartable for 100% of completed runs, and two runs can be overlaid on a shared step axis for comparison.
- **SC-006**: Host CPU and memory utilization series are present on 100% of runs; accelerator utilization/memory series are present on 100% of runs executed on accelerator-equipped hosts — **including both CUDA and MPS hosts** (MPS via the custom collector).
- **SC-007**: When managed-evaluation-dataset support is unavailable (e.g., a misconfigured/older tracking store than the mandated 3.x baseline), 100% of runs still succeed and still record per-run input lineage, and the eval-dataset API reports unavailability gracefully (0% run failures attributable to the missing capability).
- **SC-008**: Registered models exist in exactly one system (the tracking store's registry); 0 parallel local-registry entries are created for new registrations, and 0 contradictions are observed across an acceptance test suite.
- **SC-011**: For an input source with N successful experiments, the registry shows exactly **one** registered model for that source with **N** versions (0 duplicate registered models for the same source); failed/interrupted runs contribute 0 versions.
- **SC-009**: An operator can change the tracking destination in exactly one configuration location and have both run-writing and run-browsing follow it, verified end to end.
- **SC-010**: After a simulated hard kill of a training process, 100% of the affected orphaned runs are reconciled to a failed/terminated status (in both records) by the next service startup, with 0 runs left stuck in a non-terminal state.

## Assumptions

- **Constitution Article IX ("Pit of Success") governs all optional capabilities.** Experiment tracking and GPU are opt-in layers; when their runtime dependency is unavailable the system degrades silently (tracking → untracked run with a warning; GPU → CPU fallback) and NEVER raises/blocks solely for that reason. This is authoritative (`.specify/memory/constitution.md` v1.1.0, ADR-003) and supersedes any conflicting requirement.
- **Corpus role is training/source data.** The existing Corpus entity ingests a directory of files and chunks them into training documents that feed the training loop; therefore corpus is treated as training/source-data lineage (with metadata-only + artifacts fallback when non-tabular), not as an inference-time retrieval store. This resolves the spec's highest-value open question.
- **The training engine is custom (stdlib autograd) with an optional PyTorch backend.** CPU training uses the stdlib engine; `--gpu`/`use_gpu` selects the torch backend (`anvil/core/torch_engine.py`) when an accelerator is detected. Neither path uses HuggingFace/Transformers or a `mlflow.pytorch` flavor/autolog; models serialize to custom JSON in both cases, so they are tracked as custom artifacts.
- **Single-process, single-rank training** is assumed for run boundaries; distributed/multi-worker rank-0-only logging is out of scope for this feature.
- **A local-first, self-hosted tracking destination** is the default, consistent with the existing supervisor-managed tracking server and the project's lean-dependency philosophy; no external SaaS tracking dependency is introduced.
- **MLflow 3.x is mandated.** This feature bumps `pyproject.toml` from the currently-shipped `mlflow>=2.16,<3` to `mlflow>=3.1,<4` (FR-026), making managed evaluation datasets (US6) a first-class path. Runtime capability detection remains as a graceful-degradation safety net for misconfigured/older stores. Planning MUST verify MLflow 3.x resolves cleanly against the existing pins (e.g., `pydantic<3`, `torch>=2.0`).
- **The existing partial integration is the baseline.** This feature extends and corrects the current web-API integration (run creation, param/metric/artifact logging) rather than replacing it wholesale.
- **The existing local model registry is deprecated**, not retained. The tracking store's own model registry becomes the single source of truth for registered models; a transition path for any pre-existing local-registry entries is defined during planning.
- **Reusing existing entities for inputs/runs**: Dataset, Corpus, TrainingConfig, and Experiment entities are reused as the source of truth for inputs, parameters, and run linkage; no parallel data model is introduced for these. The local model-registry entities (`RegisteredModel`/`ModelVersion`) are the exception — they are deprecated in favor of the tracking store's registry (FR-019).
