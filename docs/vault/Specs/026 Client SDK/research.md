# Phase 0 Research: Client SDK

**Feature**: 026-client-sdk | **Date**: 2026-06-21

This document resolves every technical decision needed to implement the SDK. The spec contained
no `[NEEDS CLARIFICATION]` markers; this research records the rationale behind each design
choice and the alternatives rejected, grounded in (a) the anvil constitution, (b) the existing
codebase conventions, and (c) the darkness/light reference patterns.

---

## R1 — HTTP transport library

- **Decision**: Use `httpx.AsyncClient` as the transport, wrapped in a single `Transport` class.
- **Rationale**:
  - `httpx>=0.27,<1` is **already a direct dependency** in `pyproject.toml` — zero new deps (Constitution: lean dependencies).
  - It is async-native, satisfying Article V (Async-First) with no sync surface.
  - It supports SSE streaming via `client.stream(...)` + `response.aiter_lines()`, file upload via `files=`, and cookie persistence via its `cookies` jar — covering every spec requirement.
  - The existing test suite already drives the FastAPI app through `httpx.ASGITransport(app=app)`, so the SDK can be tested in-process with the same proven mechanism.
- **Alternatives considered**:
  - `requests` (used by darkness): rejected — synchronous, violates Article V, and would add a new dependency.
  - `aiohttp`: rejected — new dependency, heavier, and no in-process ASGI transport for testing.
  - stdlib `urllib`/`http.client`: rejected — no async, no ergonomic streaming/multipart, more code to maintain.

---

## R2 — Client architecture (facade / domain / command / transport)

