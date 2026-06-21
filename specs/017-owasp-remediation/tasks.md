# Tasks: OWASP Top 10 Security Remediation

**Input**: Design documents from `specs/017-owasp-remediation/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/
**Tests (TDD — MANDATORY per Constitution Article IV)**: Every NEW module/behavior (auth middleware, API-key store, CSRF, rate limiter, MLflow proxy, request-body-size limit, typed validation, ReDoS timeout, path containment, TOCTOU fix, idempotency) MUST have tests written FIRST (Red → Green → Refactor). Test tasks carry a `t` suffix (e.g. `T002t`) and MUST be completed before their paired implementation task. Coverage MUST NOT drop below the ratcheting `fail_under` baseline (Article IV / ADR-026). Pure mechanical changes that the existing suite already exercises (SHA-pinning, `print()`→logging, `html=False`, dependency bound) verify via regression (`make test`) rather than new test-first tasks.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Web app**: `anvil/` at repository root (FastAPI backend + Jinja2 frontend)
- **Tests**: `tests/` at repository root (pytest + httpx)
- All paths relative to repository root `/Users/joshburt/.local/share/opencode/worktree/5354809a525912e5a56a6d4a6e81ccf9f89efdf3/mighty-pixel`

---

## Phase 1: Setup (No Story Label)

**Purpose**: No project initialization needed — all changes modify existing files.

No setup tasks required.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Auth infrastructure that MUST be complete before ANY user story can be implemented.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete. All three user stories depend on authentication being in place.

### Tests First (TDD — write and confirm failing before implementation)

- [ ] T001t [P] Tests for the API-key store in `tests/unit/test_api_key_store.py` — key generated via CSPRNG, constant-time validation accepts the right key and rejects wrong ones, key persists across restarts, key is NEVER present in any log output, `ANVIL_API_KEY` override is honored and popped from the environment (FR-026).
- [ ] T002t [P] Tests for auth middleware in `tests/integration/test_auth_middleware.py` — unauthenticated API request → 401; valid `X-API-Key` → 200; valid session cookie on `/v1/*` → 200 (SSE cookie fallback, FR-025); unauthenticated page request → 303 to `/login`; `OPTIONS` preflight passes without auth (FR-029); exempt routes (`/v1/health`, `/static`, `/login`) pass.
- [ ] T004t [P] Tests for login + CSRF + login rate limit in `tests/integration/test_login_csrf.py` — `POST /login` with valid key sets `HttpOnly; SameSite=Strict; Max-Age=86400` cookie; cookie-auth state-changing request without `X-CSRF-Token` → 403 (FR-027); 6th `POST /login` within a minute → 429 (FR-028).

### Implementation for Foundational Phase

- [ ] T001 Implement secure API key generation, persistence, and validation in `anvil/api/deps.py` (+ a key store module). Generate via `secrets.token_urlsafe(32)`; validate via `secrets.compare_digest` (constant-time, never `==`). **Persist the key to a `0600` state file or the app DB so it survives restarts — NEVER write it to log files (FR-026).** If `ANVIL_API_KEY` is set, read it once at startup then `os.environ.pop("ANVIL_API_KEY", None)`. On first generation, emit ONLY a prefix hint (first 8 chars) + recovery instructions to stderr. Add a `--show-api-key` CLI command in `anvil/cli.py` to reveal the full key on demand.
- [ ] T002 Implement auth middleware in `anvil/api/app.py` — add `@app.middleware("http")`. **Order matters (FR-029): rate-limit → CORS → security-headers → auth.** Logic: (1) pass through `OPTIONS` (CORS preflight) without auth; (2) pass through exempt routes (`/login`, `/v1/health`, `/static/*`); (3) for `/v1/*` API routes accept EITHER a valid `X-API-Key` header OR a valid session cookie (cookie fallback is REQUIRED for browser SSE — FR-025); (4) for page routes require a valid session cookie, else redirect to `/login` (303). Distinguish API endpoints from page routes by a means other than the shared `/v1/` prefix (e.g. an explicit page-route set, or a sub-prefix) — see `contracts/auth-middleware.md`.
- [ ] T003 Implement security headers middleware in `anvil/api/app.py` — inject CSP (`default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; script-src 'self';`), HSTS (`max-age=31536000; includeSubDomains`), X-Frame-Options (`DENY`), X-Content-Type-Options (`nosniff`). (NOT `[P]` — shares `app.py` with T002; batch together.)
- [ ] T004 Create login page UI + CSRF — add `anvil/api/templates/login.html` (Jinja2), `anvil/api/static/css/login.css` (existing design tokens from `tokens.css`), `anvil/api/static/js/login.js` (POST `/login` with API key, sets `HttpOnly; SameSite=Strict; Max-Age=86400` session cookie, redirects home). Add `GET /login`, `POST /login`, `POST /logout`. **Issue a signed CSRF token on page render and validate `X-CSRF-Token` on cookie-authenticated state-changing requests (FR-027).** Apply a strict separate rate limit to `POST /login` (5/min/IP + failure delay) — login is NOT rate-limit-exempt (FR-028).
- [ ] T004b Auth migration safety (FR-031) — update `tests/conftest.py` so the shared `httpx.AsyncClient` injects a test `X-API-Key` header (otherwise all ~10 HTTP integration test files break). Confirm the Docker/compose healthcheck targets the auth-exempt `/v1/health` (it does — verify). Confirm browser SSE works via the cookie path (FR-025).

**Checkpoint**: Auth foundation ready — key generated & persisted (not logged), middleware ordered correctly, OPTIONS/exempt routes pass, SSE works via cookie, CSRF enforced, login rate-limited, tests + healthcheck still green.

---

## Phase 3: User Story 1 — Harden Critical Attack Surface (Priority: P1) 🎯 MVP

**Goal**: Authentication on all routes, structured input validation on training config, restricted MLflow access — blocking the 4 CRITICAL and most dangerous HIGH-severity findings.

**Independent Test**: Attempt `POST /services/restart-all` and `POST /training/start` without credentials — both MUST return 401. Then with valid API key — both MUST succeed. Verify training config with invalid fields returns 422. Verify MLflow is reachable ONLY through the authenticated `/v1/mlflow-proxy/` (loaded while authenticated → 200; unauthenticated → 401/redirect) and that port 5001 is NOT published to the host.

### Tests First (TDD — write and confirm failing before implementation)

- [ ] T005t [P] [US1] Tests for typed training config in `tests/integration/test_training_validation.py` — `POST /training/start` with unknown/invalid fields → 422 (FR-003, `extra="forbid"`); valid config → accepted.
- [ ] T009t [P] [US1] Tests for the MLflow reverse proxy in `tests/integration/test_mlflow_proxy.py` — authenticated request to `/v1/mlflow-proxy/` returns 200 and assets resolve under the prefix; unauthenticated → 401/redirect; direct off-host `:5001` is not reachable (port unpublished). (ADR-034)

### Implementation for User Story 1

- [ ] T005 [P] [US1] Create `TrainConfig` Pydantic model (with `ConfigDict(extra="forbid")`, `Field(ge=..., le=...)` constraints on all params) and replace `body: dict` in `POST /training/start` at `anvil/api/v1/training.py:46`.
- [ ] T006 [P] [US1] Replace `body: dict` with typed Pydantic models in `anvil/api/v1/corpora.py` — `CreateCorpusBody`, `ForkCorpusBody` with `Field(min_length=1, max_length=255)` constraints.
- [ ] T007 [P] [US1] Replace `body: dict` with typed Pydantic models in `anvil/api/v1/inference.py` — typed models for all 8 POST endpoints (`InferenceTokenizeBody`, `InferenceEmbeddingsBody`, `InferenceAttentionBody`, `InferenceSamplingBody`, `InferenceBackwardBody`, `InferenceAutogradBody`, `InferenceLossBody`) with field size limits.
- [ ] T008 [P] [US1] Replace `body: dict` with typed Pydantic models in `anvil/api/v1/registry.py` (`RegisterModelBody`) and `anvil/api/v1/eval.py` (`EvalPerplexityBody`) and `anvil/api/v1/eval_datasets.py` (`CreateEvalDatasetBody`, `AppendRecordsBody`). All with field constraints.
- [ ] T009 [US1] Implement the MLflow reverse proxy per ADR-034 (replaces the naive `--allowed-hosts` change, which is breaking AND insufficient). Subtasks: (a) add an authenticated in-process proxy route `/v1/mlflow-proxy/{path:path}` in a new `anvil/api/v1/mlflow_proxy.py` using `httpx.AsyncClient` with streaming pass-through (SSE + chunked artifact downloads); (b) launch MLflow with `--static-prefix=/v1/mlflow-proxy` and bind loopback (not `0.0.0.0`) in `anvil/supervisor/services.py:115-149`; (c) stop publishing port 5001 in `compose.yaml`; (d) change `anvil/config.py::get_mlflow_browser_uri` to return the proxy URL (`{request.base_url}v1/mlflow-proxy`) instead of `http://<host>:5001`; (e) add `MLflowService.health_check()` and gate readiness in the lifespan; (f) add `ANVIL_MLFLOW_INTERNAL_URI` (default loopback). Cross-ref ADR-034 and SaaS spec FR-057. Add an integration test loading MLflow UI through the authenticated proxy.
- [ ] T010 [US1] Add `Idempotency-Key` header handling and in-memory cache to `POST /training/start` in `anvil/api/v1/training.py` to prevent duplicate training runs on retry (FR-015).
- [ ] T011 [US1] Verify auth middleware covers all service management endpoints in `anvil/api/v1/health_ops.py` — confirm routes POST `/services/restart-all`, `/services/{name}/start`, `/services/{name}/stop`, `/services/{name}/restart`, `/services/{name}/kill-port` are intercepted by the app-level auth middleware before handler execution. If middleware does not cover them (e.g., due to router prefix or middleware ordering), add explicit `Depends(get_api_key)` to each endpoint.
- [ ] T012 [US1] Fix the version-disclosure contradiction (FR-021). Because `/v1/health` is auth-EXEMPT (Docker healthcheck), reduce the public `GET /v1/health` payload to bare liveness (`{"status": "healthy"}`) in `anvil/api/v1/health_ops.py:70-88`, and move version/uptime/CPU/memory/disk/GPU metrics to a NEW authenticated endpoint `GET /v1/health/detailed`. (The prior wording "gate version behind auth on /v1/health" was impossible since the route is exempt.)

**Checkpoint**: At this point, User Story 1 should be fully functional — auth enforced (incl. SSE via cookie + CSRF), input validated, MLflow behind the authenticated proxy with port 5001 unpublished, key never logged. Test independently.

---

## Phase 4: User Story 2 — Strengthen Endpoint & Configuration Security (Priority: P2)

**Goal**: Typed validation on remaining endpoints, rate limiting, file size limits, ReDoS protection, CI/CD pinning, sanitized error messages, AuthzContext documentation.

**Independent Test**: Send oversized file to upload endpoint (should 413), submit catastrophic regex (should timeout), make 110 rapid requests (should 429 after 100), inspect error responses (no internal paths in `detail`), verify CI/CD workflow SHA pinning.

### Implementation for User Story 2

- [ ] T013 [P] [US2] Add `Field(max_length=...)`, `Field(ge=..., le=...)`, and `Field(pattern=...)` constraints to all existing Pydantic models in `anvil/api/v1/schemas.py` — all string fields need `max_length` (255-5000 depending on purpose), all int fields need `ge=1` where applicable, `LockBody.scope` and `LockBody.holder` need `min_length=1, max_length=255`.
- [ ] T014 [US2] Create `sanitized_error()` helper utility in `anvil/api/v1/` and replace all `str(exc)` / `str(e)` patterns in `HTTPException(detail=str(exc))` with sanitized generic messages across: `anvil/api/v1/corpora.py` (4 instances), `anvil/api/v1/content.py` (9 instances), `anvil/api/v1/datasets.py` (7 instances), `anvil/api/v1/training.py` (6 instances), `anvil/api/v1/inference.py` (9 instances), `anvil/api/v1/eval.py` (1 instance), `anvil/api/v1/learning.py` (1 instance), `anvil/api/v1/experiments.py` (2 instances), `anvil/api/v1/eval_datasets.py` (3 instances). Log original exception server-side.
  > **Note**: T014 spans 41 instances across 9 files. For parallel execution, split into sub-tasks: T014a (corpora.py + content.py), T014b (datasets.py + training.py), T014c (inference.py + eval.py + remaining). All sub-tasks share the same `sanitized_error()` helper.
- [ ] T015 [US2] Implement rate limiting middleware in `anvil/api/app.py` — custom sliding-window counter keyed by `(client_ip, route_prefix)`. Default 100 req/min per client, 20 burst. Exempt ONLY `/v1/health` and `/static`. **`/login` is NOT exempt (FR-028)** — it instead gets a STRICTER separate limit (5/min/IP + failure delay) per `contracts/security-config.md` §1, implemented alongside T004. Return 429 with `Retry-After` when throttled. Configurable via `ANVIL_RATE_LIMIT` env var.
- [ ] T016 [P] [US2] Add file upload size limits — in `anvil/api/v1/datasets.py:260` check `UploadFile.size` against 100MB limit, in `anvil/api/v1/content.py:420` check against 50MB limit. Return 413 with clear message when exceeded.
- [ ] T016b [US2] Add a global maximum request body size limit (FR-006) via middleware in `anvil/api/app.py` (e.g. reject requests whose `Content-Length`/streamed body exceeds `max_request_body_mb` from `contracts/security-config.md` §5, default 10MB) — returns 413. This is distinct from the per-file upload caps (T016); it protects all JSON endpoints from oversized-payload resource exhaustion. Paired test in `tests/integration/test_body_size_limit.py` (oversized JSON body → 413).
- [ ] T017 [US2] Add ReDoS protection to user-supplied regex in `anvil/services/datasets/dataset_curation.py` (`regex_replace`, ~line 250-295, where `re.compile(pattern, flags)` runs). **Do NOT pass `timeout=` to `re.compile` — stdlib `re` has no such parameter (it raises `TypeError`).** Instead, execute the compiled pattern's `.sub()`/`.search()` under a stdlib wall-clock timeout (worker-thread + timed `join`, preferring `signal.SIGALRM` on Unix per `contracts/security-config.md` §4). Default 2s. On timeout, surface a `TimeoutError` that the route translates to HTTP 422 `"Pattern too complex or invalid"`. Log the pattern hash (not the pattern). Add a shared helper (e.g. `anvil/services/_shared/regex_timeout.py` or co-located) following the one-class-per-file rule. Confirm `corpora.py` `analyze_path` patterns are internal/gitignore (no user-supplied regex) — no timeout needed there.
- [ ] T018 [P] [US2] Pin third-party GitHub Actions to SHA digests across BOTH workflows (FR-011). In `.github/workflows/ci.yml:125` replace `SonarSource/sonarcloud-github-action@master` with `@<resolved-SHA256>`. Audit `.github/workflows/release.yml` for any floating-tag third-party action and pin it too; if release.yml contains no third-party action to pin, record that explicitly in the task notes (the original A08-001 cited `release.yml:125`).
- [ ] T019 [US2] Document `AuthzContext` as local-mode no-op in `anvil/services/content/authz.py` — add docstring explaining this is a stub for future SaaS RBAC, all actions permitted in local mode. Add a startup log warning when running on non-localhost interface.

**Checkpoint**: All HIGH-severity findings resolved. Endpoint hardening, rate limiting, CI/CD pins, and error sanitization in place.

---

## Phase 5: User Story 3 — Security Hardening Best Practices (Priority: P3)

**Goal**: CORS, path containment, TOCTOU fix, Docker pinning, logging improvements, dependency bounds, version disclosure, static file config.

**Independent Test**: Check HTTP response headers (CSP/HSTS/XFO/XCTO present), verify CORS headers restrict origins, confirm Dockerfile uses SHA-pinned base images, confirm path operations contained within expected directories, verify concurrent lock requests don't race, verify startup exceptions are logged not swallowed.

### Implementation for User Story 3

- [ ] T020 [P] [US3] Add CORS middleware in `anvil/api/app.py` — if `ANVIL_CORS_ORIGINS` env var is set, enable CORS with those origins. Default: CORS disabled (same-origin only). Use FastAPI `CORSMiddleware` (built-in, no new dep).
- [ ] T021 [P] [US3] Add path containment check in `anvil/storage/local.py:55` — after `full = (self.base_path / path).resolve()`, verify `full.is_relative_to(self.base_path.resolve())`. Raise `ValueError` if path escapes.
- [ ] T022 [US3] Add path sanitization in `anvil/services/content/local_versioned_content_store.py:214-215` — validate that `path` does not contain `..` components before constructing `staging_area / path`. Use `PurePath(path).is_relative_to()` or explicit `..` check.
- [ ] T023 [US3] Fix TOCTOU race condition in `anvil/api/v1/content.py:1085-1094` — replace the `list_active()` check-then-`acquire()` pattern with an atomic DB-level operation (add `UNIQUE(scope)` constraint on lock table, the INSERT will fail on duplicate).
- [ ] T024 [P] [US3] Pin Docker base images to SHA256 digests in `Dockerfile:11,30` — replace `FROM python:3.11-slim` with `FROM python:3.11-slim@sha256:<digest>` for both builder and runtime stages. Verify with `docker build`.
- [ ] T025 [US3] Add upper bound to optional torch dependency in `pyproject.toml:55` — change `"torch>=2.0"` to `"torch>=2.0,<3"`.
- [ ] T026 [P] [US3] Replace `print()` with `logger.info()` in `anvil/api/app.py:57,135` — startup messages should use `logger.info()` with consistent log format.
- [ ] T027 [P] [US3] Replace `print()` with `logger.info()` in `anvil/cli.py:403,408,411,413,416` and surrounding training progress output at lines `497-823` — CLI training output should use `logger.info()` for structured logging.
- [ ] T028 [P] [US3] Replace `print()` with `logger.info()` in `anvil/services/inference/demo_model_provider.py:268` — warm-up completion message should use `logger.info()`.
- [ ] T029 [US3] Triage ALL silent `except ...: pass` patterns (FR-030), not just the 4 in `app.py`. The review found ~97 across 27 files. For each: either replace with `logger.warning("...", exc_info=True)` (with meaningful context) OR explicitly annotate as accepted with a one-line rationale comment. Prioritize route handlers (info leak / hidden auth errors), DB operations (data corruption), and MLflow calls. Produce a short triage list (file:line → action) as part of the task.
- [ ] T030 [US3] Add `html=False` to StaticFiles mount in `anvil/api/app.py:198` — change `StaticFiles(directory=str(static_dir))` to `StaticFiles(directory=str(static_dir), html=False)`.
- [ ] T031 [US3] Move logging configuration (`logging.basicConfig` currently at `anvil/cli.py:162-166`) to the lifespan handler in `anvil/api/app.py` so that all runtime entry points (uvicorn, Docker, CLI) produce structured logs with the same format and level. The CLI entry point should still call the centralized setup. (FR-017, A09-001)
- [ ] T031b [US3] [P] Add `report-uri`/`report-to` to the CSP and a `POST /v1/security/csp-report` endpoint that logs violations (defense-in-depth; LOW finding L-2 from review). Optional but recommended.

**Checkpoint**: All 35 open security findings addressed, plus the review-derived CRITICAL/HIGH fixes (SSE cookie auth, CSRF, login rate-limit, MLflow proxy, key-not-logged, version split, full except:pass triage, migration safety). Application meets security best practices.

---

## Phase 6: Polish & Validation

**Purpose**: Verify all changes work correctly, run test suite, update tracker, re-verify security posture.

- [ ] T032 Run `make lint` and fix any linting issues introduced by changes
- [ ] T033 Run `make typecheck` (mypy --strict) and fix any type errors
- [ ] T034 Run `make test` and ensure all existing tests pass with no regression
- [ ] T035 Run quickstart.md validation steps — verify auth, rate limiting, security headers, typed validation all work end-to-end
- [ ] T036 Update `docs/owasp-tracker.csv` — change all resolved finding statuses from "open" to "resolved"
- [ ] T037 Update `docs/owasp-review.md` — update Progress Summary with resolved count, add resolved dates
- [ ] T038 [P] Re-run OWASP review scan or manually verify all 35 finding statuses are updated to "resolved", confirming SC-001 and SC-002

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 2)**: No dependencies — can start immediately. BLOCKS all user stories.
- **User Stories (Phase 3-5)**: All depend on Phase 2 (auth must be operational first).
- Stories CAN proceed in parallel within a phase (tasks marked [P]) where they touch different files.
- **Polish (Phase 6)**: Depends on all user stories being complete.

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2. No dependencies on other stories. **MVP scope.**
- **US2 (P2)**: Can start after Phase 2. No dependencies on US1 (different files). Independent.
- **US3 (P3)**: Can start after Phase 2. No dependencies on US1 or US2. Independent.

### Within Each Phase

- Models/files before middleware/logic changes
- Core implementation before validation
- Story complete before moving to next priority

### Parallel Opportunities

- Phase 2 tests: T001t / T002t / T004t are independent test files — fully parallel, write first.
- Phase 2 impl: **T002 and T003 both edit `app.py` — NOT parallel; batch them.** T001 (deps.py + key store) is the parallel-safe one; T004 (templates/static) is independent of the middleware files.
- Phase 3 tests: T005t / T009t are independent test files — parallel.
- Phase 3 impl: T005-T008 are in different route files — fully parallel. T009 (MLflow proxy) now spans `mlflow_proxy.py` + `supervisor/services.py` + `config.py` + `compose.yaml` + `app.py` route registration; still independent of T010 (training.py) but no longer "supervisor-only".
- Phase 4: T013 (schemas.py), T016 (datasets + content uploads), T016b (app.py body limit), T018 (workflows) are independent files — parallel. Note T016b touches `app.py`.
- Phase 5: T020 (app.py CORS), T021 (storage), T024 (Dockerfile), T026-T028 (print→logging), T030 (app.py html), T031 (app.py logging), T031b (app.py CSP report) — **all the `app.py` editors (T020, T030, T031, T031b) must be batched into one `app.py` pass**, not run in parallel with each other.

---

## Parallel Example: Foundational Phase

```bash
# All tasks can run in parallel (different files):
Task: "Implement API key generation in anvil/api/deps.py"
Task: "Implement auth middleware in anvil/api/app.py"
Task: "Implement security headers middleware in anvil/api/app.py"
Task: "Create login page UI in anvil/api/templates/ and static/"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Foundational (auth infra)
2. Complete Phase 3: User Story 1 (auth + input validation)
3. **STOP and VALIDATE**: Test US1 independently — verify auth blocks unauthenticated requests, typed validation rejects invalid input, MLflow restricted
4. Deploy/demo if ready — this already addresses all CRITICAL findings

### Incremental Delivery

1. Phase 2 → Auth foundation ready
2. Add US1 → Auth + input validation → Test independently → **MVP done!** (critical findings resolved)
3. Add US2 → Endpoint hardening → Test independently → (HIGH findings resolved)  
4. Add US3 → Defense in depth → Test independently → (all findings resolved)
5. Polish → Validated and tracked

> **Note**: T003, T020, T030, T031 all modify `anvil/api/app.py`. Consider batching all `app.py` changes into a single pass per phase to avoid repeated context reloads. T002, T003, T020, T030, T031 are the five touch points — T002/T003 are in Phase 2 and can be batched together; T020/T030/T031 are in Phase 5 and should be batched together.

### Parallel Team Strategy

With multiple developers:

1. Developer A: Phase 2 (foundational auth — blocks everything)
2. Once Phase 2 is done, split by story:
   - Developer A: US1 (auth + validation — highest priority)
   - Developer B: US2 (hardening — independent of US1)
   - Developer C: US3 (best practices — independent of US1/US2)
3. All three stories converge at Phase 6 (validation)

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- No test-before tasks — security remediation modifies existing code; existing test suite verifies no regression
- Commit after each phase or logical group
- Stop at Phase 3 checkpoint to validate MVP before proceeding