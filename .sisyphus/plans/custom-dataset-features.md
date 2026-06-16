# Custom Dataset Features Implementation Plan

## Overview
Two features: (1) Clone/Fork a dataset, (2) Create dataset from corpus with custom chunking.

---

## Shared Infrastructure

### `commit_docs_import()` in `DatasetImportService`
- **File**: `anvil/services/dataset_import.py`
- Import `list[str]` where each string becomes exactly one sample (no re-parsing/join-split)
- Follow same pipeline as `commit_import()` lines 87–153: ImportSource → Sample records → file writes → CurationOperation → Dataset stats
- Fixes existing fragmentation bug in `commit_corpus_import()`
- Signature: `async commit_docs_import(docs: list[str], source_label: str = "import", source_format: str = "docs") -> ImportResult`
- Build `ParsedSample` directly from input (no `_parse()`), preserve content byte-for-byte
- Use `"docs"` format for ImportSource

### QA: commit_docs_import()
1. Unit test via pytest: call `commit_docs_import(["hello world", "line2\nwith\nnewlines", "  spaced  "])` on a fresh dataset
2. Verify each doc became exactly one Sample record (3 samples, NOT more)
3. Verify embedded newlines preserved: `line2\nwith\nnewlines` is intact, not split
4. Verify whitespace preserved: `  spaced  ` is not stripped
5. Verify ImportSource created with correct source_label and source_format
6. Verify CurationOperation created with type "import"
7. Verify Dataset.sample_count, total_size_bytes, curation_version, status="ready"

---

## Feature 1: Clone Dataset

### Route: `POST /v1/datasets/{id}/clone`
- **File**: `anvil/api/v1/datasets.py`
- **Pydantic body**: `CloneDatasetBody(name: str, description: str | None = None)`
- Flow:
  1. Validate source dataset exists (404)
  2. Validate name is unique (422)
  3. Get active samples via `SampleRepository.get_active_texts(id)`
  4. Read sample content from `LocalFileStore("data/datasets")`
  5. Create new dataset via `DatasetService.create_dataset(name, description or source.description)`
  6. Call `commit_docs_import(docs, source_label=f"clone:dataset-{id}", source_format="clone")`
- Response: serialized new dataset

### Frontend: Clone button on dataset table
- **File**: `anvil/api/templates/datasets.html`
- Add "fork" button to each dataset row in the combined table + dataset list
- Click opens inline form with name + description inputs (pre-filled: "{name} (copy)")
- Calls `POST /v1/datasets/{id}/clone`

### QA: Clone Dataset
1. Via pytest or direct HTTP test (FastAPI TestClient):
   - POST to `/v1/datasets/{id}/clone` with valid body → 200, new dataset returned
   - Verify cloned samples count matches source active samples count
   - Verify cloned sample content is byte-identical to source (read both from LocalFileStore)
   - Verify clone has fresh `import_source_id`, NOT referencing source's import sources
   - Verify clone's `curation_version=1` (fresh), source unchanged
   - POST with duplicate name → 422
   - POST with nonexistent id → 404
   - POST on empty dataset (0 active samples) → 422
2. UI verification (manual/Playwright):
   - "fork" button visible on dataset rows in both dataset list and combined table
   - Click opens inline form with pre-filled name
   - Submit creates new dataset, shows in list

---

## Feature 2: Create Dataset from Corpus with Custom Chunking

### Route: `POST /v1/datasets/from-corpus`
- **File**: `anvil/api/v1/datasets.py`
- **Pydantic body**: `CreateFromCorpusBody(corpus_id: int, name: str, description: str | None = None, chunking_strategy: str, block_size: int | None = None, chunk_overlap: float | None = None)`
- Strategy params: block_size required when strategy="windowed"; overlap defaults to 0.25 if not provided
- Flow:
  1. Load corpus, validate exists (404)
  2. Validate dataset name is unique (422)
  3. Decode `include_patterns`/`exclude_patterns` via `json.loads()` (handle None)
  4. Instantiate `CorpusLoader` directly, call `ingest()` with corpuss root + patterns + new chunking params
  5. Read each file from disk using file relative paths from ingest result, re-chunk with new params
  6. Create new dataset via `DatasetService.create_dataset()`
  7. Call `commit_docs_import(docs, source_label=f"corpus:{corpus_id}", source_format="docs")`

### Frontend: Custom chunking import in Corpora tab
- **File**: `anvil/api/templates/datasets.html`
- Add "Import as Dataset" section at bottom of Corpora tab (after corpus list)
- Corpus selector (dropdown of existing corpora, reusing `populateImportSelects`-like logic)
- Chunking params: strategy selector, block_size slider (shown for windowed), overlap slider (shown for windowed)
- Name + description inputs
- "Create Dataset" button → calls `POST /v1/datasets/from-corpus`

### QA: Create Dataset from Corpus with Custom Chunking
1. Via pytest or FastAPI TestClient:
   - POST to `/v1/datasets/from-corpus` with corpus_id, valid params → 200
   - Verify dataset created with correct name
   - Verify sample count matches expected chunk count for chosen params
   - POST with windowed strategy and block_size=256 on a corpus → verify chunks are ~256 chars (not split on newlines)
   - POST with nonexistent corpus_id → 404
   - POST with duplicate name → 422
   - POST with windowed strategy but no block_size → 422
2. UI verification (manual/Playwright):
   - Corpus selector shows all corpora
   - Strategy selector shows windowed/file/line options
   - block_size/overlap sliders visible only when windowed selected
   - Submit creates dataset, appears in dataset list

---

## Implementation Order

```
STEP 1: commit_docs_import() ──── shared, unblocks both
        (dataset_import.py)

STEP 2a & 2b are INDEPENDENT — can be parallel:
  ├── STEP 2a: Clone route (datasets.py)
  └── STEP 2b: Corpus→dataset route (datasets.py)

STEP 3a & 3b are INDEPENDENT — can be parallel:
  ├── STEP 3a: Clone UI (datasets.html)
  └── STEP 3b: Custom chunking UI (datasets.html)
```

## Key Constraints
1. Sample text is in `LocalFileStore("data/datasets")` files, NOT in DB columns
2. Always filter `is_removed=False` via `SampleRepository.get_active_texts()`
3. New `commit_docs_import()` does NOT strip/split content — preserves byte-for-byte
4. Clone MUST NOT inherit `is_default=True` from source
5. Corpus `include_patterns`/`exclude_patterns` are JSON strings in DB — must `json.loads()` them
6. All operations at route level (orchestrate services from session), not inside DatasetService