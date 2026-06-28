---
title: 056 Reverse-Proxy Registry - tasks
type: tasks
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/056 Reverse-Proxy Registry/
related:
  - '[[056 Reverse-Proxy Registry]]'
created: '2026-06-28'
updated: '2026-06-28'
status: draft
---
# Tasks: Reverse-Proxy Registry & Single-Origin Front Door

**Input**: spec.md (FR-001..FR-013), ADR-037, ADR-035 (superseded)
**Prerequisites**: existing auth middleware in `anvil/api/app.py` + `anvil/api/auth.py` (CSRF-exempt prefix already present); existing `MLflowService` in `anvil/supervisor/services.py`; `get_mlflow_browser_uri` in `anvil/config.py`.
**Tests (TDD — MANDATORY per Constitution Article IV)**: The registry, the proxy route, the loopback bind, and the URL builder are NEW behavior and MUST be written test-first (Red → Green → Refactor). Test tasks carry a `t` suffix and precede their paired implementation task. Mechanical changes already exercised by the suite (unpublishing the compose port, `EXPOSE` edit) verify via regression (`make test` + container port inspection).

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- Include exact file paths in descriptions

---

## Phase 1: Proxy Registry Core (Blocking Foundation)

**Purpose**: The generic registry + reverse-proxy route that everything else mounts on. BLOCKS all other phases.

### Tests First

- [ ] T001t [P] Tests for the proxy registry in `tests/unit/test_proxy_registry.py` — registering an upstream (mount prefix + base URI) makes it resolvable; two upstreams route independently; duplicate prefix is rejected; lookup by request path returns the right upstream (FR-003).
- [ ] T002t [P] Tests for the reverse-proxy route in `tests/integration/test_proxy_route.py` — a request under a registered prefix is forwarded to a stub upstream and the response streams back (chunked, no full-body buffering); query string is preserved; an SSE/streamed upstream response passes through; an unreachable upstream surfaces a clear error not an opaque 502 (FR-004, FR-011).

### Implementation

- [ ] T001 Implement the proxy registry (mount prefix → upstream base URI + per-upstream options: timeouts, static-prefix). One class per file per ADR-020; place under `anvil/api/` (e.g. `anvil/api/proxy_registry.py`). `httpx.AsyncClient` streaming forward. **Prerequisite: T001t/T002t.**
- [ ] T002 Implement the reverse-proxy route `{prefix}/{path:path}` in `anvil/api/v1/proxy.py` (or per-upstream module) that looks up the registry and streams via the registry's client. Single source-of-truth mount-prefix constant so spec 023 can de-version it in one edit (FR-013).

**Checkpoint**: Generic registry + route work against a stub upstream; streaming + error surfacing verified.

---

## Phase 2: Auth & CSRF Integration

**Purpose**: Proxied sub-paths inherit the app's auth; the proxy prefix is CSRF-exempt.

- [ ] T003t [P] Tests in `tests/integration/test_proxy_auth.py` — unauthenticated request to a proxied prefix → 401 (API) / login redirect (browser) BEFORE reaching the upstream; valid session cookie / `X-API-Key` → forwarded; a cookie-authenticated state-changing request to the proxy prefix succeeds WITHOUT `X-CSRF-Token` (prefix is CSRF-exempt) (FR-005, FR-010, cross-ref spec 020 FR-027).
- [ ] T003 Confirm the existing auth middleware in `anvil/api/app.py` intercepts proxied prefixes (it already runs app-wide); wire the existing `CSRF_EXEMPT_PREFIXES = ("/v1/mlflow-proxy",)` in `anvil/api/auth.py` to the now-live route (currently dead code). No new auth scheme. **Prerequisite: T003t.**

**Checkpoint**: Proxy honors auth; CSRF exemption active and tested.

---

## Phase 3: MLflow as First Registered Upstream (the OWASP A05-001/A07 fix)

**Purpose**: Register MLflow, bind it loopback, unpublish its port, point the browser URL at the proxy.

- [ ] T004t [P] Tests in `tests/integration/test_mlflow_proxy.py` — authenticated `GET /v1/mlflow-proxy/` → 200 and SPA assets resolve under the prefix; unauthenticated → 401/redirect; cookie-auth MLflow AJAX `POST /v1/mlflow-proxy/ajax-api/...` succeeds without `X-CSRF-Token` (SC-002, SC-003). **Replaces spec 020 T009t.**
- [ ] T004 Register MLflow with the registry at `/v1/mlflow-proxy`, upstream from `ANVIL_MLFLOW_INTERNAL_URI` (local default `http://127.0.0.1:<mlflow_port>`; SaaS default Cloud Map; fail-fast if unset in SaaS) (FR-008). **Prerequisite: T004t.**
- [ ] T005 Update `MLflowService.start()` in `anvil/supervisor/services.py` — bind loopback (replace `--host 0.0.0.0`), add `--static-prefix=/v1/mlflow-proxy`, stop relying on `--allowed-hosts "*"` as sole control; add `MLflowService.health_check()` and gate readiness in the app lifespan (FR-009, FR-011).
- [ ] T006 Revise `get_mlflow_browser_uri(request)` in `anvil/config.py` — return `{request.base_url}v1/mlflow-proxy`, scheme-aware (honor `https` + `X-Forwarded-Proto`); never a bare `:5001` (FR-007).
- [ ] T007 [P] Stop publishing MLflow port `5001`: remove `"5001:5001"` from `compose.yaml`; remove `5001` from `Dockerfile EXPOSE` (FR-002, FR-009). **Resolves the spec 012 vs 024 conflict — see spec 012.**

**Checkpoint**: MLflow reachable ONLY via the authenticated proxy; port 5001 unpublished; OWASP A05-001 + A07 (MLflow surface) remediated.

---

## Phase 4: Validation

- [ ] T008 Registry stub-upstream test (SC-004) — register a throwaway upstream under a test prefix and assert end-to-end routing with no extra code (closes spec 024 SC-005).
- [ ] T009 Port/connectivity check (SC-001/SC-006) — from off-host only the app port answers; container inspection shows no `5001`.
- [ ] T010 `make lint` + `make typecheck` (mypy --strict) — zero new errors.
- [ ] T011 `make test` — all pre-existing tests pass; new proxy tests green.
- [ ] T012 Update `docs/owasp-tracker.csv` A05-001 → resolved (reverse proxy + loopback + unpublished port); cross-ref this spec.
- [ ] T013 `make vault-audit` — zero vault errors.

---

## Dependencies & Execution Order

- **Phase 1** blocks everything (registry + route are the foundation).
- **Phase 2** depends on Phase 1 (auth wraps the live route).
- **Phase 3** depends on Phases 1–2 (MLflow is the first upstream on the working, authed registry).
- **Phase 4** depends on all prior phases.

### Relationship to other specs

- **Spec 020 OWASP Remediation** — T009/T009t are SUPERSEDED by this spec's Phase 3 (T004–T007); 020 FR-004 references 056.
- **Spec 036 SaaS Observability** — Phase 5 (T027–T035) keeps only SaaS-specific layers (Cognito/RBAC enforcement, `org_id` tagging, Cloud Map upstream, CloudFront scheme); the generic route/streaming/registry/`--static-prefix`/`get_mlflow_browser_uri` come from 056.
- **Spec 024 Unified Interface Local TLS** — FR-003 (registry) is OWNED here; 024 keeps the TLS half and references 056 for the front door.
- **Spec 023 Header API Versioning** — moves the mount prefix off `/v1/`; enabled by FR-013's single-definition constant.
- **Spec 012 Pip Installable Package** — Docker/compose contracts amended (T007) to stop publishing 5001.
