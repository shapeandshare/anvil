# Implementation Plan: Responsible Sample Data & Universal No-Harm Governance

**Branch**: `013-responsible-data-governance` | **Date**: 2026-06-19 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/013-responsible-data-governance/spec.md`
**Rebased onto**: `origin/main` @ `581b832` (domain-decomposition refactor #74/#75; Constitution **v1.6.0**). All file paths and conventions below reflect the post-refactor codebase. See `research.md` R11 for the rebase-impact analysis.

## Summary

Add lawful/ethical/auditable governance to the anvil workbench across two surfaces: (1) **bundled sample data** must carry machine-readable provenance (source, license, attribution) drawn from a maintainer-curated approved-license catalog, and (2) **all data entering the system** (and consequential lifecycle actions) must pass an acceptable-use ("no-harm") gate and be recorded in a tamper-evident, hash-chained, indefinitely-retained audit trail. Deletion/takedown must remove stored artifacts (closing an existing orphan defect).

**Technical approach**: Follow the existing layered architecture (Repository → Service → God Class → Routes). Add three new SQLAlchemy ORM models (`AuditEvent`, `LicenseEntry`, and an embeddable provenance via columns on `Dataset`/`Corpus`), three repositories, two new services (`AuditService` with hash-chaining, `GovernanceService` for the acceptable-use gate + license catalog + provenance), a machine-readable `provenance.json` manifest beside the demo data, an Alembic migration, upload-gate enforcement, dataset-delete artifact cleanup, and minimal UI surfacing on the datasets page. A static acceptable-use policy page is added. The `AuditService` deliberately does NOT follow the fire-and-forget pattern of `TrackingService` — audit-write failure is surfaced (FR-011).

## Technical Context

**Language/Version**: Python 3.11+ (`requires-python = ">=3.11"`)
**Primary Dependencies**: FastAPI, SQLAlchemy[asyncio] >=2.0, aiosqlite, Alembic >=1.13, Jinja2, pytest + httpx (test). **No new runtime dependencies** — hash-chaining uses stdlib `hashlib`; provenance manifest uses stdlib `json`; license catalog seeded from code.
**Storage**: SQLite via async SQLAlchemy (`data/anvil-state.db`) for app metadata (provenance columns, `audit_events`, `license_catalog`); local filesystem via existing `LocalFileStore("data/datasets")` for sample artifacts. Bundled demo provenance manifest is a packaged read-only resource under `anvil/data/demo/provenance.json`.
**Testing**: pytest (unit + integration + contract); 100% coverage required (Constitution Article IV). Async tests via existing harness.
**Target Platform**: Local/self-hosted Linux/macOS web server (single-tenant workbench).
**Project Type**: Web service (FastAPI backend + Jinja2 server-rendered UI). Single project layout.
**Performance Goals**: Audit-write adds negligible latency to lifecycle actions; full audit-chain integrity verification over the entire trail completes in under 5 seconds for the expected local-workbench volume (thousands of entries). Not a hot path.
**Constraints** (Constitution v1.6.0): `mypy --strict` (no `# type: ignore`, no `Any` abuse); **`TYPE_CHECKING` forbidden** (extract shared types into dedicated modules); **`__init__.py` Ownership Policy (Article VI)** — bare docstring-only `__init__.py` at each authoritative package level, NO re-exports, internal imports use direct relative module paths (`from ..x import Y`); **Domain-Driven Package Decomposition (Article X)** — new governance code lives in dedicated domain sub-packages (`anvil/services/governance/`), result/value types co-located one-per-file; **one class per file (ADR-020)**; **Pydantic `BaseModel` over `dataclass` (ADR-019)** for result/value types; **StrEnum over magic strings (AGENTS.md Principle 11)** for all fixed-set values (`origin`, `action_type`, `target_type`, `outcome`); relative imports only (no absolute `anvil.` inside the package); core engine untouched (zero-dependency, sync) — this feature lives entirely in db/services/api layers. Schema changes via reversible Alembic migration. Audit trail retained indefinitely; no auto-pruning (FR-023).
**Scale/Scope**: Single-user local deployment. Bundled demo set is ~6 items. Audit volume grows with user actions but stays small (local). Provenance is one-to-one with each dataset/corpus.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Requirement | Compliance |
|---|---|---|
| I — Zero-Dependency Core | `anvil/core/` stays stdlib-only; new functionality is opt-in layer | **PASS** — feature touches only db/services/api; core untouched. No new runtime deps. |
| II — Educational Clarity | Readability over perf; WHY comments | **PASS** — hash-chaining and gate logic documented with rationale. |
| III — Seeded Reproducibility | Deterministic given seed/config | **PASS (N/A to training)** — governance is deterministic; provenance manifest is fixed input. |
| IV — TDD Mandatory | Tests before impl; 100% coverage; e2e exists | **PASS (planned)** — contract + unit + integration tests authored first; tasks ordered Red-Green-Refactor. |
| V — Async-First | Web/DB/service layers async | **PASS** — `AuditService`, `GovernanceService`, repositories all async; mirror `DatasetService`. |
| VI — `__init__.py` Ownership Policy | Bare docstring-only `__init__.py` at authoritative levels; NO re-exports; internal imports use direct relative module paths | **PASS** — new `anvil/services/governance/__init__.py` is bare; `anvil/db/models/__init__.py` stays bare (NO model re-exports — corrected from earlier draft). Models registered for Alembic via explicit import in the migration env / models-import module, not via `__init__` re-export. All internal imports relative (`from ..x import Y`). |
| VII — Layered Architecture | Repository → Service → **God Class (`AnvilWorkbench`)** → Routes/CLI/tests; no DB leak past repo | **PASS (full compliance via refactor)** — Article VII is enforced literally: `AnvilWorkbench` is refactored into a session-bound God Class exposing ALL DB-backed services (existing `datasets`, `corpora`, `dataset_import`, `dataset_curation`, `demo`, `tracking`, plus new `audit`, `governance`) as accessors. Routes/CLI/tests call the God Class via a `get_workbench` dependency instead of instantiating services directly. The pre-existing direct-DI divergence is corrected. The God Class refactor is a **structural-only change committed separately** (Constitution Article X §10.9 — moves + wiring rewrites, zero behavioral delta) before the governance behavior is layered on. New `AuditEventRepository`/`LicenseRepository` + provenance updates via existing repos; no DB primitives leak past the repository layer. |
| VIII — iOS-Grade Polish | Polished UI via design tokens | **PASS** — datasets-page provenance display + upload-gate form + policy page use `tokens.css`/`components.css` per DESIGN.md; no raw values. |
| IX — Pit of Success | Optional capabilities work without config; default path always works | **PASS** — governance is on-by-default and requires no config. Approved-license catalog seeds automatically. Demo provenance manifest ships in the wheel. |
| X — Domain-Driven Package Decomposition | Package boundaries follow domains; result/value/error types co-locate in the service's domain sub-package; plural-noun domain dirs; max 2 nesting levels | **PASS** — governance is a new bounded context → `anvil/services/governance/` sub-package holding `AuditService`, `GovernanceService`, `license_seed`, and co-located one-class-per-file result/value types (`GateDecision`, `ChainVerifyResult`, `ProvenanceView`, and the StrEnums). DB models follow the established one-file-per-model layout (`audit_event.py`, `license_entry.py`). |
| Additional — StrEnum over magic strings (Principle 11) | Fixed-set values use `StrEnum` | **PASS** — `DataOrigin`, `AuditAction`, `AuditTargetType`, `AuditOutcome` StrEnums; columns store the enum value (mirrors existing `DatasetStatus` usage). |
| Additional — Pydantic over dataclass (ADR-019) | Prefer Pydantic `BaseModel` | **PASS** — service result/value types are Pydantic `BaseModel`. |
| Additional — Alembic reversible | Reversible migration; backfill accompanies change | **PASS** — single migration `014_add_governance.py` (next after head `013` + merge head) with full `upgrade()`/`downgrade()`; data backfill for existing demo + user rows' provenance. |
| Additional — mypy strict / no TYPE_CHECKING | No suppression; no `TYPE_CHECKING` | **PASS** — strict typing on all new signatures; shared types extracted into dedicated modules instead of `TYPE_CHECKING` guards. |
| Additional — ADR for decisions | Significant decisions → ADR | **PASS (planned)** — **ADR-023** (responsible-data-governance: provenance + hash-chained audit). Renumbered from earlier "ADR-019" draft because ADR-019–022 are now taken on main. |

