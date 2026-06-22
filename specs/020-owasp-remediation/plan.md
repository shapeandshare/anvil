# Implementation Plan: OWASP Top 10 Security Remediation

**Branch**: `020-owasp-remediation` | **Date**: 2026-06-21 | **Spec**: `specs/020-owasp-remediation/spec.md`
**Input**: Feature specification from OWASP security review (36 findings across A01-A10) + clarification session (auth scope, key provisioning).

## Summary

Systematic remediation of 35 open OWASP Top 10 security findings in the anvil codebase, organized into 3 priority tiers: (P1) authentication + input validation for all HTTP routes, (P2) endpoint hardening + secure configuration, (P3) defense-in-depth best practices. The approach is local-first — a single auto-generated API key protects all routes (API + web UI), with typed request validation, rate limiting, security headers, and proper logging. Zero new runtime dependencies.

## Technical Context

**Language/Version**: Python 3.11+ (existing, `requires-python = ">=3.11"`)
**Primary Dependencies**: FastAPI, async SQLAlchemy, Pydantic v2, Jinja2, uvicorn, Alembic (all existing — zero new runtime dependencies)
**Storage**: SQLite via async SQLAlchemy (`data/anvil-state.db`); local filesystem via `LocalFileStore`; MLflow SQLite (`mlruns/mlflow.db`)
**Testing**: pytest + pytest-asyncio + httpx (async test client); Playwright browser smoke tests (`tests/browser/`); e2e API suite (`tests/e2e/api/`); coverage threshold via `[tool.coverage.report] fail_under`. **Existing tests have zero auth awareness** — T004b must inject credentials into all three client fixtures (`tests/conftest.py`, `tests/e2e/api/conftest.py`, `tests/browser/conftest.py`) to prevent breakage.
**Target Platform**: macOS (Apple Silicon + Intel), Linux (x86_64); Docker multi-stage runtime image
**Project Type**: Web application (FastAPI backend + Jinja2 frontend, no JS framework)
**Performance Goals**: Auth middleware adds <50ms p95 latency per request; rate limiting overhead negligible; no regression in existing training/inference throughput
**Constraints**: Zero new runtime pip dependencies; no architectural changes to core engine (`anvil/core/`); auth must not break existing CLI workflows (`anvil` CLI entry point); must coexist with existing `AuthzContext` stub reserved for future SaaS mode; Docker multi-stage build must remain functional
**Scale/Scope**: Single-user local development tool with LAN access; auth prevents unauthorized access from LAN; SaaS multi-tenant auth (Cognito/JWT per ADR-030) is a separate initiative

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Check | Notes |
|---------|-------|-------|
| **Article I — Zero-Dependency Core** | ✅ PASS | All changes in `anvil/api/`, `anvil/services/`, `anvil/storage/`, `anvil/supervisor/` — core engine untouched |
| **Article II — Educational Clarity** | ✅ PASS | No effect on progressive walkthrough files or teaching code |
| **Article III — Seeded Reproducibility** | ✅ PASS | No changes to training determinism. Idempotency keys prevent duplicate runs |
| **Article IV — TDD Mandatory** | ✅ PASS | **TDD is enforced via `t`-suffixed test tasks (e.g. T001t, T002t, T004t, T005t, T009t) that MUST be written and fail before their paired implementation task.** New security-critical code (auth, key store, CSRF, rate limiter, MLflow proxy, body-size limit, typed validation, ReDoS timeout) is covered test-first. Purely mechanical changes already exercised by the existing suite (SHA-pinning, `print()`→logging, `html=False`, dependency bound) verify via regression. Coverage must not drop below the ratcheting `fail_under` baseline (ADR-026). |
| **Article V — Async-First** | ✅ PASS | All changes in async layers (FastAPI middleware, async route handlers) |
| **Article VI — `__init__.py` Ownership** | ✅ PASS | No new packages/directories. All changes to existing files |
| **Article VII — Layered Architecture** | ✅ PASS | Auth middleware at API layer; typed validation at route layer; logging at app lifespan. No DB primitives leak |
| **Article VIII — iOS-Grade Polish** | ✅ PASS | Login page must match existing CSS design system. Auth errors user-friendly |
| **Article IX — Pit of Success** | ✅ PASS | API key auto-generated — zero-config auth. Silent fallback preserved |
| **Article X — DDD Package Decomposition** | ✅ PASS | Auth middleware is cross-cutting concern at API layer. No new domain packages needed |

**All gates pass.** No constitutional violations.

## Project Structure

### Documentation (this feature)

