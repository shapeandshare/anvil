# Phase 1 Data Model: Content Repository

**Feature**: `016-lakefs-content-repo` | **Date**: 2026-06-20

All models are SQLAlchemy **declarative** (`Base` from `anvil/db/base.py` +
`TimestampMixin` + `Mapped[]`/`mapped_column()`), one class per file in
`anvil/db/models/`, matching ADR-020. `anvil/db/models/__init__.py` stays **bare**
(Article VI); models register on `Base.metadata` via the explicit import list in the
Alembic env. Fixed-set columns store **StrEnum** values (AGENTS.md Principle 11).
Pydantic `BaseModel` is used for HTTP and service value types only — never for ORM rows.
Schema applied via one reversible Alembic migration (`0NN_add_content_repository.py`).

> **Naming reconciliation (per spec Clarification Q2 + research D1):** The user-facing
> canonical unit is **"Corpus"**. The existing ORM class `Corpus`/table `corpora` is the
> **legacy directory-based mechanism** (relabeled "Directory Corpus (deprecated)" in the
> UI; out of scope to migrate/remove here). One-class-per-file forbids a second `Corpus`
> class, so the NEW canonical models use a `Content*` ORM prefix and `content_*` tables.
> This keeps the clean-implementation scope (no legacy coupling) while presenting
> "Corpus" to users.

> **Blobs are content-addressed on the filesystem** (via `LocalFileStore` under
> `data/content/blobs/<aa>/<sha256>`), NOT stored in SQLite. SQLite holds metadata and
> references blobs by `content_hash` (sha256 hex). This is the local substrate (research
> D1/D3); a future SaaS `LakeFSVersionedContentStore` swaps the substrate behind the same
> interface without schema change to the metadata model.

### StrEnums (one class per file, in `anvil/services/content/`)

| Enum (file) | Members (value) | Used by |
|---|---|---|
| `ContentCorpusStatus` (`content_corpus_status.py`) | `DRAFT="draft"`, `ACTIVE="active"`, `ARCHIVED="archived"` | `ContentCorpus.status` |
| `SourceKind` (`source_kind.py`) | `INJECTOR="injector"`, `IMPORTER="importer"`, `MANUAL="manual"` | `ContentSource.kind` |
| `IngestStatus` (`ingest_status.py`) | `OPEN="open"`, `VALIDATING="validating"`, `ACCEPTED="accepted"`, `FAILED="failed"` | `IngestSession.status`, `ImportJob.status` |
| `LockState` (`lock_state.py`) | `HELD="held"`, `RELEASED="released"` | `CheckoutLock.state` |

`ChunkingStrategy` is **reused** from `anvil/services/datasets/chunking_strategy.py`
(`LINE`/`WINDOWED`/`FILE`) — not redefined.

Columns are `Mapped[str]` with `mapped_column(String(N), default=<Enum>.<MEMBER>)`,
assigned/compared via enum members (never raw literals); boundary methods accept
`str | Enum` and coerce.

---

## 1. `ContentSource` — registered content origin (NEW table `content_sources`)

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `id` | int | PK, autoincrement | |
| `slug` | str(128) | unique, not null | Stable identifier; appears in provenance + producer scoping |
| `name` | str(255) | not null | Human label |
| `kind` | str(20) | not null, default `SourceKind.MANUAL` | injector \| importer \| manual |
| `created_at`, `updated_at` | datetime | TimestampMixin | |

**VR-S1**: `slug` unique. **VR-S2**: `kind` ∈ `SourceKind`.

---

