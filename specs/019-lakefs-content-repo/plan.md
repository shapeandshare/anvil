# Implementation Plan: Content Repository (versioned, reproducible training data)

**Branch**: `019-lakefs-content-repo` | **Date**: 2026-06-20 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/019-lakefs-content-repo/spec.md`

## Summary

Deliver a versioned, reproducible content repository whose canonical unit is a **Corpus**.
Training runs pin **immutable Content Versions** (identified by a content-addressed
**manifest digest**) for reproducibility-by-reference; multiple producers ingest
concurrently into **isolated sessions** gated by fast in-process validation, with
**serialized atomic acceptance** into the canonical corpus; curators **compose weighted
versions**, browse a library/timeline/lineage, import content, and hold advisory locks.

**Pivotal architecture decision (research D1):** **local mode does NOT run LakeFS.** It
uses a **pure-Python content-addressed store** over the existing `LocalFileStore` +
SQLite, behind a new `VersionedContentStore` interface. This makes the local experience
transparent and zero-config (US8) with **no new runtime dependency and no Go-binary
sidecar**, sidesteps the **enterprise-only LakeFS RBAC** gap (producer scoping is
app-level), and avoids the **pre-\* hook loopback deadlock** (validation is in-process).
LakeFS is reclassified as a **future SaaS-mode implementation** behind the same interface.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI, async SQLAlchemy + aiosqlite, Alembic, Jinja2, MLflow
(all existing). **No new runtime dependencies for local mode.** Future SaaS extras
(separate ADR): `lakefs`/`lakefs-spec`, optional `sqladmin` for `/admin`.
**Storage**: SQLite (`data/anvil-state.db`) for metadata; content-addressed blobs on the
filesystem via `LocalFileStore` (`data/content/`). SaaS (future): LakeFS + object store.
**Testing**: pytest + pytest-asyncio + httpx; TDD, ratcheting coverage.
**Target Platform**: macOS/Linux, local-first single FastAPI process; SaaS later.
**Project Type**: Web service (FastAPI) + Jinja UI, layered.
**Performance Goals**: per-batch validation ~5 s; pre-acceptance ~30 s (SC-012).
**Constraints**: zero-config transparent local (US8); async throughout (Art. V);
isolation/serialization correctness at host-supported concurrency (SC-003); fail-closed.
**Scale/Scope**: single-machine local; text content v1 (UTF-8, extension-agnostic);
correctness over throughput.

All Technical Context unknowns are resolved in [research.md](./research.md) (D1–D8).

## Constitution Check

*GATE: passed (pre-Phase 0) and re-checked (post-Phase 1). No violations.*

| Article | Status | Notes |
|---|---|---|
| I — Zero-Dependency Core | ✅ | Opt-in layer; `anvil/core/` untouched; local mode adds zero runtime deps. |
| II — Educational Clarity | ✅ | Pure-Python content-addressed store is more legible than an opaque external binary. |
| III — Seeded Reproducibility | ✅ | Reinforced: content-addressed manifest digest is a stronger reproducibility anchor. |
| IV — TDD Mandatory | ✅ | Gate/isolation/digest invariants (VCS-1..7) tested before impl; coverage ratchets. |
| V — Async-First | ✅ | All store/service/route methods async; SQLite single-writer fits serialized accept. |
| VI — `__init__.py` Ownership | ✅ | New domain sub-package `services/content/` gets a bare `__init__.py`; models bare. |
| VII — Layered Architecture | ✅ | Repository → Service → `AnvilWorkbench` → Routes; `VersionedContentStore` behind services; no DB leakage. |
| VIII — iOS-Grade Polish | ✅ | Forge screens reuse the existing iOS-modern design system + SSE (not "CRT/glitch"). |
| IX — Pit of Success | ✅ | **Primary driver of D1**: works with no config, no binary download, never crashes; this is why local mode is pure-Python. |
| X — DDD Package Decomposition | ✅ | New bounded context `services/content/`; value/result types co-located; StrEnums in-domain; ≤2 nesting levels. |
| Additional (Pydantic, StrEnum, one-class-per-file, Alembic, mypy strict, lean deps) | ✅ | Followed; new deps deferred to SaaS (ADR). |

**New-dependency justification**: none for local mode. SaaS-only deps (`lakefs`,
`lakefs-spec`, `sqladmin`) will be added under optional extras with a dedicated ADR when
SaaS mode is implemented.

**ADR required**: yes — record the LakeFS-vs-pure-Python-local decision and the
`VersionedContentStore` boundary (divergence from the source draft). Draft as
`docs/vault/Decisions/ADR-033-content-repository-substrate.md` (add to the ADR index).
The SaaS-facing consequences are also recorded in ADR-030 (AD-17) and
`specs/016-saas-architecture/spec.md` (FR-062–FR-067, SC-021).

## Project Structure

### Documentation (this feature)

```text
specs/019-lakefs-content-repo/
├── plan.md              # This file
├── research.md          # Phase 0 — D1–D8 decisions
├── data-model.md        # Phase 1 — 10 new tables + StrEnums + manifest digest
├── quickstart.md        # Phase 1 — end-to-end local validation
├── contracts/           # Phase 1
│   ├── versioned-content-store.md
│   ├── content-service.md
│   ├── api-endpoints.md
│   └── manifest.schema.md
├── checklists/requirements.md
└── tasks.md             # Phase 2 (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
anvil/
├── db/
│   ├── models/                         # one class per file (NEW)
│   │   ├── content_source.py
│   │   ├── content_corpus.py
│   │   ├── content_version.py
│   │   ├── content_entry.py
│   │   ├── content_blob.py
│   │   ├── content_tag.py
│   │   ├── content_ingest_session.py
│   │   ├── content_import_job.py
│   │   ├── content_lock.py
│   │   └── content_version_run_ref.py
│   └── repositories/                   # NEW (Repository pattern)
│       ├── content_corpora.py
│       ├── content_sources.py
│       ├── content_versions.py
│       ├── content_ingest_sessions.py
│       ├── content_import_jobs.py
│       ├── content_locks.py
│       └── content_blobs.py
├── services/content/                   # NEW bounded context (Article X)
│   ├── __init__.py                     # bare docstring
│   ├── versioned_content_store.py      # ABC (the substrate boundary)
│   ├── local_versioned_content_store.py# pure-Python local impl
│   ├── content_corpus_status.py        # StrEnum
│   ├── source_kind.py                  # StrEnum
│   ├── ingest_status.py                # StrEnum
│   ├── lock_state.py                   # StrEnum
│   ├── manifest.py / manifest_entry.py # value types (BaseModel) + digest helper
│   ├── version_ref.py / ingest_session_ref.py / validation_report.py / accept_result.py
│   ├── corpus_service.py
│   ├── ingestion_service.py
│   ├── validation_service.py
│   ├── composition_service.py
│   ├── lineage_service.py
│   ├── advisory_service.py
│   ├── import_service.py
│   └── lock_service.py
├── api/
│   ├── v1/content.py                   # NEW router (CRUD + ingestion + SSE)
│   ├── v1/router.py                    # include content_router (EDIT)
│   ├── v1/pages.py                     # content forge pages + nav (EDIT)
│   ├── v1/schemas.py                   # content Pydantic bodies (EDIT)
│   ├── app.py                          # optional /admin SQLAdmin mount (EDIT, later)
│   └── templates/archetypes/content_*.html + nav tab in base.html (NEW/EDIT)
├── workbench.py                        # add content_* accessors + content_store seam (EDIT)
└── _resources/migrations/
    ├── versions/0NN_add_content_repository.py  # NEW reversible migration
    └── env.py                          # import new models (EDIT)

