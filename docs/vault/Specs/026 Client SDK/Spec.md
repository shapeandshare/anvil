---
title: 'Feature Specification: Client SDK'
type: spec
tags:
  - type/spec
  - domain/architecture
status: draft
created: '2026-06-21'
updated: '2026-06-21'
---
### User Story 3 - Train Models Programmatically (Priority: P1)

A developer using the SDK can start a training run with custom hyperparameters, monitor its progress via event streams, stop it if needed, and retrieve the trained model reference — all through typed SDK calls.

**Why this priority**: Training orchestration is the core value proposition of anvil. This enables automation of experiments, hyperparameter sweeps, and CI pipelines.

**Independent Test**: Can be tested by starting a training run with known hyperparameters, subscribing to the progress stream, verifying events arrive, then stopping the run and confirming its terminal state.

**Acceptance Scenarios**:

1. **Given** a connected client, **When** the developer calls `client.training.start(config)` with a valid `TrainingConfig` object (n_embd, n_layer, n_head, num_steps, learning_rate, etc.), **Then** a training run is initiated and the response contains `run_id`, `mlflow_run_id`, and `experiment_id`.
2. **Given** a started training run, **When** the developer subscribes to the run's event stream via `client.training.stream(run_id)`, **Then** they receive SSE-formatted events: `metrics` (at each step with loss value), `complete` (when finished), and `error` (if the run fails).
3. **Given** a running training run, **When** the developer calls `client.training.stop(run_id)`, **Then** the run is interrupted and a terminal event is sent.
4. **Given** a started training run, **When** the developer calls `client.training.status(run_id)`, **Then** they receive the current run state (active/completed/failed).
5. **Given** a completed training run, **When** the developer reviews the stream history, **Then** all metrics events are available as typed objects with step number and loss value.

---

### User Story 4 - Manage Experiments and Models (Priority: P2)

A developer using the SDK can list experiments, compare experiment results, register models from experiments, and manage the model registry.

**Why this priority**: After training, developers need to organize experiments and manage model artifacts — essential for MLOps workflows but not required for the first training run.

**Independent Test**: Can be tested by starting two training runs, listing experiments, comparing them, registering one as a model, and verifying the model appears in the registry.

**Acceptance Scenarios**:

1. **Given** completed training runs, **When** the developer calls `client.experiments.list()`, **Then** all experiments are returned as typed objects with enrichment data (run count, best loss, duration).
2. **Given** multiple experiment ids, **When** the developer calls `client.experiments.compare([id1, id2])`, **Then** a side-by-side comparison dataset is returned.
3. **Given** a completed experiment, **When** the developer calls `client.experiments.get_metrics(id)`, **Then** the loss metric history is returned as a list of (step, value) pairs.
4. **Given** a completed experiment, **When** the developer calls `client.registry.register(experiment_id)`, **Then** a model record is created in the registry and the model id is returned.
5. **Given** registered models, **When** the developer calls `client.registry.list()`, **Then** all models with their versions are returned.

---

### User Story 5 - Authentication and Session Management (Priority: P2)

A developer using the SDK can authenticate with the anvil server using either an API key or session-based login, with the SDK handling credential storage and token refresh transparently.

**Why this priority**: Some endpoints require authentication. The SDK must support both authentication mechanisms provided by the anvil API to access protected resources.

**Independent Test**: Can be tested by connecting with a valid API key, confirming authenticated requests succeed, then testing that unauthenticated requests receive the appropriate 401/403 response.

**Acceptance Scenarios**:

1. **Given** an API key, **When** the developer configures the client with `client = AnvilClient(api_key="...")`, **Then** all subsequent requests include the `X-API-Key` header automatically.
2. **Given** a client without credentials, **When** the developer calls `client.login(api_key)`, **Then** the SDK sends a `POST /login` request, stores the returned session cookie, and uses it for subsequent requests.
3. **Given** an authenticated session, **When** the session expires and a new request is made, **Then** the SDK transparently re-authenticates or raises a clear session-expired error.
4. **Given** invalid credentials, **When** the developer attempts to authenticate, **Then** the SDK returns a typed `AuthenticationError`.

---

### User Story 6 - File Operations and Inference (Priority: P3)

