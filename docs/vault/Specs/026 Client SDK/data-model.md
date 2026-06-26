---
title: 'Phase 1 Data Model: Client SDK'
type: spec
tags:
  - type/spec
  - domain/architecture
status: draft
created: '2026-06-21'
updated: '2026-06-21'
---

Back to [[Specs/026 Client SDK/Spec]].

## 2. Domain DTOs

> Field sets below reflect the verified anvil API responses (the standard
> `{"data": ..., "error": null}` envelope wraps these). Exact optional fields are finalized
> against `anvil/api/v1/schemas.py` and each route's serializer during implementation; the
> shapes here are the contract the SDK validates against.

### `Dataset` — `datasets/dataset.py`
| Field | Type | Notes |
|---|---|---|
| `id` | `int` | Primary key |
| `name` | `str` | |
| `description` | `str \| None` | |
| `sample_count` | `int` | |
| `created_at` | `datetime` | |
| `updated_at` | `datetime \| None` | |

### `TrainingConfig` — `training/training_config.py`
Request DTO for `POST /v1/training/start`. (Fields verified against the training start body.)

| Field | Type | Default |
|---|---|---|
| `n_embd` | `int` | `16` |
| `n_layer` | `int` | `1` |
| `n_head` | `int` | `4` |
| `block_size` | `int` | `16` |
| `num_steps` | `int` | `1000` |
| `learning_rate` | `float` | `0.01` |
| `beta1` | `float` | `0.85` |
| `beta2` | `float` | `0.99` |
| `temperature` | `float` | `0.5` |
| `compute_backend` | `str` | `"auto"` |
| `dataset_id` | `int \| None` | `None` |
| `corpus_id` | `int \| None` | `None` |
| `content_version_id` | `str \| None` | `None` |
| `device` | `str \| None` | `None` |

- **Validation**: `n_head` divides `n_embd`; positive `num_steps`, `learning_rate`, `block_size`.

### `TrainingStartResult` — `training/training_start_result.py`
| Field | Type |
|---|---|
| `run_id` | `str` |
| `mlflow_run_id` | `str` |
| `experiment_id` | `str` |

### `Experiment` — `experiments/experiment.py`
| Field | Type | Notes |
|---|---|---|
| `id` | `str` | MLflow experiment/run id |
| `name` | `str` | |
| `run_count` | `int` | enrichment |
| `best_loss` | `float \| None` | enrichment |
| `duration` | `float \| None` | seconds |
| `mlflow_url` | `str \| None` | link to MLflow UI |

### `RegisteredModel` — `registry/registered_model.py`
| Field | Type | Notes |
|---|---|---|
| `model_id` | `str` | |
| `name` | `str` | |
| `versions` | `list[str]` | version identifiers |
| `created_at` | `datetime \| None` | |

> P3 domains (corpora, eval, compute, services, governance, content, inference) introduce their
> own DTOs following the same conventions; enumerated in `contracts/commands.md`.

---

## 3. Relationships & Aggregation (not persisted — object graph)

```
AnvilClient
├── config: ServerConfig
├── _transport: Transport            (holds httpx.AsyncClient + cookie jar + api_key)
├── health:      HealthClient        ──► HealthGetCommand, HealthDetailedCommand
├── datasets:    DatasetsClient      ──► DatasetList/Get/Create/Update/Delete/Upload/ExportCommand
├── training:    TrainingClient      ──► TrainingStart/Status/Stop/StreamCommand
├── experiments: ExperimentsClient   ──► ExperimentList/Get/Compare/Metrics/Delete/Artifacts/DownloadCommand
├── registry:    RegistryClient      ──► RegistryRegister/List/Get/DeleteCommand
├── inference:   InferenceClient     ──► InferenceSample/ModelsCommand
└── (P3) corpora, eval, compute, services, governance, content
```

- Every `Command` holds a reference to the shared `Transport` (injected by its `DomainClient`).
- `DomainClient`s are instantiated once by `AnvilClient.__init__`, sharing the one `Transport`.
- No command holds `httpx` primitives directly — only the `Transport` does (Article VII analogue).

---

## 4. State Transitions

The SDK is largely stateless except for **auth state** held on the client instance:

```
[unauthenticated]
   │  AnvilClient(api_key=...)            → [api-key auth]   (X-API-Key on every request)
   │  client.login(api_key)               → [session auth]   (anvil_session cookie + CSRF on writes)
[session auth]
   │  session expires + next request      → AuthenticationError (no silent re-login in v1)
   │  client.logout()                     → [unauthenticated]
```

Training-run lifecycle is **server-side state** the SDK observes (not owns):
`active → completed | failed`, surfaced via `training.status(run_id)` and terminal SSE events
(`complete` / `error` / `divergence`).
