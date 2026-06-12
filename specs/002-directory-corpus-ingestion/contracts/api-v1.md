# API Contracts: Directory Corpus Ingestion

**Version**: v1 | **Base URL**: `http://<host>:8080/v1/`

Follows the standard conventions defined in `specs/001-bootstrap-llm-workbench/contracts/api-v1.md`:
- JSON envelope: `{ "data": ..., "error": null }` or `{ "data": null, "error": { ... } }`
- Error codes: VALIDATION_ERROR (422), NOT_FOUND (404), CONFLICT (409), INTERNAL_ERROR (500)
- Cursor-based pagination: `?cursor=<cursor>&limit=20`

---

## Corpora

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/corpora` | Create a new corpus (metadata only, no ingestion) |
| GET | `/v1/corpora` | List all corpora |
| GET | `/v1/corpora/{id}` | Get corpus details |
| DELETE | `/v1/corpora/{id}` | Delete corpus and its file records |
| POST | `/v1/corpora/{id}/ingest` | Walk directory, chunk files, update counts |
| GET | `/v1/corpora/{id}/files` | List files in a corpus (paginated) |
| GET | `/v1/corpora/{id}/files/{file_id}` | Get single file details |

### POST /v1/corpora

Create a new corpus (metadata registration only — does NOT walk the directory).

**Request Body**:
```json
{
  "name": "my-repo",
  "description": "Training on my Python project",
  "root_path": "/home/user/projects/my-repo",
  "include_patterns": ["**/*.py", "**/*.md"],
  "exclude_patterns": ["tests/", "docs/"],
  "chunking_strategy": "windowed",
  "chunk_overlap": 0.5
}
```

**Fields**:
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | yes | — | Unique corpus name |
| `description` | string | no | null | Human-readable description |
| `root_path` | string | yes | — | Absolute path to directory |
| `include_patterns` | array[string] | no | null (all defaults) | Glob patterns to include |
| `exclude_patterns` | array[string] | no | null | Glob patterns to exclude (merged with system defaults) |
| `chunking_strategy` | string | no | `"windowed"` | One of: `"line"`, `"windowed"`, `"file"` |
| `chunk_overlap` | float | no | `0.5` | Overlap ratio (0.0-1.0) for windowed strategy |

**Response (201)**:
```json
{
  "data": {
    "id": 1,
    "name": "my-repo",
    "root_path": "/home/user/projects/my-repo",
    "chunking_strategy": "windowed",
    "file_count": 0,
    "document_count": 0,
    "created_at": "2026-06-11 12:00:00"
  },
  "error": null
}
```

**Errors**:
- 422: Validation failure (name missing, root_path doesn't exist, invalid strategy)
- 409: Name already exists

---

### GET /v1/corpora

List all corpora. Supports cursor-based pagination.

**Query Params**: `?cursor=<cursor>&limit=20`

**Response (200)**:
```json
{
  "data": [
    {
      "id": 1,
      "name": "my-repo",
      "root_path": "/home/user/projects/my-repo",
      "chunking_strategy": "windowed",
      "file_count": 42,
      "document_count": 187,
      "created_at": "2026-06-11 12:00:00"
    }
  ],
  "next_cursor": "eyJpZCI6...",
  "has_more": false
}
```

---

### GET /v1/corpora/{id}

Get full corpus details including aggregate stats and language breakdown.

**Response (200)**:
```json
{
  "data": {
    "id": 1,
    "name": "my-repo",
    "description": "Training on my Python project",
    "root_path": "/home/user/projects/my-repo",
    "include_patterns": ["**/*.py", "**/*.md"],
    "exclude_patterns": ["tests/", "docs/"],
    "chunking_strategy": "windowed",
    "chunk_overlap": 0.5,
    "file_count": 42,
    "document_count": 187,
    "language_map": {
      "Python": 30,
      "Markdown": 12
    },
    "created_at": "2026-06-11 12:00:00",
    "updated_at": "2026-06-11 12:05:00"
  },
  "error": null
}
```

**Errors**:
- 404: Corpus not found

---

### DELETE /v1/corpora/{id}

Delete a corpus and all associated CorpusFile records.

**Response (200)**:
```json
{
  "data": { "status": "deleted" },
  "error": null
}
```

**Errors**:
- 404: Corpus not found

---

### POST /v1/corpora/{id}/ingest

Walk the directory, apply include/exclude filters, chunk files, update counts and file records. Idempotent — re-ingestion updates existing records.

**Request Body**: None (uses corpus configuration)

**Response (200)**:
```json
{
  "data": {
    "corpus_id": 1,
    "file_count": 42,
    "document_count": 187,
    "language_map": {
      "Python": 30,
      "Markdown": 12
    },
    "errors": [],
    "skipped": []
  },
  "error": null
}
```

**Errors**:
- 404: Corpus not found
- 422: Corpus root_path no longer exists

**Progress**: For large directories, ingestion may be slow. The endpoint is synchronous in v1. Future versions may add async ingestion with SSE progress.

---

### GET /v1/corpora/{id}/files

List files in a corpus. Supports cursor-based pagination. Optionally filter by language.

**Query Params**: `?cursor=<cursor>&limit=20&language=Python`

**Response (200)**:
```json
{
  "data": [
    {
      "id": 1,
      "corpus_id": 1,
      "relative_path": "src/main.py",
      "language": "Python",
      "line_count": 120,
      "char_count": 3400,
      "chunk_count": 8,
      "size_bytes": 3600,
      "last_modified": "2026-06-10 15:30:00"
    }
  ],
  "next_cursor": "eyJpZCI6...",
  "has_more": false
}
```

---

### GET /v1/corpora/{id}/files/{file_id}

Get a single file's details.

**Response (200)**: Same shape as file object above.

**Errors**:
- 404: Corpus or file not found

---

## TrainingConfig Changes

### POST /v1/training/start

**MODIFIED** — accepts an optional `corpus_id` field:

```json
{
  "num_steps": 1000,
  "n_embd": 16,
  "n_head": 4,
  "learning_rate": 0.01,
  "temperature": 0.5,
  "corpus_id": 1
}
```

When `corpus_id` is provided, the training service loads documents from the corpus instead of `input.txt`. When omitted, existing behavior (read `input.txt`) is preserved.

---

## Web UI Changes

### datasets.html

Add a "Corpora" section below the existing Dataset Manager:
- List corpora with their stats (files, docs, language breakdown)
- "Ingest" button per corpus (triggers POST /v1/corpora/{id}/ingest)
- "Create Corpus" form with fields: name, root_path, include/exclude patterns, chunking strategy
- File browser view per corpus (expandable tree or list)
- Follow existing retro terminal style (ls-like listing)

### training.html

Add a corpus selector dropdown next to the training config:
- Label: "Training Data Source"
- Options: "input.txt (default)" | each available corpus by name
- When a corpus is selected, sends `corpus_id` in the POST /v1/training/start body