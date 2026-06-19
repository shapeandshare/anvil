# Tasks: Developer & Agent Experience Hardening

**Input**: Design documents from `/specs/013-dx-harness-hardening/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: TDD test tasks are included **only** for the new Python helper scripts (`check_bump_scope.py`, `check_guarded_imports.py`, `check_adr_unique.py`), per the constitution's TDD mandate. Governance/documentation tasks are verified by the gates themselves (`make vault-audit`, CI) rather than unit tests. Structural refactors (US4) are verified by the unchanged existing suite.

**Organization**: Tasks are grouped by user story (US1–US4) in priority order (P1→P4). US1 is the MVP and unblocks verification of the rest.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1–US4 (maps to spec.md user stories)

## Path Conventions

Existing single-package layout: `anvil/` (package), `tests/` (suite), `scripts/ci/` (gate helpers), `.github/workflows/` (CI), `docs/vault/` (knowledge base), repo-root governance/docs.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the measured facts the gates and amendments depend on.

- [x] T001 Measure current coverage baseline: run `make test`, capture the overall coverage percentage (floor to integer), and record it under R2 in `specs/013-dx-harness-hardening/research.md``
- [ ] T002 [P] Verify local gate parity: run `make lint`, `make typecheck`, `make vault-audit` and confirm the exact invocations match those documented in `specs/013-dx-harness-hardening/contracts/ci-gates.md`; note any drift

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Reserve identifiers that multiple stories mutate, preventing collisions.

**⚠️ CRITICAL**: ADR-touching work in US2/US3 depends on this reservation.

- [ ] T003 Enumerate existing ADR numbers in `docs/vault/Decisions/`, then reserve next-free `ADR-0NN` numbers for (a) renumber targets of collisions 008/010/016 and (b) the new ADRs; record the full old→new mapping under R4 in `specs/013-dx-harness-hardening/research.md`

**Checkpoint**: Baseline coverage known; ADR number map fixed — user stories can begin.

---

## Phase 3: User Story 1 - Trustworthy automated quality gates (Priority: P1) 🎯 MVP

**Goal**: Every PR is automatically validated against the declared gates and blocked on failure (fail-closed), with a fast exemption for version-only bump PRs.

**Independent Test**: Open a deliberately-failing PR (lint/type/test/coverage) and confirm CI blocks merge and names the gate; open a clean PR and confirm it is mergeable; open a version-only bump PR and confirm the fast path.

### Tests for User Story 1 (helper script — TDD) ⚠️

- [ ] T004 [P] [US1] Write failing unit tests for the bump-scope guard (version-only vs source-touching classification) in `tests/unit/ci/test_check_bump_scope.py`

### Implementation for User Story 1

- [ ] T005 [US1] Implement `scripts/ci/check_bump_scope.py` to classify a changed-file set as version-only-bump (⊆ {pyproject version line, CHANGELOG.md}) or full, exiting non-zero only on contract violation (makes T004 pass)
- [ ] T006 [US1] Set `[tool.coverage.report] fail_under` to the measured baseline from T001 in `pyproject.toml`
- [ ] T007 [US1] Create `.github/workflows/ci.yml` with jobs `lint`, `typecheck`, `test`, `vault-audit`, and `bump-scope-guard`, triggered on `pull_request` and `push` to non-`main` branches, each calling the same `make` target a developer runs
- [ ] T008 [US1] Reconcile `.github/workflows/auto-bump.yml` and `.github/workflows/release.yml` so bot bump PRs satisfy `bump-scope-guard` and do not bypass gates for source changes (per `contracts/ci-gates.md` C7/C8)
- [ ] T009 [US1] Document branch-protection setup (required status checks, fail-closed, no bot bypass) in `CONTRIBUTING.md` and `specs/013-dx-harness-hardening/quickstart.md`
- [ ] T010 [US1] Validate the gate suite against `contracts/ci-gates.md` scenarios C1–C9 using deliberate-failure and happy-path PRs; record evidence

**Checkpoint**: Gates are real and blocking — all subsequent work is now guarded by CI.

---

## Phase 4: User Story 2 - Consistent, honest governance (Priority: P2)

**Goal**: Remove contradictions and unenforceable claims: conditional `TYPE_CHECKING` policy (code complies), honest ratcheting coverage, unique ADR numbers, reconciled `mypy` overrides — each amendment recorded as an ADR with a constitution version bump.

**Independent Test**: Cross-read governance for contradictions (0); confirm `inference.py` uses a normal import and `guarded-imports` is green; confirm no duplicate ADR numbers and `make vault-audit` passes; confirm declared coverage == enforced.

### Tests for User Story 2 (helper scripts — TDD) ⚠️

