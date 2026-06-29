# Research: Fine-Tuning Dataset Preparation

## Async Job Pattern

### Decision
Reuse the `ModelImportJob` pattern: POST returns `202 Accepted` with a `job_id`, background worker via
`asyncio.create_task()` with its own `AsyncSession`, polling endpoint for status.

### Rationale
- The codebase already has this exact pattern for model imports (`anvil/api/v1/models.py`,
  `anvil/services/model_import/model_import_service.py`)
- The pattern uses `asyncio.create_task()` with isolated sessions — no additional infra needed
- Status polling via `GET /models/import/{job_id}/status` maps directly to the spec's FR-004
- No changes to supervisor needed (it manages OS processes only)

### Alternatives considered
- SSE streaming (used in training): Overkill for dataset preparation, which is fast text processing
- Celery/Redis: Would add a heavyweight dependency for a single-task pattern

---

## Batch Processing

### Decision
Process input JSONL in configurable-size batches (default 1000 records), reusing the
`SampleRepository.add_bulk()` pattern from `anvil/db/repositories/curation.py`.

### Rationale
- `add_bulk()` already exists and handles batch inserts with `session.add_all()` + `session.flush()`
- Spec 053 says "configurable batch sizes, matching the existing dataset-service job pattern"
- The existing pattern processes synchronously per batch, which is fine for text rendering

### Alternatives considered
- Streaming/chunked I/O: Not needed for "hundreds to tens of thousands of records" (Q4 clarification)
- Single-transaction bulk insert: Risk of DB timeout for very large imports

---

## ChatTemplate Entity

### Decision
Create a new `ChatTemplate` ORM entity with a separate `chat_templates` table. No existing class exists
in the codebase. Spec 043 provides `Tokenizer` protocol + `TokenizerFactory.create_tokenizer()` but
does NOT provide any chat template support.

### Rationale
- Spec 053 clarification Q2 confirmed separate entity for future variant/versioned templates
- HuggingFace tokenizers store chat templates in `tokenizer.json` at `model.metadata.chat_template`
  but the existing `HFFastTokenizer` wrapper does not expose this — the template string lives in the
  artifact directory, not in a DB entity
- A new DB entity gives us versioning, naming, reuse across fine-tunes, and auditability

### Alternatives considered
- Derive from tokenizer at consumption time: Violates FR-001 (formatting must be recorded) and
  breaks reproducibility if the artifact's template changes
- Inline on FineTuneDataset: Precluded by Q2 clarification (future variants needed)

---

## Validation & Error Reporting

### Decision
Skip-and-continue with `PreparationResult` summary: `{total, succeeded, failed, errors: [{row, error}]}`.

### Rationale
- Confirmed in Q5 (clarification session)
- Extends existing `ImportResult.errors` pattern (`list[dict]` with `{"row": index, "error": str(e)}`)
- New `PreparationResult` adds aggregate counts (`total`, `succeeded`, `failed`) not present in
  current `CurationResult`

### Alternatives considered
- Fail-fast (Option A): Rejected in clarification — frustrating for users iterating on datasets
- Pause-on-error (Option C): Over-engineered for the current use case

---

## Dataset Lifecycle

### Decision
Add `PREPARING = "preparing"` and `FAILED = "failed"` to the existing `DatasetStatus` StrEnum (or
create a parallel `FineTuneDatasetStatus` enum for the new entity).

### Rationale
- Q1 clarification confirmed `preparing → ready | failed` lifecycle matching spec 005 governance
- If `FineTuneDataset` is a separate entity from `Dataset`, a new `FineTuneDatasetStatus` enum
  is cleaner (avoids polluting the core `DatasetStatus`)
- The `ModelImportJobStatus` pattern (`QUEUED/RESOLVING/COMPLETE/FAILED`) is the right analog

---

## Existing FileStore & Sample Storage

### Decision
Prepared records (chat-template–rendered strings) are stored as JSONL files in the FileStore,
following the existing `Sample.file_path` pattern from datasets (005). The `FineTuneDataset` ORM
records the file path and metadata.

### Rationale
- Existing `Sample` ORM stores per-record file paths + content_hash for dedup
- Prepared records are conceptually different from curation samples (they're rendered strings,
  not source text) so a new file path convention under `data/datasets/<id>/prepared/` is appropriate
- Reuses `LocalFileStore` abstraction (S3-ready)

---

## Technology Choices

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Language | Python 3.11+ | Existing project convention |
| Web framework | FastAPI | Existing |
| ORM | async SQLAlchemy + aiosqlite | Existing |
| Tokenizer abstraction | spec 043 `TokenizerFactory` | Existing, reuse before introduce (§11.4) |
| Async jobs | `asyncio.create_task()` + isolated `AsyncSession` | Existing pattern from model_import |
| Template rendering | ChatTemplate string (Jinja-like) + tokenizer encode | No new deps needed; HF template syntax is plain text |
| Serialization | JSONL | Confirmed Q3 |
| Storage | `LocalFileStore` → `data/datasets/<id>/prepared/` | Reuse existing FileStore |
| Job status | `GET /fine-tune-datasets/jobs/{id}/status` | Reuse ModelImportJob pattern |
| Audit trail | `CurationOperation(operation_type="prepare")` | Reuse existing audit infrastructure |