```text
specs/020-owasp-remediation/
├── spec.md              # Feature specification
├── plan.md              # This file (implementation plan)
├── research.md          # Phase 0 output (design research)
├── data-model.md        # Phase 1 output (data model)
├── quickstart.md        # Phase 1 output (quickstart guide)
├── contracts/           # Phase 1 output (interface contracts)
│   ├── auth-middleware.md
│   ├── api-contracts.md
│   └── security-config.md
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
# Single project: anvil/
anvil/
├── api/
│   ├── app.py                    # Auth/CSRF/SSE-cookie middleware, security headers, CORS, rate limiting (order: rate→CORS→headers→auth)
│   ├── deps.py                   # Auth DI: get_api_key (header OR cookie fallback for SSE)
│   ├── auth/ (or v1/)            # API key store (0600 file/DB, never logged), session store, CSRF token helper (new)
│   ├── v1/
│   │   ├── training.py           # dict→Pydantic, idempotency
│   │   ├── datasets.py           # dict→Pydantic, file size limits, ReDoS (exec timeout)
│   │   ├── corpora.py            # dict→Pydantic, path traversal fix, str(exc)
│   │   ├── content.py            # dict→Pydantic, file size limits, TOCTOU fix, str(exc)
│   │   ├── inference.py          # dict→Pydantic
│   │   ├── mlflow_proxy.py       # Authenticated MLflow reverse proxy /v1/mlflow-proxy/ (new, ADR-035)
│   │   ├── health_ops.py         # Bare /v1/health (public) + /v1/health/detailed (authed) split
│   │   ├── schemas.py            # Field constraints (max_length, range)
│   │   └── ...                   # Other route files with dict→Pydantic
│   ├── templates/
│   │   └── login.html            # Login page + CSRF meta token (new)
│   └── static/
│       ├── css/login.css         # Login page styles (new, design tokens)
│       └── js/login.js           # Login page JS + X-CSRF-Token on fetch (new)
├── services/
│   ├── _shared/regex_timeout.py  # Stdlib regex execution timeout helper (new, C-1/FR-008)
│   ├── datasets/dataset_curation.py  # regex_replace executes under timeout
│   ├── content/
│   │   ├── authz.py              # AuthzContext documentation/gate + non-localhost warning
│   │   └── local_versioned_content_store.py  # Path containment fix
│   └── inference/demo_model_provider.py  # print()→logging
├── storage/local.py             # Path containment check after resolve
├── supervisor/services.py       # MLflow: loopback bind + --static-prefix + health_check() (ADR-035)
├── config.py                    # get_mlflow_browser_uri → proxy URL; ANVIL_MLFLOW_INTERNAL_URI
├── cli.py                       # print()→logging; --show-api-key command; logging setup moved to lifespan

Dockerfile                        # Base image digest pinning
compose.yaml                      # Remove 5001 port publish (MLflow proxy-only)
pyproject.toml                    # torch upper bound
.github/workflows/
└── ci.yml                        # SonarCloud action SHA pinning
```

**Structure Decision**: Web application (FastAPI + Jinja2). Mostly modifications to existing files, plus new: `login.html`/`login.css`/`login.js`, an auth/CSRF/key-store module, `mlflow_proxy.py`, and a stdlib regex-timeout helper. No new runtime dependencies (`httpx` is already a FastAPI dependency, used for the MLflow proxy).

## Post-Review Revisions (2026-06-21)

This plan was revised after an adversarial spec review. Key changes and their cross-references:

- **C-1 (ReDoS)**: `re.compile` has no `timeout=`; use a stdlib execution-timeout helper. FR-008 + `contracts/security-config.md` §4 updated.
- **C-2 (SSE auth)**: browser `EventSource` can't send `X-API-Key`; auth middleware accepts header OR session cookie for `/v1/*`. FR-025 + `contracts/auth-middleware.md` updated, with greppable `SECURITY-FUTURE(C-2/FR-025)` markers required in code/docs/diagrams.
- **C-3 (versioning)**: `/v1/` URL versioning is a footgun (API/page collision) — split to a **separate feature (spec `018-header-api-versioning`) and ADR-036**. Spec 017 auth uses an explicit page-route registry so it works before/after 018.
- **C-4 (key in logs)**: key never written to logs; prefix-hint only + `--show-api-key`; env var popped after read. FR-026 + data-model + quickstart updated.
- **C-5 (MLflow)**: naive `--allowed-hosts` change is breaking + insufficient → **authenticated reverse proxy (ADR-035)**, unifying local mode with the SaaS FR-057 pattern; port 5001 unpublished. FR-004 + T009 updated; SaaS spec 014 cross-referenced.
- **HIGH findings**: CSRF token (FR-027), login rate-limit (FR-028), CORS-preflight/middleware-order (FR-029), full `except:pass` triage (FR-030), auth migration safety for tests/healthcheck (FR-031), version-disclosure split (FR-021/T012).

**Constitution re-check after revisions**: still all PASS. The MLflow proxy uses existing `httpx` (no new dep, Article I/lean-deps intact). New modules follow one-class-per-file (Article + ADR-020) and DDD placement (Article X). Auth/CSRF/SSE remain in the API layer (Article VII).

## Complexity Tracking

*No constitutional violations — Complexity Tracking not required. Note: the MLflow reverse proxy adds surface area but introduces no new dependency and is the only correct way to satisfy FR-004 (documented in ADR-035).*
