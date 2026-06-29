# API Contract: `/v1/hf-browser` Browser Page

**Feature**: 041 HuggingFace Model Browser | **Date**: 2026-06-28

## Page Route

### `GET /v1/hf-browser` — HuggingFace Model Browser page

Renders the HF Model Browser standalone page with search bar, curated catalog display, and model detail panel.

**Response**: `200 OK` — `text/html` (Jinja2 template)

**Template**: `anvil/api/templates/hf_browser.html`

**Template context**:

| Variable | Type | Description |
|----------|------|-------------|
| `catalog` | `list[dict]` | Pre-loaded curated catalog entries (serialized `CatalogEntry`) |
| `allow_list` | `list[str]` | Architecture allow-list values for display |
| `host_device` | `str` | Detected compute backend name (e.g. `"cuda"`, `"mps"`, `"cpu"`) |
| `related_lessons` | `list[dict]` | Related lesson links per existing pattern |
| `hf_available` | `bool` | Whether `huggingface_hub` is importable (i.e., `[finetune]` extra is installed) |

**Auth**: Session required — added to `PAGE_PREFIXES` in `auth.py`

## Search API

### `GET /v1/hf-browser/search?q=<query>` — Live HF Hub search (JSON)

Searches HuggingFace Hub via `huggingface_hub.HfApi.list_models()`. Available only when `[finetune]` extra is installed.

**Response**: `200 OK` — `application/json`

```json
{
  "results": [
    {
      "hf_id": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
      "display_name": "TinyLlama 1.1B Chat",
      "params": "1.1B",
      "license": "Apache-2.0",
      "architecture": "LlamaForCausalLM",
      "is_curated": false
    }
  ],
  "cached": false,
  "error": null
}
```

**Error responses**:

| Status | Condition | Body |
|--------|-----------|------|
| `422` | Missing or empty `q` param | `{"detail": [{"type": "missing", "loc": ["query", "q"], "msg": "Field required"}]}` |
| `503` | `huggingface_hub` not installed | `{"error": "HF Hub support requires [finetune] extra", "code": "EXTRA_MISSING"}` |
| `429` | Rate limited (retries exhausted) | `{"error": "Rate limited. Retry in N seconds.", "code": "RATE_LIMITED", "retry_after_seconds": N}` |
| `502` | HF Hub API unreachable | `{"error": "HF Hub API unreachable", "code": "API_UNAVAILABLE"}` |

**Query parameters**:

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `q` | `str` | Yes | Search query string |
| `limit` | `int` | No | Max results (default 20, max 50) |

**Caching**: Results cached in-memory for 5 minutes per unique query.

## Import Action

### `POST /v1/hf-browser/import` — Import a model from HF

Triggers the spec 040 import flow via `ModelImportService`.

**Request body**:

```json
{
  "hf_id": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
  "architecture": "LlamaForCausalLM"
}
```

**Response**: `202 Accepted` — triggers async import job

Delegates entirely to spec 040's import paradigm. See spec 040 contracts for full import response/error contract.