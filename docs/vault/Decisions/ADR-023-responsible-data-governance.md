---
title: "ADR-023: Responsible Data Governance — Provenance, Hash-Chained Audit, and Acceptable-Use Gate"
type: decision
tags:
- type/decision
- domain/governance
- domain/architecture
created: 2026-06-19
updated: 2026-06-19
aliases:
- ADR-023
- responsible-data-governance
source: speckit
code-refs:
- anvil/workbench.py
- anvil/services/governance/audit_service.py
- anvil/services/governance/governance_service.py
- anvil/db/models/audit_event.py
- anvil/data/demo/provenance.json
---
# ADR-023: Responsible Data Governance — Provenance, Hash-Chained Audit, and Acceptable-Use Gate

## Status

**Accepted**

## Context

The anvil workbench ships bundled sample data (literary public-domain texts, permissively-licensed name lists, and project-generated content) and allows users to upload, import, and paste arbitrary data for training. Prior to this feature, bundled data had **no machine-readable provenance** — license and source info existed only in a human-readable `README.md` table. User uploads had **no content policy gate**, and deletions **orphaned stored file artifacts**. Lifecycle events were tracked via fire-and-forget MLflow runs that silently dropped errors.

The project required lawful, ethical, respectful data inclusion with auditability, plus a universal no-harm stance applying equally to bundled data, user data, and system usage.

## Decision

We introduce a governance layer across four axes:

### 1. Provenance
- Bundled sample data carries a `provenance.json` manifest (machine-readable, shipped in the wheel) with source, license identifier, and attribution per item.
- The `Dataset` and `Corpus` ORM models gain five provenance columns (`source_description`, `license_id` FK to `license_catalog`, `attribution_text`, `origin` (bundled/user), `parent_provenance_ref`).
- A `license_catalog` table stores approved licenses (broad OSI/CC set seeded at app startup: Public Domain, CC0, MIT, BSD, Apache-2.0, CC-BY, CC-BY-SA, Generated/Original, plus an `own-content` sentinel for user data).
- `DemoBootstrapService` validates each item against the manifest; invalid items are skipped with a recorded refusal.

### 2. Hash-Chained Audit Trail
- An `audit_events` table captures every consequential lifecycle event (seed, upload, import, curate, delete, takedown, policy decision).
- Each entry stores a SHA-256 hash (`entry_hash`) computed over the canonical-JSON serialisation of the entry **including** the `prev_hash` of the prior entry. Genesis uses 64 zeros as `prev_hash`.
- The `AuditService` raises on write failure (FR-011) — deliberately diverging from the existing `TrackingService` fire-and-forget pattern.
- Integrity verification recomputes every entry's hash and checks `prev_hash` linkage, returning `valid: bool` and the first `break_at_sequence` (SC-009).

### 3. Acceptable-Use Gate
- `POST /datasets/upload` and `POST /datasets/{id}/import` require `declared_source`, `license` (approved license or `own-content`), and `acceptable_use_affirmed=true`.
- The gate is **declaration/affirmation-only** — no automated content scanning (keyword, PII, or ML).
- Rejections return HTTP 422 with a clear, respectful explanation (SC-008).
- Accept/reject decisions are recorded in the audit trail (FR-016).

### 4. Article VII God-Class Compliance
- `AnvilWorkbench` was refactored from a trivially thin wrapper (only `TrainingService`) into a **session-bound God Class** exposing all DB-backed services as lazy accessors: `datasets`, `corpora`, `dataset_import`, `dataset_curation`, `dataset_export`, `demo`, `audit`, `governance`.
- A `get_workbench` FastAPI dependency provides a request-scoped workbench bound to the request's async session.
- Routes/CLI/tests obtain services as `workbench.<service>` — never by constructing repositories/services inline. This brings the codebase into literal compliance with Constitution Article VII.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                 AnvilWorkbench                      │
│  (session-bound God Class — Article VII)            │
├─────────────────────────────────────────────────────┤
│  datasets │ corpora │ audit │ governance │ demo ... │
└─────────────────────────────────────────────────────┘
        │          │        │         │
        ▼          ▼        ▼         ▼
  ┌──────────┐ ┌──────┐ ┌────────┐ ┌──────────┐
  │DatasetSvc│ │Corpus│ │AuditSvc│ │Governance│
  │          │ │Svc   │ │sha256  │ │Svc       │
  │delete()  │ │fork()│ │chain   │ │gate()    │
  │cleanup   │ │      │ │verify()│ │catalog() │
  └──────────┘ └──────┘ └────────┘ └──────────┘
       │            │         │           │
       ▼            ▼         ▼           ▼
  ┌──────────────────────────────────────────┐
  │           SQLite (async SQLAlchemy)       │
  │  datasets  corpora  audit_events  license │
  │  .source_  .source_ (hash-       _catalog │
  │  desc.     desc.   chained)              │
  └──────────────────────────────────────────┘