- **Decision**: Four-layer client architecture mirroring anvil's server-side layering (Article VII):
  1. `AnvilClient` — top-level facade (analogue of the `AnvilWorkbench` god class) that owns one `Transport` and exposes per-domain sub-clients as attributes (`client.datasets`, `client.training`, …).
  2. `DomainClient` (e.g. `DatasetsClient`) — per-bounded-context aggregator (analogue of a Service) exposing ergonomic methods that delegate to commands.
  3. `Command` (e.g. `DatasetCreateCommand`) — one class per (resource, verb) (analogue of repository access) that owns its HTTP method, URL template, request DTO, and response DTO.
  4. `Transport` — the ONLY holder of `httpx` primitives (analogue of the repository's DB primitives); no raw HTTP leaks above it.
- **Rationale**:
  - Directly adapts the darkness `StateClient → AbstractCommand → requests` pattern the user asked for, while honoring Article VII layering and Article X domain decomposition.
  - Each command being a single class fits one-class-per-file cleanly and makes the 80+ endpoints individually testable.
  - The facade gives the <5-lines-of-code onboarding required by SC-001.
- **Alternatives considered**:
  - Flat client with one giant class holding 80+ methods: rejected — violates one-class-per-file and Article X domain decomposition; untestable in isolation.
  - Generated client from OpenAPI: rejected for v1 — the anvil app does not expose a curated `/openapi.json` (some routes return HTML/SSE), generated types would be lossy, and it forfeits the requested hand-crafted command paradigm. (Recorded as a future option.)

---

## R3 — Response envelope unwrapping

- **Decision**: A generic `Response[T]` (Pydantic generic model) parses `{"data": T, "error": <str|null>}`; the `Transport` validates the JSON into `Response[T]` and returns `.data`, raising a typed error when `error` is non-null or the HTTP status is non-2xx.
- **Rationale**: Verified against source — e.g. `anvil/api/v1/datasets.py` returns `{"data": _serialize(d), "error": None}` consistently. A generic wrapper centralizes unwrap logic in one place and yields typed `.data` for callers.
- **Alternatives considered**:
  - Per-command manual dict access: rejected — duplicated, error-prone, violates DRY and typing goals.
  - Returning raw dicts: rejected — violates FR-004 (typed models, not dicts).

---

## R4 — Error → exception mapping

- **Decision**: A typed exception hierarchy rooted at `ApiError`, mapped from HTTP status in the `Transport`:
  - `401`/`403` → `AuthenticationError`
  - `404` → `NotFoundError`
  - `422` → `ValidationError`
  - `429` → `RateLimitError`
  - `5xx` → `ServerError` (preserves the server's `error` message — SC-004)
  - transport/connection failures → `ConnectionError`
- **Rationale**: Satisfies FR-005 and SC-004; gives callers `try/except` granularity. Each exception is its own file under `_shared/errors/` per one-class-per-file + Article X §10.2 (tightly-coupled error types co-located).
- **Alternatives considered**:
  - Single generic exception with a `.status` attribute: rejected — coarse, forces callers to branch on integers, less Pythonic.

---

## R5 — Authentication (API key + session cookie + CSRF)

- **Decision**:
  - Constructor accepts `api_key`; when present, `Transport` sends `X-API-Key` on every request (verified header name in `anvil/api/app.py`).
  - `AnvilClient.login(api_key)` performs `POST /login`; the resulting `anvil_session` cookie is captured automatically by the `httpx` cookie jar and replayed on subsequent requests.
  - For cookie-authenticated state-changing requests (`POST/PUT/DELETE/PATCH`), the `Transport` attaches the `X-CSRF-Token` header (anvil enforces CSRF for cookie writes; API-key auth is CSRF-exempt).
  - Session expiry surfaces as `AuthenticationError`; the SDK does not silently re-login in v1 (explicit, predictable).
- **Rationale**: Matches the anvil dual-auth model exactly (FR-003, US-5). API-key path is the simplest "pit of success" default; cookie+CSRF path supports interactive/session flows.
- **Alternatives considered**:
  - Auto-refresh sessions transparently: deferred — adds hidden state/complexity; explicit error is clearer for v1. (Spec edge case acknowledges either behavior is acceptable; we choose explicit.)
  - Storing credentials on disk: rejected — out of scope; credentials live only in-memory on the client instance.

---

## R6 — SSE streaming client

- **Decision**: `training_stream_command` (and content stream commands later) use `httpx`'s `client.stream("GET", url)` and parse `event:`/`data:` lines from `response.aiter_lines()` into typed `StreamEvent` objects, yielded from an `async` generator. `StreamEventType` is a `StrEnum` (`metrics`, `complete`, `error`, `divergence`, `heartbeat`, `export_error`).
- **Rationale**: Verified anvil emits `event: <type>\ndata: <json>\n\n` (e.g. `anvil/api/v1/training.py` emits `event: error`, `event: heartbeat`, and dynamic `event: {msg['event']}`). Async generator gives natural `async for ev in client.training.stream(run_id)` ergonomics (FR-006, SC-005). `StrEnum` satisfies "enums over magic strings."
  - v1 does NOT auto-reconnect (spec edge case allows either; explicit is simpler/safer). Heartbeats are surfaced as events so callers can detect liveness.
- **Alternatives considered**:
  - `httpx-sse` third-party package: rejected — new dependency for a ~30-line parser.
  - Callback-based API: rejected — async generator is more idiomatic and composable.

---

## R7 — File upload & download

- **Decision**:
  - Upload (`dataset_upload_command`): `httpx` multipart via `files={"file": (name, content, mime)}` (verified shape in tests).
  - Download (`dataset_export_command`, `experiment_download_command`): stream response to a caller-provided path, or return `bytes` for small payloads. Use `client.stream(...)` to avoid buffering large artifacts in memory.
- **Rationale**: Satisfies FR-007, FR-008, US-6. Streaming-to-disk handles large artifacts (spec edge case).
- **Alternatives considered**: buffering everything in memory — rejected for large files.

---

## R8 — Configuration & defaults (Pit of Success)

- **Decision**: `ServerConfig` (Pydantic `BaseModel`) holds `base_url`, `timeout`, `retry_count`, `retry_backoff`. Resolution order per field: explicit constructor arg > environment variable > built-in default.
  - `ANVIL_SERVER_URL` (default `http://localhost:8080`)
  - `ANVIL_TIMEOUT` (default `30.0` seconds)
  - `ANVIL_RETRY_COUNT` (default `3`)
  - `ANVIL_RETRY_BACKOFF` (default `0.5` — exponential factor)
- **Rationale**: Mirrors darkness `CommandOptions` env-var pattern but adapted to anvil naming. Defaults make `AnvilClient()` work out-of-the-box against a local server (Article IX, SC-001).
- **Alternatives considered**:
  - `pydantic-settings` `BaseSettings` (already a dep): viable, but a plain `BaseModel` with an explicit classmethod loader keeps construction transparent and avoids implicit global env coupling. Either is acceptable; chosen `BaseModel` for explicitness. (Implementation may use `pydantic-settings` if cleaner — recorded as acceptable.)

---

## R9 — Retry & backoff

- **Decision**: `Transport` retries idempotent failures (transport errors and `5xx`) up to `retry_count` with exponential backoff (`retry_backoff * 2**attempt`). `429` honors `Retry-After` when present, else backs off; non-idempotent writes (`POST` that are not safe to repeat) are NOT auto-retried unless an `Idempotency-Key` is supplied (anvil's CORS allow-list includes `Idempotency-Key`).
- **Rationale**: Satisfies FR-009 and the transient-failure + rate-limit edge cases without risking duplicate writes.
- **Alternatives considered**: retry everything including POSTs — rejected (duplicate-write hazard).

---

## R10 — Packaging & distribution

- **Decision**: Ship inside the existing `anvil` distribution as the `anvil.client` package. No new distribution, no new `[project.scripts]` entry (library only). Inherits the top-level `anvil/py.typed` marker (PEP 561) — no per-subpackage marker needed.
- **Rationale**: `[tool.setuptools.packages.find] include = ["anvil*"]` already captures `anvil.client.*`. Keeps install/versioning unified.
- **Alternatives considered**:
  - Separate `anvil-client` PyPI package: rejected for v1 — premature; duplicates packaging/CI; the SDK shares DTO shapes with the server and benefits from co-versioning.
  - Adding an `anvil-client` CLI entry point: deferred to a future feature (explicitly out of scope).

---

## R11 — Testing strategy (TDD, Article IV)

- **Decision**:
  - **Unit tests** (`tests/unit/client/`): `_shared` logic in isolation — `ServerConfig` env loading, `Response[T]` unwrap, status→exception mapping, retry/backoff, SSE line parsing (fed synthetic lines).
  - **e2e tests** (`tests/e2e/api/test_client_*.py`): drive the SDK against the live FastAPI app via `httpx.ASGITransport(app=app)` (reusing the established `client` fixture mechanism), asserting real envelope unwrap, real status codes, real SSE events for a short training run.
  - Tests written **before** implementation (Red-Green-Refactor). Coverage `fail_under` ratchet must not decrease.
- **Rationale**: ASGI transport gives true end-to-end fidelity with zero network and no live server — the highest-confidence, fastest option, already proven in the repo.
- **Alternatives considered**:
  - Mocking `httpx` responses for everything: rejected as the primary strategy — would not catch real envelope/route drift; used only where a live route is impractical.

---

## R12 — ADR requirement

- **Decision**: Author an ADR in `docs/vault/Decisions/` recording the SDK architecture decision (four-layer client, httpx transport, in-distribution packaging) and linking back to this spec/plan.
- **Rationale**: Constitution "Additional Constraints" — significant decisions recorded as ADRs; vault enriched per session.

---

## Summary of resolved unknowns

| # | Topic | Decision |
|---|---|---|
| R1 | Transport | `httpx.AsyncClient` (existing dep) |
| R2 | Architecture | Facade → DomainClient → Command → Transport |
| R3 | Envelope | Generic `Response[T]` unwrap to `.data` |
| R4 | Errors | Typed `ApiError` hierarchy by status code |
| R5 | Auth | `X-API-Key` + session cookie + CSRF for cookie writes |
| R6 | SSE | `httpx.stream` + async generator of typed `StreamEvent` |
| R7 | Files | multipart upload; stream-to-disk download |
| R8 | Config | `ServerConfig` BaseModel; arg > env (`ANVIL_*`) > default |
| R9 | Retry | exponential backoff on transport/5xx/429; no blind POST retry |
| R10 | Packaging | inside `anvil` distribution as `anvil.client`; no new deps/scripts |
| R11 | Tests | unit + e2e via ASGITransport; TDD; coverage ratchet held |
| R12 | ADR | architecture ADR in `docs/vault/Decisions/` |

**All decisions resolved. No `[NEEDS CLARIFICATION]` remain. Ready for Phase 1.**
