# Research: Interactive Teaching Loop (055)

**Branch**: `055-interactive-teaching-loop` | **Date**: 2026-07-02

> ⚠️ **READ §9-§12 FIRST.** §1-§8 are the first-pass research. A critical-review verification pass (§9-§12) overturned four key assumptions in §1-§8 (training orchestration location, model-reference ID space, LoRA persistence, SSE proxying). Where §1-§8 and §9-§12 conflict, **§9-§12 is authoritative** and drove the final spec/plan/data-model/contracts.

## Overview

This document consolidates findings from parallel codebase exploration of the existing capabilities that the Interactive Teaching Loop composes: warm-start lineage (039), dataset preparation (053), inference export (045), model evaluation (054), and the page/SSE architecture.

---

## 1. Warm-Start Lineage (039) — MLflow Run Chaining

### Decision
TeachingRound = tagged MLflow run, chained via `anvil.base_model_ref` and `teaching_*` tags. TeachingSession = new lightweight DB table.

### Rationale
The existing codebase already uses MLflow runs as the primary tracking entity for training. Warm-start chaining is implemented via the `base_model_ref` field (an `experiment_id` integer) stored as an `anvil.base_model_ref` tag on the child run. TeachingRound extends this pattern with `teaching_session_id`, `teaching_round_number`, and `teaching_parent_round_id` tags. All artifacts (checkpoints, datasets, inference outputs) are native MLflow entities — independently visible outside the teaching context.

### Existing Tag Patterns

| Tag | Purpose | Source |
|-----|---------|--------|
| `anvil.warm_start` | Marks a run as warm-started | `training.py:793` |
| `anvil.base_model_ref` | Parent experiment ID (int) | `training.py:793` |
| `anvil.specialization_corpus` | Corpus used for training | `training.py:794` |
| `anvil.entity_type` | Entity type discriminator | `tracking.py:57` |
| `anvil.entity_id` | Entity ID reference | `tracking.py:58` |
| `anvil.origin` | Run origin (merge, evaluation, teaching) | `merge_service.py:500` |
| `anvil.adapter_id` | Adapter reference | `merge_service.py:501` |
| `anvil.eval_status` | Evaluation run status | `tracking.py:1543` |

### Adopted Teaching Tags

| Tag | Value | Purpose |
|-----|-------|---------|
| `teaching_session_id` | TeachingSession.id | Groups all rounds in a teaching session |
| `teaching_round_number` | int (1-based) | Sequential round number within session |
| `teaching_parent_round_id` | MLflow run ID or null | Chaining — parent round's MLflow run ID |
| `anvil.origin` | `"teaching"` | Distinguishes teaching runs from one-shot training |

### Key APIs

```python
# TrackingService — run lifecycle
tracking_svc.start_run(run_name="...", params=..., engine_backend=..., device=...) -> mlflow_run_id
tracking_svc.set_tag(run_id, key, value) -> None
tracking_svc.log_metric(run_id, key, value, step) -> None
tracking_svc.finish_run(run_id) -> None
tracking_svc.fail_run(run_id, _reason="...") -> None
tracking_svc.register_source_model(run_id, name, dataset_id, corpus_id, artifact_path) -> dict

# TrainingService — training orchestration
training_svc.start_training(config_dict, run_id, on_complete, ...) -> None
training_svc.reserve_run() -> int  # returns a reserved run_id
# config_dict = TrainConfig.model_dump() with dataset_id, base_model_ref, etc.

# Training route — HTTP trigger
POST /v1/training/start  body: TrainConfig  -> {run_id, mlflow_run_id, experiment_id, status}
GET  /v1/training/stream/{run_id}  -> SSE (metrics, complete, error, divergence, heartbeat)
POST /v1/training/{run_id}/stop
```

### Alternatives Considered

| Alternative | Rejected Because |
|-------------|------------------|
| New TeachingRound DB table | Duplicates MLflow's run tracking and artifacts; breaks "every entity independently visible" constraint |
| Pure tag-based session (no TeachingSession table) | No FK enforcement, no schema guarantees for session metadata; `mlflow.search_runs()` with tag filters is less ergonomic than FK joins |

---

## 2. Dataset Preparation (053)

### Decision
Teaching rounds create datasets via the existing `DatasetService` + `DatasetImportService`. The teaching round records the `dataset_id` in its MLflow tags for lineage tracing.

### Existing API

```python
# DatasetService
workbench.datasets.create_dataset(name, description) -> Dataset
workbench.datasets.load_docs(dataset_id) -> list[str]

# DatasetImportService (factory per dataset)
workbench.dataset_import(dataset_id).commit_docs_import(docs, source_label, source_format) -> ImportResult
workbench.dataset_import(dataset_id).commit_import(text, format) -> ImportResult  # txt/csv/jsonl
```