```

### Key files

| File | Role |
|---|---|
| `anvil/workbench.py` | Session-bound AnvilWorkbench God Class |
| `anvil/api/deps.py` | `get_workbench` FastAPI dependency |
| `anvil/services/governance/` | Domain sub-package: audit, gate, provenance |
| `anvil/db/models/audit_event.py` | Hash-chained audit ORM model |
| `anvil/db/models/license_entry.py` | Approved-license catalog ORM model |
| `anvil/db/models/dataset.py` | Dataset model (+ provenance columns) |
| `anvil/db/models/corpus.py` | Corpus model (+ provenance columns) |
| `anvil/db/repositories/audit_events.py` | Append-only audit repository |
| `anvil/db/repositories/licenses.py` | License catalog repository |
| `anvil/services/governance/audit_service.py` | `AuditService` (sha256 chain, verify) |
| `anvil/services/governance/governance_service.py` | `GovernanceService` (gate, catalog, provenance) |
| `anvil/services/governance/license_seed.py` | Broad OSI/CC license seed data |
| `anvil/_resources/migrations/versions/014_add_governance.py` | Alembic migration |
| `anvil/data/demo/provenance.json` | Bundled provenance manifest |

### Conventions applied

- **StrEnum over magic strings** (Principle 11): `DataOrigin`, `AuditAction`, `AuditTargetType`, `AuditOutcome`
- **Pydantic `BaseModel` over `dataclass`** (ADR-019): `GateDecision`, `ChainVerifyResult`, `ProvenanceView`
- **One class per file** (ADR-020): each enum, result type, ORM model, and service gets its own module
- **`__init__.py` Ownership Policy** (Article VI): bare docstring-only `__init__.py` at `anvil/services/governance/`
- **Domain-Driven Package Decomposition** (Article X): governance is a new bounded context at `anvil/services/governance/`

## Consequences

### Easier
- **Auditability**: Any dataset's full lifecycle is reconstructable from the verifiable audit trail (SC-003, SC-007).
- **Legal compliance**: Bundled data has machine-readable provenance; redistribution is restricted to the approved-license list.
- **No-harm enforcement**: Every data submission requires an actionable affirmation; rejections are recorded.
- **Architecture consistency**: All services flow through the God Class (Article VII compliance).
- **Tamper detection**: Hash-chain verification detects any insertion, mutation, or removal (SC-009).

### Harder
- **Larger migration surface**: The God-Class refactor (T004–T006) required migrating 44 call sites across `datasets.py` and `corpora.py`.
- **New concepts for users**: Upload/import now require license and affirmation fields.
- **Test scope**: Audit-chain integrity requires deterministic DB-agnostic tests.

## Compliance

- Provenance verification: `GovernanceService.validate_bundled()` is tested in `test_license_seed.py`.
- Hash-chain integrity: `AuditService.verify_chain()` tests in `test_audit_service.py` (genesis, chaining, mutation detection).
- Gate enforcement: `GovernanceService.evaluate_submission()` unit tests in `test_gate.py` + API tests in `test_upload_gate.py`.
- Article VII: all route handlers use `workbench: AnvilWorkbench = Depends(get_workbench)`, verified by import grep.
- `make lint && make typecheck && make test` must pass (CI merge gate).