# API Contract: `POST /v1/hf-browser/import` — Model Import

**Feature**: 041 HuggingFace Model Browser | **Date**: 2026-06-28

Imports a HuggingFace model into the local registry. Delegates entirely to spec 040's `ModelImportService`.

## Request

**Method**: `POST`
**Path**: `/v1/hf-browser/import`
**Content-Type**: `application/json`

**Body**:

```json
{
  "hf_id": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
  "architecture": "LlamaForCausalLM"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `hf_id` | `str` | Yes | HuggingFace model ID to import |
| `architecture` | `str` | Yes | Model architecture class (for registry metadata) |

## Response

### Success

**Status**: `202 Accepted`

```json
{
  "status": "accepted",
  "job_id": "uuid-string",
  "message": "Import job created"
}
```

### Errors

| Status | Condition | Body |
|--------|-----------|------|
| `400` | Missing or invalid fields | `{"error": "hf_id and architecture are required", "code": "INVALID_INPUT"}` |
| `503` | `huggingface_hub` not installed | `{"error": "HF Hub support requires [finetune] extra", "code": "EXTRA_MISSING"}` |
| `409` | Model already imported | `{"error": "Model already exists in registry", "code": "ALREADY_EXISTS", "existing_id": N}` |

## Delegation

This endpoint does NOT implement import logic. It delegates to:

```python
workbench.model_import.create_job(hf_id=hf_id, architecture=architecture)
```

For full import job lifecycle, job status polling, and error handling, see spec 040 contracts.