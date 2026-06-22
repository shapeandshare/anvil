# Data Model: Bootstrap Demo Datasets

**Phase 1 output** — entity definitions for demo data bootstrapping.

## Overview

This feature reuses existing entities (`Corpus`, `Dataset`, `CorpusFile`, `Sample`) with no new database tables. The key design is naming convention and directory discovery logic — no schema changes required.

## Existing Entities (Reused)

### Corpus (existing — unchanged)

| Field | Type | Notes |
|-------|------|-------|
| `id` | int (PK) | Auto-increment |
| `name` | str(255) | **Unique**. Naming convention: `"Demo - {size}/{name}"` (e.g., `"Demo - small/names"`) |
| `root_path` | str(500) | Absolute path to `data/demo/{size}/{name}` directory |
| `chunking_strategy` | str(20) | `"file"` for small dirs, `"windowed"` for large dirs |
| `chunk_overlap` | float | `0.25` for windowed, `0.0` for file |
| `block_size` | int | `16` for small, `64-128` for large |
| `description` | str(1000) | Brief description including license/source attribution |
| `file_count` | int | Set by `ingest()` |
| `document_count` | int | Set by `ingest()` |
| `language_map` | str (JSON) | Set by `ingest()` |

**Demo corpus naming convention**: `"Demo - {size}/{name}"` — e.g.:
- `"Demo - small/names"`
- `"Demo - medium/alice"`
- `"Demo - large/earnest"`

### Dataset (existing — unchanged)

| Field | Type | Notes |
|-------|------|-------|
| `id` | int (PK) | Auto-increment |
| `name` | str(255) | **Unique**. Naming convention: `"Demo - {size}/{stem}"` (e.g., `"Demo - small/presidents"`) |
| `description` | str(1000) | Brief description with license info |
| `status` | str(20) | `"ready"` after bootstrap import |

**Demo dataset naming convention**: `"Demo - {size}/{stem}"` — e.g.:
- `"Demo - small/presidents"`
- `"Demo - medium/math-facts"`

### CorpusFile (existing — unchanged)
Created by `CorpusService.ingest()`. Each text file in a corpus directory becomes one `CorpusFile` record with metadata (language, line count, size, etc.).

### Sample (existing — unchanged)
Created by `DatasetImportService.commit_import()`. Each non-empty parsed line/record becomes one `Sample` with content stored in `LocalFileStore`.

## Demo-Specific Logic (New, No Schema)

### DemoDataRegistry (naming convention)
Rather than a new DB table, demo entities are identified by name prefix:
- **Demo corpora**: Names starting with `"Demo - "`
- **Demo datasets**: Names starting with `"Demo - "`

Lookup queries:
```python
# Find a demo corpus by its short name
corpus_name = "Demo - small/names"
corpus = session.query(Corpus).filter(Corpus.name == corpus_name).first()

# List all demo corpora
demo_corpora = session.query(Corpus).filter(Corpus.name.like("Demo - %")).all()

# Find default training corpus
default_corpus = session.query(Corpus).filter(Corpus.name == "Demo - medium/alice").first()
```

### Idempotency
When running bootstrap, check by exact name match:
```python
async def _corpus_exists(name: str) -> bool:
    return await repo.get_by_name(name) is not None  # needs get_by_name method

async def _dataset_exists(name: str) -> bool:
    return await ds_repo.get_by_name(name) is not None
```

## State Transitions

### Corpus lifecycle
```
Bootstrap: Corpus.create() → Corpus.ingest() → status: ready (implicit via file_count > 0)
Deletion:   User deletes via UI/API (with warning) → DB record removed
Re-bootstrap: Name check → no existing match → create fresh
```

### Dataset lifecycle
```
Bootstrap: Dataset.create() → DatasetImportService.commit_import() → status: "ready"
Deletion:   User deletes via UI/API (with warning) → DB record + sample files removed
Re-bootstrap: Name check → no existing match → create fresh
```

## File Layout (Not in DB)

```
data/demo/                          # Source of truth for demo data
├── README.md                       # Overview, licensing, attribution
├── small/
│   ├── names/                      # → Corpus "Demo - small/names"
│   ├── hello-world/                # → Corpus "Demo - small/hello-world"
│   └── presidents.txt              # → Dataset "Demo - small/presidents"
├── medium/
│   ├── alice/                      # → Corpus "Demo - medium/alice"
│   └── math-facts.txt             # → Dataset "Demo - medium/math-facts"
└── large/
    └── earnest/                    # → Corpus "Demo - large/earnest"

data/datasets/                      # Runtime storage (created by import)
└── {dataset_id}/
    └── {import_source_id}/
        └── {index}.txt             # Each sample as individual file
```