- [ ] T011 [P] [US2] Write failing unit tests for the guarded-imports checker (flag a `TYPE_CHECKING` symbol used in runtime code; pass annotation-only usage) in `tests/unit/ci/test_check_guarded_imports.py`
- [ ] T012 [P] [US2] Write failing unit tests for the ADR-uniqueness check (detect duplicate `ADR-0NN` numbers; pass unique set) in `tests/unit/ci/test_check_adr_unique.py`

### Implementation for User Story 2

- [ ] T013 [US2] Implement `scripts/ci/check_guarded_imports.py` flagging any `TYPE_CHECKING`-guarded symbol referenced in non-annotation runtime code (makes T011 pass)
- [ ] T014 [US2] Implement the ADR-uniqueness check as `scripts/ci/check_adr_unique.py` (or extend `scripts/ci/vault_audit.py`) (makes T012 pass)
- [ ] T015 [US2] Refactor `anvil/services/inference/inference.py`: replace the `TYPE_CHECKING` guard with a top-level `from ...core.autograd import Value` and remove the redundant function-local re-import (~line 676)
- [ ] T016 [P] [US2] Add the required one-line cycle comment to the `TYPE_CHECKING` guards in `anvil/db/models/corpus.py` and `anvil/db/models/corpus_file.py`
- [ ] T017 [US2] Renumber the later duplicate ADRs (008/010/016) to the reserved numbers from T003, add redirect/alias stubs at the former filenames, and fix all inbound wikilinks in `docs/vault/`
- [ ] T018 [US2] Normalize `docs/vault/Decisions/010-numpy-docstring-enforcement.md` to the reserved `ADR-0NN-...` filename and update inbound links
- [ ] T019 [US2] Reconcile the `mypy` `ignore_errors` overrides for `anvil.services.tracking` and `anvil.services.mlflow_inputs` in `pyproject.toml` — narrow to specific error codes (preferred, if MLflow stub gaps) or remove
- [ ] T020 [P] [US2] Author ADR `docs/vault/Decisions/ADR-0NN-coverage-ratcheting-baseline.md` (reserved number from T003)
- [ ] T021 [P] [US2] Author ADR `docs/vault/Decisions/ADR-0NN-type-checking-conditional-allow.md` (include the rejected co-location alternative)
- [ ] T022 [P] [US2] Author ADR `docs/vault/Decisions/ADR-0NN-ci-merge-gate-enforcement.md`
- [ ] T023 [P] [US2] Author ADR `docs/vault/Decisions/ADR-0NN-adr-renumbering-and-uniqueness.md`
- [ ] T024 [US2] Amend `.specify/memory/constitution.md`: Article IV coverage → ratcheting baseline + phased goal; `TYPE_CHECKING` → conditional-allow + 4-point discipline; bump `**Version**` and `**Last Amended**` (depends on T020, T021)
- [ ] T025 [US2] Align `AGENTS.md` `TYPE_CHECKING`/PEP-563 guidance with the amended constitution so the policy reads consistently in both (per `contracts/governance-invariants.md` INV-1)
- [ ] T026 [US2] Extend `.github/workflows/ci.yml` and the `make vault-audit` target to run the `guarded-imports` and `adr-uniqueness` gates (depends on T013, T014)
- [ ] T027 [US2] Cross-document contradiction sweep across constitution/`AGENTS.md`/`CONTRIBUTING.md` per INV-1; record 0 contradictions
- [ ] T028 [US2] Run `make vault-audit` and `python scripts/ci/check_guarded_imports.py`; confirm 0 errors after renumbering, new ADRs, and the inference refactor (depends on T015–T024)

**Checkpoint**: Governance is internally consistent and code-true; every amendment is recorded.

---

## Phase 5: User Story 3 - Fast, self-service onboarding (Priority: P3)

**Goal**: A newcomer can understand the architecture, find mandatory rules, run gates locally, and browse decisions — from the repo root, without source-diving or special tooling.

**Independent Test**: Hand the docs to an unfamiliar reader; confirm they can explain the layering model, locate gate commands, and find a named decision's rationale within ~10 minutes.

### Implementation for User Story 3

- [ ] T029 [P] [US3] Create `ARCHITECTURE.md` (repo root): layering model (Repository → Service → `AnvilWorkbench` → Routes/CLI), data-flow narrative, "how to add a service/route/endpoint", and where ADRs live
- [ ] T030 [P] [US3] Expand `CONTRIBUTING.md`: code map, mandatory-rules digest, local gate commands, and links to `ARCHITECTURE.md` + the ADR index
- [ ] T031 [US3] Generate `docs/vault/Decisions/README.md` — a human-readable ADR index (id, title, status, one-line summary); wire its validation into `make vault-audit` if practical (depends on T017, T018, T020–T023)
- [ ] T032 [US3] Trim `AGENTS.md` "Active Technologies"/"Recent Changes" into `CHANGELOG.md`, leaving only durable rules in the agent guide (FR-016/INV-7)

