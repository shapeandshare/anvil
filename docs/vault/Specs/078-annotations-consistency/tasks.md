# Tasks — 078 PEP 563 Annotations Consistency

**Mechanical, low-risk. CORRECTED SCOPE: route files, not schema files (see context.md).**

## Phase 0 — Audit (get the TRUE list)
- [ ] T001 Run `grep -L "from __future__ import annotations" anvil/**/*.py` to list ALL non-conforming files package-wide.
- [ ] T002 Exclude exempt files: bare `__init__.py`, `anvil/_resources/migrations/**`, data-only modules. Produce the final edit list.

## Phase 1 — Add the import
- [ ] T010 For each file in the list, add `from __future__ import annotations` as the first import after the copyright header (before other imports).
- [ ] T011 Known route files needing it: `backup.py`, `compute.py`, `config.py`, `eval.py`, `eval_datasets.py`, `experiments.py`, `health_ops.py`, `registry.py`, `router.py` — plus any others from T001.

## Phase 2 — Verify no string-literal forward refs
- [ ] T020 Grep for quoted type annotations in the edited files; convert any `"MyClass"` forward refs to bare names.

## Phase 3 — Optional enforcement
- [ ] T030 (Optional) Extend `scripts/ci/check_import_placement.py` or add a lint rule to require the import in non-exempt files.

## Phase 4 — Gates
- [ ] T040 `grep -L "from __future__ import annotations" anvil/**/*.py` returns only exempt files.
- [ ] T041 `make lint && make typecheck && make test` — no behavior change.

## Verification (Success Criteria)
- SC-001: every non-exempt `.py` file has the import.
- SC-002: zero string-literal forward refs in edited files.
- SC-003: gates green.
- SC-004: no serialization/behavior change.
