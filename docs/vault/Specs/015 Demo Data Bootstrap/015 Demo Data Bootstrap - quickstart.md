---
title: 015 Demo Data Bootstrap - quickstart
type: quickstart
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/015 Demo Data Bootstrap/
related:
  - '[[015 Demo Data Bootstrap]]'
created: ~
updated: ~
---
# Quickstart: Demo Data Bootstrap Guard

**Date**: 2026-06-19 | **Plan**: [plan.md](plan.md)

## Summary

4 file edits, zero new dependencies, zero new files. See [tasks.md](../tasks.md) for the full ordered work breakdown.

## Changes

| # | File | Action | Description |
|---|------|--------|-------------|
| 1 | `anvil/db/repositories/corpora.py` | **Edit** | Add `count_by_origin()` method |
| 2 | `anvil/db/repositories/datasets.py` | **Edit** | Add `count_by_origin()` method |
| 3 | `anvil/api/app.py` | **Edit** | Add origin-based guard before bootstrap_all() in lifespan handler |
| 4 | `anvil/api/v1/health_ops.py` | **Edit** | Add `POST /v1/demo/bootstrap` endpoint |
| 5 | `anvil/api/templates/operations.html` | **Edit** | Add button in System Actions + `ops.rebootstrapDemo()` JS handler |
| 6 | `anvil/cli.py` | **Edit** | Conditional banner in `bootstrap_datasets_main()` |
| 7 | `tests/test_bootstrap.py` | **Edit** | Add tests for guard, endpoint, CLI banner |

## Pattern Reference

### Repository Method

```python
async def count_by_origin(self, origin: str) -> int:
    stmt = select(func.count()).where(self._model_cls.origin == origin)
    result = await self._session.execute(stmt)
    return result.scalar_one()
```

### Lifespan Guard (app.py)

```python
# Before bootstrap_all(), add:
from ..services.governance.data_origin import DataOrigin
from ..db.repositories.corpora import CorpusRepository
from ..db.repositories.datasets import DatasetRepository

corpus_repo = CorpusRepository(session)
dataset_repo = DatasetRepository(session)
corpus_count = await corpus_repo.count_by_origin(DataOrigin.BUNDLED.value)
dataset_count = await dataset_repo.count_by_origin(DataOrigin.BUNDLED.value)

if corpus_count == 0 and dataset_count == 0:
    # Run bootstrap (existing code follows)
    svc = DemoBootstrapService(session)
    ...
```

### API Endpoint (health_ops.py)

```python
@router.post("/demo/bootstrap")
async def rebootstrap_demo(
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict:
    result = await workbench.demo().bootstrap_all()
    return result.model_dump()
```

### Button HTML (operations.html)

```html
<button class="btn btn-secondary" onclick="ops.rebootstrapDemo()" id="btn-rebootstrap-demo">↻ Re-bootstrap Demo</button>
```

### JS Handler (operations.html)

```javascript
rebootstrapDemo: async function() {
  setBtnLoading('btn-rebootstrap-demo', true);
  try {
    var resp = await fetch('/v1/demo/bootstrap', { method: 'POST' });
    var data = await resp.json();
    if (resp.ok) {
      var created = data.corpora_created + data.datasets_created;
      var skipped = data.corpora_skipped + data.datasets_skipped;
      toast('Demo: ' + created + ' created, ' + skipped + ' skipped', 'success');
    } else {
      toast(data.detail || 'Error', 'error');
    }
  } catch(e) {
    toast('Network error', 'error');
  }
  setBtnLoading('btn-rebootstrap-demo', false);
}
```

### CLI Banner (cli.py)

```python
# Before line 730, replace:
#     print("Bootstrapping demo data from data/demo/...")
# with:
bootstrap = await svc.bootstrap_all()
if bootstrap.corpora_created > 0 or bootstrap.datasets_created > 0:
    print("Bootstrapping demo data from data/demo/...")
```

## Test Plan

| Test | File | Approach |
|------|------|----------|
| `test_count_by_origin` | `tests/test_bootstrap.py` | Bootstrap, then verify `count_by_origin("bundled")` returns 6 (3 corpora + 3 datasets) |
| `test_guard_skips_on_second_startup` | `tests/test_bootstrap.py` | Bootstrap, mock `count_by_origin` to return >0, verify `bootstrap_all` not called |
| `test_rebootstrap_endpoint` | `tests/test_bootstrap.py` | Use `TestClient` to `POST /v1/demo/bootstrap`, verify 200 + correct counts |
| `test_cli_banner` | `tests/test_bootstrap.py` | Call `_run()` helper with populated DB, verify no "Bootstrapping" in output |