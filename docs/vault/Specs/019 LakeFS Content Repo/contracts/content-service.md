# Contract: Content domain services (`anvil/services/content/`)

**Feature**: `016-lakefs-content-repo` | **Phase 1**

Service layer (Article VII) consuming repositories + the `VersionedContentStore`.
One class per file; Pydantic `BaseModel` for value/result types; reuse governance +
chunking. Exposed via `AnvilWorkbench` accessors; routes call the workbench.

## Services

### `CorpusService` (`content/corpus_service.py`)
- `create(...)`, `get(id)`, `list()`, `delete(id)` (guard: refuse if a version is
  run-referenced unless cascade explicitly allowed), `list_versions(id)`,
  `revert(id, to_version_id)`, `tag(version_id, name)` (promotion tag, sets
  `ContentTag.gc_protected=True`; FR-023).
- Enforces provenance gate via `GovernanceService` (license approval, acceptable-use)
  on create — reusing existing governance (no parallel mechanism).

### Management-action authorization seam (`content/authz.py`)
- A single guard/dependency through which management actions (rename, tag, compose,
  promote, acquire/release lock) pass (FR-036). In local single-user mode it permits the
  local operator (trivial); it is the documented injection point for multi-principal
  RBAC in the future SaaS delivery. Data-access (producer write) scoping is enforced
  separately in `IngestionService` (FR-007/008).

### `IngestionService` (`content/ingestion_service.py`)
- `open_session(corpus_id, source)`, `stage(session_id, path, stream)`,
  `validate(session_id) -> ValidationReport`, `accept(session_id) -> AcceptResult`,
  `abandon(session_id)`, `list_active()`.
- Owns the validation gate pipeline (per-batch + pre-acceptance), the serialized
  acceptance (`asyncio.Lock` per corpus + SQLite txn), fail-closed semantics, and
  problem recording (→ `IngestSession.problems_json`, drives SSE Injection Monitor).
- App-level producer scoping (VR-I1) — replaces OSS LakeFS RBAC.

### `ValidationService` (`content/validation_service.py`)
- Pure, testable gate functions. Per-batch: UTF-8/readability, size bounds, required
  provenance metadata, intra-batch exact dedup. Pre-acceptance: cross-corpus exact dedup
  (content-hash set), language allowlist, sensitive-info scan (reuse governance), shape
  conformance. Returns structured `ValidationReport` (pass | fail+reasons). Targets:
  per-batch ~5s, pre-acceptance ~30s (SC-012). Fail-closed on timeout/error.

### `CompositionService` (`content/composition_service.py`)
- `preview(corpus_id, spec) -> CompositionPreview` (per-source token/byte contribution),
  `freeze(corpus_id, spec|None) -> VersionRef`. Rejects empty / all-zero-weight (FR-022).

### `LineageService` (`content/lineage_service.py`)
- `record_run_ref(version_id, mlflow_run_id, digest)`,
  `lineage(version_id) -> LineageOut` (sources via entries + runs via run_refs).

### `AdvisoryService` (`content/advisory_service.py`)
- Post-acceptance async (non-blocking): near-dup detection (flags only), re-tokenize /
  derived-state refresh, acceptance stats + lineage recording (FR-015, FR-026a).

### `ImportService` (`content/import_service.py`)
- `start(corpus_id, source, config)`, `status(job_id)`. Routes content through an
  `IngestSession` so imports pass the same gates (FR-033).

### `LockService` (`content/lock_service.py`)
- `acquire(scope, holder)`, `release(id)`, `list_active()`. Advisory only.

## Value/result types (Pydantic `BaseModel`, co-located per Article X)
`IngestSessionRef`, `StagedEntry`, `ValidationReport`, `ValidationProblem`,
`AcceptResult`, `VersionRef`, `Manifest`, `ManifestEntry`, `CompositionPreview`,
`LineageOut`. StrEnums per data-model.

## Workbench accessors (`anvil/workbench.py`)
Add lazy accessors: `content_corpora`, `content_ingestion`, `content_composition`,
`content_lineage`, `content_imports`, `content_locks`, plus repositories and a
`content_store` accessor returning `LocalVersionedContentStore` (the seam where a future
SaaS factory injects the LakeFS impl).

## Service contract guarantees
- All DB access via repositories only (Article VII); no DB primitives leak to routes.
- All methods async (Article V).
- TDD: each service has unit tests with the gate/serialization invariants (VCS-1..VCS-7)
  covered before implementation (Article IV); coverage ratchets up.
