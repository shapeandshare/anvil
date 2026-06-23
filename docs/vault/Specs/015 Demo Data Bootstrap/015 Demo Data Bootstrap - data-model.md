---
title: 015 Demo Data Bootstrap - data-model
type: data-model
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/015 Demo Data Bootstrap/
related:
  - '[[015 Demo Data Bootstrap]]'
created: ~
updated: ~
---
# Data Model: Demo Data Bootstrap Guard

**Date**: 2026-06-19 | **Plan**: [plan.md](plan.md)

## No New Entities

This feature introduces **no new database tables or ORM models**. All data needed for the first-run guard already exists in the schema:

### Existing Entities Used for Guard Detection

#### `Corpus`

| Field | Value for Demo Entities | Purpose |
|-------|------------------------|---------|
| `origin` | `"bundled"` | Primary detection field — demo entities have this set by `_assign_provenance()` |
| `name` | `"Demo - small/names"`, etc. | Name with `"Demo - "` prefix (secondary check, not used for guard) |

**Definition**: `anvil/db/models/corpus.py`, line 94:
```python
origin: Mapped[str] = mapped_column(String(20), default="user")
```

#### `Dataset`

| Field | Value for Demo Entities | Purpose |
|-------|------------------------|---------|
| `origin` | `"bundled"` | Primary detection field |
| `name` | `"Demo - small/presidents.txt"`, etc. | Name with `"Demo - "` prefix (secondary check) |

**Definition**: `anvil/db/models/dataset.py`, line 72:
```python
origin: Mapped[str] = mapped_column(String(20), default="user")
```

#### `DataOrigin` Enum

**Definition**: `anvil/services/governance/data_origin.py`:
```python
class DataOrigin(StrEnum):
    BUNDLED = "bundled"
    USER = "user"
```

### Guard Detection Logic

```python
# In the lifespan handler, before calling bootstrap_all():
async with AsyncSessionLocal() as session:
    corpus_repo = CorpusRepository(session)
    dataset_repo = DatasetRepository(session)
    corpus_count = await corpus_repo.count_by_origin(DataOrigin.BUNDLED.value)
    dataset_count = await dataset_repo.count_by_origin(DataOrigin.BUNDLED.value)
    
    if corpus_count == 0 and dataset_count == 0:
        # Fresh environment — run bootstrap
        result = await DemoBootstrapService(session).bootstrap_all()
        ...
    else:
        # Already bootstrapped — skip
        logger.debug("Demo data already exists (%d corpora, %d datasets), skipping bootstrap", corpus_count, dataset_count)
```

### New Repository Methods Required

Add to both `CorpusRepository` and `DatasetRepository`:

```python
async def count_by_origin(self, origin: str) -> int:
    """Count entities with the given origin value.
    
    Parameters
    ----------
    origin : str
        The origin value to count (e.g., ``"bundled"`` or ``"user"``).
    
    Returns
    -------
    int
        Number of entities with this origin.
    """
    stmt = select(func.count()).where(self._model_cls.origin == origin)
    result = await self._session.execute(stmt)
    return result.scalar_one()
```

### BootstrapResult (Existing)

**File**: `anvil/services/demo/bootstrap_result.py`

```python
class BootstrapResult(BaseModel):
    corpora_created: int = 0
    datasets_created: int = 0
    corpora_skipped: int = 0
    datasets_skipped: int = 0
    errors: list[str] = Field(default_factory=list)
    total_time_ms: float = 0.0
```

Used as the return type for both the startup bootstrap call and the ops menu re-trigger API response.