## 2. `ContentCorpus` — canonical content unit (NEW table `content_corpora`)

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `id` | int | PK, autoincrement | |
| `slug` | str(128) | unique, not null | URL/identifier-safe |
| `name` | str(255) | not null | |
| `description` | str(1000) | nullable | |
| `chunking_strategy` | str(20) | not null, default `ChunkingStrategy.WINDOWED` | applied at resolution |
| `block_size` | int | not null, default 16 | |
| `chunk_overlap` | float | not null, default 0.5 | |
| `default_language` | str(16) | not null, default `"en"` | |
| `status` | str(20) | not null, default `ContentCorpusStatus.DRAFT` | lifecycle |
| `current_version_id` | int | nullable, FK→`content_versions.id` `ondelete=SET NULL` | canonical "latest" pointer (mutable) |
| `source_description` | str(1000) | nullable | provenance (reuse governance pattern) |
| `license_id` | int | nullable, FK→`license_catalog.id` `ondelete=RESTRICT` | provenance |
| `attribution_text` | str(1000) | nullable | provenance |
| `origin` | str(20) | not null, default `"user"` | `bundled`\|`user` (reuse `DataOrigin`) |
| `parent_provenance_ref` | int | nullable | derived-from lineage |
| `created_at`, `updated_at` | datetime | TimestampMixin | |

**Relationships**: `versions: list[ContentVersion]` (back_populates `corpus`,
cascade all,delete-orphan); `current_version: ContentVersion | None`.
**VR-C1**: `slug` unique. **VR-C2**: training MUST pin a version, never
`current_version` directly (FR-005) — enforced in the service/resolver, not the schema.

---

## 3. `ContentVersion` — immutable frozen snapshot (NEW table `content_versions`)

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `id` | int | PK, autoincrement | internal id |
| `corpus_id` | int | not null, FK→`content_corpora.id` `ondelete=CASCADE` | |
| `version_number` | int | not null | monotonic per corpus (human label basis) |
| `manifest_digest` | str(64) | not null, indexed | **sha256 of canonical manifest — the pinnable opaque ref (FR-002/003)** |
| `label` | str(64) | nullable | e.g. `v3` |
| `note` | str(1000) | nullable | |
| `is_composition` | bool | not null, default False | True if weighted ensemble (US4) |
| `entry_count` | int | not null, default 0 | denormalized for listing |
| `total_bytes` | int | not null, default 0 | denormalized |
| `created_at`, `updated_at` | datetime | TimestampMixin | |

**Relationships**: `corpus: ContentCorpus`; `entries: list[ContentEntry]`
(cascade all,delete-orphan); `tag: ContentTag | None` (uselist=False);
`run_refs: list[VersionRunRef]`.
**Constraints**: `UniqueConstraint(corpus_id, version_number)`;
`UniqueConstraint(corpus_id, manifest_digest)`.
**State/lifecycle**: append-only & immutable (FR-004) — no update/delete of entries
after creation; a "change" creates a NEW version.

---

## 4. `ContentEntry` — one content item in a version (NEW table `content_entries`)

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `id` | int | PK, autoincrement | |
| `version_id` | int | not null, FK→`content_versions.id` `ondelete=CASCADE` | |
| `path` | str(1024) | not null | logical path within the corpus |
| `content_hash` | str(64) | not null, indexed | sha256 of blob bytes (content-addressed) |
| `weight` | float | not null, default 1.0 | ensemble sampling weight (US4) |
| `source_id` | int | nullable, FK→`content_sources.id` `ondelete=SET NULL` | originating source |
| `size_bytes` | int | not null, default 0 | |

**Index**: `Index("ix_content_entries_version_path", "version_id", "path")`.
**VR-E1**: `(version_id, path)` unique within a version.
**VR-E2**: `content_hash` references a blob present in the content-addressed store.

---

## 5. `ContentBlob` — content-addressed blob metadata (NEW table `content_blobs`)

Tracks stored blobs for stats, dedup, and retention/GC (bytes live on the filesystem).

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `content_hash` | str(64) | PK | sha256 hex of bytes |
| `size_bytes` | int | not null | |
| `created_at`, `updated_at` | datetime | TimestampMixin | |

**VR-B1**: a blob is retention-protected iff any `ContentEntry` of any
retention-protected version references its `content_hash` (FR-024). GC removes only
blobs with zero reachable references (research D3).

---

