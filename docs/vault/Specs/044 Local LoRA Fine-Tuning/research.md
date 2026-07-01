# Phase 0 Research — Local LoRA Fine-Tuning

**Branch**: `062-local-lora-fine-tuning` | **Date**: 2026-06-30

## Research Areas

### 1. peft.LoraConfig Integration for TinyLlama-Class Models

**Decision**: Use `peft.LoraConfig` directly with `get_peft_model()` wrapping for LoRA, and
`transformers.AutoModelForCausalLM.from_pretrained()` with `quantization_config=BitsAndBytesConfig`
for QLoRA. Follow the standard HuggingFace PEFT pattern.

**Rationale**: `peft` is the de-facto standard for LoRA in the HF ecosystem. TinyLlama uses
`LlamaForCausalLM` architecture with standard linear layer names (`q_proj`, `v_proj`, `k_proj`,
`o_proj`, `gate_proj`, `up_proj`, `down_proj`). The default target modules for Llama should be
`["q_proj", "v_proj"]` (matching common practice), with user-override via `lora_target_modules`.

**Target module defaults by architecture**:
| Architecture | Default target modules |
|---|---|
| `LlamaForCausalLM` | `["q_proj", "v_proj"]` |
| `OPTForCausalLM` | `["q_proj", "v_proj"]` |
| `Qwen2ForCausalLM` | `["q_proj", "v_proj"]` |

These defaults MUST live in `curated-models.yaml` per-model, not hardcoded in the backend.

**Key integration points**:
```python
from peft import LoraConfig, get_peft_model, TaskType

lora_config = LoraConfig(
    r=lora_rank,
    lora_alpha=lora_alpha,
    target_modules=lora_target_modules,  # from config or catalog default
    lora_dropout=lora_dropout,
    bias=lora_bias or "none",
    task_type=TaskType.CAUSAL_LM,
)
peft_model = get_peft_model(base_model, lora_config)
# Train peft_model normally → only adapter weights update
# Save: peft_model.save_pretrained(adapter_path)
# Inference: AutoPeftModelForCausalLM.from_pretrained(adapter_path)
```

---

### 2. bitsandbytes 4-bit NF4 QLoRA Setup and Platform Compatibility

**Decision**: Use `transformers.BitsAndBytesConfig` with `load_in_4bit=True` and
`bnb_4bit_quant_type="nf4"` for QLoRA. Gate on `bitsandbytes` being importable.

**Rationale**: `bitsandbytes` is the standard quantization backend for QLoRA in the HF ecosystem.
It has full CUDA support on Linux and is experimental/unavailable on macOS MPS.

**Platform support matrix**:
| Platform | bitsandbytes | QLoRA status |
|---|---|---|
| Linux + CUDA | ✅ Full | QLoRA works |
| macOS + MPS | ❌ Unavailable | Degrade to LoRA with warning |
| macOS + CPU | ❌ Unavailable | LoRA only |
| Linux + CPU | ❌ Unavailable (no need) | LoRA only |

**Detection code**:
```python
try:
    import bitsandbytes  # noqa: F401
    _bitsandbytes_available = True
except ImportError:
    _bitsandbytes_available = False
```

**QLoRA integration**:
```python
from transformers import BitsAndBytesConfig, AutoModelForCausalLM

quant_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_use_double_quant=True,
)

base_model = AutoModelForCausalLM.from_pretrained(
    model_path,
    quantization_config=quant_config,
    device_map="auto",  # let accelerate handle placement
    torch_dtype=torch.float16,
    trust_remote_code=False,  # FT-AD-11: only allow-listed architectures
)
```

---

### 3. Adapter Storage Layout

**Decision**: LoRA adapters stored at `models/{external_model_id}/adapters/{run_id}/` using the
existing `LocalFileStore` + `ModelAsset` pattern. Each adapter directory contains the peft-saved
adapter files (`adapter_model.safetensors`, `adapter_config.json`).

**Rationale**: The existing external model asset storage path is `models/{id}/assets/{sha256}/{filename}`.
Adapters are a new asset type that live under the same base model ID but in a separate `adapters/`
subdirectory. This keeps adapters discoverable (list `adapters/{base_model_id}`) without mixing
them with downloaded model assets.