**Gate result: PASS.** No violations against Constitution v1.6.0. Complexity Tracking section omitted (no justified deviations).

One governance note for `/speckit.tasks`: the spec's "universal no-harm stance applies to the system itself" (FR-018) is satisfied by a documented Acceptable-Use Policy + the enforcement gate; it does NOT require a new Constitution article, but an ADR records the decision. If maintainers later want it as a binding principle, that is a separate constitution amendment (out of scope here).

## Project Structure

### Documentation (this feature)

```text
specs/013-responsible-data-governance/
├── plan.md              # This file (/speckit.plan command output)
├── spec.md              # Feature spec (with Clarifications)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── audit-service.md
│   ├── governance-service.md
│   ├── provenance-manifest.schema.md
│   └── api-endpoints.md
├── checklists/
│   └── requirements.md  # Spec quality checklist (already present)
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
anvil/
├── db/
│   ├── base.py                       # (unchanged) DeclarativeBase
│   ├── timestamp_mixin.py            # (unchanged) TimestampMixin — import from here
│   ├── models/                       # bare __init__.py (one class per file)
│   │   ├── audit_event.py            # NEW: AuditEvent (hash-chained)
│   │   ├── license_entry.py          # NEW: LicenseEntry (approved-license catalog)
│   │   ├── dataset.py                # MODIFY (via migration only): Dataset provenance columns
│   │   └── corpus.py                 # MODIFY (via migration only): Corpus provenance columns
│   ├── repositories/                 # bare __init__.py
│   │   ├── audit_events.py           # NEW: AuditEventRepository (append + chain-tail read + ordered scan)
│   │   ├── licenses.py               # NEW: LicenseRepository (catalog seed + lookup)
│   │   └── datasets.py / corpora.py  # MODIFY: provenance field updates
│   └── _resources/migrations/versions/014_add_governance.py  # NEW (next after head 013 + merge head)
├── services/
│   ├── governance/                   # NEW domain sub-package (Article X), bare __init__.py
│   │   ├── audit_service.py          # NEW: AuditService (hash-chain; surfaces write failure)
│   │   ├── governance_service.py     # NEW: GovernanceService (gate, license catalog, provenance, takedown)
│   │   ├── license_seed.py           # NEW: seed data for approved-license catalog (broad OSI/CC set)
│   │   ├── data_origin.py            # NEW: DataOrigin(StrEnum) {bundled, user}
│   │   ├── audit_action.py           # NEW: AuditAction(StrEnum)
│   │   ├── audit_target_type.py      # NEW: AuditTargetType(StrEnum)
│   │   ├── audit_outcome.py          # NEW: AuditOutcome(StrEnum)
│   │   ├── gate_decision.py          # NEW: GateDecision (Pydantic BaseModel)
│   │   ├── chain_verify_result.py    # NEW: ChainVerifyResult (Pydantic BaseModel)
│   │   └── provenance_view.py        # NEW: ProvenanceView (Pydantic BaseModel)
│   ├── datasets/
│   │   ├── datasets.py               # MODIFY: delete_dataset removes artifacts; provenance carry-forward on clone
│   │   └── dataset_import.py         # MODIFY: gate enforcement on import/paste path
│   └── demo/
│       └── demo_bootstrap.py         # MODIFY: read provenance.json; set provenance on seeded items; record audit refusals
├── cli.py                            # MODIFY (Art. VII): refactor AnvilWorkbench → session-bound God Class exposing ALL DB-backed services + new audit/governance
├── api/
│   ├── deps.py                       # MODIFY: add `get_workbench` dependency (session-bound AnvilWorkbench)
│   ├── v1/
│   │   ├── governance.py             # NEW: audit query/verify + licenses + takedown + per-dataset governance report endpoints
│   │   ├── schemas.py                # MODIFY: add governance Pydantic request/response schemas (centralized here on main)
│   │   ├── datasets.py               # MODIFY: call God Class; upload/import gate; provenance in responses; delete artifact cleanup
│   │   ├── corpora.py                # MODIFY: call God Class; provenance in responses
│   │   └── router.py                 # MODIFY: register governance routes; acceptable-use policy page route
│   └── templates/
│       ├── datasets.html             # MODIFY: provenance display + upload-gate fields (declared source/license/affirmation)
│       └── acceptable_use.html       # NEW: published no-harm / acceptable-use policy page
└── data/demo/
    └── provenance.json               # NEW: machine-readable manifest (mirrors README license table)

tests/
├── test_api/     # API route tests (gate reject/accept, audit endpoints, delete cleanup)
├── integration/  # bootstrap-with-provenance, upload-gate, delete-artifact-cleanup, audit-verify
└── unit/         # hash-chain correctness, license lookup, provenance carry-forward, StrEnum/manifest schema

docs/vault/Decisions/
└── ADR-023-responsible-data-governance.md   # NEW (019–022 already taken)

docs/vault/Sessions/   # session log enrichment per AGENTS.md vault protocol
```

