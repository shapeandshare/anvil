# Phase 1 Data Model: Client SDK

**Feature**: 026-client-sdk | **Date**: 2026-06-21

All structured types are Pydantic `BaseModel` subclasses (Constitution: `BaseModel` over
dataclass). All enumerations are `StrEnum` (enums over magic strings). Every type lives in its
own file (one-class-per-file). Annotations use PEP 604 unions (`X | None`) with
`from __future__ import annotations` at file top.

Two categories of types:
1. **Infrastructure types** — SDK plumbing (`_shared/`).
2. **Domain DTOs** — typed request/response payloads, co-located with their domain sub-package.

---

## 1. Infrastructure Types (`anvil/client/_shared/`)

### `ServerConfig` — `_shared/server_config.py`
Connection configuration. Resolution per field: explicit arg > env var > default.

| Field | Type | Default | Env Var | Notes |
|---|---|---|---|---|
| `base_url` | `str` | `"http://localhost:8080"` | `ANVIL_SERVER_URL` | Server root; no trailing slash |
| `timeout` | `float` | `30.0` | `ANVIL_TIMEOUT` | Per-request seconds; `> 0` |
| `retry_count` | `int` | `3` | `ANVIL_RETRY_COUNT` | `>= 0` |
| `retry_backoff` | `float` | `0.5` | `ANVIL_RETRY_BACKOFF` | Exponential factor seconds; `>= 0` |

- **Validation**: `timeout > 0`; `retry_count >= 0`; `retry_backoff >= 0`; `base_url` non-empty.
- **Classmethod**: `from_env(**overrides) -> ServerConfig` applies the resolution order.

### `Response[T]` — `_shared/response.py`
Generic Pydantic model unwrapping the API envelope.

| Field | Type | Notes |
|---|---|---|
| `data` | `T \| None` | Payload; `None` only on error envelopes |
| `error` | `str \| None` | Server error message; `None` on success |

- `T` is a `TypeVar`. Transport validates JSON into `Response[ConcreteModel]` and returns `.data`.

### `HttpMethod` (StrEnum) — `_shared/http_method.py`
`GET="get"`, `POST="post"`, `PUT="put"`, `DELETE="delete"`, `PATCH="patch"`.

### `StreamEventType` (StrEnum) — `_shared/stream_event_type.py`
`METRICS="metrics"`, `COMPLETE="complete"`, `ERROR="error"`, `DIVERGENCE="divergence"`,
`HEARTBEAT="heartbeat"`, `EXPORT_ERROR="export_error"`.
(Verified against `anvil/api/v1/training.py` emitted event names.)

### `StreamEvent` — `_shared/stream_event.py`
Typed SSE event.

| Field | Type | Notes |
|---|---|---|
| `type` | `StreamEventType` | Parsed from the `event:` line |
| `data` | `dict[str, Any]` | Parsed from the `data:` JSON line |

### Exception hierarchy — `_shared/errors/`
Plain exception classes (NOT `BaseModel`). Root `ApiError(Exception)` carries
`status_code: int | None` and `message: str`.

| Class | File | Trigger |
|---|---|---|
| `ApiError` | `api_error.py` | base for all SDK errors |
| `AuthenticationError` | `authentication_error.py` | `401`, `403` |
| `NotFoundError` | `not_found_error.py` | `404` |
| `ValidationError` | `validation_error.py` | `422` |
| `RateLimitError` | `rate_limit_error.py` | `429` (carries `retry_after: float \| None`) |
| `ServerError` | `server_error.py` | `5xx` (preserves server `error` text — SC-004) |
| `ConnectionError` | `connection_error.py` | transport-level failure / unreachable host |

---

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
