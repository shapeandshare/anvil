---
title: 017 Graph Health Subsumption - tasks
type: tasks
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/017 Graph Health Subsumption/
related:
  - '[[017 Graph Health Subsumption]]'
created: ~
updated: ~
---
# Tasks: Graph Health Subsumption into Anvil

**Input**: Design documents from `docs/vault/Specs/017 Graph Health Subsumption/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli.md, quickstart.md

**Tests**: Test tasks are included per TDD convention (Constitution Art IV). Write tests FIRST (red), then implement (green).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- **Package root**: `anvil/`
- **New vault sub-package**: `anvil/services/vault/`
- **Tests**: `tests/services/vault/`
- **CLI entry points**: `pyproject.toml [project.scripts]`
- **Makefile**: `shared/vault.mk`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the `anvil/services/vault/` domain sub-package structure, configure optional extras, stub the CLI entry point

- [X] T001 Create `anvil/services/vault/` directory structure with bare docstring-only `__init__.py` at `anvil/services/vault/__init__.py`
- [X] T002 Register `vault-health` optional extra in `pyproject.toml` under `[project.optional-dependencies]` with `networkx>=3,<4`
- [X] T003 [P] Register `anvil-vault` console script in `pyproject.toml` under `[project.scripts]`: `anvil-vault = "anvil.services.vault.cli:main"`
- [X] T004 [P] Create stub CLI module at `anvil/services/vault/cli.py` with argparse subcommand parsers for `audit`, `check-adrs`, `check-guarded-imports`, `check-bump-scope` (each prints "not yet implemented" placeholder)

**Checkpoint**: Vault sub-package exists, `anvil-vault --help` shows all subcommands, `anvil-vault audit` prints placeholder

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core types and test infrastructure that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T005 Create `anvil/services/vault/_types.py` with Pydantic `BaseModel` types: `NoteMetadata`, `ConnectivityMetrics`, `TopologicalMetrics`, `HygieneMetrics`, `TemporalMetrics`, `StructuralMetrics`, `HealthScore`, `ScoredPair`, `LinkPredictionResult`, `MechanicalReport`, `Finding`, `GraphHealthReport` (migrated from legacy `@dataclass` in `scripts/ci/graph_health/__init__.py`)
- [X] T006 Create abstract analysis module interfaces: `connectivity.py`, `topology.py`, `hygiene.py`, `temporal.py`, `structural.py`, `scoring.py`, `prediction.py`, `report.py` — each with stub function signatures matching `data-model.md` contracts
- [X] T007 Create `anvil/services/vault/vault_audit.py` with `VaultAuditService` class (async interface, sync file I/O wrapped in `asyncio.to_thread()`)
- [X] T008 Create `anvil/services/vault/scanner.py` with `GraphHealthRunner` class (migrated from `scripts/ci/graph_health/__init__.py`)
- [X] T009 Create test directory `tests/services/vault/` with `__init__.py` and conftest with vault fixture pointing to a test vault directory
- [X] T010 Write foundational type validation tests in `tests/services/vault/test_types.py` — verify all `BaseModel` types accept valid data and reject invalid data

**Checkpoint**: Types are importable, test vault fixture works, service stubs compile with `mypy --strict`

---

## Phase 3: User Story 1 — `anvil-vault audit` CLI (Priority: P1) 🎯 MVP

**Goal**: Developer runs vault health checks via `anvil-vault audit`, getting identical output to legacy `scripts/ci/vault_audit.py`

**Independent Test**: Run `anvil-vault audit --vault-dir docs/vault` and compare output with `python scripts/ci/vault_audit.py docs/vault` — both must produce same exit code and same report content

### Tests for User Story 1

- [X] T011 [P] [US1] Write test for `VaultAuditService.run_mechanical_audit()` in `tests/services/vault/test_vault_audit.py` — verify it returns `MechanicalReport` with typed findings
- [X] T012 [P] [US1] Write test for `GraphHealthRunner` in `tests/services/vault/test_scanner.py` — verify `scan_all_notes()` and `build_graph()` produce correct `NoteMetadata` and graph structure
- [X] T013 [US1] Write test for `connectivity.compute_connectivity()` in `tests/services/vault/test_connectivity.py` — verify orphan/dead-end/density/bidirectional metrics match known test vault
- [X] T014 [P] [US1] Write test for `topology.compute_topological()` in `tests/services/vault/test_topology.py`
- [X] T015 [P] [US1] Write test for `hygiene.compute_hygiene()` in `tests/services/vault/test_hygiene.py`
- [X] T016 [P] [US1] Write test for `temporal.compute_temporal()` in `tests/services/vault/test_temporal.py`
- [X] T017 [P] [US1] Write test for `structural.compute_structural()` in `tests/services/vault/test_structural.py`
- [X] T018 [US1] Write test for `scoring.compute_health_score()` in `tests/services/vault/test_scoring.py`
- [X] T019 [P] [US1] Write test for `report.render_markdown()` in `tests/services/vault/test_report.py`
- [X] T020 [P] [US1] Write CLI integration test in `tests/services/vault/test_cli.py` — verify `anvil-vault audit --skip-graph-health` exits 0 on clean vault, 1 on violations
- [X] T021 [P] [US1] Write CLI help output test in `tests/services/vault/test_cli.py` — verify `anvil-vault --help` lists all 4 subcommands (`audit`, `check-adrs`, `check-guarded-imports`, `check-bump-scope`) with descriptions
- [X] T022 [US1] Write end-to-end test: legacy `scripts/ci/vault_audit.py` output vs `anvil-vault audit` output match on the project's own vault

### Implementation for User Story 1

- [X] T023 [P] [US1] Implement `compute_connectivity()` in `anvil/services/vault/connectivity.py` (migrate from `scripts/ci/graph_health/scanner.py`, refactor to use Pydantic types)
- [X] T024 [P] [US1] Implement `compute_topological()` in `anvil/services/vault/topology.py` (migrate from `scripts/ci/graph_health/topology.py`)
- [X] T025 [P] [US1] Implement `compute_hygiene()` in `anvil/services/vault/hygiene.py` (migrate from `scripts/ci/graph_health/hygiene.py`, refactor to use Pydantic types)
- [X] T026 [P] [US1] Implement `compute_temporal()` in `anvil/services/vault/temporal.py` (migrate from `scripts/ci/graph_health/temporal.py`)
- [X] T027 [P] [US1] Implement `compute_structural()` in `anvil/services/vault/structural.py` (migrate from `scripts/ci/graph_health/structural.py`)
- [X] T028 [US1] Implement `compute_health_score()` in `anvil/services/vault/scoring.py` (migrate from `scripts/ci/graph_health/scoring.py`)
- [X] T029 [US1] Implement link prediction ensemble in `anvil/services/vault/prediction.py` (migrate from `scripts/ci/graph_health/prediction.py`)
- [X] T030 [US1] Implement `render_markdown()` in `anvil/services/vault/report.py` (migrate from `scripts/ci/graph_health/report.py`)
- [X] T031 [US1] Implement `GraphHealthRunner` class in `anvil/services/vault/scanner.py` with `scan_all_notes()`, `build_graph()`, `run_all()`, `write_reports()` methods (migrate from `scripts/ci/graph_health/__init__.py`)
- [X] T032 [US1] Implement `VaultAuditService` class in `anvil/services/vault/vault_audit.py` with mechanical audit methods (migrate from `scripts/ci/vault_audit.py` frontmatter/wikilink validation logic)
- [X] T033 [US1] Implement `cli.main()` `audit` subcommand handler in `anvil/services/vault/cli.py` — wire `VaultAuditService` + `GraphHealthRunner` + argparse flags (`--apply`, `--diff`, `--skip-graph-health`, `--vault-dir`). All vault paths MUST be parameterized via CLI arguments (no hardcoded paths).
- [X] T034 [US1] Add NumPy-style docstrings to all public classes, methods, and functions in `anvil/services/vault/`
- [X] T035 [US1] Run `mypy --strict` on `anvil/services/vault/` and fix all type errors — no `# type: ignore` or `Any` suppressions
- [X] T036 [US1] Verify `anvil-vault audit` produces identical exit codes and report content as legacy `scripts/ci/vault_audit.py` on the project's own vault