tests/
├── unit/services/content/              # gate/isolation/digest/composition invariants
├── unit/db/repositories/               # repository tests
├── integration/                        # API + ingestion→accept→pin→resolve flows
└── e2e/                                # quickstart journey
```

**Structure Decision**: Single project (existing `anvil/` layout). The content
repository is a new domain sub-package `anvil/services/content/` plus new ORM models,
repositories, a router, and forge pages — all following the established layered + DDD
conventions. No new top-level project; SaaS substrate (`anvil/_saas/`) is out of scope.

## Phased delivery (MVP-first; research D7/Q5)

> Each phase is an independently shippable, testable slice. Detailed tasks come from
> `/speckit.tasks`.

- **Phase A — Reproducibility core (P1 thin vertical slice)**: models + migration for
  `ContentSource/Corpus/Version/Entry/Blob/VersionRunRef`; `LocalVersionedContentStore`
  (content-addressed blobs + manifest digest); `CorpusService` + a single-session
  `IngestionService` (open→stage→validate(per-batch)→accept→freeze); resolve; MLflow
  pin (`corpus_ref` + manifest); minimal API. **Delivers SC-001/010/012** and US1+US8
  end-to-end. *No new sidecar, no config.*
- **Phase B — Concurrent isolation + safety**: multi-session isolation, serialized
  atomic acceptance, cross-corpus pre-acceptance gates (~30s), fail-closed, revert,
  retention/GC of unreferenced blobs, app-level producer scoping. **US2/US3, SC-002/003/004/005**.
- **Phase C — Composition/ensembling**: weighted selection, preview (token/byte), freeze
  composition versions, weighted resolution. **US4, SC-006**.
- **Phase D — Visibility (forge screens + SSE)**: the browser **content hub** — Corpus
  Library, Version Timeline (diff), Lineage, Injection Monitor, and the **Ensemble
  Composer** — plus `content.js` workflow interactions, the 4 SSE streams, and a
  **design-system + accessibility conformance pass** (Constitution Article VIII / DESIGN.md;
  delegated to `visual-engineering` + `frontend-ui-ux`). The MVP (Phase A) is API-first;
  the UI lands here. **US5, SC-007/008**.
- **Phase E — Import + advisory**: import jobs (through gates), near-dup advisory,
  re-tokenize/derived-state refresh, checkout board/locks. **US6/US7, FR-015/026a**.
- **Phase F — SaaS mode (separate delivery + ADR)**: `LakeFSVersionedContentStore` behind
  the same interface in `anvil/_saas/`; managed-component visibility; optional `/admin`
  SQLAdmin. **US9, FR-041**. *Not in this delivery.*

## Complexity Tracking

> No constitution violations to justify. The one significant decision (NOT using LakeFS
> locally) *reduces* complexity and dependency surface; it is recorded as an ADR rather
> than a violation.

## Spec deltas surfaced during planning

- The feature title references "LakeFS"; the implementation makes LakeFS a **SaaS-mode,
  future** substrate. Spec body is already substrate-agnostic — no requirement changes.
  ADR will record this; directory name retained for traceability.
- FR-007/FR-036 producer scoping → **app-level enforcement** (OSS LakeFS RBAC
  unavailable). Spec already frames management/data planes app-side — consistent.
- Validation "gates" → **in-process service calls** locally (not LakeFS webhooks). Spec
  is mechanism-agnostic — consistent; latency targets (SC-012) unchanged.
- **SaaS spec enhanced (cross-feature)**: the SaaS-mode consequences of this feature were
  propagated into `specs/016-saas-architecture/spec.md` — `VersionedContentStore` added to
  the abstraction interfaces (FR-016), a new **Content Repository (versioned)** requirement
  group (FR-062–FR-067), SC-021 (cross-mode parity + org isolation), and **AD-17** (LakeFS
  substrate, app-level RBAC reconciliation, in-process validation, manifest-digest parity).
  ADR-030's canonical decision table + abstraction layer were updated (AD-17), and
  `SaaSArchitecture.md` gained the `anvil-content-{env}` LakeFS bucket/namespace. The SaaS
  body of work (014) therefore now owns the LakeFS-backed delivery (016 Phase F / US9).

## Post-Design Constitution Re-check

Re-evaluated after Phase 1: **PASS** (table above). No new violations introduced by the
data model or contracts; layering, async, DDD, one-class-per-file, StrEnum, Pydantic,
and reversible-migration rules are all honored.
