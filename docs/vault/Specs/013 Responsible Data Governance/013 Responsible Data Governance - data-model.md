---
title: 013 Responsible Data Governance - data-model
type: data-model
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/013 Responsible Data Governance/
related:
  - '[[013 Responsible Data Governance]]'
created: ~
updated: ~
---
# Phase 1 Data Model: Responsible Sample Data & Universal No-Harm Governance

**Feature**: `010-responsible-data-governance` | **Date**: 2026-06-19

All models are SQLAlchemy **declarative** (`Base` from `anvil/db/base.py` + `TimestampMixin` from `anvil/db/timestamp_mixin.py` + `Mapped[]` / `mapped_column()`), matching the post-refactor convention in `anvil/db/models/` (one class per file, ADR-020). Pydantic `BaseModel` is used for HTTP request/response bodies (in `anvil/api/v1/schemas.py`) and for service result/value types (ADR-019) — never for ORM rows. **`anvil/db/models/__init__.py` stays bare (Article VI) — new models are NOT re-exported there**; Alembic autogenerate sees them via `Base.metadata` populated by an explicit models import (migration env / dedicated import module). Fixed-set columns store **StrEnum** values (AGENTS.md Principle 11), mirroring `Dataset.status` → `DatasetStatus`. Schema is applied via one reversible Alembic migration (`014_add_governance.py`).

### StrEnums (one class per file, in `anvil/services/governance/`)

| Enum | Members (value) | Used by |
|---|---|---|
| `DataOrigin` (`data_origin.py`) | `BUNDLED="bundled"`, `USER="user"` | `Dataset.origin`, `Corpus.origin` |
| `AuditAction` (`audit_action.py`) | `SEED`, `UPLOAD`, `IMPORT`, `CURATE`, `DELETE`, `TAKEDOWN`, `POLICY_ACCEPT`, `POLICY_REJECT`, `CHAIN_CHECKPOINT` (snake_case values) | `AuditEvent.action_type` |
| `AuditTargetType` (`audit_target_type.py`) | `DATASET`, `CORPUS`, `SAMPLE`, `POLICY`, `AUDIT_CHAIN` | `AuditEvent.target_type` |
| `AuditOutcome` (`audit_outcome.py`) | `SUCCESS`, `REJECTED`, `ERROR` | `AuditEvent.outcome` |

Columns are typed `Mapped[str]` with `mapped_column(String(N), default=<Enum>.<MEMBER>)` and assigned/compared using the enum members (never raw string literals).

---

## 1. `LicenseEntry` — approved-license catalog (NEW table `license_catalog`)

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `id` | int | PK, autoincrement | |
| `identifier` | str(100) | unique, not null | e.g. `MIT`, `CC-BY-4.0`, `Public Domain`, `Generated/Original`, `own-content` |
| `display_name` | str(255) | not null | Human label |
| `requires_attribution` | bool | not null, default False | Drives FR-006 attribution carry-through |
| `redistribution_allowed` | bool | not null, default True | `own-content` may be False (private, non-redistributable) |
| `is_own_content_sentinel` | bool | not null, default False | True only for the `own-content` row (user-supplied, exempt from approved-list per FR-002/FR-014) |
| `created_at`, `updated_at` | datetime | from `TimestampMixin` | |

**Seed (FR-002, Clarification Q4)** via `anvil/services/governance/license_seed.py`, idempotent by `identifier`:
`Public Domain`, `CC0-1.0`, `MIT`, `BSD-2-Clause`, `BSD-3-Clause`, `Apache-2.0`, `CC-BY-4.0` (requires_attribution=True), `CC-BY-SA-4.0` (requires_attribution=True), `Generated/Original`, and `own-content` (is_own_content_sentinel=True, redistribution_allowed=False).

**Validation rules**:
- VR-L1: `identifier` unique; seeding skips existing identifiers.
- VR-L2: Exactly one row may have `is_own_content_sentinel=True`.

---

## 2. Provenance columns on `Dataset` and `Corpus` (MODIFY existing tables)

Added to **both** `datasets` and `corpora` via migration (no new table — 1:1 per R1):

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `source_description` | str(1000) | nullable (backfilled) | Where the data came from (FR-001) |
| `license_id` | int | FK → `license_catalog.id`, nullable (backfilled), `ondelete="RESTRICT"` | The governing license / own-content sentinel |
| `attribution_text` | str(1000) | nullable | Required attribution (may be empty when license requires none) |
| `origin` | str(20) | not null, default `"user"` | `"bundled"` or `"user"` (FR-001 classification) |
| `parent_provenance_ref` | int | nullable | Id of parent dataset/corpus when derived (FR-007) |