## 6. `ContentTag` — promotion tag (NEW table `content_tags`)

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `id` | int | PK, autoincrement | |
| `version_id` | int | not null, unique, FK→`content_versions.id` `ondelete=CASCADE` | |
| `name` | str(256) | unique, not null | e.g. `corpus/<slug>/v3` |
| `gc_protected` | bool | not null, default True | tagged versions never collected |
| `created_at`, `updated_at` | datetime | TimestampMixin | |

**VR-T1**: a promotion tag is additive — pinning does NOT require a tag; every
run-referenced version is retention-protected regardless of tag (spec Assumptions).

---

## 7. `IngestSession` — isolated staging workspace (NEW table `content_ingest_sessions`)

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `id` | int | PK, autoincrement | |
| `corpus_id` | int | not null, FK→`content_corpora.id` `ondelete=CASCADE` | |
| `source_id` | int | not null, FK→`content_sources.id` `ondelete=RESTRICT` | producer scope |
| `staging_key` | str(512) | not null, unique | session-scoped staging namespace (isolation, FR-006) |
| `status` | str(20) | not null, default `IngestStatus.OPEN` | open→validating→accepted\|failed |
| `staged_entry_count` | int | not null, default 0 | |
| `problems_json` | Text | nullable | validation failures (FR-014) → drives Injection Monitor |
| `accepted_version_id` | int | nullable, FK→`content_versions.id` `ondelete=SET NULL` | set on acceptance |
| `opened_at` | datetime | not null, default now | |
| `closed_at` | datetime | nullable | set on accept/fail/abandon |
| `created_at`, `updated_at` | datetime | TimestampMixin | |

**State transitions**: `OPEN → VALIDATING → ACCEPTED` (fold + new version) | `→ FAILED`
(gate failure or abandon). Acceptance is **serialized per corpus** (research D4).
**Retention (FR-025)**: `ACCEPTED` staging removed after fold; `FAILED`/abandoned
staging retained ~30 days then cleaned.
**VR-I1**: only the owning session may write to its `staging_key`; only `accept_session`
mutates canonical state (app-level producer scoping replacing OSS LakeFS RBAC).

---

## 8. `ImportJob` — monitored external/local import (NEW table `content_import_jobs`)

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `id` | int | PK, autoincrement | |
| `corpus_id` | int | not null, FK→`content_corpora.id` `ondelete=CASCADE` | |
| `source_id` | int | not null, FK→`content_sources.id` `ondelete=RESTRICT` | |
| `config_json` | Text | not null | connector params (NO secrets) |
| `status` | str(20) | not null, default `IngestStatus.OPEN` | reuses IngestStatus |
| `session_id` | int | nullable, FK→`content_ingest_sessions.id` `ondelete=SET NULL` | import routes through an ingest session (FR-033) |
| `message` | str(1000) | nullable | progress/failure detail |
| `started_at` | datetime | not null, default now | |
| `finished_at` | datetime | nullable | |
| `created_at`, `updated_at` | datetime | TimestampMixin | |

**VR-J1**: imported content flows through the same validation gates as any injection
(FR-033) — i.e., an import job opens/accepts an `IngestSession`.

---

## 9. `CheckoutLock` — advisory lock (NEW table `content_locks`)

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `id` | int | PK, autoincrement | |
| `scope` | str(512) | not null | corpus/path/branch scope checked out |
| `holder` | str(256) | not null | who holds it |
| `state` | str(20) | not null, default `LockState.HELD` | held \| released |
| `acquired_at` | datetime | not null, default now | |
| `released_at` | datetime | nullable | |
| `created_at`, `updated_at` | datetime | TimestampMixin | |

**VR-K1**: advisory only — does NOT hard-block canonical content (spec edge case);
board shows age + holder (FR-034/035).

---