**Checkpoint**: `anvil-vault audit` fully functional with all legacy flags — mechanical audit + graph health produce identical results

---

## Phase 4: User Story 2 — CI Validator CLI Commands (Priority: P1)

**Goal**: Developer runs `anvil-vault check-adrs`, `anvil-vault check-guarded-imports`, `anvil-vault check-bump-scope` with identical behavior to legacy scripts

**Independent Test**: Run each `anvil-vault check-*` variant on the project and compare exit codes + output with the corresponding `python scripts/ci/check_*.py` legacy call

### Tests for User Story 2

- [X] T037 [P] [US2] Write test for `check_adr_unique.validate_adrs()` in `tests/services/vault/test_check_adr_unique.py`
- [X] T038 [P] [US2] Write test for `check_guarded_imports.scan_directory()` in `tests/services/vault/test_check_guarded_imports.py`
- [X] T039 [US2] Write test for `check_bump_scope_classify()` in `tests/services/vault/test_check_bump_scope.py`
- [X] T040 [P] [US2] Write CLI integration tests for `anvil-vault check-adrs`, `check-guarded-imports`, `check-bump-scope` in `tests/services/vault/test_cli.py`

### Implementation for User Story 2

- [X] T041 [P] [US2] Implement `check_adr_unique` module in `anvil/services/vault/check_adr_unique.py` (migrate from `scripts/ci/check_adr_unique.py`, refactor to use Pydantic types, add NumPy docstrings)
- [X] T042 [P] [US2] Implement `check_guarded_imports` module in `anvil/services/vault/check_guarded_imports.py` (migrate from `scripts/ci/check_guarded_imports.py`, add NumPy docstrings)
- [X] T043 [P] [US2] Implement `check_bump_scope` module in `anvil/services/vault/check_bump_scope.py` (migrate from `scripts/ci/check_bump_scope.py`, add NumPy docstrings)
- [X] T044 [US2] Implement `cli.main()` handlers for `check-adrs`, `check-guarded-imports`, `check-bump-scope` subcommands in `anvil/services/vault/cli.py`
- [X] T045 [US2] Run `mypy --strict` on all three new modules and fix type errors