### API Endpoints

| Route | Purpose |
|-------|---------|
| `POST /v1/datasets` | Create dataset |
| `POST /v1/datasets/{id}/import` | Import text into dataset |
| `POST /v1/datasets/from-corpus` | Create + fill from corpus |
| `GET /v1/datasets/{id}/samples` | List samples |
| `POST /v1/datasets/{id}/curate/*` | Dedup, filter, regex replace |

### Integration Pattern
The teaching UI collects examples from the learner, then calls `workbench.datasets.create_dataset()` + `workbench.dataset_import(dataset_id).commit_docs_import(examples, "teaching", "txt")`. The resulting `dataset_id` is passed to training as `TrainConfig.dataset_id`.

---

## 3. Inference Export (045)

### Decision
Teaching rounds use the existing `InferenceService.generate()` for output inspection. Generated text is returned in-memory in the HTTP response. Persistence of inference outputs for lineage is handled via the teaching round's MLflow artifacts (not a new storage layer).

### Existing API

```python
# InferenceService
workbench.inference.load_model(model_id, version, adapter_id) -> LoadedModel
workbench.inference.generate(loaded, prompt, temperature, max_tokens) -> str
workbench.inference.tokenize(text, loaded) -> dict
workbench.inference.attention(text, loaded) -> dict
workbench.inference.sampling_distribution(prompt, temperature, top_k, loaded) -> dict
```

### API Endpoints

| Route | Purpose |
|-------|---------|
| `POST /v1/inference/generate` | Generate text (`InferenceGenerateBody: {model_id, prompt, adapter_id?, temperature, max_tokens}`) |
| `GET /v1/inference/model-params` | Parameter list |

### Integration Pattern
After training completes, the teaching round calls `workbench.inference.load_model(model_id=experiment_id, ...)` and generates outputs for inspection prompts. Outputs are shown inline in the teaching UI and optionally logged to the MLflow run as artifacts via `tracking_svc.log_artifact_dir()`.

---

## 4. Model Evaluation (054)

### Decision
Teaching rounds offer an optional "compare" step that triggers the existing `EvaluationService.start_evaluation()` with SSE streaming for progress.

### Existing API

```python
# EvaluationService
workbench.evaluate_fine_tuned(
    model_id, base_model_id,
    adapter_id=None,
    eval_dataset_name=None,
    prompts=None,
    tokenizer_family="char",
    base_tokenizer_family=None,
) -> EvaluationRun  # PENDING status; background worker spawned

workbench.get_evaluation_run(run_id) -> EvaluationRun | None
workbench.get_evaluation_samples(run_id) -> list[EvalSample]
workbench.list_evaluation_runs(model_id, status, limit, offset) -> tuple[list, int]
```

### API Endpoints

| Route | Purpose |
|-------|---------|
| `POST /v1/eval/fine-tuned` | Trigger async eval (returns `{run_id, status, sse_url}`) |
| `GET /v1/sse/eval/{run_id}` | SSE stream for eval progress |
| `GET /v1/eval/fine-tuned/{run_id}` | Fetch run metrics |
| `GET /v1/eval/fine-tuned/{run_id}/samples` | Per-prompt side-by-side outputs |

### Integration Pattern
After inference inspection, the learner may choose to compare the current round against the base model or a prior round. This triggers `workbench.evaluate_fine_tuned()` with the current round's model as `model_id` and the prior round's model as `base_model_id`. The SSE stream feeds into the teaching UI for live progress.

---

## 5. Page Architecture & SSE Streaming

### Decision
New dedicated page at `/v1/teach` following the existing page pattern: route handler in `pages.py`, template extending `base.html`, sidebar entry in `base.html`, SSE via `SSESession` from `sse.js`.

### Route Registration
```python
# anvil/api/v1/router.py — all sub-routers included
router.include_parser(training_router)
router.include_parser(pages_router)  # page rendering routes live here

# anvil/api/app.py:697
app.include_router(v1_router, prefix="/v1")
```

### Page Route Handler Pattern
```python
@router.get("/teach", response_class=HTMLResponse)
async def teach_page(request: Request) -> HTMLResponse:
    return request.app.state.templates.TemplateResponse(
        request,
        "teach.html",
        {"related_lessons": related_lessons("training-loop", "autograd", "adam")},
    )
```

