---
title: 013 Responsible Data Governance - research
type: research
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/013 Responsible Data Governance/
related:
  - '[[013 Responsible Data Governance]]'
created: ~
updated: ~
---
# Phase 0 Research: Responsible Sample Data & Universal No-Harm Governance

**Feature**: `010-responsible-data-governance` | **Date**: 2026-06-19

All Technical Context unknowns were resolved through two parallel codebase explorations (DB/repo/migration patterns; God-class/service/route/upload-flow patterns) plus the spec's recorded Clarifications. No external library research was required — the feature adds **no new runtime dependencies**. Findings are recorded below in Decision / Rationale / Alternatives form.

---

## R1. Provenance storage shape (columns on Dataset/Corpus vs. separate table)

- **Decision**: Add provenance as **columns directly on `Dataset` and `Corpus`** (`source_description`, `license_id` FK → `license_catalog`, `attribution_text`, `origin` enum-as-string `"bundled" | "user"`, `parent_provenance_ref`), not a separate `provenance` table.
- **Rationale**: Provenance is strictly one-to-one with each dataset/corpus (spec Key Entities). The existing models already carry denormalized scalar fields (`Dataset.status`, `Corpus.file_count`) directly. Columns keep reads single-row, avoid a join on every list view, and match the codebase's existing flat-model convention. The approved-license set is the only thing genuinely shared, so only that is normalized into `license_catalog`.
- **Alternatives considered**:
  - *Separate `provenance` table (1:1)* — rejected: adds a join with no shared-row benefit; inconsistent with existing denormalized fields.
  - *Extend `ImportSource`* — rejected: `ImportSource` is per-import-batch (many per dataset) and corpora have no `ImportSource`; provenance must attach to the dataset/corpus itself.

## R2. Audit model: hash-chaining approach (Clarification Q2 → cryptographic hash-chaining)

- **Decision**: Single `audit_events` table; each row stores `prev_hash` and `entry_hash`. `entry_hash = sha256(canonical_json(action_type, target_type, target_id, timestamp_iso, actor, outcome, params_json, prev_hash))`. The first ever row uses a fixed genesis `prev_hash` (e.g. 64 zeros). Computed with stdlib `hashlib.sha256` over a deterministic, sorted-key JSON serialization.
- **Rationale**: Satisfies FR-010 tamper-evidence with zero new dependencies. Verification recomputes each row's hash and checks `row[i].prev_hash == row[i-1].entry_hash`; any insert/alter/remove breaks the chain at a detectable index (SC-009). Deterministic canonical JSON (sorted keys, no whitespace, UTF-8) makes hashing reproducible.
- **Alternatives considered**:
  - *App-level append-only without chaining* — rejected by Clarification Q2 (user chose cryptographic chaining).
  - *Per-entry digital signatures (asymmetric keys)* — rejected: requires key management not present in a local single-tenant tool; chaining is sufficient against the relevant threat (post-hoc tampering of the local store).
  - *Merkle tree* — rejected: over-engineered for a strictly append-only, linearly-ordered log.

## R3. Audit-write reliability (must NOT mimic TrackingService)

- **Decision**: `AuditService.record(...)` performs the audit write **in the same DB transaction/session as the action being audited where feasible**, and on failure **raises** (surfacing per FR-011) rather than swallowing. The chain tail (`prev_hash`) is read within the same session to avoid races. Audit recording for an action is part of that action's success criteria.
- **Rationale**: The existing `TrackingService.log_*_lifecycle_event` is fire-and-forget (catches all exceptions, sets `_degraded`, returns `""`). Mirroring that would violate FR-008/FR-011 ("surface, not silently swallow"). Co-locating the audit write in the action's session gives atomicity: if audit fails, the action rolls back.
- **Alternatives considered**:
  - *Reuse TrackingService / MLflow runs as the audit log* — rejected: no actor/reason, silent failure, not tamper-evident, not chronologically queryable as a chain.
  - *Async best-effort queue* — rejected: introduces a window where an action succeeds but is unaudited; violates the auditable guarantee.

## R4. Single-writer ordering for the hash chain

- **Decision**: Serialize audit appends so the chain tail is read-then-written atomically. For SQLite (single-writer, WAL) the write transaction already serializes writers; `AuditService.record` reads the current tail and inserts within one transaction, relying on SQLite's write lock to prevent interleaving. A uniqueness constraint on `entry_hash` provides a backstop against duplicate insertion.
- **Rationale**: anvil uses SQLite with WAL (`anvil/db/session.py`). SQLite permits only one writer at a time, which naturally serializes the read-tail/append step. No additional locking primitive is required for the local single-tenant scale.
- **Alternatives considered**:
  - *Application-level mutex/lock* — deferred: unnecessary given SQLite's writer serialization at current scale; can be added if a multi-writer backend is ever introduced (noted for future ADR).

