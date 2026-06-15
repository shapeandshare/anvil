# Research: Bootstrap Demo Datasets

**Phase 0 output** — consolidated findings from codebase investigation and external research.

## 1. Corpus Ingestion Pipeline

### Decision
Reuse the existing corpus ingestion pipeline (`CorpusService` + `CorpusLoader`) as the primary import path for demo corpora. For `.txt` dataset uploads, reuse `DatasetImportService.commit_import()`.

### Pipeline Flow
- **Corpus path**: `CorpusService.create()` → `CorpusService.ingest()` → stored in DB as `Corpus` records with `CorpusFile` children
- **Dataset path**: `DatasetService.create()` → `DatasetImportService.commit_import()` → stored as `Sample` records + text files in `data/datasets/`
- **Training loading**: `TrainingService._load_docs()` checks `dataset_id` first, then `corpus_id`, then falls back to default

### Key Findings
- Both `cli.py` and `training.py` have an identical `names.txt` download fallback — both must be modified
- Corpus ingestion supports chunking strategies: `line`, `windowed`, `file`. Demo should use `file` strategy for small files and `windowed` for larger ones
- `CorpusService.create()` creates only a DB record — `ingest()` must be called separately to scan the directory
- `DatasetImportService` requires a pre-existing `Dataset` record before importing into it
- `commit_corpus_import(docs)` joins docs with `\n` and calls `commit_import(text, fmt="corpus")` which splits on `\n` — so each doc becomes one sample
- Both services require an `AsyncSession` but do NOT commit — the caller is responsible for `session.commit()`

### CorpusService Method Signatures

| Method | Signature |
|--------|-----------|
| `create(name, root_path, description, include_patterns, exclude_patterns, chunking_strategy="windowed", chunk_overlap=0.5, block_size=16)` | Returns `Corpus` |
| `ingest(id, max_files=10000)` | Returns `tuple[Corpus, list[str]]` — updated corpus + error list |
| `load_docs(corpus_id)` | Returns `list[str]` — all chunks |
| `get(id)`, `list()`, `delete(id)`, `get_files(id, language=None)`, `get_file(file_id)` | |

### DatasetService Method Signatures

| Method | Signature |
|--------|-----------|
| `create_dataset(name, description=None)` | Returns `Dataset` |
| `get_dataset(id)`, `list_datasets()`, `search_datasets(query)`, `delete_dataset(id)`, `update_dataset(id, name=None, description=None)` | |
| `load_docs(dataset_id)` | Returns `list[str]` — reads samples from `LocalFileStore` |

### DatasetImportService Method Signatures

| Method | Signature |
|--------|-----------|
| `commit_import(text, fmt="txt")` | Returns `ImportResult` |
| `commit_corpus_import(docs)` | Returns `ImportResult` — joins with `\n`, calls `commit_import` with `fmt="corpus"` |

### Corpus DB Model
- **Table**: `corpora`
- **Key columns**: `id`, `name` (unique), `root_path`, `chunking_strategy`, `chunk_overlap`, `block_size`, `file_count`, `document_count`, `language_map`, `errors`
- **`CorpusFile` table**: `corpus_id` (FK), `relative_path`, `language`, `size_bytes`, `line_count`, `char_count`, `chunk_count`

### Dataset DB Model
- **Table**: `datasets`
- **Key columns**: `id`, `name` (unique), `description`, `sample_count`, `total_size_bytes`, `curation_version`, `status` ("empty"/"importing"/"ready")

## 2. CLI Structure

### Decision
Add a new CLI top-level command `anvil-bootstrap-datasets` following the exact pattern of `anvil-corpus`.

### Patterns
- Entry points in `pyproject.toml` lines 54-58:
  ```toml
  anvil = "anvil.cli:serve"
  anvil-train = "anvil.cli:train"
  anvil-corpus = "anvil.cli:corpus_main"
  anvil-stop = "anvil.cli:stop"
  anvil-migrate-registry = "anvil.cli:migrate_registry"
  ```
- `corpus_main()` at line 267 shows the subcommand dispatch pattern: `argparse.ArgumentParser` → `subparsers` → `asyncio.run(_run())`
- Bootstrap command has no subcommands — it's a straightforward single-action command
- The `_load_docs()` in `cli.py` (lines 36-60) is a module-level function (not on TrainingService), used only by the CLI `train()` function

## 3. Training Fallback Replacement

### Decision
Remove the `names.txt` URL download from both `cli.py:_load_docs()` (lines 54-56) and `training.py:TrainingService._load_docs()` (lines 80-84). Replace with a lookup to the default demo corpus by well-known name.