**Checkpoint**: All three `anvil-vault check-*` commands functional with identical output to legacy scripts

---

## Phase 5: User Story 3 — Programmatic API (Priority: P2)

**Goal**: Developer imports `VaultHealthService` and `GraphHealthService` directly from `anvil.services.vault` for programmatic use

**Independent Test**: `from anvil.services.vault import VaultHealthService, GraphHealthService` — instantiate with a vault path, call analysis methods, inspect typed return objects

### Tests for User Story 3

- [X] T046 [P] [US3] Write test for `VaultHealthService.run_full_audit()` in `tests/services/vault/test_vault_health_service.py`
- [X] T047 [P] [US3] Write test for `GraphHealthService.analyze()` in `tests/services/vault/test_graph_health_service.py`

### Implementation for User Story 3

- [X] T048 [US3] Implement `VaultHealthService` orchestrator class in `anvil/services/vault/vault_health_service.py` — wraps `VaultAuditService` + `GraphHealthRunner` with a unified `run_full_audit()` method returning `GraphHealthReport`
- [X] T049 [US3] Implement `GraphHealthService` class in `anvil/services/vault/vault_health_service.py` (or dedicated file) — wraps `GraphHealthRunner` with convenience methods for individual analysis passes
- [X] T050 [US3] Verify programmatic API is importable from `anvil.services.vault` (update `__init__.py` docstring to describe public API)
- [X] T051 [US3] Run `mypy --strict` on service classes

