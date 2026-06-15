# DemoBootstrapService Interface Contract

**File**: `anvil/services/demo_bootstrap.py` (NEW)

## Purpose
Orchestrates importing demo data from `data/demo/` directory into the database via existing corpus and dataset pipelines.

## Constructor

```python
class DemoBootstrapService:
    def __init__(self, session: AsyncSession)
```

- **session**: Existing async SQLAlchemy session (caller manages commit/rollback)

## Public Methods

### `bootstrap_all() -> BootstrapResult`

**Signature**: `async def bootstrap_all() -> BootstrapResult`

**Behavior**:
1. Walks `data/demo/` discovering subdirectories (corpora) and `.txt` files (datasets)
2. For each item, checks name-based idempotency (FR-008)
3. Creates + ingests corpora via `CorpusService`
4. Creates + imports datasets via `DatasetService` + `DatasetImportService`
5. Gathers errors per-item (continues on failure)
6. Does NOT commit — caller commits the session

**Returns**:
```python
@dataclass
class BootstrapResult:
    corpora_created: int          # Number of new corpora created
    datasets_created: int         # Number of new datasets created
    corpora_skipped: int          # Already existed (idempotent)
    datasets_skipped: int         # Already existed (idempotent)
    errors: list[str]             # Non-fatal errors per item
    total_time_ms: float          # Duration of bootstrap process
```

### `get_default_corpus() -> Corpus | None`

**Signature**: `async def get_default_corpus() -> Corpus | None`

**Behavior**: Queries for the default demo corpus by well-known name (e.g., `"Demo - medium/alice"`). Used by training fallback to find the default training data.

**Returns**: `Corpus` object or `None` if not yet bootstrapped.

### `get_demo_corpus(name: str) -> Corpus | None`

**Signature**: `async def get_demo_corpus(name: str) -> Corpus | None`

**Behavior**: Queries for a demo corpus by short name (e.g., `"small/names"` → looks up `"Demo - small/names"`).

### `list_demo_corpora() -> Sequence[Corpus]`

Lists all demo corpora (names starting with `"Demo - "`).

### `list_demo_datasets() -> Sequence[Dataset]`

Lists all demo datasets (names starting with `"Demo - "`).

## Internal Methods (Private)

### `_demo_dir() -> Path`
Returns `Path("data/demo")`.

### `_is_demo_path(path: Path) -> bool`
Returns True if path is a subdirectory or `.txt` file under `data/demo/`.

### `_strategy_for(path: Path) -> str`
Returns chunking strategy based on directory content size.

### `_corpus_name_for(path: Path) -> str`
Converts path to entity name: e.g., `data/demo/medium/alice/` → `"Demo - medium/alice"`.

### `_dataset_name_for(path: Path) -> str`
Converts path to entity name: e.g., `data/demo/small/presidents.txt` → `"Demo - small/presidents"`.

## Error Handling
- Each item is processed independently — a failure on one item does not abort others
- Errors are accumulated in `BootstrapResult.errors` with context (which path failed)
- The caller commits the session only if at least one item succeeded
- Fatal errors (e.g., `data/demo/` missing) raise immediately

## Dependencies
- `anvil.services.corpora.CorpusService` — corpus creation/ingestion
- `anvil.services.corpus_loader.CorpusLoader` — directory scanning
- `anvil.services.datasets.DatasetService` — dataset creation
- `anvil.services.dataset_import.DatasetImportService` — dataset import
- `anvil.db.repositories.corpora.CorpusRepository` — corpus queries
- `anvil.db.repositories.datasets.DatasetRepository` — dataset queries