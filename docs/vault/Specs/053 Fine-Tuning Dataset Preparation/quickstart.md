# Quickstart: Fine-Tuning Dataset Preparation

## Setup

No new dependencies. The feature uses the existing project stack (FastAPI, async SQLAlchemy,
LocalFileStore). Run migrations:

```bash
# Auto-migrated on next startup (ANVIL_DB_AUTO_MIGRATE=true)
make run
```

Or manually:
```bash
make db-migrate
```

## Usage

### 1. Create a ChatTemplate

Before preparing a dataset, the target chat template must exist. If you've imported a base model
that has one, you can register it:

```python
from anvil.services._shared.tokenizer_family import TokenizerFamily

chat_template = await workbench.chat_templates.create(
    name="tinyllama-chat",
    template_string="{{ bos_token }}...{% for message in messages %}...{% endfor %}",
    tokenizer_family=TokenizerFamily.SUBWORD,
    base_model_ref=5,
)
```

Or via the API:
```bash
curl -X POST /v1/chat-templates \
  -H "Content-Type: application/json" \
  -d '{
    "name": "tinyllama-chat",
    "template_string": "...",
    "tokenizer_family": "subword",
    "base_model_ref": 5
  }'
```

### 2. Prepare a Dataset

Submit a JSONL file with instruction examples through the existing dataset curation (005), then
trigger preparation:

```bash
curl -X POST /v1/fine-tune-datasets \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": 1,
    "chat_template_id": 2,
    "base_model_ref": 5,
    "record_type": "sft"
  }'
```

Returns `{"job_id": 42, "status": "preparing"}`.

### 3. Poll for Completion

```bash
curl /v1/fine-tune-datasets/jobs/42/status
```

Returns `{"status": "ready", "summary": {"total": 500, "succeeded": 498, "failed": 2, ...}}`.

### 4. Use in Fine-Tuning (044/047)

The prepared dataset is consumable by fine-tuning specs directly — no ad-hoc reformatting needed.

```python
# FineTuneSpec references FineTuneDataset.id
# The prepared JSONL file contains chat-template–rendered strings
```

## Testing

```bash
make test  # Runs unit + e2e tests
```

New test files:
- `tests/unit/services/finetuning/test_chat_template_service.py`
- `tests/unit/services/finetuning/test_dataset_preparation_service.py`
- `tests/e2e/test_fine_tune_datasets.py`

## Key Patterns

| Action | Pattern | Reference |
|--------|---------|-----------|
| Async job submission | `POST → 202 + job_id` | `anvil/api/v1/models.py` |
| Background worker | `asyncio.create_task()` + isolated `AsyncSession` | `anvil/api/v1/models.py` |
| Status polling | `GET /{resource}/jobs/{id}/status` | `anvil/api/v1/models.py` |
| Batch insert | `add_bulk()` with `session.add_all() + flush` | `anvil/db/repositories/curation.py` |
| Audit trail | `CurationOperation(operation_type="prepare")` | `anvil/db/models/curation_operation.py` |
| File storage | `LocalFileStore → data/datasets/<id>/prepared/` | `anvil/storage/` |
