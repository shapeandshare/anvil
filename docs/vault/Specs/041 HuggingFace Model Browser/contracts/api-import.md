# Import Action: Reuse Existing `POST /v1/models/import`

**Feature**: 041 HuggingFace Model Browser | **Date**: 2026-06-28

> **DECISION (post-review)**: This spec does **NOT** introduce a new import endpoint. The existing spec 040
> route `POST /v1/models/import` already performs HuggingFace imports. Adding a second `/v1/hf-browser/import`
> endpoint would violate Constitution Article XI §11.4 (Reuse First) and create two parallel ways to import.
> The browser UI's "Import" button calls the existing route directly.

## Existing Endpoint (spec 040 — already implemented)

**Route**: `POST /v1/models/import` (in `anvil/api/v1/models.py`)
**Status**: `202 Accepted`

**Request body** (`ImportModelBody`, `extra="forbid"`):

```json
{
  "source": "huggingface",
  "identifier": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
  "revision": "main",
  "name": "TinyLlama 1.1B Chat"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source` | `str` | Yes | `"huggingface"` or `"local"` (a `SourceType` value) |
| `identifier` | `str` | Yes | HF repo ID (the browser passes the catalog/search `hf_id` here) |
| `revision` | `str` | No | Source revision. Default `"main"` |
| `name` | `str \| None` | No | Optional display name for the registry entry |

> **There is NO `architecture` field.** The import service derives `architecture_family` from the model's
> `config.json` and sets `runnable_status` itself by comparing against `_ALLOWED_ARCHITECTURES`. The browser
> MUST NOT attempt to pass an architecture.

**Response**:

```json
{ "job_id": 123, "status": "queued" }
```

**Errors**: `422` if the source type is invalid (raised as `HTTPException` from a `ValueError`).

## Underlying Service API (spec 040)

```python
# anvil/workbench.py  →  property `model_imports` (plural)
job_id: int = await workbench.model_imports.submit_import(
    source="huggingface",
    identifier=hf_id,          # NOT hf_id= keyword on a create_job method
    revision="main",
    name=display_name,
)
```

Related existing routes the browser MAY use for status/feedback:

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/v1/models/import/{job_id}/status` | Poll import job status |
| `GET` | `/v1/models/external` | List imported external models |
| `GET` | `/v1/models/external/{model_id}` | Get a single imported model |

## Browser Responsibility

The HF Browser page's "Import" button issues a client-side `POST /v1/models/import` with
`source="huggingface"` and `identifier=<hf_id>`. It then optionally polls
`GET /v1/models/import/{job_id}/status` to show progress. No new server route is added by this spec.