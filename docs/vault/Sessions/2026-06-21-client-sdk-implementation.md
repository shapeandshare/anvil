# Session: Client SDK Implementation

**Date**: 2026-06-21
**Feature**: 026-client-sdk

## Summary

Implemented a full Client SDK (`anvil.client`) for the anvil server API. The SDK follows the darkness/light pattern (facade → domain client → command → transport) adapted to the anvil constitution. Covers all 12 API domains with typed request/response DTOs, dual auth (API key + session cookie), SSE streaming, file upload/download, and configurable retry/backoff.

## Deliverables

- **95 source files** across `anvil/client/` (12 domain packages + `_shared/` infrastructure)
- **`AnvilClient` facade** exposing 12 domain sub-clients: health, datasets, training, experiments, registry, inference, corpora, eval, compute, services, governance, content
- **`Transport` layer**: `httpx.AsyncClient` wrapper, envelope unwrap, retry/backoff, SSE parsing, file download, status→exception mapping
- **Auth**: `X-API-Key` and session cookie login/logout with CSRF
- **ADR-039**: Published at `docs/vault/Decisions/ADR-039-client-sdk-architecture.md`

## Quality Gates

- `mypy --strict`: 0 errors (95 files)
- `ruff check`: All checks passed
- Unit tests: 43/43 passed
- E2E health tests: 3/3 passed (ASGI transport)

## Key Decisions

- Zero new dependencies (httpx + pydantic already in project)
- In-distribution packaging (no separate PyPI package)
- Hand-crafted commands over OpenAPI generation (for type precision)
- Injected httpx client for testability (ASGI transport pattern)

## Next Steps

- Add e2e tests for remaining domains (datasets, training, experiments, registry, auth)
- Run `make vault-audit` after venv rebuild
- Add SDK section to README.md