**Validation rules**:
- VR-P1 (bundled, FR-003): when `origin="bundled"`, `license_id` MUST reference a catalog row whose `is_own_content_sentinel=False`; otherwise the item is not seeded/surfaced and a refusal is recorded.
- VR-P2 (user, FR-014): when `origin="user"`, `license_id` MUST be set to either an approved license or the `own-content` sentinel.
- VR-P3 (FR-006): if the referenced license has `requires_attribution=True`, `attribution_text` MUST be non-empty.
- VR-P4 (FR-007): derived entities copy parent provenance and set `parent_provenance_ref = parent.id`.

**Backfill (migration `upgrade()`):** existing demo rows (`name` starts with `"Demo - "`) get `origin="bundled"` and provenance from `provenance.json`; all other existing rows get `origin="user"`, `license_id = own-content sentinel`, `source_description="(pre-governance import)"`. This keeps the migration reversible and avoids null-not-null churn.

---

## 3. `AuditEvent` — hash-chained audit trail (NEW table `audit_events`)

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `id` | int | PK, autoincrement | Monotonic insertion order |
| `sequence` | int | unique, not null, indexed | Explicit chain ordinal (genesis = 1) |
| `action_type` | str(50) | not null, indexed | `seed`, `upload`, `import`, `curate`, `delete`, `takedown`, `policy_accept`, `policy_reject`, `chain_checkpoint` |
| `target_type` | str(50) | not null, indexed | `dataset`, `corpus`, `sample`, `policy`, `audit_chain` |
| `target_id` | str(100) | nullable | Identifier of the target (string to allow non-int targets) |
| `actor` | str(255) | not null | Operating user/session or automated process name (e.g. `system:bootstrap`) |
| `outcome` | str(20) | not null | `success`, `rejected`, `error` |
| `reason` | str(1000) | nullable | Reason/explanation (esp. for rejections) |
| `params_json` | Text | nullable | Canonical JSON of structured params (no full content bodies — FR-013) |
| `event_timestamp` | datetime | not null | Action time (distinct from `created_at`) |
| `prev_hash` | str(64) | not null | Hex sha256 of previous entry; genesis = 64×`0` |
| `entry_hash` | str(64) | unique, not null | Hex sha256 over canonical entry incl. `prev_hash` |
| `created_at`, `updated_at` | datetime | from `TimestampMixin` | |

**Hash definition (R2):**
```
entry_hash = sha256_hex(
  canonical_json({
    "sequence", "action_type", "target_type", "target_id",
    "actor", "outcome", "reason", "params_json",
    "event_timestamp": <ISO-8601 UTC>, "prev_hash"
  })  # keys sorted, separators (",",":"), UTF-8
)
```

**Validation / integrity rules**:
- VR-A1 (FR-010): `prev_hash` of entry N == `entry_hash` of entry N-1; genesis `prev_hash` = 64 zeros.
- VR-A2 (FR-010): recomputing `entry_hash` from stored fields must equal the stored `entry_hash`.
- VR-A3 (FR-023): no update/delete operations are exposed for `audit_events` through services/routes; the only write is append. Archival/reset is itself an appended `chain_checkpoint` event.
- VR-A4 (FR-011): if an append cannot be committed, the surrounding action transaction is rolled back and the failure is surfaced (HTTP 5xx / raised exception) — never silently swallowed.

**State / lifecycle**: append-only. `sequence` strictly increasing. Verification (`AuditService.verify_chain`) returns `valid: bool` and, if invalid, the `break_at_sequence` (SC-009).

---

## 4. Entity relationships

```
license_catalog (1) ──< (N) datasets.license_id      [RESTRICT]
license_catalog (1) ──< (N) corpora.license_id       [RESTRICT]
datasets.parent_provenance_ref ──> datasets.id        (self, derived)
corpora.parent_provenance_ref  ──> corpora.id         (self, derived; complements existing parent_id)
audit_events  (chain) ── prev_hash/entry_hash linkage; target_type+target_id loosely reference dataset/corpus/sample/policy
```

Audit events use a **loose** (string `target_id`) reference rather than hard FKs, so that an audit entry for a deleted/taken-down entity survives the deletion (the audit trail must outlive its targets — FR-008, FR-021).

---

## 5. Request/response Pydantic models (in `anvil/api/v1/schemas.py` — not ORM)

- `UploadGateFields` (multipart form / body): `declared_source: str`, `license: str` (identifier or `own-content`), `acceptable_use_affirmed: bool`.
- `ImportBody` (extend existing): add `declared_source`, `license`, `acceptable_use_affirmed`.
- `ProvenanceOut`: `source_description`, `license`, `attribution`, `origin`.
- `AuditEventOut`: `sequence`, `action_type`, `target_type`, `target_id`, `actor`, `outcome`, `reason`, `event_timestamp`, `entry_hash`.
- `ChainVerifyOut`: `valid: bool`, `break_at_sequence: int | null`, `entries_checked: int`.
- `TakedownBody`: `reason: str`.

All responses keep the existing `{"data": ..., "error": ...}` wrapper.
