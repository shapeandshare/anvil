# Tasks — 067 Add response_model to All Routes

**TDD order. This is the largest spec (221 routes) — work domain-by-domain.**

## Phase 0 — Prerequisites
- [ ] T001 Resolve `shared-decisions.md` Decision 1 (envelope convention). Grep `anvil/api/static/` and `anvil/client/_shared/` for response-shape dependencies.
- [ ] T002 Complete specs 072 (error format) and 073 (extra="forbid") first, OR coordinate closely.
- [ ] T003 Re-verify route count and current `response_model` usage (see context.md commands).

## Phase 1 — Establish pattern & shared models
- [ ] T010 **[Red]** Write a contract test that fetches `/openapi.json` and asserts a sample endpoint (e.g. `GET /v1/datasets`) has a non-empty response schema. Confirm FAILS.
- [ ] T011 Define shared response models (e.g. `PaginatedResponse[T]`, list wrappers) in the appropriate `schemas_*.py`.
- [ ] T012 **[Green]** Add `response_model=` to the pilot domain (datasets) and its response models. Make T010 pass for datasets.

## Phase 2 — Per-domain rollout (repeat Red-Green per domain)
For EACH domain below: write a contract test asserting the OpenAPI response schema, then add `response_model=` + response models.
- [ ] T020 datasets.py
- [ ] T021 corpora.py
- [ ] T022 training.py (exempt SSE stream endpoints)
- [ ] T023 experiments.py (coordinate with spec 070 — response model mirrors extracted service return type)
- [ ] T024 inference.py
- [ ] T025 eval.py (already done — verify/extend)
- [ ] T026 eval_datasets.py
- [ ] T027 models.py, registry.py
- [ ] T028 adapters.py, fine_tune_datasets.py
- [ ] T029 governance.py, content.py
- [ ] T030 health_ops.py (exempt `/health`), compute.py, config.py
- [ ] T031 backup.py, user_secrets.py, teach.py, hf_browser_api.py, learning.py
- [ ] T032 pages.py (HTML routes — exempt, document why)

## Phase 3 — Consistency & envelope
- [ ] T040 Ensure all migrated routes follow the SAME envelope convention (Decision 1).
- [ ] T041 If wrapper retained anywhere, document which endpoints and why.

## Phase 4 — Gates
- [ ] T050 `make lint && make typecheck && make test && make vault-audit`.
- [ ] T051 Fetch `/openapi.json`, confirm every non-exempt endpoint has a response schema (write a test that enumerates routes and asserts).

## Verification (Success Criteria)
- SC-001: `/openapi.json` shows complete response schemas for every non-exempt endpoint.
- SC-002: zero `dict[str, Any]` return annotations on non-exempt routes.
- SC-003: single envelope convention project-wide.
- SC-004: no behavioral regression (all current response values preserved or intentionally migrated).
