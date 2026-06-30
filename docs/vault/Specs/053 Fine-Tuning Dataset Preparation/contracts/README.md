# API Contracts: Fine-Tuning Dataset Preparation

## POST `/v1/fine-tune-datasets`

Create a new `FineTuneDataset` record (preparation job). Returns `202 Accepted` with a job ID
for status polling.

**Request Body:**
```json
{
  "dataset_id": 1,
  "chat_template_id": 2,
  "base_model_ref": 5,
  "record_type": "sft",
  "batch_size": 1000
}
```

**Fields:**
- `dataset_id` (int, required): Source dataset ID
- `chat_template_id` (int, required unless `base_model_ref` has a default template): ChatTemplate to apply
- `base_model_ref` (int, required): Base model ID for template validation
- `record_type` (str, required): `"sft"` or `"preference"`
- `batch_size` (int, optional, default `1000`): Records per batch

**Response (202):**
```json
{
  "job_id": 42,
  "fine_tune_dataset_id": 10,
  "status": "preparing"
}
```

**Errors:**
- `404` — `dataset_id`, `chat_template_id`, or `base_model_ref` not found
- `422` — validation failure (invalid `record_type`, missing required fields)
- `409` — dataset is already being prepared (active `FineTuneDataset` for this `dataset_id`)

---

## GET `/v1/fine-tune-datasets/jobs/{job_id}/status`

Poll preparation job status.

**Response (200):**
```json
{
  "job_id": 42,
  "fine_tune_dataset_id": 10,
  "status": "preparing",
  "started_at": "2026-06-28T10:30:00Z",
  "finished_at": null,
  "summary": null
}
```

**Response (200, complete):**
```json
{
  "job_id": 42,
  "fine_tune_dataset_id": 10,
  "status": "ready",
  "started_at": "2026-06-28T10:30:00Z",
  "finished_at": "2026-06-28T10:30:05Z",
  "summary": {
    "total": 500,
    "succeeded": 498,
    "failed": 2,
    "errors": [
      {"row": 12, "error": "Empty response field"},
      {"row": 89, "error": "Invalid role value"}
    ]
  }
}
```

**Response (200, failed):**
```json
{
  "job_id": 42,
  "fine_tune_dataset_id": 10,
  "status": "failed",
  "started_at": "2026-06-28T10:30:00Z",
  "finished_at": "2026-06-28T10:30:02Z",
  "summary": {
    "total": 0,
    "succeeded": 0,
    "failed": 1,
    "errors": [
      {"row": 0, "error": "Token mismatch: template tokenizer_family != base_model tokenizer_family"}
    ]
  }
}
```

**Errors:**
- `404` — `job_id` not found

---

## GET `/v1/fine-tune-datasets/{id}`

Get the prepared dataset metadata (available after job completes).

**Response (200):**
```json
{
  "id": 10,
  "dataset_id": 1,
  "chat_template_id": 2,
  "base_model_ref": 5,
  "status": "ready",
  "record_type": "sft",
  "record_count": 498,
  "prepared_file_path": "data/datasets/1/prepared/10_prepared.jsonl",
  "summary": {
    "total": 500,
    "succeeded": 498,
    "failed": 2,
    "errors": [...]
  },
  "created_at": "2026-06-28T10:29:55Z",
  "updated_at": "2026-06-28T10:30:05Z"
}
```

---

## GET `/v1/fine-tune-datasets`

List prepared fine-tune datasets with optional filters.

**Query Parameters:**
- `dataset_id` (int, optional): Filter by source dataset
- `status` (str, optional): Filter by status (`preparing`, `ready`, `failed`)
- `base_model_ref` (int, optional): Filter by base model

**Response (200):**
```json
{
  "items": [...],
  "total": 5
}
```

---

## POST `/v1/fine-tune-datasets/{id}/retry`

Retry a failed preparation. Creates a new preparation job.

**Response (202):**
```json
{
  "job_id": 43,
  "fine_tune_dataset_id": 11,
  "status": "preparing"
}
```

**Errors:**
- `404` — `id` not found
- `409` — status is not `failed` (cannot retry a non-failed job)

---

## POST `/v1/chat-templates`

Create a new chat template.

**Request Body:**
```json
{
  "name": "llama3-instruct",
  "template_string": "{{ bos_token }}{% for message in messages %}{% if message['role'] == 'user' %}...{% endif %}...",
  "tokenizer_family": "subword",
  "base_model_ref": 5,
  "description": "Standard Llama 3 instruct template"
}
```

**Response (201):**
```json
{
  "id": 2,
  "name": "llama3-instruct",
  "tokenizer_family": "subword",
  "status": "active",
  "created_at": "2026-06-28T10:29:55Z"
}
```

---

## GET `/v1/chat-templates`

List chat templates with optional filters.

**Query Parameters:**
- `tokenizer_family` (str, optional): Filter by tokenizer family
- `status` (str, optional): Filter by status (`active`, `deprecated`)

**Response (200):**
```json
{
  "items": [...],
  "total": 3
}
```
