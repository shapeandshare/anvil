---
title: 'Implementation Plan: Client SDK'
type: spec
tags:
  - type/spec
  - domain/architecture
status: draft
created: '2026-06-21'
updated: '2026-06-21'
---

Back to [[Specs/026 Client SDK/Spec]].

# Implementation Plan: Client SDK

**Branch**: `026-client-sdk` | **Date**: 2026-06-21 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `docs/vault/Specs/026 Client SDK/spec.md`

## Summary

Build a pure-Python, async, fully-typed client SDK (`anvil.client`) that lets developers
connect to the anvil server API programmatically. The SDK adopts the **darkness**
client/command/abstract paradigm — a top-level `AnvilClient` facade aggregating per-domain
sub-clients, each delegating to one-command-per-resource classes that descend from an
`AbstractCommand` base — adapted to anvil's constitutional conventions (async-first,
Pydantic `BaseModel` DTOs, `StrEnum` over magic strings, one-class-per-file, bare
`__init__.py`, `mypy --strict`). Transport is `httpx.AsyncClient` (already a direct
dependency). The SDK unwraps the standard `{"data": ..., "error": ...}` envelope into typed
models, maps HTTP errors to typed exceptions, supports both `X-API-Key` and session-cookie
auth (with CSRF for cookie writes), provides an SSE stream client for training/content
event streams, and handles file upload/download.

## Technical Context

**Language/Version**: Python 3.11+ (matches repo; uses `StrEnum`, PEP 604 unions, PEP 563 `from __future__ import annotations`)
**Primary Dependencies**: `httpx>=0.27,<1` (transport — already a direct dep), `pydantic>=2,<3` (DTOs — already a dep). No new runtime dependencies.
**Storage**: N/A — the SDK is a stateless HTTP client; the only persisted state is an in-memory session cookie + optional API key held on the client instance.
**Testing**: `pytest` + `pytest-asyncio` (`asyncio_mode = "auto"`). SDK is tested against the live FastAPI app via `httpx.ASGITransport(app=app)` — the same in-process transport the existing `client` fixture uses, giving real end-to-end coverage with zero network and no live server.
**Target Platform**: Any Python 3.11+ environment (Linux/macOS). Pure library — no GUI, no platform-specific code.
**Project Type**: Library (importable Python package `anvil.client`) shipped inside the existing `anvil` distribution.
**Performance Goals**: SDK-induced overhead (envelope unwrap + Pydantic validation) under 100ms per typical response after the server replies (SC-003). No measurable throughput ceiling imposed by the SDK beyond `httpx`'s.
**Constraints**: `mypy --strict` clean; `ruff`/`black`/`isort`/`pylint` clean; NumPy docstrings on every module/class/method; one class per file; bare `__init__.py`; relative imports only inside the package; no `as any`/`# type: ignore` suppression.
**Scale/Scope**: ~12 domain sub-clients covering 80+ endpoints. Phased delivery: P1 = transport + auth + health + datasets + training (incl. SSE); P2 = experiments + registry + auth/session; P3 = file ops + inference + remaining domains (corpora, eval, compute, services, governance, content).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Applies? | Compliance |
|---|---|---|
| **I — Zero-Dependency Core** | No (this is not `anvil/core/`) | SDK lives in `anvil/client/`, NOT `anvil/core/`. Core remains untouched and stdlib-only. ✅ |
| **II — Educational Clarity** | Yes | SDK code prioritizes readability; docstrings explain WHY; quickstart demonstrates the facade→command flow. ✅ |
| **III — Seeded Reproducibility** | No | SDK does not run training; it forwards `seed`/`config` to the server unchanged. N/A. |
| **IV — TDD Mandatory** | Yes | Every command/sub-client gets a failing test first (Red-Green-Refactor). e2e tests via ASGI transport assert real envelope/error behavior. Coverage ratchet (`fail_under`) must not drop. ✅ |
| **V — Async-First** | Yes | The entire SDK is async — `httpx.AsyncClient`, `async def execute(...)`, async SSE generators. No sync surface in v1. ✅ |
| **VI — `__init__.py` Ownership** | Yes | `anvil/client/` and every sub-package get bare docstring-only `__init__.py`. No re-exports for internal use. Data-only dirs (none expected) get none. ✅ |
| **VII — Layered Architecture** | Yes (adapted) | The SDK mirrors the layering on the *client* side: `AnvilClient` (facade/god-class analogue) → `DomainClient` (service analogue) → `Command` (resource access analogue) → `Transport` (the only HTTP-primitive holder). No raw `httpx` calls leak above the transport layer. ✅ |
| **VIII — iOS-Grade Polish** | No (no UI) | SDK ships no UI/templates/CSS. N/A. |
| **IX — Pit of Success** | Yes | Defaults produce a working client: `AnvilClient()` reads `ANVIL_SERVER_URL` (default `http://localhost:8080`), sensible timeout/retry defaults. Missing optional auth doesn't crash health checks. ✅ |
| **X — Domain-Driven Decomposition** | Yes | Sub-packages follow bounded contexts (`datasets/`, `training/`, `experiments/`, …) with plural nouns; `_shared/` for cross-domain types (transport, base command, errors, response wrapper); max 2 levels of nesting; one class per file; result/error types co-located. ✅ |

