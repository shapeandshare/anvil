---
title: Safetensors Export & HF Interop
type: reference
tags:
  - type/reference
  - domain/core
created: 2026-06-15
updated: 2026-06-15
aliases:
  - export-pipeline
  - hf-interop
  - safetensors
related:
  - '[[Reference/MlflowIntegration]]'
---

# Safetensors Export & HuggingFace Interoperability

## Overview

After training completes, anvil can export the model to the **safetensors** format — a safe, fast serialization format that is the standard for HuggingFace `transformers` libraries. This export converts anvil's internal state dict (Value objects in nested Python lists) into HF-convention tensor names with proper metadata.

**Why this matters**: A model exported by anvil can be loaded by any Llama-compatible inference tool — `transformers`, `llama.cpp`, `vLLM`, `text-generation-inference`, or custom PyTorch code. The export pipeline ensures:
- Tensor names match `LlamaForCausalLM` conventions
- Config keys match `LlamaConfig` expectations
- Tokenizer metadata matches anvil's character-level format
- MLflow can register the model as a pyfunc for deployment

## Export Pipeline

```
LlamaModel (CPU)
    │
    ├── export_state_dict()
    │     └── Map internal keys → HF tensor names
    │
    ├── generate_config()
    │     └── Build LlamaConfig-compatible JSON
    │
    ├── generate_tokenizer()
    │     └── Character-level tokenizer metadata
    │
    └── SafetensorsExportService.export()
          ├── Convert to numpy arrays (float32)
          ├── Write model.safetensors
          ├── Write config.json
          ├── Write tokenizer.json
          ├── Write MLmodel (MLflow pyfunc loader)
          └── Write conda.yaml (MLflow env spec)
```

**File**: `anvil/services/export.py` — `class SafetensorsExportService`

## Tensor Name Mapping

The critical bridge is in `export_state_dict()`. Every anvil internal key maps to an HF `LlamaForCausalLM` tensor name:

### Embeddings & LM Head

| anvil key | HF key | Shape |
|-----------|--------|-------|
| `wte` | `model.embed_tokens.weight` | `vocab_size × n_embd` |
| `lm_head` | `lm_head.weight` | `vocab_size × n_embd` |

### Attention (per layer `i`)

| anvil key | HF key | Shape |
|-----------|--------|-------|
| `layer{i}.attn_wq` | `model.layers.{i}.self_attn.q_proj.weight` | `n_embd × n_embd` |
| `layer{i}.attn_wk` | `model.layers.{i}.self_attn.k_proj.weight` | `n_embd × n_embd` |
| `layer{i}.attn_wv` | `model.layers.{i}.self_attn.v_proj.weight` | `n_embd × n_embd` |
| `layer{i}.attn_wo` | `model.layers.{i}.self_attn.o_proj.weight` | `n_embd × n_embd` |

### SwiGLU MLP (per layer `i`)

| anvil key | HF key | Shape |
|-----------|--------|-------|
| `layer{i}.mlp_gate` | `model.layers.{i}.mlp.gate_proj.weight` | `intermediate_size × n_embd` |
| `layer{i}.mlp_up` | `model.layers.{i}.mlp.up_proj.weight` | `intermediate_size × n_embd` |
| `layer{i}.mlp_down` | `model.layers.{i}.mlp.down_proj.weight` | `n_embd × intermediate_size` |

### RMSNorm Learned Scales (per layer `i`)

| anvil key | HF key | Shape |
|-----------|--------|-------|
| `layer{i}.rms_1` | `model.layers.{i}.input_layernorm.weight` | `n_embd` |
| `layer{i}.rms_2` | `model.layers.{i}.post_attention_layernorm.weight` | `n_embd` |
| `rms_final` | `model.norm.weight` | `n_embd` |

### What is NOT exported

No biases — Llama architecture uses bias-free linear layers. No `wpe` (learned position embeddings) — RoPE is a computation, not a parameter. No embedding-level norm — removed per Llama architecture.

## Config Generation (`generate_config()`)

The generated `config.json` is compatible with HuggingFace `LlamaConfig`. Key fields:

```json
{
  "model_type": "llama",
  "vocab_size": 27,
  "hidden_size": 16,
  "intermediate_size": 42,
  "num_hidden_layers": 2,
  "num_attention_heads": 4,
  "num_key_value_heads": 4,
  "max_position_embeddings": 16,
  "hidden_act": "silu",
  "rms_norm_eps": 1e-5,
  "attention_bias": false,
  "mlp_bias": false,
  "head_dim": 4,
  "rope_theta": 10000.0,
  "rope_scaling": null,
  "tie_word_embeddings": false
}
```

Key design points:
- **MHA, not GQA**: `num_key_value_heads == num_attention_heads` (no grouped-query attention)
- **No weight tying**: `tie_word_embeddings: false` — `wte` and `lm_head` are separate parameters
- **Standard RoPE frequency**: `rope_theta: 10000.0` — matches original Llama
- **SiLU activation**: `hidden_act: "silu"` — the SiLU/Swish activation used by SwiGLU

## Tokenizer Export

The character-level tokenizer is exported as a JSON file with this structure:

```json
{
  "type": "CharacterLevelTokenizer",
  "vocab": {"a": 0, "b": 1, ..., "z": 25},
  "bos_token": "<BOS>",
  "bos_token_id": 26,
  "chars": ["a", "b", ..., "z"]
}
```

## MLflow Pyfunc Model

The export also generates MLflow-compatible metadata for model registry and deployment:

- **`MLmodel`**: Points to `anvil._pyfunc_model.AnvilPyfuncModel` as the loader
- **`conda.yaml`**: Environment specification listing `anvil`, `transformers`, `torch`, `safetensors`, `numpy` as dependencies

## Loading Exported Models in HuggingFace

```python
from transformers import AutoModelForCausalLM, AutoConfig

config = AutoConfig.from_pretrained("./export_dir")
model = AutoModelForCausalLM.from_pretrained("./export_dir", config=config)
```

The model loads as a `LlamaForCausalLM` instance with the corresponding architecture. Because parameters are float32 and tiny (the default anvil config), this is primarily useful for:
- Verifying the export pipeline correctness
- Educational inspection of Llama weight structure
- Testing downstream tooling compatibility

## See Also

- [[Decisions/ADR-007-llama-engine-evolution|ADR-007]] — Architecture decisions that drove the Llama migration
- [[TrainingDataFlow]] — Full training pipeline from browser to export
- [[ProgressiveWalkthroughs]] — train5 demonstrates safetensors export