A developer using the SDK can download model artifacts, export datasets, and run inference on a trained model.

**Why this priority**: These are advanced workflows that build on earlier stories. Useful for post-training analysis but not required for core automation.

**Independent Test**: Not tested independently — requires a trained model with exported artifacts. Verified as part of the end-to-end training workflow.

**Acceptance Scenarios**:

1. **Given** a completed training run with exported artifacts, **When** the developer calls `client.experiments.list_artifacts(experiment_id, run_id)`, **Then** available artifact files are listed with their paths and sizes.
2. **Given** an artifact path, **When** the developer calls `client.experiments.download_artifact(experiment_id, run_id, path)`, **Then** the artifact file is downloaded to a specified local path.
3. **Given** a dataset id, **When** the developer calls `client.datasets.export(id, format="txt")`, **Then** the dataset content is downloaded in the requested format.
4. **Given** a registered model, **When** the developer calls `client.inference.sample(model_id, prompt, temperature)`, **Then** generated text is returned.

---

### Edge Cases

- **Server unreachable**: What happens when the server is down at connection time vs. mid-operation?
- **Authentication expiry**: How does the SDK handle session cookie expiration during a long-running streaming operation?
- **Retry on transient failure**: Should the SDK automatically retry on 5xx errors? (Yes, with configurable retry count and backoff.)
- **Large file uploads**: How are large dataset uploads handled — streaming or buffered?
- **SSE reconnection**: Does the SSE stream client auto-reconnect on connection drops?
- **Concurrent operations**: Can multiple training runs be managed from a single client instance?
- **Rate limiting**: How does the SDK respond when the server returns 429 Too Many Requests?
- **Non-blocking monitoring**: How can a developer monitor a training stream in the background while doing other work?

## Requirements

### Functional Requirements

- **FR-001**: The SDK MUST provide a client class (`AnvilClient`) that accepts server URL, optional API key, and timeout/retry configuration.
- **FR-002**: The SDK MUST organize API operations into domain-specific sub-clients accessed via named attributes (e.g., `client.datasets.*`, `client.training.*`, `client.experiments.*`).
- **FR-003**: The SDK MUST support both authentication mechanisms: `X-API-Key` header (direct config) and session cookie (via `POST /login`).
- **FR-004**: All API responses MUST be returned as typed Pydantic model instances, not raw dictionaries.
- **FR-005**: API errors MUST be mapped to typed exception classes (e.g., `AuthenticationError`, `NotFoundError`, `ServerError`, `ValidationError`).
- **FR-006**: The SDK MUST provide an SSE stream client for the `/v1/training/stream/{run_id}` endpoint that yields typed event objects.
- **FR-007**: The SDK MUST expose file download for artifacts and dataset exports as stream-to-disk or in-memory bytes.
- **FR-008**: The SDK MUST expose dataset file upload with support for multipart/form-data.
- **FR-009**: The SDK MUST support configurable retry with exponential backoff for transient failures — `5xx` server errors, `429` rate-limit responses (honoring `Retry-After` when present), and transport-level connection errors. Non-idempotent writes (`POST`/`PUT`/`PATCH`) MUST NOT be auto-retried unless an idempotency key is supplied.
- **FR-010**: The health check (`GET /v1/health`) MUST be accessible even before authentication is configured.
- **FR-011**: The SDK MUST use the standard `{"data": ..., "error": None}` response envelope to consistently unwrap responses.
- **FR-012**: The SDK MUST expose the complete anvil API surface through the following domain sub-clients:

| Domain Sub-client | API Resources Covered |
|---|---|
| `client.health.*` | `/v1/health`, `/v1/health/detailed` |
| `client.datasets.*` | All `/v1/datasets/*` endpoints |
| `client.corpora.*` | All `/v1/corpora/*` endpoints |
| `client.training.*` | All `/v1/training/*` endpoints |
| `client.experiments.*` | All `/v1/experiments/*` endpoints |
| `client.registry.*` | All `/v1/registry/*` endpoints |
| `client.inference.*` | All `/v1/inference/*` endpoints |
| `client.eval.*` | `/v1/eval/*`, `/v1/eval-datasets/*` |
| `client.compute.*` | `/v1/compute/*` |
| `client.services.*` | All `/v1/services/*` endpoints |
| `client.governance.*` | All `/v1/governance/*` endpoints |
| `client.content.*` | All `/v1/content/*` endpoints |

