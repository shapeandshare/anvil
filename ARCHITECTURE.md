# Architecture Guide — anvil

**Last updated**: 2026-06-19

## Overview

anvil is a pip-installable Python package for training and experimenting with small LLMs from scratch. It follows a strict layered architecture that is enforced by convention and automated gates.

## Layer Hierarchy

```
Repository → Service → AnvilWorkbench → Routes / CLI
```

| Layer | Directory | Responsibility |
|---|---|---|
| **Repository** | `anvil/db/repositories/` | DB access only. One repository per entity. Async SQLAlchemy queries. No business logic. |
| **Service** | `anvil/services/<domain>/` | Business logic. Consumes repositories. One domain per sub-package. |
| **God Class** | `anvil/workbench.py` (`AnvilWorkbench`) | Single entry point exposing all services. Routes, CLI, and tests obtain services through it — never by directly instantiating a service. |
| **Routes** | `anvil/api/v1/` | FastAPI route handlers. Thin: extract params from request, call service, format response. No business logic. |
| **CLI** | `anvil/cli.py` | Command-line entry points. Same layer as Routes — calls `AnvilWorkbench`. |

### Supporting layers

| Layer | Directory | Responsibility |
|---|---|---|
| **Core engine** | `anvil/core/` | Stdlib-only training engine (zero pip dependencies). LlamaModel with RoPE, SwiGLU MLP, RMSNorm. |
| **Storage** | `anvil/storage/` | File I/O abstraction (local filesystem, S3-ready interface). |
| **Supervisor** | `anvil/supervisor/` | Process manager for background services (web server, MLflow). |

## Adding a new service

1. Create the service class in `anvil/services/<domain>/`. Implement business logic. Consume repositories via constructor injection.
2. Expose it on `AnvilWorkbench` as a lazy `@property` in `anvil/cli.py`.
3. Create route handlers in `anvil/api/v1/` accessing the service via `AnvilWorkbench`.
4. Register the route in `anvil/api/v1/router.py`.
5. Write unit tests in `tests/unit/services/` and integration tests in `tests/integration/`.
6. All gates (`make lint`, `make typecheck`, `make test`, `make vault-audit`) must pass.

## Quality gates

Every pull request into `main` must pass:
- **Lint**: `make lint` (ruff → black --check → isort --check → pylint)
- **Type check**: `make typecheck` (mypy --strict)
- **Test + coverage**: `make test` (pytest; coverage must meet/beat `fail_under` in `pyproject.toml`)
- **Vault audit**: `make vault-audit` (frontmatter validation, wikilink resolution, controlled vocabulary, ADR uniqueness)
- **Bump-scope guard**: confirms version-only bumps (pyproject.toml + CHANGELOG only) skip heavy gates

Local commands are identical to CI commands (parity guarantee).

## Architecture decisions

All significant architecture decisions are recorded as ADRs in `docs/vault/Decisions/`. Each ADR has a unique sequential identifier (ADR-001, ADR-002, etc.). A human-readable index is at `docs/vault/Decisions/README.md`.

## Routing Architecture

All API routes are defined in per-domain router modules under `anvil/api/v1/`. The top-level `router.py` (39 lines) is a thin aggregator that combines them via `include_router`:

| Module | Contents | Lines |
|--------|----------|-------|
| `router.py` | Aggregator (includes all others) | 39 |
| `training.py` | Training start/stop/stream endpoints | ~721 |
| `experiments.py` | Experiment listing, comparison, lineage | ~803 |
| `datasets.py` | Dataset CRUD, import, curation, export | ~1269 |
| `corpora.py` | Corpus CRUD, file listing, ingestion | ~838 |
| `registry.py` | Model registry | ~448 |
| `eval.py` | Evaluation endpoints | — |
| `inference.py` | Inference / sampling | — |
| `compute.py` | Compute backend selection | — |
| `health_ops.py` | Health check + service management | 319 |
| `pages.py` | HTML page rendering routes | 177 |
| `learning.py` | Learning content data + routes + inference sample | 1423 |