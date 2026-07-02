# Data Model: Fine-Tune Compute Routing

**Feature**: 046 Fine-Tune Compute Routing
**Date**: 2026-07-01
**Extends**: Existing `anvil/services/compute/` data model

## Entities

### ResourceSpec (fine-tune conceptual type)

A computed representation of a fine-tune job's resource requirements. Used by `resolve_fine_tune()` to determine whether a job fits the local envelope.

| Field | Type | Description | Derivation |
|-------|------|-------------|------------|
| `base_params` | `int` | Number of parameters in the base model | From model entry (e.g., TinyLlama = 1.1B) |
| `method` | `str` | Fine-tuning method | `"full"`, `"lora"`, `"qlora"` |
| `quantization` | `str \| None` | Quantization level | `None` (none), `"4bit"`, `"8bit"` |
| `computed_vram_gb` | `float` | Estimated VRAM in GB | `base_params * method_mult * quant_factor + overhead` |
| `fits_local` | `bool` | Whether the job fits the local envelope | `computed_vram_gb <= available_host_memory_gb` |

**Method multipliers**:
- `full`: 2.0× base param size on RAM
- `lora`: 1.2× base param size on RAM
- `qlora`: 0.6× base param size on RAM

**Constraints**:
- `method` must be one of `"full"`, `"lora"`, `"qlora"` (validated at routing time)
- `base_params` is obtained from the model entry (curated catalog or imported model metadata)
- Overhead is a fixed constant (e.g., 0.5 GB) to account for intermediate buffers

### ComputeBackend (enum — modify)

**File**: `anvil/services/compute/compute_backend.py`

| Member | Value | Description |
|--------|-------|-------------|
| `AUTO` | `"auto"` | Auto-select best available backend (existing) |
| `LOCAL_CPU` | `"local-cpu"` | Local CPU-only execution (existing) |
| `LOCAL_GPU` | `"local-gpu"` | Local GPU execution (existing) |
| `MODAL` | `"modal"` | Modal cloud GPU (existing) |
| `SAAS` | `"saas"` | **New** — SaaS batch compute (spec 047) |

### ComputeBackendResult (enum — modify)

**File**: `anvil/services/compute/compute_backend_result.py`

| Member | Value | Description |
|--------|-------|-------------|
| `LOCAL` | `"local"` | Local execution (existing) |
| `MODAL` | `"modal"` | Modal cloud GPU (existing) |
| `SAAS` | `"saas"` | **New** — SaaS batch compute |

### RegistryBackend (enum — modify)

**File**: `anvil/services/compute/registry_backend.py`

| Member | Value | Description |
|--------|-------|-------------|
| `LOCAL_STDLIB` | `"local-stdlib"` | Local stdlib backend (existing) |
| `LOCAL_TORCH` | `"local-torch"` | Local PyTorch backend (existing) |
| `LOCAL_LORA` | `"local-lora"` | Local LoRA fine-tuning backend (existing) |
| `MODAL` | `"modal"` | Modal cloud GPU (existing) |
| `SAAS_FINETUNE` | `"saas-finetune"` | **New** — SaaS fine-tune backend (spec 047) |

### ComputeResult (existing — no changes needed)

**File**: `anvil/services/compute/result.py`

Already supports the adapter path used by fine-tuning:
- `adapter_id: str | None` — scoped adapter identifier
- `artifact_uris["adapter_path"]` — path to adapter weights
- `backend: ComputeBackendResult` — identifies which backend ran the job (will include `SAAS`)

### ComputeStatus (existing — no changes needed)

**File**: `anvil/services/compute/compute_status.py`

- `SUBMITTED`, `RUNNING`, `COMPLETED`, `FAILED` — full lifecycle coverage

## Relationships

```text
User config (compute_backend="auto")
  → resolve_backend(config)                    # existing entry point
    → if method in ("lora","qlora") → delegates to resolve_fine_tune(config)
  → resolve_fine_tune(config)
    → Compute ResourceSpec (params × method × quant)
    → if fits local → local-lora backend → ComputeResult(backend=LOCAL, adapter_id=...)
    → if over local + SaaS configured → SaaS backend → ComputeResult(backend=SAAS, adapter_id=...)
    → if over local + SaaS not configured → guidance message (auto) / raise (explicit local)
```

## State Transitions

```text
[Submitted] → [Running] → [Completed]
                         → [Failed]  (including SaaS mid-job failure)
```

The `ComputeStatus` enum covers all states. Transitions are driven by the backend's submit-then-poll loop (D3 pattern).

## Validation Rules

1. `resolve_fine_tune()` input config must contain `method` and `base_model_ref`
2. `method` must be one of `"full"`, `"lora"`, `"qlora"`
3. `compute_backend` must be one of the existing `ComputeBackend` values plus the new `saas`:
   `"auto"`, `"local-cpu"`, `"local-gpu"`, `"saas"`. There is **no bare `"local"`** value — "run
   locally" is expressed via `local-cpu`/`local-gpu`/`auto`.
4. If `compute_backend` is `"local-cpu"`/`"local-gpu"` and `ResourceSpec.fits_local=False` → raise
   `ComputeBackendUnavailable`
5. If `compute_backend="saas"` and SaaS not configured → raise `ComputeBackendUnavailable`