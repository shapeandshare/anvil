# Quickstart: Directory Corpus Ingestion

**Phase**: Phase 1 — Quickstart Guide
**Date**: 2026-06-11

## CLI Usage

```bash
# Create a corpus (register metadata)
microgpt corpus create /path/to/project \
    --name "my-project" \
    --description "Training on my Python project" \
    --pattern "**/*.py" \
    --pattern "**/*.md" \
    --ignore "tests/" \
    --strategy windowed \
    --overlap 0.5

# Ingest the corpus (walk directory, chunk files)
microgpt corpus ingest 1

# List all corpora
microgpt corpus list

# Show corpus details
microgpt corpus show 1

# List files in a corpus
microgpt corpus files 1

# Delete a corpus
microgpt corpus delete 1

# Train using a corpus
microgpt train --corpus 1 --steps 1000
```

## Web UI Usage

1. Navigate to `/datasets` in the web UI
2. Use the "Corpora" section to create a new corpus
3. Fill in: name, root path, file patterns, chunking strategy
4. Click "Create" → then "Ingest" to walk the directory
5. Navigate to `/training` in the web UI
6. Select the corpus from the "Training Data Source" dropdown
7. Configure hyperparameters and click "Start Training"

## API Usage

```bash
# Create a corpus
curl -X POST http://localhost:8080/v1/corpora \
    -H "Content-Type: application/json" \
    -d '{
        "name": "my-project",
        "root_path": "/path/to/project",
        "include_patterns": ["**/*.py"],
        "chunking_strategy": "windowed"
    }'

# Ingest
curl -X POST http://localhost:8080/v1/corpora/1/ingest

# List corpora
curl http://localhost:8080/v1/corpora

# Start training with corpus
curl -X POST http://localhost:8080/v1/training/start \
    -H "Content-Type: application/json" \
    -d '{
        "num_steps": 1000,
        "corpus_id": 1
    }'

# List corpus files
curl http://localhost:8080/v1/corpora/1/files
```

## Chunking Strategies

| Strategy | Flag | Description | Best For |
|----------|------|-------------|----------|
| Line | `--strategy line` | Each non-empty line = one doc | Simple corpora, backward compat |
| Windowed | `--strategy windowed` | Sliding window of `block_size` chars (default 50% overlap) | Source code, multi-line patterns |
| File | `--strategy file` | Entire file = one doc (truncated to block_size) | Small files, prose |

## Default Ignore Patterns

The following directories are always excluded (merged with user-specified excludes):

```
.git/
__pycache__/
node_modules/
venv/
.venv/
.env/
.hg/
.svn/
build/
dist/
*.pyc
*.pyo
*.so
*.dll
*.dylib
*.png
*.jpg
*.jpeg
*.gif
*.svg
*.ico
*.woff
*.ttf
*.exe
```

## Backward Compatibility

- Existing `input.txt` training works unchanged (no `corpus_id` = old behavior)
- Existing dataset upload via `/v1/datasets/upload` works unchanged
- `TrainingConfig.dataset_id` FK is preserved (renamed to `corpus_id`)
- The `train()` function in `core/engine.py` receives the same `list[str]` — no changes needed