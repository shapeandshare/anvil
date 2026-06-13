# Research: Dataset Curation

**Date**: 2026-06-12
**Status**: Complete (research agents consolidated)

## Design Decisions

### Storage Strategy: Hybrid SQLite + Filesystem

**Decision**: Store sample metadata in SQLite (async SQLAlchemy), store bulk text content on filesystem via LocalFileStore.

**Rationale**:
- SQLite can handle metadata for up to 1M samples comfortably (id, index, length, dataset_id FK, curation_op_id FK)
- Storing large text blobs directly in SQLite rows with async access risks performance degradation at scale
- The project already has LocalFileStore abstraction for file-based storage
- Filesystem storage enables streaming reads for training pipeline

**Alternatives Considered**:
- Pure SQLite (all text in rows): Simpler but risks performance with 1M samples with ~10KB text each (~10GB in DB)
- Pure filesystem (JSONL file per dataset): No ability to query/index individual samples

### Import Atomicity Pattern

**Decision**: Wrap import in a database transaction; write samples to staging table; on commit, move to main samples table; on failure, rollback transaction.

**Rationale**:
- Async SQLAlchemy supports transaction rollback natively
- Staging approach validates all data before committing
- Supports the spec requirement for atomic rollback on failure

**Alternatives Considered**:
- Import to temp file, then bulk insert: More complex, no built-in rollback
- Row-by-row with delete-on-failure: Error-prone, partial data cleanup is fragile

### Curation Operations Model

**Decision**: Immutable operation log pattern — each curation operation records its parameters and the set of affected sample IDs. Samples are soft-deleted (marked as removed by operation) rather than physically deleted.

**Rationale**:
- Supports the versioning/history feature (User Story 6)
- Enables undo by tracking which operation removed which samples
- Maintains referential integrity for training configs that reference datasets
- Operations are append-only, enabling audit trail

**Alternatives Considered**:
- Mutating samples in place: Simple but loses history, can't undo
- Copy-on-write (full version on each operation): Storage explosion with large datasets

### Corpus Integration Approach

**Decision**: Provide an API that allows importing corpus content into a Dataset. The existing `CorpusService.load_docs()` already returns chunked text; this output feeds into the dataset import pipeline.

**Rationale**:
- Reuses existing chunking infrastructure (window/line/file chunkers)
- No need to duplicate chunking logic in the curation system
- Corpus remains the authoritative source for raw data; Dataset gets a curated snapshot

**Alternatives Considered**:
- Building curation directly on top of Corpus model: More coupled, harder to maintain separation of concerns
- Importing raw files without chunking: Loses the existing chunking strategy sophistication

### Concurrency Model

**Decision**: Single-user, single-threaded access. No concurrent operation handling needed for v1. Operations run synchronously within the web request lifecycle, with progress indication for long-running operations via SSE or polling.

**Rationale**:
- Spec explicitly states single-user
- Existing project pattern uses synchronous request handling for dataset operations
- SSE infrastructure already exists in the project (for training loss streaming)

**Alternatives Considered**:
- Background task queue: Over-engineered for single-user
- WebSocket-based progress: SSE is already used in project, simpler to adopt

### Training Consumption Pattern

**Decision**: Add a `DatasetService.load_docs(dataset_id)` method that queries active samples from the DB and returns `list[str]` for the training pipeline. The existing `TrainingService._load_docs()` should be extended to support both corpus-based and dataset-based consumption.

**Rationale**:
- Currently `CorpusService.load_docs()` re-ingests from filesystem every time — it doesn't query stored data
- For curated datasets, samples exist in SQLite + LocalFileStore; reading from DB is more efficient
- The `core/engine.py::train()` function already accepts `docs: list[str]` — so the interface is compatible

**Implementation**:
```python
async def load_docs(self, dataset_id: int) -> list[str]:
    samples = await self._repo.get_active_samples(dataset_id)
    texts = []
    for sample in samples:
        text = await self._storage.get(sample.file_path)
        texts.append(text)
    return texts
```

**Patterns found**:
- SQLite with WAL mode already enabled (supports concurrent reads + writes)
- TimestampMixin provides `created_at` + `updated_at` on all models
- Versioning pattern exists via `ModelVersion` with `get_next_version_number()` using `func.max()`
- State tracking via simple `status: Mapped[str]` with `default="pending"` (Experiment pattern)
- No soft-delete currently exists in the codebase — adds to new model as `is_removed: bool`

### API Route Pattern

**Decision**: Create a new `microgpt/api/v1/curation.py` module with its own `router`, registered in `router.py`. Follow existing patterns: service dependency injection via `Depends(get_service)`, `{"data": ..., "error": None}` response envelope (corpora pattern).

**Rationale**:
- Existing pattern: each feature gets its own route module and `router.include_router()` in `router.py`
- Corpus module uses `{"data": ..., "error": None}` envelope — more robust than flat dicts
- Service DI via `Depends(get_service)` is the established pattern

**Alternatives Considered**:
- Adding routes to existing `datasets.py`: Would make the file too large, mixing curation with CRUD
- Separate router module is cleaner separation of concerns

### UI Template Pattern

**Decision**: Create `microgpt/api/templates/dataset_detail.html` extending `base.html`. Use IIFE pattern for JavaScript, `fetch` + `FormData` for uploads, Unix `ls`-style CSS classes for list display. No HTMX.

**Rationale**:
- Existing `datasets.html` and `base.html` provide established patterns
- Vanilla JavaScript with `fetch` API is the project convention
- Existing CSS classes (`.panel`, `.terminal-input`, `.terminal-btn`, `.ls-*`, `.telemetry`) provide consistent retro styling

**Patterns found**:
- Page routes: `@router.get("/{name}-page", response_class=HTMLResponse)` → `TemplateResponse`
- JS pattern: IIFE wrapping, `window.loadX()` for data reload, `Array.map().join('')` for list rendering
- Form submission: `FormData` + `fetch` POST, status via `.telemetry` div
- CSS: `.panel`/`.panel-titlebar`/`.panel-body` for sections, `.ls-line`/`.ls-name`/`.ls-size` for lists, `.terminal-input`/`.terminal-btn` for controls

## Architecture Diagram

```
User Browser (Jinja2 + JS)
        │
        ▼
  FastAPI Routes (datasets.py)
        │
        ├──► DatasetService     (CRUD, listing, search)
        ├──► DatasetImportService (parse, validate, atomic import)
        ├──► DatasetCurationService (dedup, filter, replace)
        ├──► DatasetExportService  (format, stream, download)
        └──► TrainingPipeline      (consume curated dataset)
                │
                ▼
          ┌──────────┬──────────┐
          ▼          ▼          ▼
    SQLAlchemy   LocalFileStore  MLflow
    (metadata)   (sample text)   (experiments)
```

## Performance Targets

| Operation | Target Size | Target Time | Notes |
|-----------|-------------|-------------|-------|
| Import (parse + validate) | 100K samples | <30s | Excluding upload time |
| Import + preview (first 20 rows) | 100K samples | <2s preview | Dedicated preview pass |
| Export (TXT/CSV/JSONL) | 10K samples | <10s | Download excluded |
| Dedup (exact match) | 10K samples | <2s | O(n) hash-based |
| Filter (length-based) | 10K samples | <2s | Single pass |
| Regex replace | 10K samples | <2s per pattern | Iterates all samples |
| Quality metrics | 10K samples | <3s | Token count via heuristic |
| Max dataset size | 1M samples | No time SLA | Must succeed with streaming |