### Template Pattern
```html
{% extends "base.html" %}
{% block extra_css %}<link rel="stylesheet" href="/static/css/archetypes.css">{% endblock %}
{% block content %}<div class="section-card">...</div>{% endblock %}
{% block scripts %}
<script src="/static/js/sse.js"></script>
<script nonce="{{ request.state.csp_nonce }}">
(function() {
  var session = new SSESession(runId);
  session.onmetrics = function(d) { updateMetrics(d); };
  session.start();
})();
</script>
{% endblock %}
```

### SSE Pattern (Training)
```python
# Backend
GET /v1/training/stream/{run_id} -> StreamingResponse
  event: metrics\ndata: {step, loss, ...}\n\n
  event: complete\ndata: {run_id, experiment_id}\n\n
  event: error\ndata: {message}\n\n

# Client (sse.js)
SSESession(runId)  -> EventSource connected to /v1/training/stream/{run_id}
  .onstatechange = fn(state)
  .onmetrics = fn(data)
  .oncomplete = fn(data)
  .onerror = fn(err)
  .start()
```

### Sidebar Entry Pattern
```html
<a href="/v1/teach" class="tab-item">
  <span class="tab-icon"><!-- SVG icon --></span>
  <span class="tab-label">Teach</span>
</a>
```

### CSS Token Usage
All tokens from `static/css/tokens.css`: `var(--surface)`, `var(--text)`, `var(--accent)`, `var(--space-*)`, `var(--radius-sm)`, `var(--text-footnote)`, etc. Templates reference `archetypes.css` for page archetype layouts.

---

## 6. AnvilWorkbench God Class — All Services

```python
# Properties relevant to teaching:
workbench.training            -> TrainingService
workbench.tracking            -> TrackingService
workbench.datasets            -> DatasetService
workbench.dataset_repo        -> DatasetRepository
workbench.dataset_import(id)  -> DatasetImportService (factory)
workbench.dataset_curation(id) -> DatasetCurationService (factory)
workbench.dataset_export(id)  -> DatasetExportService (factory)
workbench.inference           -> InferenceService
workbench.evaluation          -> EvaluationService
workbench.evaluate_fine_tuned(...) -> EvaluationRun
workbench.session             -> AsyncSession
workbench.transaction()       -> asynccontextmanager

# Not yet present — will be added:
workbench.teaching            -> TeachingService (NEW)
```

---

## 7. ORM Models (Existing — Relevant)

```python
# VersionRunRef — links MLflow runs to content versions
class VersionRunRef(Base):
    version_id: int  # FK to content_versions.id
    mlflow_run_id: str
    corpus_ref: str

# EvaluationRun — fine-tuned model evaluation
class EvaluationRun(Base):
    external_model_id: int  # FK to external_models.id (fine-tuned)
    base_external_model_id: int | None  # FK (base)
    adapter_id: str | None
    mlflow_run_id: str | None
    status: str  # EvaluationRunStatus

# LoRAAdapter
class LoRAAdapter(Base):
    external_model_id: int
    run_id: int
    adapter_id: str
    method: str
    storage_path: str
    merged_at: datetime | None

# ExternalModel — base model registry
class ExternalModel(Base):
    source_type: str
    source_identifier: str
    architecture_family: str
    tokenizer_family: str
    runnable_status: str
```

---

## 8. Complexity Tracking

The initial plan assumed pure orchestration with zero refactor. A critical-review verification pass (§9-§12 below) invalidated that assumption. The recorded complexity is now the `TrainingRunService` extraction — see plan.md Complexity Tracking. TeachingSession remains a minimal single-table addition.

---

## 9. CRITICAL REVIEW FINDINGS (2026-07-02) — Corrected Facts

A second, deeper verification pass (3 explore agents + Oracle consult) overturned four assumptions the first-pass research made. These corrections drove a rewrite of spec.md/plan.md/data-model.md/contracts.

### §9.1 — Training lifecycle lives in the ROUTE, not the service

- `TrainingService.start_training()` ONLY loads docs, dispatches to backend, emits SSE, and invokes an `on_complete` callback. It does **NOT** persist a loadable model.
- The `POST /training/start` **route handler** owns: hyperparameter validation, LoRA validation, warm-start validation, backend resolution, GPU memory estimation, run reservation, MLflow run creation + tags, and a ~200-line `on_complete` **closure**.
- The `on_complete` closure is where the **loadable artifact is written**: `model.save(data/models/experiment_{experiment_id}.json)`. Plus safetensors export + `tracking_svc.register_source_model()` (MLflow registry only).
- `workbench.training` returns a stateless `TrainingService` — there is **NO** god-class method wrapping the full flow.

**Impact**: TeachingService cannot just call `TrainingService.start_training()` — the resulting model would never be persisted, silently breaking inspect. **Resolution (Oracle)**: extract the lifecycle into a new `TrainingRunService` (services/training/), consumed by BOTH the route and teaching. Route-parity test enforces NMRG.

