# Quickstart: Dataset Curation

**For developers implementing this feature**

## What We're Building

Feature-rich dataset curation for anvil: users create datasets, import text data from multiple formats (TXT/CSV/JSONL/JSON/paste/corpus), curate (dedup, filter, regex replace, edit/delete individual samples), view quality metrics, export, and use curated datasets for training.

## Key Architecture Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Sample storage | SQLite metadata + filesystem text via LocalFileStore | 1M samples; existing FileStore pattern |
| Import semantics | Append only, atomic rollback on failure | Data integrity |
| Curation tracking | Immutable operation log | Versioning, undo, audit |
| Deletion | Soft-delete samples, block dataset deletion if referenced | Data integrity |
| Maximum scale | 1M samples (performance tuned for 100K) | Clarified with stakeholder |

## Files to Create/Modify

### New Files
- `anvil/db/migrations/versions/003_add_dataset_curation.py` - DB migration
- `anvil/services/dataset_import.py` - Multi-format import with validation + atomicity
- `anvil/services/dataset_curation.py` - Dedup, filter, replace engine
- `anvil/services/dataset_export.py` - Format-based export
- `anvil/api/templates/dataset_detail.html` - Curation UI page
- `tests/unit/test_dataset_services.py` - Service unit tests
- `tests/integration/test_dataset_curation.py` - Full workflow tests

### Modified Files
- `anvil/db/models/training_config.py` - Extend Dataset model
- `anvil/db/repositories/datasets.py` - Add sample, curation operation, import source CRUD
- `anvil/services/datasets.py` - Delegate to new curation services
- `anvil/api/v1/datasets.py` - Add curation/import/export endpoints
- `anvil/api/v1/router.py` - Register new routes
- `anvil/api/templates/datasets.html` - Link to curation UI, show metrics

## Data Flow

```
User uploads file
  → POST /v1/datasets/{id}/import
  → DatasetImportService parses file (streaming for large files)
  → Preview first N rows returned to user
  → User confirms → atomic SQLite transaction:
      1. Create ImportSource record
      2. Write sample files to LocalFileStore
      3. Insert Sample rows in bulk
      4. Create CurationOperation (type=import)
      5. Update Dataset.sample_count, status
  → On failure: rollback transaction (no partial data)

User clicks "Remove Duplicates"
  → POST /v1/datasets/{id}/curate/dedup
  → DatasetCurationService:
      1. Find duplicates by content_hash
      2. Soft-delete duplicates (set is_removed=true)
      3. Create CurationOperation record
      4. Update Dataset.sample_count

User clicks "Export as JSONL"
  → GET /v1/datasets/{id}/export?format=jsonl
  → DatasetExportService:
      1. Query active samples (is_removed=false)
      2. Read text from LocalFileStore
      3. Stream as JSONL response
```

## Implementation Order

1. DB migration (new tables, indexes)
2. Extend Dataset model + DatasetRepository
3. DatasetImportService (parse, validate, bulk insert, atomicity)
4. DatasetCurationService (dedup, filter, replace)
5. DatasetExportService (format, stream)
6. API endpoints
7. UI template (dataset_detail.html)
8. Tests

## Key Constraints

- **No new pip dependencies** — all functionality built with existing deps
- **Async throughout** — services use async SQLAlchemy + aiofiles
- **Layer discipline** — Repository → Service → API (no shortcuts)
- **Atomicity** — imports are all-or-nothing; curation ops use soft-delete
- **No inline imports** — all imports at module level
- **Strict typing** — all function signatures typed