### Design
- The default demo corpus will have a fixed name (e.g., `"Demo - names"`)
- Both `_load_docs()` functions will query for it by name when no `corpus_id`/`dataset_id` is provided
- If the default corpus doesn't exist (bootstrap hasn't run), raise a helpful error: `"No demo data found. Run 'anvil bootstrap-datasets' first."`
- The `cli.py` train `--help` text should be updated from `"default: input.txt"` to `"default: bundled demo corpus"`

## 4. Inference DEMO_CORPUS Replacement

### Decision
Replace the hardcoded `DEMO_CORPUS` list in `inference.py` with data drawn from one of the curated demo datasets/corpora. The demo model pre-training at startup should:
1. Check if a demo dataset with a known name exists in the DB via `DatasetService`
2. If yes, load a small subset for training the demo model
3. If not, use a minimal embedded fallback (2-3 lines, much smaller than current 8 lines)
4. The bootstrapped demo model should still train with the same hyperparameters (400 steps, etc.)

### Current code locations
- `DEMO_CORPUS` at `anvil/services/inference.py` lines 15-24
- `_train_demo_model()` at lines 28-42
- `DemoModelProvider.get_model()` at lines 55-76
- Pre-training trigger at `anvil/api/app.py` lines 38-44 (FastAPI lifespan startup)

## 5. Public Domain Text Sources

### Decision
Use the following public-domain/permissively-licensed texts for demo data:

| File | Source | Approx Size | License |
|------|--------|-------------|---------|
| `first-names.txt` | karpathy/makemore `names.txt` | ~5 KB (subset) | MIT |
| `hello.py` + `factorial.py` | Hand-crafted code snippets | ~2 KB each | Generated (no license issue) |
| `presidents.txt` | US State of the Union (Washington) - Gutenberg #5010 | ~30 KB | Public Domain (US Gov) |
| `chapter-01.txt` | Alice in Wonderland - Gutenberg #11 | ~25 KB (chapter 1 only) | Public Domain |
| `math-facts.txt` | Hand-crafted structured facts | ~10 KB | Generated (no license issue) |
| `part-01.txt`, `part-02.txt` | Metamorphosis (Kafka) - alternate PD translation needed OR Gutenberg #844 "Importance of Being Earnest" | ~40 KB each or ~100 KB | Public Domain (earnest) |
| `sonnet-18.txt`, etc. | Shakespeare Sonnets - Gutenberg #1041 | ~10 KB subset | Public Domain |

**Total estimate**: ~250-350 KB (well under 500 KB limit)

