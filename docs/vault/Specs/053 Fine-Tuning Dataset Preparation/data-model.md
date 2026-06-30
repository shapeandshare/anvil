# Data Model: Fine-Tuning Dataset Preparation

## Entities

### ChatTemplate

Stored in the `chat_templates` table. Represents a chat template string that renders prompts/responses
for a given base model's tokenizer family.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | int | PK, autoincrement | |
| `name` | str | String(255), unique, not null | Human-readable name (e.g., `"llama3-instruct"`, `"tinyllama-chat"`) |
| `template_string` | str | Text, not null | The Jinja-like template string (HuggingFace chat template syntax) |
| `tokenizer_family` | str | String(20), not null | `TokenizerFamily` value (`CHAR`, `SUBWORD`); validated at assign time |
| `base_model_ref` | int | FK → `external_models.id`, nullable | Optional — which base model this template originates from; nullable for custom/user-created templates |
| `status` | str | String(20), not null, default `"active"` | `ChatTemplateStatus` — `ACTIVE`, `DEPRECATED` |
| `description` | str | Text, nullable | Optional human description |
| `created_at` | datetime | `TimestampMixin` | |
| `updated_at` | datetime | `TimestampMixin` | |

**Indexes:**
- Unique on `(name)` — no duplicate template names
- Index on `(base_model_ref)` — quick lookup by source model
- Index on `(tokenizer_family, status)` — filter active templates by family

**Validation rules:**
- `name` must be non-empty, max 255 chars
- `template_string` must be non-empty, parseable as a Jinja template
- `tokenizer_family` must be a valid `TokenizerFamily` enum value
- Cannot delete a `ChatTemplate` that is referenced by any `FineTuneDataset`

---

### FineTuneDataset

Stored in the `fine_tune_datasets` table. Represents a prepared, tracked dataset of SFT or preference
records with recorded formatting.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | int | PK, autoincrement | |
| `dataset_id` | int | FK → `datasets.id`, not null | The source dataset (spec 005) being prepared |
| `chat_template_id` | int | FK → `chat_templates.id`, nullable | The template applied; nullable during preparation, set on completion |
| `base_model_ref` | int | FK → `external_models.id`, nullable | The base model being fine-tuned; nullable during preparation, set on completion |
| `status` | str | String(20), not null, default `"preparing"` | `FineTuneDatasetStatus` — `PREPARING`, `READY`, `FAILED` |
| `record_type` | str | String(20), not null | `"sft"` or `"preference"` |
| `summary_json` | str | Text, nullable | JSON blob: `{"total": N, "succeeded": N, "failed": N, "errors": [{"row": i, "error": "..."}]}` |
| `prepared_file_path` | str | String(500), nullable | Path to the prepared JSONL file in FileStore |
| `record_count` | int | not null, default 0 | Number of successfully prepared records |
| `started_at` | datetime | nullable | When preparation job started |
| `finished_at` | datetime | nullable | When preparation job finished (success or failure) |
| `created_at` | datetime | `TimestampMixin` | |
| `updated_at` | datetime | `TimestampMixin` | |

**Indexes:**
- Index on `(dataset_id, status)` — find prepared datasets by source
- Index on `(status)` — find active/preparing jobs
- Index on `(base_model_ref)` — find all fine-tune datasets for a model

**Validation rules:**
- `record_type` must be `"sft"` or `"preference"`
- `summary_json` must be valid JSON when set
- `prepared_file_path` must reference a valid FileStore location when set
- When `status = READY`: `chat_template_id`, `base_model_ref`, `prepared_file_path`, and `record_count > 0` all required
- When `status = FAILED`: `summary_json` must contain error details

---

### Lifecycle State Transitions

```
FineTuneDataset:
  PREPARING ──→ READY   (all records processed, summary generated)
  PREPARING ──→ FAILED  (fatal error before or during processing)
```

The `FAILED` state is terminal. A failed preparation can be retried by creating a new
`FineTuneDataset` record. The `summary_json` captures per-record errors from the
skip-and-continue approach.

---

### Relationships

```text
ExternalModel (040)
      │
      ├──< base_model_ref
      │
      ▼
ChatTemplate ──< chat_template_id ── FineTuneDataset
                                               │
                                          dataset_id
                                               │
                                               ▼
                                          Dataset (005)
```

- `ChatTemplate.base_model_ref` → `ExternalModel.id` (nullable — user-created templates)
- `FineTuneDataset.chat_template_id` → `ChatTemplate.id` (nullable during preparation)
- `FineTuneDataset.base_model_ref` → `ExternalModel.id` (nullable during preparation)
- `FineTuneDataset.dataset_id` → `Dataset.id` (the source curated dataset)

---

### Enums

#### FineTuneDatasetStatus (`anvil/services/_shared/fine_tune_dataset_status.py`)

```python
class FineTuneDatasetStatus(StrEnum):
    PREPARING = "preparing"
    READY = "ready"
    FAILED = "failed"
```

#### ChatTemplateStatus (`anvil/services/_shared/chat_template_status.py`)

```python
class ChatTemplateStatus(StrEnum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
```

---

### Value Objects

#### PreparationResult (`anvil/services/finetuning/preparation_result.py`)

```python
@dataclass  # or BaseModel — follow existing pattern
class PreparationResult:
    job_id: int
    total: int
    succeeded: int
    failed: int
    errors: list[dict]  # [{"row": int, "error": str}, ...]
```
