# Research: OWASP Top 10 Security Remediation

**Phase**: 0 (Outline & Research) | **Date**: 2026-06-21 | **Plan**: `plan.md`

## Research Findings

### R1: Route Definitions & Auth Patterns

**Source**: Codebase exploration of `anvil/api/v1/` — all 17 route files scanned.

**Decision**: Use existing `Depends()` injection pattern for auth middleware. Add a new `get_api_key` dependency that validates an `X-API-Key` header.

**Rationale**:
- Existing pattern: `Depends(get_workbench)` is used across all protected routes — clean seam for auth
- `anvil/services/content/authz.py` already has `require_content_auth()` returning an `AuthzContext` — this is the exact injection point for API key auth
- ~125+ routes across 17 files need auth (all routes)
- Adding a single middleware or a base router dependency is more maintainable than changing every route signature

**Alternatives considered**:
- Per-route `Depends()` injection: Works but requires touching all route files. Avoidable with FastAPI middleware or `dependencies=` on the router.
- Custom ASGI middleware: More flexible but harder to test and maintain. Use FastAPI middleware instead.

**Key findings**:
- 18 endpoints use `body: dict` (untyped) across 8 files (verified against current HEAD): `corpora.py` (4), `inference.py` (7), `eval_datasets.py` (2), `registry.py` (1), `eval.py` (1), `learning.py` (1), `content.py` (1), `datasets.py` (1). NOTE: `training.py` `POST /training/start` uses `config: dict` (also untyped — covered by T005), and `learning.py`/`content.py`/`datasets.py` were missed in the original audit (now covered by T008b).
- ~34 `str(exc)`/`str(e)` instances in HTTPException details across 8 files (verified against current HEAD post-merge: content.py 9, inference.py 9, datasets.py 7, corpora.py 4, training.py 2, eval.py 1, learning.py 1, experiments.py 1 f-string; eval_datasets.py 0). The earlier "48 across 15 files" estimate was from an older tree and is superseded — see T014 for the authoritative line list.
- 97 `except Exception: pass` patterns across 27 files (mostly in tracking/MLflow calls) — order-of-magnitude estimate; T029 triages the full set discovered at implementation time.
- `--host 0.0.0.0` at `supervisor/services.py:136-137` and `--allowed-hosts "*"` at `supervisor/services.py:142-143` (within `start()`, lines 115-149)

---

### R2: Configuration & Infrastructure Files

**Source**: Codebase exploration of Dockerfile, CI/CD, schemas, storage, logging.

**Decision**: Pin Docker images and CI/CD actions to SHA256 digests. Add field constraints to existing Pydantic models rather than creating new ones.

**Rationale**:
- Docker: `FROM python:3.11-slim` (lines 11, 30) — both builder and runtime stages use floating tags (verified)
- CI/CD: `SonarSource/sonarcloud-github-action@master` in `ci.yml:128` (verified post-merge; was cited as :125) — `@master` is a floating tag. `release.yml` has no floating-tag third-party action.
- Pydantic: 28+ models in `schemas.py` — most lack `Field(max_length=...)`, `Field(ge=..., le=...)` constraints
- Path containment: `storage/local.py:55` `_resolve()` does `(self.base_path / path).resolve()` with no `is_relative_to()` check (verified); `staging_area / path` at `local_versioned_content_store.py:214` has no `..` validation (verified)
- torch: `pyproject.toml:54` — `torch>=2.0` needs `<3` upper bound (verified line 54, not 55)

**Key findings**:
- Docker: 2 stages both need SHA pinning
- CI/CD: Only `ci.yml` has SonarCloud — `release.yml` does not
- Pydantic: Models exist for most endpoints but lack field-level constraints
- upload: `datasets.py:260` and `content.py:420` use `UploadFile` with no size check
- TOCTOU: `content.py` `acquire_lock` at lines 1071-1117 (check at ~1096-1102, acquire at ~1104; verified post-merge — was cited as 1085-1094) — check-then-act for lock acquisition. `CheckoutLock` model (`anvil/db/models/content_lock.py`) has NO `UNIQUE(scope)` constraint.
- print(): ~39 in `cli.py` (403-823) + `app.py:57,135` + `demo_model_provider.py:268` (verified post-merge)

---

## Technology Choices

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Auth mechanism | API key via `X-API-Key` header + session cookie for web UI | Simplest effective mechanism for local-first tool. Session cookie avoids re-sending API key on every page request. |
| API key storage | Persisted to `0600` state file or app DB; env var override (popped after read). **Never logged** — prefix hint only + `--show-api-key` (C-4/FR-026). | Zero-config first run without credential disclosure to persistent/tailable log stores. |
| Rate limiting | Custom middleware with per-endpoint config | Avoids new dependency (`slowapi`). Simple token-bucket or sliding-window per IP. |
| Security headers | Custom middleware in `app.py` | Avoids new dependency (`django-csp`, `secure.py`). FastAPI `Response` headers middleware is trivial. |
| ReDoS protection | Stdlib wall-clock timeout wrapping regex *execution* (worker thread + timed `join`, fallback to `signal.SIGALRM` on Unix). 2s default. | **CORRECTION**: stdlib `re` has NO `timeout=` parameter — that is only in the third-party `regex` package. To honor zero-deps, the timeout MUST wrap `pattern.search/sub` execution in a thread and abandon it on timeout. See ADR for the chosen mechanism. |
| Path containment | `Path.resolve().relative_to(base_path)` | Stdlib, no new deps. Throws `ValueError` if path escapes. |
| Logging | `logging.getLogger(__name__)` convention | Already established in codebase. Replace `print()` and `except: pass` with `logger.info/warning/error`. |
| Idempotency | `Idempotency-Key` header → in-memory TTL cache | Simple, no DB changes. TTLCache or dict with expiry for dedup window. |

## Architecture Decisions

| AD | Decision | Rationale |
|----|----------|-----------|
| AD-1 | Auth middleware at app level, not per-router | Single `@app.middleware("http")` or `app.add_middleware()` covers all routes + future routes. Login page is exempt route. |
| AD-2 | Header for API, cookie for browser; both accepted on `/v1/*` | `X-API-Key` header for programmatic access. Browser login exchanges the key for a `HttpOnly; SameSite=Strict` session cookie + CSRF token. **`/v1/*` accepts EITHER header OR cookie** so browser SSE works (C-2/FR-025). CSRF token required on cookie-auth state changes (FR-027). |
| AD-3 | No new pip dependencies | All security controls achievable with stdlib + existing deps (FastAPI, Pydantic, `re`, `secrets`, `pathlib`, `logging`). |
| AD-4 | Typed models in existing `schemas.py` | Add `Field()` constraints and new models there. Don't create a new schemas file — but new training/inference config models go in their respective route files or a dedicated module. |
| AD-5 | MLflow host list derived from `ANVIL_MLFLOW_URI` | Parse hostname from the configured URI. Defaults to `127.0.0.1`. No separate config variable needed. |
| AD-6 | Reverse CI/CD pinning to SHA | Must resolve current `@master` SHA for `SonarSource/sonarcloud-github-action` first, then pin. |
| AD-7 | Atomic lock via DB unique constraint | Add `UNIQUE(scope)` constraint to lock table. The `acquire` INSERT will fail on duplicate. Eliminates TOCTOU entirely. |