# Contract: Safetensors Export Interface

**Feature**: 006-llama-engine-evolution  
**Phase**: 1 — Design & Contracts  
**Date**: 2026-06-14  

## Purpose

Define the interface for exporting trained models to the safetensors format — the primary model delivery artifact.

## Export Function Signature

```python
async def export_to_safetensors(
    model_path: str,              # Path to internal model.json
    experiment_id: str,           # MLflow experiment ID
    run_id: str,                  # MLflow run ID
    output_dir: str | None = None, # Override output directory
) -> SafetensorsExportResult:
    ...
```

## Return Type

```python
@dataclass
class SafetensorsExportResult:
    success: bool
    safetensors_path: str | None        # Path to model.safetensors
    config_path: str | None             # Path to config.json
    tokenizer_path: str | None          # Path to tokenizer.json
    error: str | None                   # Error message if failed
    tensor_count: int                   # Number of tensors exported
    total_bytes: int                    # Total byte size of weights
```

## Internal Steps

1. **Load model** — Read `model.json` via `GPT.load()`
2. **Map keys** — Convert internal state dict keys to HF naming convention
3. **Convert to numpy** — Each tensor matrix → `np.float32` contiguous array
4. **Write safetensors** — `safetensors.numpy.save_file(tensors, path)`
5. **Generate config.json** — Map hyperparams to LlamaConfig schema
6. **Generate tokenizer.json** — Serialize character vocabulary
7. **Track in MLflow** — Log safetensors artifact with run metadata
8. **Return result** — Paths to all generated files

## Error Handling (FR-016)

```python
# On failure during training completion:
# - Training is still recorded as successful
# - Error is flagged in UI and logs
# - User can retry export later from JSON
```

## Dependency

```toml
# pyproject.toml (service layer)
[project.dependencies]
safetensors = ">=0.4"
numpy = ">=1.24"
```

## Naming Convention Mapping

| anvil (internal) | safetensors (HF convention) |
|-----------------|---------------------------|
| `wte` | `model.embed_tokens.weight` |
| `lm_head` | `lm_head.weight` |
| `rms_final` | `model.norm.weight` |
| `layer{i}.attn_wq` | `model.layers.{i}.self_attn.q_proj.weight` |
| `layer{i}.attn_wk` | `model.layers.{i}.self_attn.k_proj.weight` |
| `layer{i}.attn_wv` | `model.layers.{i}.self_attn.v_proj.weight` |
| `layer{i}.attn_wo` | `model.layers.{i}.self_attn.o_proj.weight` |
| `layer{i}.mlp_gate` | `model.layers.{i}.mlp.gate_proj.weight` |
| `layer{i}.mlp_up` | `model.layers.{i}.mlp.up_proj.weight` |
| `layer{i}.mlp_down` | `model.layers.{i}.mlp.down_proj.weight` |
| `layer{i}.rms_1` | `model.layers.{i}.input_layernorm.weight` |
| `layer{i}.rms_2` | `model.layers.{i}.post_attention_layernorm.weight` |

## Export Correctness Requirements (CRITICAL)

These prevent silent logit mismatches when the export is loaded by a standards-compatible tool:

1. **Tensor layout**: All weight matrices MUST be written in `[out_features, in_features]` row-major order, matching the target architecture. If anvil's internal `linear()` uses the opposite layout, transpose on export.
2. **RoPE convention**: The engine MUST train/infer with half-split (rotate_half) RoPE so weights export without permutation (FR-003). If interleaved RoPE were used, `q_proj`/`k_proj` rows would need a per-head permutation on export — the spec mandates half-split to avoid this.
3. **SwiGLU branch mapping**: `gate_proj` is the SiLU-activated branch; `up_proj` is the linear branch. Swapping them loads cleanly but produces wrong output — verify the mapping.
4. **No biases**: Llama linear layers are bias-free; the export MUST NOT emit any `*.bias` tensors.
5. **All 12 parameter groups present**: embed_tokens, q/k/v/o_proj, gate/up/down_proj, input_layernorm, post_attention_layernorm, model.norm, lm_head. A missing group fails loading (not silent).
6. **Verification**: A toy one-layer/one-head golden test SHOULD compare native intermediate tensors (q, k, rotated q/k, attention scores, final logits) against the target-tool forward pass to catch silent export bugs early.

## Retry Export

```python
async def retry_export_from_json(
    experiment_id: str,
    run_id: str,
) -> SafetensorsExportResult:
    """Retry safetensors generation from a previously-trained model's JSON."""
    ...
```