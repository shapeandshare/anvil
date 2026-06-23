---
title: 013 Responsible Data Governance - tasks
type: tasks
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/013 Responsible Data Governance/
related:
  - '[[013 Responsible Data Governance]]'
created: ~
updated: ~
---
---
description: "Task list for Responsible Sample Data & Universal No-Harm Governance"
---

# Tasks: Responsible Sample Data & Universal No-Harm Governance

**Input**: Design documents from `/docs/vault/Specs/013 Responsible Data Governance/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/
**Branch**: `010-responsible-data-governance` | **Rebased onto**: `origin/main` @ `581b832` (Constitution v1.6.0)

**Tests**: REQUIRED — Constitution Article IV mandates TDD (Red-Green-Refactor) with 100% coverage. Each contract in `contracts/` carries explicit test obligations. Test tasks precede their implementation within every phase.

**Organization**: Tasks grouped by user story for independent implementation/testing.

> **Post-analysis remediation applied** (`/speckit.analyze`): C1/I1 (Article VII God Class) resolved by a full God-Class refactor (T004–T006, T024); G1 curation audit (T039/T044); G2 export+training attribution (T036); G3/SC-007 per-dataset governance report (T040/T047); G4 re-seed idempotency (T027/T033); U1 FR-013 redaction assertion (T019).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: US1–US4 (user-story phases only)

## Conventions (post-refactor, Constitution v1.6.0)

- One class per file (ADR-020); bare docstring-only `__init__.py`, NO re-exports (Article VI); relative imports only; `TYPE_CHECKING` forbidden.
- **Article VII**: ALL DB-backed services are exposed through the `AnvilWorkbench` God Class; routes/CLI/tests obtain services via the `get_workbench` dependency (`workbench.<service>`), never by constructing repositories/services inline.
- Governance = new bounded context → `anvil/services/governance/` (Article X). Result/value types co-located there as Pydantic `BaseModel` (ADR-019).
- Fixed-set columns use `StrEnum` (Principle 11), mirroring `Dataset.status` → `DatasetStatus`.
- ORM: `Base` (`anvil/db/base.py`) + `TimestampMixin` (`anvil/db/timestamp_mixin.py`) + `Mapped[]`/`mapped_column()`.
- HTTP schemas in `anvil/api/v1/schemas.py`. Response wrapper `{"data": ..., "error": ...}`.
- Every module/class/method needs NumPy-style docstrings (ruff `D`, convention=numpy).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Scaffolding required before any model/service work.

- [x] T001 [P] Create the governance domain package with a bare docstring-only `anvil/services/governance/__init__.py` (Article VI — no re-exports).
- [x] T002 [P] Add `"data/demo/**/*.json"` to `[tool.setuptools.package-data]` `anvil = [...]` in `pyproject.toml` so the provenance manifest ships in the wheel (research.md R5).
- [x] T003 Ensure new ORM models are visible to Alembic autogenerate by adding explicit imports of `anvil.db.models.audit_event` and `anvil.db.models.license_entry` in `anvil/_resources/migrations/env.py` (populate `Base.metadata`; do NOT re-export via `__init__.py`).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Article VII God-Class compliance refactor (structural), then cross-cutting building blocks: StrEnums, license catalog, hash-chained audit core, schema migration, shared result types.

**⚠️ CRITICAL**: No user story work begins until this phase completes.

### God Class refactor — Article VII (STRUCTURAL ONLY, commit separately per Article X §10.9)

> Pure moves + wiring rewrites, **zero behavioral delta**. Land these as their own commit before any governance behavior.

- [x] T004 Refactor `AnvilWorkbench` into a session-bound God Class in `anvil/cli.py` (or a new `anvil/workbench.py`): accept an optional `AsyncSession`, expose lazy accessors for ALL DB-backed services — `datasets` (`DatasetService`), `corpora` (`CorpusService`), `dataset_import` (`DatasetImportService` factory by dataset id), `dataset_curation` (`DatasetCurationService`), `demo` (`DemoBootstrapService`), `tracking` (`TrackingService`); keep stateless `training` accessor session-free.
- [x] T005 Add a request-scoped `get_workbench(session: AsyncSession = Depends(get_db_session)) -> AnvilWorkbench` dependency in `anvil/api/deps.py`.
- [x] T006 Migrate all existing call sites from direct service/repository instantiation to the God Class (structural-only, zero behavioral delta): replace per-route `get_service`/inline repo construction with `Depends(get_workbench)` + `workbench.<service>` across `anvil/api/v1/datasets.py`, `anvil/api/v1/corpora.py`, and any CLI/test entry points; update affected tests to call the God Class.

### StrEnums (Principle 11)

- [x] T007 [P] Create `DataOrigin(StrEnum)` `{BUNDLED="bundled", USER="user"}` in `anvil/services/governance/data_origin.py`.
- [x] T008 [P] Create `AuditAction(StrEnum)` `{SEED, UPLOAD, IMPORT, CURATE, DELETE, TAKEDOWN, POLICY_ACCEPT, POLICY_REJECT, CHAIN_CHECKPOINT}` (snake_case values) in `anvil/services/governance/audit_action.py`.
- [x] T009 [P] Create `AuditTargetType(StrEnum)` `{DATASET, CORPUS, SAMPLE, POLICY, AUDIT_CHAIN}` in `anvil/services/governance/audit_target_type.py`.
- [x] T010 [P] Create `AuditOutcome(StrEnum)` `{SUCCESS, REJECTED, ERROR}` in `anvil/services/governance/audit_outcome.py`.

### Shared result/value types (Pydantic BaseModel, ADR-019)

- [x] T011 [P] Create `GateDecision` (`accepted: bool`, `reason: str | None`, `license_id: int | None`, `origin: DataOrigin`) in `anvil/services/governance/gate_decision.py`.
- [x] T012 [P] Create `ChainVerifyResult` (`valid: bool`, `break_at_sequence: int | None`, `entries_checked: int`) in `anvil/services/governance/chain_verify_result.py`.
- [x] T013 [P] Create `ProvenanceView` (`source_description: str | None`, `license: str | None`, `attribution: str | None`, `origin: DataOrigin`) in `anvil/services/governance/provenance_view.py`.

### ORM models (one class per file)

- [x] T014 [P] Create `LicenseEntry` model (`license_catalog`; fields per data-model.md §1) in `anvil/db/models/license_entry.py`.
- [x] T015 [P] Create `AuditEvent` model (`audit_events`; fields per data-model.md §3, incl. `sequence`, `prev_hash`, `entry_hash`) in `anvil/db/models/audit_event.py`.

### Migration (after models exist)

- [x] T016 Author reversible Alembic migration `anvil/_resources/migrations/versions/014_add_governance.py` (generate via `make db-revision MESSAGE="add governance: provenance columns, license_catalog, audit_events"`, then hand-edit): provenance columns on `datasets` & `corpora` (`source_description`, `license_id` FK→`license_catalog.id` RESTRICT, `attribution_text`, `origin` default `"user"`, `parent_provenance_ref`); create `license_catalog` and `audit_events` with indexes; backfill existing rows (demo → `origin="bundled"`; others → `origin="user"`, own-content sentinel) per data-model.md §2. `down_revision` = current alembic head; full `downgrade()`.

### Repositories (after models exist)

- [x] T017 [P] Create `LicenseRepository` (`__init__(session)`, async `get_by_identifier`, `get`, `add`, `all`) in `anvil/db/repositories/licenses.py`.
- [x] T018 [P] Create `AuditEventRepository` (`__init__(session)`, async `get_tail`, `append`, `all_ordered`, `query(**filters)`; NO update/delete — append-only, VR-A3) in `anvil/db/repositories/audit_events.py`.

### Audit core + license seed (TDD: tests before impl)

- [x] T019 [P] Write unit tests for AuditService hash-chaining: genesis (`sequence=1`, `prev_hash`=64 zeros), `prev_hash[N]==entry_hash[N-1]`, recompute equals stored, `verify_chain` valid for clean chain, detects mutation/removal/insertion with correct `break_at_sequence` (T-A1–A5, SC-009), AND assert `params_json` stores references/summaries not full content bodies (FR-013, U1), in `tests/unit/services/governance/test_audit_service.py`. MUST fail initially.
- [x] T020 [P] Write unit tests for license catalog seed idempotency + the broad OSI/CC set incl. `own-content` sentinel and `requires_attribution` flags in `tests/unit/services/governance/test_license_seed.py`. MUST fail initially.
- [x] T021 Create `license_seed.py` (broad OSI/CC set per research.md R6) in `anvil/services/governance/license_seed.py`.
- [x] T022 Implement `AuditService` (`record`, canonical-JSON `hashlib.sha256` hashing, `verify_chain`, `list_events`, `checkpoint`; raises on write failure — must NOT mimic TrackingService) in `anvil/services/governance/audit_service.py` to make T019 pass (contracts/audit-service.md).
- [x] T023 Create `GovernanceService` with `seed_catalog()` (idempotent) and `list_licenses()` in `anvil/services/governance/governance_service.py` to make T020 pass (contracts/governance-service.md C-G1/C-G2).
- [x] T024 Register `audit` (`AuditService`) and `governance` (`GovernanceService`) as session-bound `AnvilWorkbench` accessors in `anvil/cli.py` (Article VII — extends T004).
- [x] T025 Wire license-catalog seeding into application startup alongside demo bootstrap in `anvil/api/app.py` lifespan via `workbench.governance.seed_catalog()` (idempotent; before/with demo bootstrap so license refs resolve).

**Checkpoint**: God Class compliant; schema migrated; StrEnums, license catalog, and tamper-evident audit core exist and are unit-tested. User stories can begin.

---

## Phase 3: User Story 1 — Bundled provenance (Priority: P1) 🎯 MVP

**Goal**: Every bundled sample carries verifiable source/license/attribution; samples with incomplete/unapproved provenance are not seeded/surfaced; provenance is visible to users and carried on display/export/training.

**Independent Test**: Fresh install → every seeded dataset/corpus exposes complete provenance (`origin="bundled"`, approved license); remove a manifest entry → item skipped with recorded refusal; re-seed → provenance unchanged, no duplicate audit.

### Tests for User Story 1 (write first, must fail)

- [ ] T026 [P] [US1] Unit test: provenance manifest schema validation — every key maps to a bundled path, every `license` resolves to an approved catalog identifier, attribution-required licenses have non-empty attribution (T-M1/M2/M4) in `tests/unit/services/governance/test_provenance_manifest.py`.
- [ ] T027 [P] [US1] Integration test: bootstrap-with-provenance — seeded items have complete provenance + `origin="bundled"`; invalid/removed manifest entry skipped with recorded refusal (FR-003, T-M3); AND re-running bootstrap does NOT overwrite provenance and emits NO duplicate audit entries (Edge case "Duplicate/re-seeding", G4) in `tests/integration/test_bootstrap_provenance.py`.
- [ ] T028 [P] [US1] API test: `GET /v1/datasets` and `GET /v1/corpora` include a `provenance` object (source/license/attribution/origin) per item (FR-005) in `tests/test_api/test_provenance_surfacing.py`.

### Implementation for User Story 1

- [ ] T029 [US1] Add provenance methods to `GovernanceService` — `assign_provenance`, `get_provenance`, `validate_bundled` (enforce VR-P1/P3; raise when attribution-required license has empty attribution) in `anvil/services/governance/governance_service.py` (C-G7/C-G9).
- [ ] T030 [P] [US1] Add provenance field read/write helpers to `DatasetRepository` in `anvil/db/repositories/datasets.py`.
- [ ] T031 [P] [US1] Add provenance field read/write helpers to `CorpusRepository` in `anvil/db/repositories/corpora.py`.
- [ ] T032 [US1] Author the machine-readable manifest `anvil/data/demo/provenance.json` mirroring `anvil/data/demo/README.md` (one entry per bundled corpus dir and `.txt` dataset; verbatim source/license/attribution) per contracts/provenance-manifest.schema.md.
- [ ] T033 [US1] Update `DemoBootstrapService` (`anvil/services/demo/demo_bootstrap.py`) to load `provenance.json` via `importlib.resources`, set provenance on each seeded corpus/dataset (replacing bare `description=`), skip + record a refusal audit event (`SEED`/`REJECTED`) for items failing `validate_bundled`, and on re-seed leave existing provenance unchanged without emitting duplicate audit (idempotent, G4).
- [ ] T034 [US1] Surface provenance in API list/detail responses via the God Class: add a `provenance` object to dataset and corpus serializers/schemas in `anvil/api/v1/datasets.py`, `anvil/api/v1/corpora.py`, and `anvil/api/v1/schemas.py` (FR-005).
- [ ] T035 [US1] Display per-row source/license/attribution (+ `origin` badge) in `anvil/api/templates/datasets.html` using design tokens (Article VIII).
- [ ] T036 [P] [US1] Carry attribution beyond display (FR-006): include required attribution when exporting (`anvil/services/datasets/dataset_export.py`) and when loading docs for training (`DatasetService.load_docs` / corpus load path), with a unit test in `tests/unit/services/test_attribution_carry.py` (G2).

**Checkpoint**: US1 independently functional — provenance seeded, enforced, visible, and carried (MVP).

---

## Phase 4: User Story 2 — Auditable lifecycle (Priority: P1)

**Goal**: Every consequential action (seed, upload, import, curate, delete, takedown, policy decision) produces a durable, hash-chained, queryable audit entry; failure to audit surfaces (rolls back); a per-dataset governance report composes provenance + audit history.

**Independent Test**: Representative actions → each yields an ordered audit entry retrievable via the audit API; `verify` valid; tampering detected; per-dataset report returns provenance + full audit history in one response.

### Tests for User Story 2 (write first, must fail)

- [ ] T037 [P] [US2] Integration test: upload/import/delete each produce an audit entry with action/target/actor/outcome/reason; audit-write failure rolls back the action (FR-008/FR-011, T-A6) in `tests/integration/test_audit_lifecycle.py`.
- [ ] T038 [P] [US2] API test: `GET /v1/governance/audit` chronological + filterable (FR-012); `GET /v1/governance/audit/verify` returns `{valid, break_at_sequence, entries_checked}` (SC-009) in `tests/test_api/test_audit_endpoints.py`.
- [ ] T039 [P] [US2] Integration test: a curation operation (dedup/filter/edit/remove) produces a `CURATE` audit entry with operation type, target, parameters, before/after counts (FR-008, US2 AS#3, G1) in `tests/integration/test_curation_audit.py`.
- [ ] T040 [P] [US2] API test: `GET /v1/governance/datasets/{id}/report` returns the dataset's provenance plus its complete chronological audit history in one response (SC-007, G3) in `tests/test_api/test_governance_report.py`.

### Implementation for User Story 2

- [ ] T041 [US2] Wire `AuditService.record` into dataset deletion in `anvil/services/datasets/datasets.py` `delete_dataset` (action `DELETE`), replacing the fire-and-forget TrackingService hook; audit write shares the action's session and raises on failure (FR-011).
- [ ] T042 [US2] Wire `AuditService.record` into the upload and import routes via the God Class in `anvil/api/v1/datasets.py` (actions `UPLOAD`/`IMPORT`, outcome `SUCCESS`), within the request session.
- [ ] T043 [US2] Wire `AuditService.record` into demo seeding success path in `anvil/services/demo/demo_bootstrap.py` (action `SEED`, `actor="system:bootstrap"`) — complements refusals from T033.
- [ ] T044 [US2] Wire `AuditService.record` into curation operations in `anvil/services/datasets/dataset_curation.py` (action `CURATE`, params + before/after counts) (FR-008, G1).
- [ ] T045 [P] [US2] Add governance audit Pydantic schemas (`AuditEventOut`, `ChainVerifyOut`, `DatasetGovernanceReportOut`) to `anvil/api/v1/schemas.py`.
- [ ] T046 [US2] Create the governance router with `GET /v1/governance/audit` (filter target_type/target_id/action_type, limit/offset) and `GET /v1/governance/audit/verify` in `anvil/api/v1/governance.py`; register in `anvil/api/v1/router.py`. Calls the God Class.
- [ ] T047 [US2] Add `GET /v1/governance/datasets/{id}/report` (composes `workbench.governance.get_provenance` + `workbench.audit.list_events(target_type=DATASET, target_id=id)`) to `anvil/api/v1/governance.py` (SC-007, G3).

**Checkpoint**: US2 independently functional — all lifecycle actions (incl. curation) audited; trail queryable, verifiable, and reportable per dataset.

---

## Phase 5: User Story 3 — Acceptable-use gate (Priority: P1)

**Goal**: All data entering via upload/import/paste must declare source + license + no-harm affirmation before acceptance; rejections are clear, respectful, audited; `own-content` accepted without an approved redistribution license.

**Independent Test**: Upload without affirmation → 422 + reject audit; declared-prohibited → 422; compliant own-content → accepted, provenance stored, accept audit.

### Tests for User Story 3 (write first, must fail)

- [ ] T048 [P] [US3] Unit test: `evaluate_submission` rejects each missing field with a clear reason, accepts compliant submission, accepts `own-content` without approved-license membership, records exactly one `POLICY_ACCEPT`/`POLICY_REJECT` per evaluation (T-G1/G2/G3, FR-014/FR-016, SC-008) in `tests/unit/services/governance/test_gate.py`.
- [ ] T049 [P] [US3] API test: `POST /v1/datasets/upload` and `POST /v1/datasets/{id}/import` reject non-compliant submissions with 422 (no dataset/samples created) and accept compliant ones (FR-015) in `tests/test_api/test_upload_gate.py`.

### Implementation for User Story 3

- [ ] T050 [US3] Add `evaluate_submission` to `GovernanceService` (declaration/affirmation-only; no content scanning; records audit decision) in `anvil/services/governance/governance_service.py` (C-G3–C-G6).
- [ ] T051 [P] [US3] Add gate request schemas (`UploadGateFields`; extend `ImportBody` with `declared_source`, `license`, `acceptable_use_affirmed`) in `anvil/api/v1/schemas.py`.
- [ ] T052 [US3] Enforce the gate in `POST /v1/datasets/upload` via `workbench.governance.evaluate_submission` before creating the `Dataset`; reject → 422 `{"data": null, "error": reason}`; accept → assign provenance `origin="user"`, in `anvil/api/v1/datasets.py`.
- [ ] T053 [US3] Enforce the gate in `POST /v1/datasets/{id}/import` (and the paste path) before `commit_import`, in `anvil/api/v1/datasets.py` / `anvil/services/datasets/dataset_import.py`.
- [ ] T054 [P] [US3] Add `GET /v1/governance/licenses` (catalog for UI select, FR-005) to `anvil/api/v1/governance.py`.
- [ ] T055 [US3] Add upload-form gate fields (declared-source input, license `<select>` from catalog, no-harm affirmation checkbox + policy link) to `anvil/api/templates/datasets.html` using design tokens; pass the license list as context from `/v1/datasets-page` in `anvil/api/v1/router.py`.

**Checkpoint**: US3 independently functional — no data enters without a recorded provenance declaration + acceptable-use decision.

---

## Phase 6: User Story 4 — No-harm stance, takedown & artifact cleanup (Priority: P2)

**Goal**: Publish a discoverable universal no-harm policy; support takedown; deletion/takedown removes stored artifacts (zero orphans); derived data carries provenance forward.

**Independent Test**: Locate the policy page in ≤2 clicks; delete a dataset → zero orphaned artifacts + delete audit; takedown removes record + artifacts + audit.

### Tests for User Story 4 (write first, must fail)

- [ ] T056 [P] [US4] Integration test: deleting a dataset removes all sample artifacts under `data/datasets/{id}/` (zero orphans, SC-005) and records a `DELETE` audit event in `tests/integration/test_delete_cleanup.py`.
- [ ] T057 [P] [US4] API test: `POST /v1/datasets/{id}/takedown` removes record + artifacts + records `TAKEDOWN`; demo guard (`force`) preserved (FR-021/FR-022) in `tests/test_api/test_takedown.py`.
- [ ] T058 [P] [US4] Unit test: provenance carry-forward on clone/fork copies parent provenance and sets `parent_provenance_ref` (FR-007, T-G7) in `tests/unit/services/governance/test_carry_forward.py`.
- [ ] T059 [P] [US4] API test: `GET /v1/acceptable-use` renders the policy page stating the universal no-harm stance applies to bundled data, user data, and system usage, reachable via global nav (FR-018, SC-006) in `tests/test_api/test_policy_page.py`.

### Implementation for User Story 4

- [ ] T060 [US4] Add artifact cleanup to `delete_dataset` in `anvil/services/datasets/datasets.py`: enumerate `Sample.file_path` artifacts and `LocalFileStore.delete(...)` each, plus sweep the `{dataset_id}/` directory, before deleting DB rows (SC-005); preserve referencing-config and demo guards.
- [ ] T061 [US4] Add `takedown` to `GovernanceService` (delegates artifact removal to the `delete_dataset` cleanup path; records `TAKEDOWN`; preserves demo guard) in `anvil/services/governance/governance_service.py` (C-G10/C-G11).
- [ ] T062 [US4] Add `POST /v1/datasets/{id}/takedown` (body `TakedownBody{reason}`) to `anvil/api/v1/governance.py` (via God Class) and register the route; add `TakedownBody` to `anvil/api/v1/schemas.py`.
- [ ] T063 [US4] Implement provenance carry-forward in the dataset clone and corpus fork paths (`anvil/services/datasets/datasets.py` / `anvil/services/datasets/corpora.py`) via `GovernanceService` (FR-007).
- [ ] T064 [P] [US4] Create the acceptable-use / no-harm policy page `anvil/api/templates/acceptable_use.html` (design tokens) stating prohibited uses and the universal stance (FR-018/FR-019).
- [ ] T065 [US4] Add `GET /v1/acceptable-use` route rendering `acceptable_use.html` in `anvil/api/v1/router.py`, and link it from the global nav and the upload form so it is reachable in ≤2 clicks (FR-017, SC-006).

**Checkpoint**: All four user stories independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, governance records, and full validation.

- [x] T066 [P] Write `docs/vault/Decisions/ADR-023-responsible-data-governance.md` (provenance + hash-chained audit + acceptable-use gate + **the Article VII God-Class refactor rationale**; note ADR-019–022 already taken) using the vault ADR template; controlled-vocabulary tags, resolving wikilinks.
- [x] T067 [P] Add a governance/provenance note to `anvil/data/demo/README.md` (provenance.json is the enforced source-of-truth) and a brief governance section to `README.md`.
- [x] T068 [P] Add a vault session log `docs/vault/Sessions/2026-06-19-responsible-data-governance.md` per the vault enrichment protocol; run `make vault-audit` (must report 0 errors).
- [x] T069 Execute the `quickstart.md` validation end-to-end (steps 1–7) and fix any gaps.
- [x] T070 Run `make lint && make typecheck && make test` — resolve all issues; confirm `mypy --strict` clean (no suppressions, no `TYPE_CHECKING`) and 100% coverage including all new suites.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup. The God-Class refactor (T004–T006) is a structural prerequisite committed on its own (Article X §10.9) before behavioral work; the remaining foundational items (StrEnums, license catalog, audit core, migration) BLOCK all user stories.
- **User Stories (Phase 3–6)**: all depend on Foundational. US1 and US2 are mutually independent after Foundational; US3 consumes license catalog + audit + gate; US4 consumes the delete path + audit. Each is independently testable.
- **Polish (Phase 7)**: after the desired stories are complete.

### Within Each Story

- Tests first (must fail) → models → repositories → services → endpoints → UI/integration.
- Same-file note: `GovernanceService` (`governance_service.py`) is extended across Foundational/US1/US3/US4 — those edits are sequential (not `[P]`).

### Parallel Opportunities

- Setup: T001, T002 in parallel.
- Foundational: God-Class refactor T004→T005→T006 sequential; then T007–T015 (enums, result types, models) all `[P]`; T016 migration; T017/T018 `[P]`; T019/T020 tests `[P]` before T021–T025.
- US1 tests T026–T028 `[P]`; repo helpers T030/T031 `[P]`; export/training carry T036 `[P]`.
- US2 tests T037–T040 `[P]`.
- US3 tests T048/T049 `[P]`.
- US4 tests T056–T059 `[P]`.
- Polish T066–T068 `[P]`.

---

## Parallel Example: Foundational StrEnums + models

```bash
# After the God-Class refactor (T004–T006), launch the independent foundational files together:
Task: "Create DataOrigin StrEnum in anvil/services/governance/data_origin.py"        # T007
Task: "Create AuditAction StrEnum in anvil/services/governance/audit_action.py"      # T008
Task: "Create AuditTargetType StrEnum in anvil/services/governance/audit_target_type.py"  # T009
Task: "Create AuditOutcome StrEnum in anvil/services/governance/audit_outcome.py"    # T010
Task: "Create LicenseEntry model in anvil/db/models/license_entry.py"                # T014
Task: "Create AuditEvent model in anvil/db/models/audit_event.py"                    # T015
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → 2. Phase 2 Foundational (God-Class refactor + audit/license core) → 3. Phase 3 US1 → **STOP & VALIDATE** provenance independently → demo.

### Incremental Delivery

1. Setup + Foundational → compliant foundation ready.
2. US1 (provenance) → MVP.
3. US2 (audit) → auditability.
4. US3 (gate) → enforced no-harm on ingress.
5. US4 (takedown + policy + artifact cleanup) → remediation + published stance.
6. Polish → ADR, docs, full gates.

### TDD discipline

- Every phase: write the listed tests first, confirm they fail, then implement to green, then refactor.
- Never suppress type errors; never delete failing tests to pass.

---

## Notes

- `[P]` = different files, no incomplete dependencies.
- `[Story]` maps each task to a user story for traceability.
- **Article VII**: all DB-backed services are reached via `workbench.<service>` (the `get_workbench` dependency), never constructed inline in routes.
- The God-Class refactor (T004–T006) is structural-only with zero behavioral delta and SHOULD be its own commit (Article X §10.9).
- Audit writes share the action's DB session and raise on failure (FR-011) — do NOT replicate the fire-and-forget `TrackingService` pattern.
- Migration `down_revision` must be the live alembic head (resolve via `make db-revision` autogenerate, then hand-edit).
- Commit after each task or logical group (only when the user requests a commit).