### §9.2 — Model-reference ID conflation

| Context | ID it uses |
|---------|-----------|
| Warm-start `TrainConfig.base_model_ref` | native **experiment_id** → `data/models/experiment_{id}.json` |
| `InferenceService.load_model(model_id)` | native **experiment_id** (cache → experiment artifact → MLflow registry fallback) |
| `EvaluationService.start_evaluation(model_id, base_model_id)` | **`ExternalModel.id`** (SQL FK) |
| `ExternalModel` rows | created ONLY by the HF/local import workflow — a natively-trained model NEVER gets one |

**Impact**: The first-pass data-model put `TeachingSession.base_model_ref` as an FK to `external_models.id`. That is WRONG — teaching chains on experiment_id. **Resolution**: `TeachingSession.current_base_experiment_id` (native experiment id, no FK). Evaluation deferred.

### §9.3 — LoRA adapter DB row is never auto-created

- LoRA training saves the adapter to `data/adapters/lora_{timestamp}/` and emits `adapter_id="run_{run_id}"` via SSE — but **NO `LoRAAdapter` DB row** is created by the training pipeline.
- `InferenceService.load_model(adapter_id)` looks up `LoRAAdapterRepository.get_by_adapter_id` → would find nothing.

**Impact**: Adapter teaching rounds cannot be inspected. **Resolution**: LoRA deferred from MVP (native full-model only).

### §9.4 — SSE queue is process-local; cannot be proxied

- The training progress queue is an in-memory `asyncio.Queue` keyed by `run_id` on the module-level `TrainingService` singleton.
- Cross-process proxying is impossible; the frontend connects directly to `/v1/training/stream/{run_id}`.

**Impact**: Removed the "proxy SSE" task. Teaching returns the same `run_id`; the frontend streams directly.

### §9.5 — Dataset origin has no API path

- `Dataset.origin` field exists (freeform `String(20)`, default `"user"`) but no create/update endpoint sets it.

**Impact**: Setting `origin="teaching"` requires a minor boundary change to the import service/repository (small, in-scope).

---

## 10. Oracle Architectural Guidance (2026-07-02)

**Bottom line**: Extract the full training lifecycle into a service-layer coordinator (`TrainingRunService`); both `/training/start` and teaching use it. Teaching chains on the native integer experiment id. Defer formal evaluation and `ExternalModel` integration.

Key rulings:
1. **Extract, don't HTTP-call or duplicate.** Internal HTTP preserves the wrong boundary and hides persistence behind a route; duplication drifts and will miss the model-artifact write.
2. **`TeachingSession.current_base_experiment_id`** (nullable int), not an `ExternalModel` FK, not a generic `base_model_ref`. Round 1 uses it or null; each successful round updates it after finalization.
3. **Session row is the chain head** — MLflow tags provide lineage/history but are NOT the source of truth for "next base."
4. **Compare = side-by-side inference** between two experiment ids for MVP. Do NOT route teaching models through `EvaluationService`.
5. **Defer**: imported-model round-1 seed (no experiment artifact), LoRA (no loadable artifact), formal eval (needs ExternalModel.id).
6. **Watch**: update `current_base_experiment_id` only after finalization; reuse the existing SSE flow unchanged.

Escalation triggers (would push beyond an MVP refactor): mandatory imported-model seeding → needs import-to-native artifact generation; mandatory formal compare/eval → needs `EvaluationService` redesign around native experiment-backed models.

---

## 11. Revised Reuse Map (corrected)

| Capability | How teaching reuses it |
|-----------|------------------------|
| Training lifecycle | NEW `TrainingRunService` (extracted from route); teaching + route both call it |
| Warm-start (039) | Pass `base_model_ref = current_base_experiment_id` to the training config |
| Dataset prep (053) | `DatasetService.create_dataset()` + `DatasetImportService.commit_docs_import(examples)`, `origin="teaching"` |
| Inference (045) | `InferenceService.load_model(experiment_id)` + `.generate()` for inspect and compare |
| SSE | Frontend connects directly to existing `/v1/training/stream/{run_id}` |
| Evaluation (054) | **Deferred** — not used in MVP |

---

## 12. Effort & Risk (revised)

- **Effort**: Medium (1-2d) for the `TrainingRunService` extraction + narrowed native-only MVP. Large if imported-model seeding or formal evaluation must stay in v1 (becomes a model-identity cleanup project).
- **Primary risk**: the extraction must preserve `/training/start` behavior exactly — mitigated by a route-parity e2e test written before the refactor.