**Storage structure**:
```
data/
└── models/
    └── {external_model_id}/
        ├── assets/{sha256}/           # Downloaded model assets (040/042)
        │   ├── model.safetensors
        │   ├── config.json
        │   └── tokenizer.json
        └── adapters/{run_id}/         # NEW: LoRA adapters
            ├── adapter_model.safetensors  # peft-saved adapter weights
            ├── adapter_config.json        # peft LoraConfig serialization
            └── training_state.json        # metadata: method, rank, alpha, final_loss, etc.
```

**Database tracking**: Either extend `ModelAssetType` with an `ADAPTER` member or create a new
`Adapter` model. Following the existing pattern:
- `ModelAssetType.ADAPTER = "adapter"` — reuses existing `ModelAsset` table and repository
- `adapter_id` maps to the storage directory name (run ID, e.g. `run_42`)
- Each adapter is linked to its base model via `external_model_id` FK

---

### 4. Dual Dataset Format Loading

**Decision**: Distinguish data source by which existing selector is used — `corpus_id` (raw `.txt`)
vs `dataset_id` (prepared dataset). **CORRECTION from initial research**: the `Dataset` ORM model
(`anvil/db/models/dataset.py`) has NO `format` field. Corpora and datasets are separate ORM models
(`Corpus` vs `Dataset`) with separate tables, repositories, and API endpoints. There is no single
"format discriminator" column to read.

**Rationale**: The existing system already distinguishes raw text (`Corpus`) from prepared datasets
(`Dataset`) at the model/endpoint level. For structured (instruction/conversation) HF-format datasets,
the discriminator must come from the fine-tune dataset preparation layer (spec 053 —
`anvil/db/models/fine_tune_dataset.py`), which is where structured-format datasets are produced. A
`FineTuneDataset` already carries `base_model_ref` and structured content.

**Loading logic (corrected — no `Dataset.format` field)**:
```python
# Data source is chosen by which ID is populated, matching existing training flow:
if corpus_id is not None:
    docs = load_corpus_documents(corpus_id)          # raw .txt path (existing)
elif fine_tune_dataset_id is not None:
    # Structured instruction/conversation dataset (spec 053 artifact)
    ft_dataset = await ft_dataset_repo.get(fine_tune_dataset_id)
    docs = load_structured_examples(ft_dataset)      # datasets.load_dataset() over prepared file
elif dataset_id is not None:
    docs = load_dataset_documents(dataset_id)         # existing prepared-dataset path
```

**Open decision for planning**: whether structured LoRA training consumes `FineTuneDataset` (spec 053)
or a plain `Dataset`. Recommendation: reuse `FineTuneDataset` for instruction-tuning (it already models
structured content + `base_model_ref`), and `Corpus`/`Dataset` for the ad-hoc `.txt` path. This avoids
adding a `format` column that does not exist today.

---

### 5. Existing Pattern Reuse Summary

**ComputeBackendProtocol**: `LocalLoraBackend` implements `name`, `is_available()`, `async run()`.
Follows `LocalTorchBackend` pattern: `loop.run_in_executor()` for the blocking training loop,
`progress_callback(step, loss, tokens=n, grad_norm=g)` for SSE streaming, `stop_check()` for
cancellation.

**TrainConfig extension**: Add `method`, `lora_rank`, `lora_alpha`, `lora_target_modules`,
`lora_dropout`, `lora_bias` fields. All nullable — absent/null means use defaults. `method="full"`
or absent preserves existing behavior. `extra="forbid"` means explicit field definitions required.

**ComputeResult**: The existing `model` field can hold a `LlamaModel` instance (for downstream
safetensors export). The `artifact_uris` dict can carry adapter-specific paths. No structural
changes needed.

**RegistryBackend**: Add `LOCAL_LORA = "local-lora"` enum member. Auto-register via side-effect
import in `training.py` (existing pattern from `local_torch_backend.py`).

**TrainingService**: The `_build_progress_callback()` and `start_training()` flow is unchanged.
The SSE event types (`metrics`, `complete`, `error`, `divergence`) are reused exactly.

