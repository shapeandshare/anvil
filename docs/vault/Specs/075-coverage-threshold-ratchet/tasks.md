# Tasks — 075 Raise Coverage Threshold (Ratcheting)

**Run this spec LAST (after 066-074, 076-080 add their tests).**

## Phase 0 — Measure
- [ ] T001 `make setup` if `.venv` missing.
- [ ] T002 `make test` — record the `TOTAL ... NN%` coverage line. This is the real baseline (docs say ~41%, VERIFY).

## Phase 1 — Ratchet
- [ ] T010 Set `pyproject.toml:203` `fail_under` to `floor(NN)` from T002.
- [ ] T011 Re-run `make test` — confirm it PASSES with the new threshold (no drop).

## Phase 2 — Policy
- [ ] T020 Add a "Coverage Ratchet Policy" section to CONTRIBUTING.md: threshold may only increase; lowering needs recorded approval (Article IV).
- [ ] T021 (Optional) Add a PR-template checkbox: "coverage did not drop".

## Phase 3 — Gates
- [ ] T030 `make lint && make typecheck && make test && make vault-audit`.

## Verification (Success Criteria)
- SC-001: `fail_under` raised from 23 to measured value.
- SC-002: `make test` passes at new threshold.
- SC-003: ratchet policy documented.

## Note
If run before the rest of the suite, bump to the current measured value now, then bump AGAIN after the suite lands to capture the added test coverage.
