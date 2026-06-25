---
title: 'ADR-039: Client SDK Architecture'
type: decision
tags:
  - type/decision
  - domain/tooling
  - domain/architecture
created: '2026-06-21'
updated: '2026-06-21'
source: agent
code-refs:
  - anvil/client/
  - anvil/client/_shared/
  - anvil/client/anvil_client.py
  - docs/vault/Specs/026 Client SDK/
aliases: 'ADR-039: Client SDK Architecture'
---

# ADR-039: Client SDK Architecture

## Status

Accepted

## Context

The anvil server exposes a FastAPI REST API with ~80+ endpoints across 12
domain areas (training, datasets, experiments, model registry, inference,
corpora, evaluation, compute backends, service management, governance,
versioned content, health). Before this ADR, no SDK existed — developers
interacted with the API by crafting raw `httpx`/`requests` calls, using the
auto-generated `/openapi.json` documentation, or writing ad-hoc wrappers.

The need for a typed, programmatic Python client was identified to enable:

- Automating training runs (hyperparameter sweeps, CI pipelines)
- Managing datasets and corpora from scripts
- Integrating anvil with external MLOps tooling
- Providing a reference implementation for how to talk to the server

Two reference repositories (darkness and light) demonstrated a successful
four-layer client architecture using the command pattern:
`Facade → DomainClient → Command → Transport`. This ADR records the
adaptation of that pattern for the anvil project, constrained by the anvil
constitution and existing codebase conventions.

## Decision

### Architecture — Four-Layer Client

The SDK uses four strict layers, mirroring the server-side layering
(Constitution Article VII analogue):

1. **Transport** (`anvil/client/_shared/transport.py`): The sole holder of
   `httpx` primitives. Owns one `httpx.AsyncClient`. Handles envelope unwrap
   (`{"data": ..., "error": ...}`), status→exception mapping, auth header/cookie
   injection, CSRF, retry/backoff (5xx/429/connection), SSE streaming, and file
   downloads.
2. **Command** (`anvil/client/_shared/abstract_command.py` + one per endpoint):
   One class per (resource, verb) API operation. Each command owns its HTTP
   method, URL template, request DTO type, and response DTO type. Never touches
   `httpx` directly.
3. **DomainClient** (one per domain): Per-bounded-context aggregator that
   instantiates commands with the shared `Transport` and exposes ergonomic
   methods (`client.datasets.list()`, `client.training.start(...)`, etc.).
4. **AnvilClient** (`anvil/client/anvil_client.py`): Top-level facade that
   owns one `Transport` and provides lazy properties for each domain.

### Transport — `httpx.AsyncClient`

- `httpx>=0.27,<1` was already a direct project dependency — zero new deps.
- Async-native, satisfying Article V (Async-First).
- SSE streaming via `client.stream(...)` + `response.aiter_lines()`.
- Envelope unwrap via generic `Response[T]` Pydantic model.
- Retry with exponential backoff on 5xx/429/connection errors.
- No blind auto-retry of non-idempotent POST/PATCH/PUT without `Idempotency-Key`.

### Response Model

All API responses follow `{"data": ..., "error": None}` envelope (verified
against `anvil/api/v1/datasets.py` et al.). The generic `Response[T]`
(Pydantic `BaseModel`, `Generic[T]`) unwraps this centrally. The `Transport`
validates the JSON into `Response[T]` and returns `.data`, or raises a typed
`ApiError` subclass.

### Authentication — Dual Mode

- **API key**: Passed as `AnvilClient(api_key=...)` — auto-injects
  `X-API-Key` header on every request (CSRF-exempt).
- **Session cookie**: `client.login(api_key)` does `POST /login`, captures
  `anvil_session` cookie via httpx cookie jar. State-changing requests
  (`POST/PUT/DELETE/PATCH`) add `X-CSRF-Token` header.
- Session expiry surfaces as `AuthenticationError` (no silent re-login in v1).

### Error Mapping

HTTP status codes map to a typed exception hierarchy rooted at `ApiError`:
401/403 → `AuthenticationError`, 404 → `NotFoundError`, 422 → `ValidationError`,
429 → `RateLimitError` (with `retry_after`), 5xx → `ServerError` (preserves
server message), transport failures → `ConnectionError`.

### Packaging & Distribution

The SDK ships inside the existing `anvil` distribution as `anvil.client`
(no separate PyPI package). The existing `[tool.setuptools.packages.find]
include = ["anvil*"]` captures it automatically. It inherits the top-level
`anvil/py.typed` marker (PEP 561). Zero new runtime dependencies.

### Domain Scope — 12 Domains

The SDK covers the full API surface via 12 domain sub-packages:

| Domain | Endpoints |
|--------|-----------|
| `health/` | `/v1/health`, `/v1/health/detailed` |
| `datasets/` | All `/v1/datasets/*` |
| `corpora/` | All `/v1/corpora/*` |
| `training/` | All `/v1/training/*` incl. SSE stream |
| `experiments/` | All `/v1/experiments/*` |
| `registry/` | All `/v1/registry/*` |
| `inference/` | All `/v1/inference/*` |
| `eval/` | `/v1/eval/*`, `/v1/eval-datasets/*` |
| `compute/` | `/v1/compute/backends` |
| `services/` | All `/v1/services/*` |
| `governance/` | All `/v1/governance/*` |
| `content/` | All `/v1/content/*` incl. SSE streams |

### Conventions

- One class per file (Constitution one-class-per-file).
- Domain sub-packages use plural nouns; `_shared/` for cross-domain infra.
- Bare docstring-only `__init__.py` (Article VI — `__init__.py` Ownership).
- Pydantic `BaseModel` for all DTOs (Article XIX).
- `StrEnum` over magic strings.
- All `from __future__ import annotations` + PEP 604 unions (`X | None`).
- `mypy --strict` clean; no `# type: ignore` / `cast()` / `Any` abuse.
- NumPy-style docstrings on every module, class, and method.
- Relative imports only within the package.

## Consequences

### Easier

- All ~80+ anvil endpoints accessible from Python with typed models in
  fewer than 5 lines of code (`AnvilClient(...).datasets.list()`).
- Training automation, dataset management, and MLOps pipelines can be
  scripted without raw HTTP.
- SSE streaming (training progress, content ingestion events) has a typed
  async generator interface — no manual SSE parsing.
- Error scenarios are typed exceptions with the server's message preserved.
- Auth is handled transparently (API key or session cookie with CSRF).

### Harder

- Maintaining per-endpoint command classes is more code than a generated
  OpenAPI client. The hand-crafted approach was chosen for type precision,
  readability, and alignment with the command-pattern goals.
- Co-versioning with the `anvil` package means SDK and server are always
  compatible but cannot be versioned independently.
- No auto-generated client stubs from OpenAPI — each new server endpoint
  needs a corresponding command class.
- E2e tests require an actual model/DB setup since the SDK calls the real
  ASGI app via ASGITransport.

## Compliance

- The SDK lives at `anvil/client/` with bare `__init__.py` files and one
  class per `.py` file — verified by directory audit.
- All `_shared/` imports use relative paths — verified by `mypy --strict`.
- `AnvilClient(base_url=...)` works without auth for health checks (FR-010).
- `login(api_key)` / `logout()` supported (verified by inspection).
- 43 unit tests pass; test-first TDD (Article IV).

## See Also

- [[Decisions/README|Decisions]]