### Key Entities

- **AnvilClient** (facade): Top-level client object. Holds connection configuration (`ServerConfig`), authentication state, and domain sub-client instances. One class — no inheritance.
- **ServerConfig**: Connection configuration DTO — server URL (base), timeout in seconds, retry count, retry backoff factor. Configurable via constructor args and/or environment variables (`ANVIL_SERVER_URL`, `ANVIL_TIMEOUT`, `ANVIL_RETRY_COUNT`).
- **BaseCommand**: Abstract base class for all domain commands. Each concrete command handles one API resource (e.g., `DatasetCreateCommand`, `TrainingStartCommand`, `ExperimentListCommand`). Commands own their HTTP method, URL path construction, request DTO type, and response DTO type.
- **DomainClient**: An intermediate aggregation class per domain (e.g., `DatasetsClient`, `TrainingClient`, `ExperimentsClient`). Owns command instances and exposes high-level methods that delegate to commands — one class per API domain group.
- **Response[T]**: Generic response wrapper that unwraps `{"data": T, "error": None}` into a typed Python object.
- **StreamEvent**: Typed Pydantic model for SSE events — `type` (metrics/complete/error/etc.), `data` (generic payload), `timestamp`.
- **ApiError**: Base exception for all SDK errors; subclasses `AuthenticationError`, `NotFoundError`, `ServerError`, `ValidationError`, `RateLimitError`, `ConnectionError`.
- **TrainingConfig**: Pydantic model for training hyperparameters (n_embd, n_layer, n_head, block_size, num_steps, learning_rate, beta1, beta2, temperature, compute_backend, dataset_id, corpus_id, content_version_id, device).
- **Dataset**: Pydantic model representing a dataset record — id, name, description, sample_count, created_at, updated_at, metrics.
- **Experiment**: Pydantic model representing an experiment — id, name, run_count, best_loss, duration, mlflow_url, artifacts.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Developers can install the SDK and connect to a running anvil server with fewer than 5 lines of code.
- **SC-002**: All anvil API endpoints (80+) are accessible through the SDK with typed request/response models — no endpoint requires raw HTTP calls.
- **SC-003**: SDK-induced overhead (envelope unwrap + Pydantic validation) for the 5 most common operations (health check, list datasets, start training, list experiments, create dataset) adds under 100ms on top of the server's own response time, measured as `total_sdk_call_time − server_processing_time` over a sample of calls.
- **SC-004**: SDK correctly handles all error scenarios: invalid auth returns `AuthenticationError`, missing resource returns `NotFoundError`, server errors return `ServerError` with the server's error message preserved — each with a dedicated exception type.
- **SC-005**: SSE stream client successfully delivers all event types (metrics, complete, error, divergence, heartbeat, export_error) as typed objects with no data loss during a 1000-step training run.
- **SC-006**: The SDK package passes `mypy --strict` type checking and all tests pass in CI.

## Assumptions

- The SDK will be a Python 3.11+ package (`anvil.client`) distributed alongside the existing `anvil` package or as a companion package.
- The SDK will use `httpx` (async-capable) as the HTTP transport — matching the project's existing `httpx` dependency in test infrastructure — rather than `requests`.
- The SDK will follow the `anvil` project conventions: Pydantic `BaseModel` for all DTOs, `mypy --strict` type enforcement, `ruff` linting, NumPy-style docstrings, enum over magic strings, relative imports within the package, one class per file.
- The API response envelope `{"data": ..., "error": None}` is consistent across all endpoints. If any endpoint deviates, the SDK will normalize it at the transport layer.
- The `POST /login` endpoint sets `Set-Cookie` headers that the SDK's HTTP client can capture and replay on subsequent requests.
- The anvil server runs on `http://localhost:8080` by default (overridable through `ANVIL_SERVER_URL` env var or constructor argument).
- The SDK will NOT include the core `anvil.core.engine` (no training engine, no MLflow client) — it is a pure API client.
- Mobile platforms and non-Python languages are out of scope for v1.
