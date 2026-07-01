# Data Model — Local LoRA Fine-Tuning

## Entities

### LoRAAdapter

Represents a single LoRA fine-tuning result — a set of low-rank weight deltas applied to a
specific base model.

**Decision**: A dedicated `LoRAAdapter` ORM model in `anvil/db/models/lora_adapter.py` (NOT an
extension of `ModelAsset`). Rationale: adapters carry training-run semantics (rank, alpha, method,
final_loss, merged_at) that don't fit `ModelAsset`'s per-file columns; mixing them violates Article X
§10.2 (tight coupling / bounded contexts). Uses `Base` + `TimestampMixin` (provides `created_at` /
`updated_at`). Requires a new Alembic migration (`make db-revision MESSAGE="add lora adapters"`).
A matching `LoRAAdapterRepository` (ctor takes `AsyncSession`) follows the existing repository pattern
and is exposed via a lazy property on `AnvilWorkbench`.

| Field | Type | Description |
|---|---|---|
| `id` | `int` (PK, auto) | Primary key |
| `external_model_id` | `int` (FK → `external_models.id`) | Base model this adapter applies to |
| `run_id` | `int` (FK → training run) | Training run that produced this adapter |
| `adapter_id` | `str` | Human-readable unique ID within base model scope (auto-generated: `run_{run_id}`) |
| `label` | `str \| None` | Optional user-provided display label |
| `method` | `str` (`"lora"` \| `"qlora"`) | Fine-tuning method used |
| `storage_path` | `str` | Path to adapter directory: `models/{base_id}/adapters/{run_id}/` |
| `lora_rank` | `int` | LoRA rank (r) |
| `lora_alpha` | `float` | LoRA scaling alpha |
| `lora_target_modules` | `list[str]` | Target module names (e.g. `["q_proj", "v_proj"]`) |
| `lora_dropout` | `float` | LoRA dropout rate |
| `lora_bias` | `str` | Bias setting (`"none"` \| `"all"` \| `"lora_only"`) |
| `final_loss` | `float \| None` | Final training loss |
| `final_step` | `int \| None` | Final training step |
| `created_at` | `datetime` | Creation timestamp (from `TimestampMixin`) |
| `updated_at` | `datetime` | Update timestamp (from `TimestampMixin`) |
| `merged_at` | `datetime \| None` | Timestamp of optional merge operation |

**Uniqueness constraint**: (`external_model_id`, `adapter_id`) unique — adapter IDs are scoped to
their base model.

**State transitions**:
```
CREATED → ADAPTER_SAVED → (MERGE_REQUESTED → MERGED)
                         → (DELETED)
```

### FineTuneSpec (embedded in TrainConfig)

Configuration for a fine-tuning job, expressed as fields on the existing `TrainConfig` Pydantic model.

| Field | Type | Default | Description |
|---|---|---|---|
| `method` | `Literal["full", "lora", "qlora"]` | `"full"` | Training method. `"full"` = existing from-scratch behavior |
| `lora_rank` | `int \| None` | `None` (→ peft default: 8) | LoRA rank r |
| `lora_alpha` | `float \| None` | `None` (→ peft default: 16) | LoRA scaling alpha |
| `lora_target_modules` | `list[str] \| None` | `None` (→ catalog default per arch) | Target module names |
| `lora_dropout` | `float \| None` | `None` (→ peft default: 0.05) | LoRA dropout |
| `lora_bias` | `Literal["none", "all", "lora_only"] \| None` | `None` (→ `"none"`) | Bias training mode |

**Validation rules**:
- When `method != "full"`, `base_model_ref` MUST be set (must reference an imported external model)
- `lora_rank` >= 1, <= 1024
- `lora_alpha` > 0
- `lora_dropout` >= 0, <= 1
- When `method == "qlora"` and `bitsandbytes` not available → warn and fall back to `"lora"`
- When `method == "full"`, all `lora_*` fields MUST be `None` (or absent)

### TrainConfig (extended)

Existing `TrainConfig` Pydantic model with new fields:

```python
class TrainConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Existing fields (unchanged):
    n_embd: int = Field(default=16, ge=4, le=4096)
    n_layer: int = Field(default=1, ge=1, le=128)
    n_head: int = Field(default=4, ge=1, le=64)
    block_size: int = Field(default=16, ge=8, le=4096)
    num_steps: int = Field(default=1000, ge=1, le=1_000_000)
    learning_rate: float = Field(default=0.01, gt=0, le=1.0)
    beta1: float = Field(default=0.85)
    beta2: float = Field(default=0.99)
    temperature: float = Field(default=0.5, ge=0, le=2.0)
    compute_backend: str | None = Field(default="auto")
    dataset_id: int | None = None
    corpus_id: int | None = None
    content_version_id: int | None = None
    device: str | None = None
    base_model_ref: int | None = None

    # NEW: Fine-tuning method and LoRA hyperparams
    method: Literal["full", "lora", "qlora"] = Field(default="full")
    lora_rank: int | None = Field(default=None, ge=1, le=1024)
    lora_alpha: float | None = Field(default=None, gt=0)
    lora_target_modules: list[str] | None = None
    lora_dropout: float | None = Field(default=None, ge=0, le=1)
    lora_bias: Literal["none", "all", "lora_only"] | None = None
```

### ResourceEnvelope (curated catalog entry enrichment)

The `ResourceEnvelope` Pydantic model (`anvil/services/inference/resource_envelope.py`) is extended
with a `default_target_modules` field. Current fields: `min_ram_gb`, `min_vram_per_backend` (must
include `"cpu"` key), `supported_methods` (min_length=1).

```python
class ResourceEnvelope(BaseModel):
    min_ram_gb: float = Field(ge=0)
    min_vram_per_backend: dict[str, float]
    supported_methods: list[str] = Field(min_length=1)
    default_target_modules: list[str] | None = None   # NEW — arch-specific LoRA target modules
```

Per-model metadata in `curated-models.yaml`:

```yaml
- hf_id: "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
  # ... existing fields ...
  resource_envelope:
    min_ram_gb: 8.0
    min_vram_per_backend: { cpu: 0, cuda: 4.0, mps: 6.0 }
    supported_methods:
      - "lora"
    default_target_modules:       # NEW: arch-specific LoRA defaults
      - "q_proj"
      - "v_proj"
```

## Relationships

```
ExternalModel (1) ───────< (N) LoRAAdapter
    │                              │
    │                              ├── references training run (run_id)
    │                              └── stores files at storage_path
    │
    └─── assets stored at models/{id}/assets/
    └─── adapters stored at models/{id}/adapters/{run_id}/
```

## Storage Layout

```
data/models/{external_model_id}/
├── assets/{sha256}/
│   ├── model.safetensors        # Base model weights
│   ├── config.json              # HF config
│   └── tokenizer.json           # Tokenizer
└── adapters/{run_id}/
    ├── adapter_model.safetensors  # PeftModel adapter weights
    ├── adapter_config.json        # LoraConfig serialization
    └── training_state.json        # Metadata: method, rank, alpha, loss
```