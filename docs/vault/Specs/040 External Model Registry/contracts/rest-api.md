# REST API Contract: External Model Import

## `POST /v1/models/import`

Submit an import job for an external model.

### Request Body

```json
{
  "source": "huggingface",
  "identifier": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
  "revision": "main",
  "name": "My TinyLlama"
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `source` | `str` | Yes | — | Source type: `huggingface` or `local` |
| `identifier` | `str` | Yes | — | Source-specific model ID (HF repo path or local path) |
| `revision` | `str` | No | `main` | Source revision/branch/commit SHA |
| `name` | `str | None` | No | `None` | Display name (auto-derived from identifier if omitted) |

### Response: 202 Accepted

```json
{
  "job_id": 42,
  "status": "queued"
}
```

### Response: 422 Unprocessable

```json
{
  "detail": "Unknown source type: unknown-source"
}
```

### Error Codes

| HTTP Status | `detail` |
|-------------|----------|
| 422 | Unknown source type, missing required fields, invalid identifier format |

---

## `GET /v1/models/import/{job_id}/status`

Poll import job status.

### Response: 200 OK

**In progress:**
```json
{
  "job_id": 42,
  "status": "queued",
  "started_at": null,
  "finished_at": null,
  "error_code": null,
  "error_message": null,
  "external_model_id": null
}
```

**Completed:**
```json
{
  "job_id": 42,
  "status": "complete",
  "started_at": "2026-06-28T12:00:00Z",
  "finished_at": "2026-06-28T12:00:03Z",
  "error_code": null,
  "error_message": null,
  "external_model_id": 7
}
```

**Failed:**
```json
{
  "job_id": 42,
  "status": "failed",
  "started_at": "2026-06-28T12:00:00Z",
  "finished_at": "2026-06-28T12:00:03Z",
  "error_code": "not_found",
  "error_message": "Model not found on HuggingFace Hub: TinyLlama/Nonexistent",
  "external_model_id": null
}
```

### Error Codes

| `error_code` | Meaning | Retryable |
|--------------|---------|-----------|
| `network_error` | Connection timeout, DNS failure, SSL error | Yes |
| `auth_required` | Gated model requires `HF_TOKEN` | Yes (with token) |
| `rate_limited` | HF Hub API rate limit exceeded | Yes (backoff) |
| `not_found` | Model identifier not found on source | No |
| `invalid_identifier` | Malformed or unsupported identifier format | No |
| `parse_failure` | Model card/config could not be parsed | No |

---

## `GET /v1/models/external`

List all imported external models.

### Response: 200 OK

```json
[
  {
    "id": 7,
    "display_name": "My TinyLlama",
    "source_type": "huggingface",
    "source_identifier": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
    "architecture_family": "LlamaForCausalLM",
    "parameter_count": 1100000000,
    "license": "apache-2.0",
    "tokenizer_family": "sentencepiece",
    "revision_sha": "abc123def456",
    "runnable_status": "runnable",
    "asset_availability": "metadata_only",
    "created_at": "2026-06-28T12:00:03Z"
  }
]
```

---

## `GET /v1/models/external/{model_id}`

Get a single external model by ID.

### Response: 200 OK

Same shape as a single entry in the list endpoint, plus `config_json` field.

### Response: 404 Not Found

```json
{
  "detail": "External model not found"
}
```
