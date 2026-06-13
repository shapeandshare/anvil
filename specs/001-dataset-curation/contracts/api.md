# API Contracts: Dataset Curation

**Date**: 2026-06-12
**Status**: Draft

## Existing Endpoints (Extended)

### GET /v1/datasets

List all datasets with curation stats.

**Response** (200):
```json
{
  "data": {
    "datasets": [
      {
        "id": 1,
        "name": "My Dataset",
        "description": "...",
        "sample_count": 10000,
        "total_size_bytes": 5242880,
        "status": "ready",
        "curation_version": 3,
        "created_at": "2026-06-12T10:00:00Z",
        "updated_at": "2026-06-12T14:30:00Z"
      }
    ]
  },
  "error": null
}
```

### GET /v1/datasets/{id}

Get single dataset details.

**Response** (200): Same schema as above, plus curation operation history summary.

### DELETE /v1/datasets/{id}

Delete dataset. Blocked if training configs reference it.

**Response** (200): `{"data": {"message": "Dataset deleted"}, "error": null}`
**Response** (409): `{"data": null, "error": "Cannot delete dataset: 2 training configs reference it: ['run-001', 'run-002']"}`

## New Endpoints

### GET /v1/datasets/{id}/samples

Paginated sample listing for curation browsing.

**Query params**: `offset` (int, default 0), `limit` (int, default 50), `search` (str, optional)

**Response** (200):
```json
{
  "data": {
    "samples": [
      {
        "id": 1,
        "index": 0,
        "text_preview": "The first 200 characters...",
        "length": 1500,
        "content_hash": "abc123..."
      }
    ],
    "total": 10000,
    "offset": 0,
    "limit": 50
  },
  "error": null
}
```

### PUT /v1/datasets/{id}/samples/{sample_id}

Edit a single sample's text content.

**Request body**: `{"text": "new text content"}`
**Response** (200): `{"data": {"sample_id": 1, "length": 42}, "error": null}`

### DELETE /v1/datasets/{id}/samples/{sample_id}

Delete (soft) a single sample.

**Response** (200): `{"data": {"message": "Sample removed"}, "error": null}`

### POST /v1/datasets/{id}/import

Import data into a dataset (atomic append).

**Request body** (multipart/form-data):
- `file`: File upload (txt, csv, jsonl, json) — OR —
- `text`: Raw text paste — OR —
- `source_type`: "corpus", `corpus_id`: int — Import from existing corpus

**Response** (200):
```json
{
  "import_source_id": 5,
  "rows_imported": 5000,
  "errors": [],
  "preview": [
    {"index": 0, "text_preview": "First 200 chars..."}
  ]
}
```

**Errors**:
- **400**: Parsing errors with row-level detail
- **422**: All rows malformed

### GET /v1/datasets/{id}/preview

Preview parsed data before committing import (used during import flow).

**Query params**: `format`, `preview_rows` (default 20)
**Request body**: same as import (file/text/corpus_id)

**Response** (200): Same preview format as import response.

### POST /v1/datasets/{id}/curate/dedup

Remove exact duplicate samples.

**Response** (200):
```json
{
  "operation_id": 10,
  "samples_removed": 150,
  "samples_before": 10000,
  "samples_after": 9850
}
```

### POST /v1/datasets/{id}/curate/filter

Filter by text length.

**Request body**: `{"min_length": 50, "max_length": 10000}` (both optional)
**Response** (200): Same as dedup response.

### POST /v1/datasets/{id}/curate/replace

Regex search and replace.

**Request body**: `{"pattern": "\\s+", "replacement": " ", "case_sensitive": false}`
**Response** (200):
```json
{
  "operation_id": 11,
  "samples_affected": 3000,
  "samples_before": 9850,
  "samples_after": 9850
}
```

### GET /v1/datasets/{id}/export

Export dataset.

**Query params**: `format` (enum: txt, csv, jsonl, required)
**Response**: File download with correct Content-Type and Content-Disposition headers.

| Format | Content-Type | File Extension |
|--------|-------------|----------------|
| txt | text/plain | .txt |
| csv | text/csv | .csv |
| jsonl | application/x-ndjson | .jsonl |

### GET /v1/datasets/{id}/metrics

Get dataset quality metrics.

**Response** (200):
```json
{
  "sample_count": 9850,
  "total_chars": 14750000,
  "estimated_tokens": 3687500,
  "vocabulary_size": 42500,
  "length_distribution": {
    "min": 10,
    "max": 50000,
    "mean": 1497.5,
    "median": 1200
  },
  "duplicate_count": 0
}
```

### GET /v1/datasets/{id}/operations

Get curation operation history.

**Response** (200):
```json
{
  "operations": [
    {
      "id": 10,
      "operation_type": "dedup",
      "parameters": {},
      "sample_count_before": 10000,
      "sample_count_after": 9850,
      "created_at": "2026-06-12T14:00:00Z"
    },
    {
      "id": 5,
      "operation_type": "import",
      "parameters": {"format": "csv", "filename": "data.csv", "row_count": 10000},
      "sample_count_before": 0,
      "sample_count_after": 10000,
      "created_at": "2026-06-12T13:00:00Z"
    }
  ]
}
```

## Error Schema (All Endpoints)

```json
{
  "detail": "Human-readable error message"
}
```

For validation errors:
```json
{
  "detail": [
    {"loc": ["body", "file"], "msg": "field required", "type": "value_error.missing"}
  ]
}
```