## 10. `VersionRunRef` — lineage: version ↔ training run (NEW table `content_version_run_refs`)

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `id` | int | PK, autoincrement | |
| `version_id` | int | not null, FK→`content_versions.id` `ondelete=CASCADE` | |
| `mlflow_run_id` | str(64) | not null, indexed | the run that pinned this version |
| `corpus_ref` | str(64) | not null | manifest digest logged to MLflow (mirror) |
| `created_at`, `updated_at` | datetime | TimestampMixin | |

**VR-R1**: a version with ≥1 `VersionRunRef` is retention-protected (FR-024/SC-002),
exactly like a tagged version. Lineage view (FR-031) joins
sources (via entries) and runs (via run_refs) per version.

---

## 11. Manifest digest definition (the version ref — research D3)

```
manifest = {
  "corpus_slug": <str>,
  "version_number": <int>,
  "chunk_cfg": {"strategy": <str>, "block_size": <int>, "chunk_overlap": <float>},
  "entries": [  # sorted by path, then content_hash
     {"path": <str>, "content_hash": <sha256 hex>, "weight": <float>, "source": <slug|null>},
     ...
  ]
}
manifest_digest = sha256_hex(
  canonical_json(manifest)   # keys sorted, separators (",",":"), UTF-8
)
```

`manifest_digest` is the opaque, pinnable, reproducible ref (FR-002/003, SC-001). The
canonical-JSON manifest is also persisted as `corpus_manifest.json` (portable, self-
describing fallback, MLflow artifact).

---

## 12. Entity relationships

```
content_sources (1) ──< (N) content_ingest_sessions.source_id   [RESTRICT]
content_sources (1) ──< (N) content_entries.source_id           [SET NULL]
content_corpora (1) ──< (N) content_versions.corpus_id          [CASCADE]
content_corpora.current_version_id ──> content_versions.id      [SET NULL] (mutable latest pointer)
content_versions (1) ──< (N) content_entries.version_id         [CASCADE]
content_versions (1) ──  (0..1) content_tags.version_id         [CASCADE, unique]
content_versions (1) ──< (N) content_version_run_refs.version_id[CASCADE]
content_entries.content_hash ──> content_blobs.content_hash     (logical, content-addressed)
content_ingest_sessions (1) ── (0..1) content_import_jobs.session_id [SET NULL]
license_catalog (1) ──< (N) content_corpora.license_id          [RESTRICT] (reuse governance)
```

---

## 13. Request/response Pydantic models (`anvil/api/v1/schemas.py` — not ORM)

- `CorpusCreate`: `name`, `slug?`, `description?`, `chunking_strategy?`, `block_size?`,
  `chunk_overlap?`, provenance (`declared_source`, `license`, `attribution?`).
- `SessionOpen`: `corpus_id`, `source` (slug).
- `StageEntry` (multipart/body): `path`, content bytes.
- `CompositionSpec`: `entries: [{version_id|content_hash, path, weight}]` for ensembling.
- `FreezeVersionBody`: `note?`, `label?`, optional `composition: CompositionSpec`.
- `TagBody`: `name`.
- `RevertBody`: `to_version_id`.
- `LockBody`: `scope`, `holder`.
- `ImportStart`: `corpus_id`, `source`, `config` (no secrets).
- Outputs: `CorpusOut`, `VersionOut` (incl. `manifest_digest`, `version_number`,
  `label`, `entry_count`, `total_bytes`, `tag?`), `EntryOut`, `SessionOut` (incl.
  `status`, `problems`), `ValidationReportOut`, `LineageOut`, `ImportJobOut`, `LockOut`.
- All responses keep the `{"data": ..., "error": ...}` wrapper.

---

## 14. Migration & registration

- One reversible Alembic migration `0NN_add_content_repository.py` creating the 10 new
  tables (no changes to existing `corpora`/`datasets`). Reuses `license_catalog` FK.
- Add explicit model imports to the Alembic env import list (`anvil/_resources/
  migrations/env.py`) so autogenerate sees them; `anvil/db/models/__init__.py` stays bare.
- No data backfill (clean implementation, no legacy migration — spec D1/FR-038a).