## R5. Machine-readable bundled provenance manifest

- **Decision**: Add `anvil/data/demo/provenance.json` — a JSON object keyed by demo relative path (e.g. `"medium/alice"`, `"presidents.txt"`) with `{ "source": ..., "license": ..., "attribution": ... }`. Bundle it in the wheel via the existing `[tool.setuptools.package-data]` glob (it already includes `data/demo/**/*.md`; add `**/*.json`). `DemoBootstrapService` loads it via `importlib.resources` (same mechanism it already uses to resolve `data/demo`).
- **Rationale**: The demo README license table is currently human-only (FR-004 requires an enforced source-of-truth). A JSON manifest mirroring the README columns is machine-readable, ships read-only in the package, and is resolved with the exact `importlib.resources` pattern the bootstrap already uses. Demo data lives in a read-only installed location, so the manifest (not mutable DB defaults) is the authoritative seed input.
- **Alternatives considered**:
  - *Parse the README markdown table at runtime* — rejected: brittle, formatting-dependent.
  - *Hardcode provenance in `demo_bootstrap.py`* — rejected: mixes data with logic; harder for maintainers to audit/extend than a declarative manifest.

## R6. Approved-license catalog seed (Clarification Q4 → broad OSI/CC set)

- **Decision**: Seed `license_catalog` from a code-defined list in `anvil/services/governance/license_seed.py`: Public Domain, CC0-1.0, MIT, BSD-2-Clause, BSD-3-Clause, Apache-2.0, CC-BY-4.0, CC-BY-SA-4.0, plus a project sentinel `Generated/Original`. Each entry carries `requires_attribution` (true for CC-BY / CC-BY-SA) and `redistribution_allowed=true`. Seeding is idempotent (by license identifier) and runs at startup alongside demo bootstrap.
- **Rationale**: Matches Clarification Q4. Covers all currently-bundled demo licenses (Public Domain, MIT, Generated) plus headroom for future samples. `requires_attribution` flag drives FR-006 attribution carry-through.
- **Alternatives considered**:
  - *Narrow set (only currently-used licenses)* — rejected by Clarification Q4 in favor of broader future-proofing.
  - *External SPDX dataset dependency* — rejected: avoids a new dependency; the curated subset is sufficient and maintainer-extendable.

## R7. Acceptable-use gate placement (Clarification Q3 → affirmation/declaration only)

- **Decision**: Enforce the gate at the two data-entry points: `POST /v1/datasets/upload` and `POST /v1/datasets/{id}/import` (and the paste path that flows through import). The gate requires `declared_source`, `license` (an approved-license id OR the `own-content` sentinel), and `acceptable_use_affirmed=true`. Rejection returns HTTP 422 with the existing `{"data": null, "error": ...}` wrapper shape and a clear message. **No content scanning** — prohibition is by submitter declaration only.
- **Rationale**: Clarification Q1 (own-content category) + Q3 (affirmation-only). The upload route currently bypasses `DatasetService.create_dataset` and builds a `Dataset` inline — the gate is added there and in the import route, the two real ingress points. Reusing the existing response wrapper keeps the API consistent.
- **Alternatives considered**:
  - *Keyword/PII/ML scanning* — rejected by Clarification Q3 (out of scope).
  - *Gate only at upload* — rejected: import/paste are independent ingress paths and must be gated too (FR-014 "all data entering").

## R8. Deletion artifact cleanup (closing the orphan defect)

- **Decision**: Extend `DatasetService.delete_dataset` (and the takedown path) to enumerate the dataset's `Sample.file_path` artifacts and call `LocalFileStore.delete(path)` for each before deleting DB rows, within the same operation, then record a `delete`/`takedown` audit event. The existing demo-protection guard (`force=true` for `"Demo - "` datasets) is preserved (FR-022).
- **Rationale**: Exploration confirmed `delete_dataset` drops the DB row but never calls `store.delete()`, orphaning files (SC-005 = zero orphans). `LocalFileStore.delete(path)` already exists. Sample file paths follow `{dataset_id}/{import_source_id}/{index}.txt`.
- **Alternatives considered**:
  - *Delete the whole `{dataset_id}/` directory* — preferred as a robust sweep, used in addition to per-sample deletion to catch any stragglers; both honor SC-005.
  - *Background GC job* — rejected: leaves a window of orphaned content; synchronous cleanup is simpler and immediate at this scale.

## R9. Provenance carry-forward on derived data (FR-007)

- **Decision**: On clone/fork/curate that produces a new dataset/corpus, copy the parent's provenance fields to the child and set `parent_provenance_ref` to the parent's id. Curation (in-place sample edits) does not create a new entity, so it retains existing provenance and is captured via audit events instead.
- **Rationale**: `Corpus` already has `parent_id` for forks; datasets support clone. Copying provenance + referencing the parent satisfies FR-007 without inventing new lineage machinery.
- **Alternatives considered**:
  - *Re-prompt the user for provenance on every clone* — rejected: poor UX; the parent's provenance is authoritative for a derivative.

