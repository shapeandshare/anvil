# API Contract: POST /v1/demo/bootstrap

**Plan**: [plan.md](../plan.md) | **Spec**: [spec.md](../spec.md)

## Endpoint

```
POST /v1/demo/bootstrap
```

## Purpose

Manually trigger the demo data bootstrap process. Idempotent — existing entities are skipped, not duplicated.

## Request

No request body required. No query parameters.

## Authorization

None. The ops page is accessible without authentication (single-user development tool).

## Response

### 200 OK

```json
{
  "corpora_created": 0,
  "datasets_created": 0,
  "corpora_skipped": 3,
  "datasets_skipped": 3,
  "errors": [],
  "total_time_ms": 1234.56
}
```

**Fields** (from `BootstrapResult`):

| Field | Type | Description |
|-------|------|-------------|
| `corpora_created` | int | Number of new demo corpora created |
| `datasets_created` | int | Number of new demo datasets created |
| `corpora_skipped` | int | Number of existing demo corpora skipped |
| `datasets_skipped` | int | Number of existing demo datasets skipped |
| `errors` | list[str] | Error messages (empty if none) |
| `total_time_ms` | float | Total bootstrap duration in milliseconds |

### Error Responses

| Status | Body | Description |
|--------|------|-------------|
| 500 | `{"detail": "Internal server error"}` | Unexpected server error during bootstrap |

## Handler Signature

```python
@router.post("/demo/bootstrap")
async def rebootstrap_demo(
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict:
    """Re-bootstrap all demo data into the database.

    Returns
    -------
    dict
        BootstrapResult fields (corpora_created, datasets_created,
        corpora_skipped, datasets_skipped, errors, total_time_ms).
    """
    result = await workbench.demo().bootstrap_all()
    return result.model_dump()
```

## Example Usage

```javascript
// JS handler in ops page
var resp = await fetch('/v1/demo/bootstrap', { method: 'POST' });
var data = await resp.json();
// data.corpora_created, data.datasets_created, etc.
```

## Related

- `GET /v1/health` — health check endpoint
- `POST /v1/services/restart-all` — existing ops action (same endpoint pattern)