**Note on Metamorphosis**: The Wyllie translation on Gutenberg is copyrighted. Alternative: use "The Importance of Being Earnest" by Oscar Wilde (Gutenberg #844, ~100 KB, public domain).

### License Notes
- **Project Gutenberg texts**: Public domain in the USA
- **US Government works**: Public domain under 17 U.S.C. § 105
- **Karpathy's names.txt**: MIT license (from makemore repo)
- **Hand-crafted content**: No licensing concerns

## 6. Demo Directory Structure

### Decision
```
data/demo/
├── README.md                              # Overview of demo data
├── small/
│   ├── names/                             # Corpus: directory of name files
│   │   ├── first-names.txt                # ~5KB: subset of common first names (MIT)
│   │   └── last-names.txt                 # ~5KB: subset of common surnames
│   ├── hello-world/                       # Corpus: tiny code snippets
│   │   ├── hello.py                       # ~1KB: "hello world" in Python
│   │   ├── factorial.py                   # ~1KB: factorial function
│   │   └── fizzbuzz.py                    # ~1KB: fizzbuzz
│   └── presidents.txt                     # Dataset: Washington's addresses (~30KB, PD)
├── medium/
│   ├── alice/                             # Corpus: Alice in Wonderland excerpt
│   │   ├── chapter-01.txt                 # ~25KB: Down the Rabbit-Hole (PD)
│   │   └── chapter-02.txt                 # ~20KB: The Pool of Tears (PD)
│   └── math-facts.txt                     # Dataset: structured math facts (~10KB)
└── large/
    └── earnest/                           # Corpus: The Importance of Being Earnest
        ├── act-i.txt                      # ~35KB: Oscar Wilde play, Act I (PD)
        ├── act-ii.txt                     # ~35KB: Act II
        └── act-iii.txt                    # ~30KB: Act III
```

### Corpus configuration
- `small/names/` → chunking: `file` strategy (each file = 1 doc)
- `small/hello-world/` → chunking: `file` strategy
- `medium/alice/` → chunking: `windowed` strategy, `block_size=64`, `overlap=0.25`
- `large/earnest/` → chunking: `windowed`, `block_size=128`, `overlap=0.25`

## 7. Bootstrap Command Design

### Algorithm (pseudocode for `DemoBootstrapService`)

```python
async def bootstrap_demo_data():
    DEMO_DIR = Path("data/demo")
    session = AsyncSession()
    
    corpus_svc = CorpusService(CorpusRepository(session), CorpusLoader())
    ds_svc = DatasetService(DatasetRepository(session))
    
    for size_dir in sorted(DEMO_DIR.iterdir()):  # small, medium, large
        if not size_dir.is_dir() or size_dir.name.startswith("."):
            continue
        for item in sorted(size_dir.iterdir()):
            if item.is_dir():
                name = f"Demo - {size_dir.name}/{item.name}"
                # Check idempotency
                existing = await find_corpus_by_name(name)
                if existing:
                    print(f"  ✓ Corpus '{name}' already exists, skipping")
                    continue
                corpus = await corpus_svc.create(
                    name=name,
                    root_path=str(item.absolute()),
                    chunking_strategy=_strategy_for(item),
                    block_size=_block_size_for(item),
                    chunk_overlap=_overlap_for(item),
                )
                await corpus_svc.ingest(corpus.id)
                print(f"  ✓ Created corpus '{name}' (id={corpus.id})")
            elif item.suffix == ".txt":
                name = f"Demo - {size_dir.name}/{item.stem}"
                existing = await find_dataset_by_name(name)
                if existing:
                    print(f"  ✓ Dataset '{name}' already exists, skipping")
                    continue
                dataset = await ds_svc.create_dataset(name=name)
                text = item.read_text(encoding="utf-8")
                import_svc = DatasetImportService(session, dataset.id)
                await import_svc.commit_import(text, fmt="txt")
                print(f"  ✓ Created dataset '{name}' (id={dataset.id})")
    
    await session.commit()
```

### Strategies
| Path | Strategy | Block Size | Overlap |
|------|----------|------------|---------|
| `small/names/` | `file` | 16 | N/A |
| `small/hello-world/` | `file` | 16 | N/A |
| `medium/alice/` | `windowed` | 64 | 0.25 |
| `large/earnest/` | `windowed` | 128 | 0.25 |

## 8. Files to Create/Modify

### New files
| File | Purpose |
|------|---------|
| `anvil/services/demo_bootstrap.py` | `DemoBootstrapService` — orchestrates demo data import |
| `data/demo/README.md` | Overview of demo data contents and licensing |
| `data/demo/small/names/first-names.txt` | Name list (MIT licensed) |
| `data/demo/small/names/last-names.txt` | Name list |
| `data/demo/small/hello-world/hello.py` | Code snippet |
| `data/demo/small/hello-world/factorial.py` | Code snippet |
| `data/demo/small/hello-world/fizzbuzz.py` | Code snippet |
| `data/demo/small/presidents.txt` | US State of Union (public domain) |
| `data/demo/medium/alice/chapter-01.txt` | Alice excerpt (public domain) |
| `data/demo/medium/alice/chapter-02.txt` | Alice excerpt |
| `data/demo/medium/math-facts.txt` | Structured facts (generated) |
| `data/demo/large/earnest/act-i.txt` | Wilde play (public domain) |
| `data/demo/large/earnest/act-ii.txt` | Wilde play |
| `data/demo/large/earnest/act-iii.txt` | Wilde play |
| `tests/test_bootstrap.py` | Tests for bootstrap flow |

### Modified files
| File | Change |
|------|--------|
| `pyproject.toml` | Add `anvil-bootstrap-datasets` console_scripts entry |
| `anvil/cli.py` | Add `bootstrap_datasets_main()`, modify `_load_docs()` fallback |
| `anvil/services/training.py` | Modify `_load_docs()` fallback in `TrainingService` |
| `anvil/services/inference.py` | Replace `DEMO_CORPUS` with DB-backed demo data lookup |
| `anvil/api/app.py` | Update demo model pre-training to work with new lookup |
| `tests/services/test_training.py` | Update tests for new fallback behavior |

## Open Questions Addressed in Clarify Phase

| Question | Answer |
|----------|--------|
| Bootstrap idempotency | Match by dataset/corpus name |
| Deletion lifecycle | Allow with warning; re-bootstrap recreates |
| Content organization | Directory corpora primary, 3 sizes × 4 domains |