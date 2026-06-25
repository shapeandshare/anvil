---
title: 'ADR-015: Pluggable Compute Backend Abstraction'
type: decision
tags:
  - type/decision
  - domain/architecture
  - domain/infrastructure
status: accepted
created: '2026-06-18'
updated: '2026-06-18'
aliases:
  - pluggable-compute-backends
source: agent
code-refs:
  - anvil/services/compute/
---
# ADR-015: Pluggable Compute Backend Abstraction

## Status
Accepted

## Context

anvil runs training only on the local machine (CPU or Apple MPS) via two engines: a stdlib-only `train()` in `anvil/core/engine.py` and a PyTorch GPU variant `train_torch()` in `anvil/core/torch_engine.py`. Engine selection is a simple boolean: `use_gpu_backend = device != "cpu"` at `anvil/services/training.py:222`.

The project needs to support training on external compute (cloud/serverless GPU, multi-cloud, orchestrated workflows) as pluggable, swappable modules — each also teachable as a `/v1/learn` lesson — without vendor lock-in. MLflow + safetensors → Hugging Face Hub remain the portable tracking/registry spine.

Cross-referenced research (Modal docs, SkyPilot docs, Metaflow docs, ZenML docs, and the broader MLOps landscape) identified four viable paradigms: serverless GPU (Modal), multi-cloud (SkyPilot), orchestration (Metaflow), and full platforms (deferred). ZenML's pluggable stack-component pattern was considered but rejected in favor of a lighter approach that matches anvil's actual conventions (no ABCs, string-key dispatch, injected `client_factory` pattern).

## Decision

Adopt a **string-key registry + thin Protocol** abstraction for compute backends, with a normalized `ComputeResult` value object as the unified return type. This avoids ABCs (anvil's service layer uses none) while satisfying `mypy --strict` via PEP 544 structural typing.

### Key design decisions (D1–D4)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| D1 | String-key registry + Protocol (not ABC hierarchy) | Matches anvil's existing `engine_backend` dispatch + `client_factory` injection pattern. Zero ABCs in the service layer. |
| D2 | `ComputeResult` value object (not raw model object) | The real seam is *local in-process model* vs *remote artifact URI*. Unify both behind one typed dataclass. |
| D3 | Submit-then-poll for remote (not blocking `run_in_executor`) | Remote jobs outlive the request; async poll loop with SSE `submitted`/`status`/`metrics`/`complete` events. |
| D4 | Capability-scoped fallback | Implicit "GPU→CPU" silently falls back (Art IX). Explicit "Modal" that fails → visible error. |

### Optional dependency

```toml
compute = ["modal>=0.70,<1"]
```

Added to `[project.optional-dependencies]`. The `modal` package is lazy-imported inside `ModalBackend.is_available()` — base install unchanged, Art I satisfied.

### Local-vs-remote execution model

- **Local backends** (`LocalStdlibBackend`, `LocalTorchBackend`): wrap existing `train()`/`train_torch()` in `run_in_executor`, return `ComputeResult(model=..., ...)`. Existing `on_complete` path unchanged (local safetensors export + MLflow `log_artifact` + DB persist).
- **Modal backend** (`ModalBackend`): remote job sets `MLFLOW_TRACKING_URI`, calls `mlflow.log_artifact()`/`log_model()` itself (proxy-mode MLflow server issues presigned URLs → uploads to S3). Local `on_complete` does metadata-only `register_source_model("runs:/<run_id>/model")` — zero artifact transfer.

### UI contract

The `use_gpu` boolean is retired end-to-end. A single 4-value `compute_backend` field (`auto | local-cpu | local-gpu | modal`) controls execution location + engine. `GET /v1/compute/backends` returns availability dicts for the dropdown.

## Mode Scope Clarification

The Modal backend is a **local-mode-only** compute option. It is not designed or
intended for SaaS mode (`ANVIL_MODE=saas`). The three-mode architecture
([[Decisions/ADR-030-saas-architecture|ADR-030]]) assigns Modal to local mode;
SaaS mode uses AWS Batch via `BatchComputeBackend` in `anvil/_saas/implementations/`.

The SaaS compute spec requires capabilities that ModalBackend does not implement:
structured `ResourceSpec`, `job_events` append-only table, `EventBus` integration,
IAM auth chain, S3 config-object pattern, checkpointing, and usage metering.
See [[Discoveries/modal-local-mode-boundary]] for the full gap analysis.

## Consequences

**Easier:**
- New backends (SkyPilot, Metaflow) drop in as new packages in `anvil/services/compute/` — no abstraction changes.
- MLflow remains the portable tracking layer; anvil never surrenders its lock-in-free spine.
- Each backend doubles as a `/v1/learn` lesson (teaching MLOps lifecycle stages).
- Both existing local engines prove the abstraction before any remote backend validates it.

**Harder:**
- Remote jobs outlive the web process — `remote_job_id` / status must persist to DB (added to `Experiment` model). Full out-of-process resumption is deferred to Phase 2.
- MLflow server must run in proxy artifact mode (`--artifacts-destination s3://...`) for credential-free remote uploads — ops prerequisite.
- `on_complete` signature changes from `(model, config, loss, samples, uchars)` to `(ComputeResult, config)` — touches two call sites.

**Explicitly deferred to Phase 2:** SkyPilot backend, Metaflow orchestrator, engine vectorization (batched sequence dim), and the model serving layer (BentoML/KServe).

## Compliance

- All compute backend I/O sits behind injected runner/client factories — 100% test coverage without cloud calls.
- `make test` (100% `fail_under`), `make typecheck` (mypy strict), `make lint` must pass.
- The `use_gpu` field is fully removed from all API payloads, CLI args, and DB columns (`engine_backend` retains its meaning).
- New ADR review triggered before adding SkyPilot or Metaflow backends.

## See Also

- [[Decisions/README|Decisions]]
