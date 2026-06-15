# Quickstart: Bootstrap Demo Datasets

**Phase 1 output** — developer implementation guide.

## Implementation Order

### Step 1: Create demo data files (`data/demo/`)

Create the directory structure and populate with public-domain text files:

1. Create directory tree under `data/demo/` (small/, medium/, large/)
2. Add `first-names.txt` (~5K names from karpathy/makemore names.txt, MIT)
3. Add `hello.py`, `factorial.py`, `fizzbuzz.py` (hand-crafted code snippets)
4. Download Gutenberg #5010 (Washington's addresses) → `presidents.txt`
5. Download Gutenberg #11 ch. 1-2 (Alice in Wonderland) → `medium/alice/`
6. Create `math-facts.txt` (hand-crafted structured records)
7. Download Gutenberg #844 (Importance of Being Earnest) → `large/earnest/`

### Step 2: Create `DemoBootstrapService` (`anvil/services/demo_bootstrap.py`)

New service with methods:
- `bootstrap_all()` → walks `data/demo/`, creates corpora/datasets
- `get_default_corpus()` → returns default training corpus
- `list_demo_corpora()` / `list_demo_datasets()` → list demo entities

### Step 3: Add CLI command

1. Add function `bootstrap_datasets_main()` to `anvil/cli.py`
2. Add entry point to `pyproject.toml`: `anvil-bootstrap-datasets = "anvil.cli:bootstrap_datasets_main"`

### Step 4: Remove training fallback

1. In `anvil/services/training.py:_load_docs()`, replace lines 80-88 with:
   - Query for default demo corpus by name
   - If found, load from corpus
   - If not found, raise informative error

2. In `anvil/cli.py:_load_docs()`, same change on lines 54-60

### Step 5: Update inference demo model

1. In `anvil/services/inference.py`, replace `DEMO_CORPUS`:
   - `_train_demo_model()` takes optional `docs` parameter
   - `DemoModelProvider.get_model()` tries DB lookup first
   - Falls back to tiny embedded corpus (2-3 lines) if no DB available

### Step 6: Add tests

1. `tests/test_bootstrap.py`: Test `DemoBootstrapService` with:
   - Fresh bootstrap (creates all entities)
   - Idempotent re-run (skips all)
   - Mixed success/failure (partial errors)
   - Dry-run mode (no changes made)

2. Update `tests/services/test_training.py`:
   - Test fallback with default corpus present
   - Test fallback with no corpus (error message)

## Key Files Reference

| File | Action | Detail |
|------|--------|--------|
| `pyproject.toml` | Add entry | `anvil-bootstrap-datasets = "anvil.cli:bootstrap_datasets_main"` |
| `anvil/cli.py` | Add function + modify fallback | New `bootstrap_datasets_main()`, edit `_load_docs()` |
| `anvil/services/demo_bootstrap.py` | **CREATE** | Orchestration service |
| `anvil/services/training.py` | Modify `_load_docs()` | Replace download with corpus lookup |
| `anvil/services/inference.py` | Modify `DEMO_CORPUS` | DB-backed or minimal fallback |
| `anvil/api/app.py` | Optional | Auto-bootstrap on startup if missing |
| `Makefile` | Optional | Add `bootstrap-datasets` to `make setup` |

## Verification

```bash
# Unit tests
make test

# Manual flow
make setup                    # Creates DB + runs bootstrap
anvil bootstrap-datasets      # Idempotent - should skip everything
anvil train                   # Should auto-use demo corpus
anvil bootstrap-datasets --dry-run  # Preview without changes
```