**Checkpoint**: `VaultHealthService` and `GraphHealthService` importable, runnable, and fully typed

---

## Phase 6: User Story 4 — Makefile Delegation (Priority: P2)

**Goal**: `make vault-audit`, `make vault-audit-apply`, `make vault-audit-diff`, `make vault-audit-fast`, `make adr-check`, `make guarded-imports-check` all delegate to `anvil-vault` CLI

**Independent Test**: Run each `make vault-*` target and verify identical output + exit code to before subsumption

### Implementation for User Story 4

- [X] T052 [US4] Update `shared/vault.mk` to replace `$(PYTHON) scripts/ci/vault_audit.py` with `anvil-vault audit` in all four audit targets
- [X] T053 [US4] Update `shared/vault.mk` to replace `$(PYTHON) scripts/ci/check_adr_unique.py` with `anvil-vault check-adrs`
- [X] T054 [US4] Update `shared/vault.mk` to replace `$(PYTHON) scripts/ci/check_guarded_imports.py` with `anvil-vault check-guarded-imports`

**Checkpoint**: All `make vault-*` and `make *-check` targets delegate to `anvil-vault` and produce identical output

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Cleanup, legacy wrappers, vault enrichment

- [X] T055 [P] Create thin wrapper at `scripts/ci/vault_audit.py` that imports and delegates to `anvil-vault audit` (for backward CI compatibility)
- [X] T056 Remove or replace `scripts/ci/check_adr_unique.py`, `scripts/ci/check_guarded_imports.py`, `scripts/ci/check_bump_scope.py` — either delete or convert to thin wrappers
- [X] T057 Remove or replace `scripts/ci/graph_health/` package — code fully migrated to `anvil/services/vault/`
- [X] T058 Verify all tests pass: `make test` (unit + integration)
- [X] T059 Run `make lint` and `make typecheck` — both must pass with zero violations on all code
- [X] T060 [P] Run `ruff` and `pylint` specifically on `anvil/services/vault/` to verify full convention compliance (NumPy docstrings, one-class-per-file, no unused imports)
- [X] T061 Write ADR for the subsumption architecture decision in `docs/vault/Decisions/ADR-025-vault-health-subsumption.md`
- [X] T062 Write vault session log in `docs/vault/Sessions/2026-06-19-graph-health-subsumption.md`
- [X] T063 Run `make vault-audit` to verify the subsumption doesn't break vault health on the project's own vault — must report 0 errors
- [X] T064 Final validation: run all checkpoints sequentially to confirm every user story is independently testable and functional

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — can start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 completion — BLOCKS all user stories
- **Phase 3 (US1 — P1)**: Depends on Phase 2 completion
- **Phase 4 (US2 — P1)**: Depends on Phase 2 completion — independent from US1 (different modules)
- **Phase 5 (US3 — P2)**: Depends on Phase 3 completion (reuses VaultAuditService, GraphHealthRunner)
- **Phase 6 (US4 — P2)**: Depends on Phase 3 + Phase 4 completion (needs CLI entry points)
- **Phase 7 (Polish)**: Depends on all phases complete

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2 — foundational types + analysis modules
- **US2 (P1)**: Can start after Phase 2 — independent from US1 (separate modules: check_adr_unique, check_guarded_imports, check_bump_scope)
- **US3 (P2)**: Depends on US1 completion (wraps VaultAuditService + GraphHealthRunner)
- **US4 (P2)**: Depends on US1 + US2 CLI being functional

### Within Each Phase