## R10. UI surfacing & policy page (Constitution Article VIII)

- **Decision**: Extend `datasets.html` to (a) show source/license/attribution per row and (b) add declared-source/license-select/affirmation-checkbox to the upload form, all using `tokens.css`/`components.css` per DESIGN.md. Add a new server-rendered `acceptable_use.html` policy page and a route, linked from the data-entry surface (FR-017) and discoverable in nav (FR-019, SC-006).
- **Rationale**: `datasets.html` is static + JS-fetch; the page route passes no context today but `TemplateResponse` accepts a context dict for the license-options list. Design tokens are mandatory (no raw values).
- **Alternatives considered**:
  - *Modal-only policy* — rejected: FR-019 wants a discoverable standalone policy; a dedicated page is clearer and linkable.

## R11. Rebase onto main @ 581b832 — impact of the domain-decomposition refactor (#74/#75)

- **Decision**: Realign all design artifacts to the post-refactor codebase and Constitution **v1.6.0**. No change to the feature's WHAT (spec.md is tech-agnostic and unchanged); only the HOW (paths + conventions) is updated.
- **Rationale**: The branch was 2 commits behind main; main landed a large domain-driven decomposition (227 files) that relocated every module this feature targets and added binding conventions. Building against the pre-refactor layout would have produced non-mergeable code.
- **Concrete deltas applied**:
  | Was (pre-refactor) | Now (main @ 581b832) |
  |---|---|
  | `anvil/db/models/training_config.py` (Dataset) | `anvil/db/models/dataset.py` |
  | `anvil/db/models/curation.py` (Sample/ImportSource/CurationOperation) | split into `sample.py`, `import_source.py`, `curation_operation.py`, `corpus_file.py` |
  | `TimestampMixin` in `anvil/db/base.py` | `anvil/db/timestamp_mixin.py` |
  | `anvil/services/datasets.py` (DatasetService) | `anvil/services/datasets/datasets.py` |
  | `anvil/services/dataset_import.py` | `anvil/services/datasets/dataset_import.py` |
  | `anvil/services/demo_bootstrap.py` | `anvil/services/demo/demo_bootstrap.py` |
  | `anvil/services/tracking.py` | `anvil/services/tracking/tracking.py` |
  | models re-exported from `db/models/__init__.py` | **bare `__init__.py`, NO re-exports** (Article VI) |
  | (no centralized HTTP schemas) | `anvil/api/v1/schemas.py` (centralized Pydantic schemas) |
- **New binding conventions now in force (Constitution v1.6.0 + ADRs)**:
  - **Article VI — `__init__.py` Ownership**: bare docstring-only `__init__.py`; no re-exports; direct relative module imports. → My new models/services must NOT be re-exported from `__init__.py`. Alembic visibility comes from an explicit models import (migration env / dedicated import), confirmed by inspecting `migrations/env.py`'s `target_metadata = Base.metadata`.
  - **Article X — Domain-Driven Decomposition**: governance = new bounded context → `anvil/services/governance/` sub-package; co-locate result/value/error types one-per-file.
  - **ADR-020 — one class per file**: each model, enum, and result type gets its own file.
  - **ADR-019 — Pydantic over dataclass**: `GateDecision`, `ChainVerifyResult`, `ProvenanceView` are Pydantic `BaseModel`.
  - **AGENTS.md Principle 11 — StrEnum over magic strings**: `DataOrigin`, `AuditAction`, `AuditTargetType`, `AuditOutcome` are `StrEnum`; columns store the enum value (mirrors `DatasetStatus`, confirmed in `anvil/db/models/dataset.py`).
  - **`TYPE_CHECKING` forbidden**: extract shared types into dedicated modules (already implied by domain decomposition).
- **ADR renumber**: planned ADR is now **ADR-023** (ADR-019–022 already exist on main).
- **Migration number**: next is `014_add_governance.py` (current head `013_drop_experiment_registry_tables_add_run_id_seq.py` plus the merge head `12a4027155f0_merge_002b_and_006_heads.py`; the new revision's `down_revision` is the live alembic head — resolve via `make db-revision` autogenerate).
- **Unaffected findings**: R1–R10 decisions (provenance-as-columns, hash-chaining, affirmation-only gate, broad license set, artifact-cleanup defect, carry-forward, manifest, indefinite retention) all remain valid — only their target paths/conventions shifted. The `delete_dataset` artifact-orphan gap is **re-confirmed present** in the new `anvil/services/datasets/datasets.py`.

---

**All NEEDS CLARIFICATION resolved; artifacts realigned to main @ 581b832 (Constitution v1.6.0).** Ready for Phase 1 design / `/speckit.tasks`.