**God Class compliance (Article VII)**: `AnvilWorkbench` is refactored into a **session-bound God Class**. It exposes every DB-backed service as a lazy accessor; a FastAPI dependency `get_workbench(session=Depends(get_db_session))` yields a request-scoped workbench, and routes/CLI/tests obtain services as `workbench.<service>` rather than constructing repositories/services inline. Stateless services (e.g. `training`) remain accessible without a session. This refactor is performed **structurally and committed on its own** (Article X §10.9: pure moves + import/wiring rewrites, zero behavioral delta) ahead of the governance feature work, so the behavioral tasks build on a compliant layering.

**Structure Decision**: Single-project web-service layout matching the post-refactor anvil package. Governance is treated as a **new bounded context** and gets its own `anvil/services/governance/` domain sub-package per Constitution Article X, with result/value/enum types co-located **one class per file** (ADR-020) and result types as **Pydantic `BaseModel`** (ADR-019). New ORM models follow the established one-file-per-model layout (`audit_event.py`, `license_entry.py`) using `Base` + `TimestampMixin` (imported from `anvil/db/timestamp_mixin.py`) + `Mapped[]`/`mapped_column()`. Fixed-set columns use **StrEnum** (mirroring `DatasetStatus`), not magic strings. `__init__.py` files stay **bare** (Article VI) — models are made visible to Alembic autogenerate via an explicit models-import (in the migration env or a dedicated import module), NOT via `__init__` re-exports. Repositories take `session: AsyncSession` and are `async`. Provenance is added as columns on `Dataset`/`Corpus` (1:1) with a `license_id` FK into `license_catalog`. HTTP request/response schemas go in `anvil/api/v1/schemas.py` (centralized on main).

## Complexity Tracking

> No Constitution Check violations — section intentionally empty.