**Checkpoint**: Human + agent onboarding is discoverable and tooling-free.

---

## Phase 6: User Story 4 - Consistent, navigable architecture (Priority: P4)

**Goal**: All services route through one access surface; the oversized route aggregator is decomposed. Each refactor is a standalone, behavior-free change verified by the (now-enforced) suite.

**Independent Test**: Confirm every service is obtained via `AnvilWorkbench`; confirm `router.py` is a thin aggregator delegating to per-area modules; confirm the full test suite passes identically before and after each refactor (zero behavioral delta).

### Implementation for User Story 4

- [ ] T033 [US4] Behavior-free refactor (own commit per §10.9): consolidate the god class — expose all services through `AnvilWorkbench`, relocate it from `anvil/cli.py` to `anvil/workbench.py`, and migrate all routes/CLI/tests to obtain services via it; run the full suite and confirm zero delta (FR-018, FR-020)
- [ ] T034 [US4] Behavior-free refactor (own commit per §10.9): decompose `anvil/api/v1/router.py` into cohesive per-area modules (page-rendering, health/ops, learning, per-domain routers), reducing `router.py` to a thin aggregator while keeping one class per file and Article X boundaries; confirm identical route table and zero suite delta (FR-019, FR-020)
- [ ] T035 [US4] Update `ARCHITECTURE.md` so the documented service-access pattern matches the consolidated god class (FR-017) (depends on T029, T033)

**Checkpoint**: Code structure matches the documented architecture; onboarding doc is accurate.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final verification against the spec's measurable outcomes.

- [ ] T036 [P] Run the `quickstart.md` walkthrough end-to-end (contributor flow, newcomer flow, ADR-add flow); record results
- [ ] T037 Verify Success Criteria SC-001–SC-011 are met; record evidence in `specs/013-dx-harness-hardening/`
- [ ] T038 [P] Confirm `make lint`, `make typecheck`, `make test`, `make vault-audit`, and the new checks are all green on the branch

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: After Setup. T003 blocks all ADR-touching tasks.
- **US1 (Phase 3)**: After Foundational. Delivers the MVP enforcement; T006 depends on T001.
- **US2 (Phase 4)**: After US1 (so changes are gate-guarded). T026 extends the `ci.yml` created in T007.
- **US3 (Phase 5)**: After US2 (ADR index needs final ADR set). T029/T030 can start earlier in parallel.
- **US4 (Phase 6)**: After US1 (needs the enforced suite to prove zero delta). T035 depends on T029 + T033.
- **Polish (Phase 7)**: After all desired stories.

### User Story Dependencies

- **US1 (P1)**: Independent; the MVP.
- **US2 (P2)**: Logically sequenced after US1 (to be gate-guarded); not code-coupled to US1.
- **US3 (P3)**: ADR index (T031) depends on US2's final ADR set; ARCHITECTURE/CONTRIBUTING drafts are independent.
- **US4 (P4)**: Independent of US2/US3; relies on US1's enforced suite for verification.

### Within Each User Story

- Helper-script tests (T004, T011, T012) MUST be written and fail before their implementation (T005, T013, T014).
- ADR authoring (T020–T023) before constitution amendment (T024).
- Renumbering (T017/T018) before ADR index generation (T031) and final vault-audit (T028).
- Each US4 refactor is its own commit; suite must pass identically before/after.

### Parallel Opportunities

- T002 ∥ T001 partially (T002 independent of the coverage number).
- US2 ADRs T020/T021/T022/T023 are all [P] (separate files).
- Helper-script tests T011 ∥ T012 [P]; T016 [P] (separate model files).
- US3 docs T029 ∥ T030 [P].
- Polish T036 ∥ T038 [P].

---

## Parallel Example: User Story 2 ADRs

```bash
# Author the four decision records in parallel (separate files):
Task: "Author ADR-0NN-coverage-ratcheting-baseline.md"
Task: "Author ADR-0NN-type-checking-conditional-allow.md"
Task: "Author ADR-0NN-ci-merge-gate-enforcement.md"
Task: "Author ADR-0NN-adr-renumbering-and-uniqueness.md"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → Phase 2 Foundational → Phase 3 US1.
2. **STOP and VALIDATE**: deliberate-failure PR is blocked; clean PR merges; bump PR fast-paths.
3. Enable branch protection. The harness is now trustworthy — ship it.

### Incremental Delivery

1. US1 (enforcement) → MVP, gates real.
2. US2 (governance honesty) → no contradictions, code-true, recorded.
3. US3 (onboarding) → discoverable docs + ADR index.
4. US4 (structure) → two behavior-free refactors, each gate-verified.

### Notes

- [P] = different files, no incomplete-task dependency.
- Commit after each task or logical group; US4 tasks are explicitly one-refactor-per-commit (§10.9).
- Do not merge any task's change without the US1 gates passing once US1 lands.