**Inference adaptation**: When `adapter_id` is specified on the generation request, load the
base model + apply the LoRA adapter via `PeftModel.from_pretrained(base_model, adapter_path)`.
When `adapter_id` is absent, fall back to base-only inference. **CORRECTION**: there is NO existing
text-generation endpoint — the inference API (`anvil/api/v1/inference.py`) has only 9 educational
routes (tokenize, embeddings, attention, sampling-distribution, forward-graph, backward-graph,
autograd-example, loss-breakdown, model-params). A generation endpoint is NEW work owned by this spec.
`InferenceService.load_model()` currently loads a single `LlamaModel` from
`data/models/experiment_{id}.json` with NO adapter concept — it must be extended.

### 6. Corrected Ground-Truth Reference (post pre-implementation verification)

| Item | Verified reality |
|---|---|
| Training request model | `TrainConfig` (NOT `TrainingConfig`), `anvil/api/v1/training.py` L54, `extra="forbid"` at L99 |
| Training route | `POST /v1/training/start` |
| Torch backend file | `anvil/services/compute/local_torch_backend.py` (NOT `torch_backend.py`) |
| `RegistryBackend` enum | `LOCAL_STDLIB="local-stdlib"`, `LOCAL_TORCH="local-torch"`, `MODAL="modal"` |
| `ComputeBackend` (user-facing) enum | `AUTO="auto"`, `LOCAL_CPU="local-cpu"`, `LOCAL_GPU="local-gpu"`, `MODAL="modal"` |
| `ComputeBackendProtocol` | `name: str` (class attr), `is_available()` staticmethod, `async run(docs, config, *, progress_callback, stop_check) -> ComputeResult` |
| `ComputeResult` fields | 12 fields incl. `model: object \| None`, `artifact_uris: dict[str,str]`, `engine`, `backend` |
| `ModelAssetType` | `StrEnum`: `WEIGHTS`, `TOKENIZER`, `CONFIG` (no `ADAPTER` yet) |
| `TimestampMixin` | `anvil/db/timestamp_mixin.py` — `created_at`, `updated_at` |
| Repository pattern | ctor takes `AsyncSession` → `self._session`; async methods; `flush()` + `refresh()` |
| Asset storage path | `models/{model_id}/assets/{sha256}/{filename}` (model_asset_service.py L325) |
| Inference load | `data/models/experiment_{model_id}.json`; NO adapter concept |
| God class | `AnvilWorkbench` (`anvil/workbench.py`); routes use `Depends(get_workbench)`, lazy service/repo properties |
| `[finetune]` extra (current) | `huggingface_hub`, `tokenizers`, `sentencepiece`, `transformers` — MUST add `peft`, `bitsandbytes`, `datasets`, `accelerate`; `torch` is in `[gpu]` |
| `Dataset` model | NO `format` field; `Corpus`/`Dataset`/`FineTuneDataset` are separate models |
| Catalog loader | `ModelBrowserService` (`anvil/services/inference/model_browser.py`) reads `curated-models.yaml`; envelope is `ResourceEnvelope` pydantic model (`resource_envelope.py`) — needs `default_target_modules` field |
| Training JS | inline in `training.html` (L1159 `startTraining()`); NO `training.js` file |
| Data source form IDs | `corpus_id` (L81), `dataset_id` (L87) |
| e2e tests | `tests/e2e/api/test_training_router.py`, `test_inference_api.py` exist; NO `tests/e2e/test_endpoints.py` |
| NMRG test precedent | `tests/e2e/test_nmrg_040.py` exists — mirror as `test_nmrg_044.py` |

---

### Resolved Unknowns

| Original Unknown | Resolution |
|---|---|
| `peft.LoraConfig` defaults | Target modules by arch in catalog; rank=8, alpha=16, dropout=0.05 as peft defaults |
| `bitsandbytes` availability gate | Try-import; degrade gracefully on platforms where unavailable |
| Adapter storage path | `models/{base_id}/adapters/{run_id}/` with `ModelAssetType.ADAPTER` |
| Dataset format detection | Check dataset metadata for HF-structured vs raw .txt |
| `ComputeBackendProtocol` integration | New `LocalLoraBackend` class, new `RegistryBackend.LOCAL_LORA` |
| Inference adapter selection | Explicit `adapter_id` field on inference request |