**Additional Constraints**:
- `mypy --strict` — enforced; SDK ships full annotations + `py.typed` already covers it (top-level marker covers subpackages). ✅
- Pydantic `BaseModel` for all DTOs — yes; no dataclasses. ✅
- One class per file — yes; `StrEnum`s in their own files unless inseparable from a class. ✅
- Lean dependencies — **zero new runtime deps** (`httpx`, `pydantic` already present). No ADR for a new dependency required, but an ADR documenting the SDK architecture decision SHALL be written (`docs/vault/Decisions/`). ✅
- New `[project.scripts]` — none required for v1 (library only). Optional `anvil-client` CLI is explicitly OUT of scope for v1.

**Gate result**: PASS — no violations. Complexity Tracking table not required.

## Project Structure

### Documentation (this feature)

```text
docs/vault/Specs/026 Client SDK/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   ├── client-facade.md     #   AnvilClient + ServerConfig public surface
│   ├── transport.md         #   Transport + Response[T] + envelope/error mapping
│   ├── commands.md          #   AbstractCommand contract + per-domain command catalog
│   └── streaming.md         #   SSE stream client contract + StreamEvent types
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

The SDK is a new domain top-level package under `anvil/`, decomposed per Article X. Internal,
cross-domain infrastructure (transport, base command, errors, response wrapper, config) lives
in `anvil/client/_shared/`. Each API domain is its own plural-noun sub-package holding one
command class per file plus a `DomainClient` aggregator.

```text
anvil/client/
├── __init__.py                      # bare docstring-only (Article VI)
├── anvil_client.py                  # AnvilClient — top-level facade (one class)
├── _shared/                         # cross-domain SDK infrastructure (Article X §10.3)
│   ├── __init__.py                  #   bare docstring-only
│   ├── server_config.py             #   ServerConfig (BaseModel) — url, timeout, retries, env-var loading
│   ├── transport.py                 #   Transport — wraps httpx.AsyncClient; sole HTTP-primitive holder
│   ├── abstract_command.py          #   AbstractCommand — base for all commands (one class)
│   ├── response.py                  #   Response[T] — generic envelope unwrapper
│   ├── stream_event.py              #   StreamEvent (BaseModel) — typed SSE event
│   ├── stream_event_type.py         #   StreamEventType (StrEnum) — metrics/complete/error/...
│   ├── http_method.py               #   HttpMethod (StrEnum) — GET/POST/PUT/DELETE/PATCH
│   └── errors/                      #   typed exception hierarchy (Article X §10.2)
│       ├── __init__.py              #     bare docstring-only
│       ├── api_error.py             #     ApiError (base)
│       ├── authentication_error.py  #     AuthenticationError (401/403)
│       ├── not_found_error.py       #     NotFoundError (404)
│       ├── validation_error.py      #     ValidationError (422)
│       ├── rate_limit_error.py      #     RateLimitError (429)
│       ├── server_error.py          #     ServerError (5xx)
│       └── connection_error.py      #     ConnectionError (transport-level)
├── health/                          # P1 — health domain
│   ├── __init__.py
│   ├── health_client.py             #   HealthClient (DomainClient aggregator)
│   ├── health_get_command.py        #   GET /v1/health
│   └── health_detailed_command.py   #   GET /v1/health/detailed
├── datasets/                        # P1 — datasets domain
│   ├── __init__.py
│   ├── datasets_client.py           #   DatasetsClient aggregator
│   ├── dataset.py                   #   Dataset (BaseModel) response DTO
│   ├── dataset_list_command.py      #   GET /v1/datasets (+ ?q= search)
│   ├── dataset_get_command.py       #   GET /v1/datasets/{id}
│   ├── dataset_create_command.py    #   POST /v1/datasets
│   ├── dataset_update_command.py    #   PUT /v1/datasets/{id}
│   ├── dataset_delete_command.py    #   DELETE /v1/datasets/{id}
│   ├── dataset_upload_command.py    #   POST /v1/datasets/upload (multipart)
│   └── dataset_export_command.py    #   GET /v1/datasets/{id}/export (download)
├── training/                        # P1 — training domain (incl. SSE)
│   ├── __init__.py
│   ├── training_client.py           #   TrainingClient aggregator
│   ├── training_config.py           #   TrainingConfig (BaseModel) request DTO
│   ├── training_start_result.py     #   TrainingStartResult (run_id, mlflow_run_id, experiment_id)
│   ├── training_start_command.py    #   POST /v1/training/start
│   ├── training_status_command.py   #   GET /v1/training/{run_id}/status
│   ├── training_stop_command.py     #   POST /v1/training/{run_id}/stop
│   └── training_stream_command.py   #   GET /v1/training/stream/{run_id} (SSE)
├── experiments/                     # P2 — experiments domain
│   ├── __init__.py
│   ├── experiments_client.py
│   ├── experiment.py                #   Experiment (BaseModel)
│   ├── experiment_list_command.py
│   ├── experiment_get_command.py
│   ├── experiment_compare_command.py
│   ├── experiment_metrics_command.py
│   ├── experiment_delete_command.py
│   ├── experiment_artifacts_command.py
│   └── experiment_download_command.py
├── registry/                        # P2 — model registry domain
│   ├── __init__.py
│   ├── registry_client.py
│   ├── registered_model.py
│   ├── registry_register_command.py
│   ├── registry_list_command.py
│   ├── registry_get_command.py
│   └── registry_delete_command.py
├── inference/                       # P3 — inference domain
│   ├── __init__.py
│   ├── inference_client.py
│   ├── inference_sample_command.py
│   └── inference_models_command.py
└── (P3 domains, same shape) corpora/, eval/, compute/, services/, governance/, content/
```

> NOTE on **Article X §10.5 (max two levels of nesting)**: `anvil/client/_shared/errors/` is
> two levels below the `anvil/client/` package root (`_shared/` then `errors/`). This is the
> maximum permitted and is justified: error classes are tightly coupled cross-domain types
> (§10.2/§10.3) that belong together under `_shared/`. No deeper nesting is used anywhere.

### Tests

```text
tests/unit/client/                   # unit tests — mirror SDK package layout
├── _shared/
│   ├── test_server_config.py        #   env-var loading, defaults, validation
│   ├── test_transport.py            #   envelope unwrap, retry/backoff, error mapping
│   ├── test_response.py             #   Response[T] generic behavior
│   └── test_errors.py               #   status-code → exception mapping
├── test_anvil_client.py             #   facade wiring; sub-clients reachable
└── (per-domain command tests as needed for pure-logic units)

tests/e2e/api/                       # e2e via ASGITransport(app=app) — real round-trips
├── test_client_health.py            #   P1
├── test_client_datasets.py          #   P1
├── test_client_training.py          #   P1 (incl. SSE stream assertions)
├── test_client_experiments.py       #   P2
├── test_client_registry.py          #   P2
└── test_client_inference.py         #   P3 ... (one file per domain)
```

**Structure Decision**: Single-project library layout. The SDK is a new domain package
`anvil/client/` inside the existing `anvil` distribution (NOT a separate distribution), so it
ships automatically via the existing `[tool.setuptools.packages.find] include = ["anvil*"]`
and inherits the top-level `py.typed` marker. Cross-domain SDK infrastructure is grouped under
`anvil/client/_shared/` per Article X §10.3; every API domain is a plural-noun sub-package with
one command class per file and a `DomainClient` aggregator, mirroring the
`anvil/services/<domain>/` decomposition already used in the codebase. Tests mirror the package
layout under `tests/unit/client/` (logic) and `tests/e2e/api/test_client_*.py` (round-trips
against the in-process FastAPI app).

## Complexity Tracking

> No constitutional violations. Table intentionally omitted.