- Tests MUST be written and FAIL before implementation (TDD — Constitution Art IV)
- Modules before service classes
- Service classes before CLI handlers
- Integration tests after implementation

---

## Parallel Opportunities

| Group | Tasks | Why Parallel |
|-------|-------|-------------|
| Phase 1: T003 + T004 | CLI entry + stub CLI | Different files, no deps |
| Phase 2: T005—T010 | Types, stubs, tests | Different modules, types first |
| Phase 3: T011—T021 (tests) | All test files | Different test modules |
| Phase 3: T023—T030 (analysis modules) | connectivity, topology, hygiene, temporal, structural, scoring, prediction, report | Each is a standalone module |
| Phase 3: T031 + T032 | GraphHealthRunner + VaultAuditService | Independent service classes |
| Phase 4: T037—T045 (US2) | Three check-* modules | Independent modules |
| Phase 5: T046—T047 (US3) | Service tests | Independent test files |
| Phase 7: T055—T056 | Legacy wrappers | Independent file operations |
| Phase 7: T060 | Convention compliance check | Standalone verification |

### Parallel Example: User Story 1 Implementation

```bash
# Launch all analysis modules in parallel:
Task: "Implement compute_connectivity() in anvil/services/vault/connectivity.py"
Task: "Implement compute_topological() in anvil/services/vault/topology.py"
Task: "Implement compute_hygiene() in anvil/services/vault/hygiene.py"
Task: "Implement compute_temporal() in anvil/services/vault/temporal.py"
Task: "Implement compute_structural() in anvil/services/vault/structural.py"
Task: "Implement compute_health_score() in anvil/services/vault/scoring.py"
Task: "Implement compute_link_prediction() in anvil/services/vault/prediction.py"
Task: "Implement render_markdown() in anvil/services/vault/report.py"

# After all analysis modules done:
Task: "Implement GraphHealthRunner in anvil/services/vault/scanner.py"
Task: "Implement VaultAuditService in anvil/services/vault/vault_audit.py"

# After both runner + service done:
Task: "Implement CLI audit handler in anvil/services/vault/cli.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001—T004)
2. Complete Phase 2: Foundational (T005—T010) — **CRITICAL: blocks all stories**
3. Complete Phase 3: User Story 1 (T011—T036)
4. **STOP and VALIDATE**: Run `anvil-vault audit` on project vault, compare with legacy output
5. MVP is ready: core vault audit functionality via `anvil-vault audit`

### Incremental Delivery

1. **Phase 1 + 2** → Foundation ready (types, stubs, test infrastructure)
2. **+ Phase 3** → `anvil-vault audit` functional — MVP! (`make vault-audit` still uses legacy script)
3. **+ Phase 4** → `anvil-vault check-adrs`, `check-guarded-imports`, `check-bump-scope` functional
4. **+ Phase 5** → Programmatic API available for Python consumers
5. **+ Phase 6** → `make vault-*` targets transparently delegate — full migration
6. **+ Phase 7** → Legacy scripts removed, vault enriched, ADR written

### Parallel Team Strategy

With multiple agents/developers:

1. **Agent A**: Phase 1 Setup → Phase 2 Foundational (T001—T010)
2. **After Phase 2 done**:
   - **Agent A**: US1 analysis modules (T023—T030 in parallel) → US1 services (T031—T032) → US1 CLI (T033)
   - **Agent B**: US2 all tasks (T037—T045, independent of US1)
3. **After US1 done**:
   - **Agent A**: US3 service classes (T046—T051)
   - **Agent B**: US4 Makefile (T052—T054)
4. **After all stories done**: Agent A: Polish phase (T055—T064)

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Write tests FIRST (red) before implementation (green) per Constitution Art IV
- All code must pass `mypy --strict` with zero type suppressions
- All public symbols must have NumPy-style docstrings
- Legacy `@dataclass` types in `scripts/ci/graph_health/` must be converted to Pydantic `BaseModel`
