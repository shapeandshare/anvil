# Tasks — 073 Add extra="forbid" to Schema Files

**TDD order. Smallest/lowest-risk spec — good first PR.**

## Phase 0 — Audit
- [ ] T001 Run the audit loop (context.md) across ALL `schemas_*.py` to get the true list of request-body models missing `extra="forbid"`.
- [ ] T002 Classify each model: request (needs forbid) vs response (leave default).

## Phase 1 — schemas_dataset.py (Red-Green)
- [ ] T010 **[Red]** `test_create_dataset_rejects_extra_field` — `POST /v1/datasets` with `{"name":"x","bogus":1}` → 422. Confirm FAILS (currently 200).
- [ ] T011 **[Green]** Add `model_config = ConfigDict(extra="forbid")` to all 8 request models in `schemas_dataset.py`. Make test pass.

## Phase 2 — schemas_content.py
- [ ] T020 **[Red]** `test_content_create_rejects_extra_field` for a content request body.
- [ ] T021 **[Green]** Add `extra="forbid"` to the 8 request models (NOT the 7 `*Out` response models).

## Phase 3 — Other schema files (from audit)
- [ ] T030 Apply `extra="forbid"` to any other request-body models found in T001.

## Phase 4 — Optional enforcement
- [ ] T040 (Optional) Add a lint check to `make lint` verifying request-body models have `extra="forbid"`.

## Phase 5 — Gates
- [ ] T050 `grep -c 'extra="forbid"'` shows expected counts.
- [ ] T051 `make lint && make typecheck && make test` — existing valid requests still pass.

## Verification (Success Criteria)
- SC-001: zero request-body models lack `extra="forbid"`.
- SC-002: unknown field → 422.
- SC-003: `make test` green.
- SC-004: no valid-request regressions.
