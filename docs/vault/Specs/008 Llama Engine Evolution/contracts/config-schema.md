# Contract: Config JSON Schema (Llama-compatible)

**Feature**: 006-llama-engine-evolution  
**Phase**: 1 — Design & Contracts  
**Date**: 2026-06-14  

## Purpose

Define the `config.json` schema generated as part of the safetensors checkpoint. Matches HuggingFace `LlamaConfig` for compatibility.

## Schema

| Field | Type | Required | Default | Source |
|-------|------|----------|---------|--------|
| `model_type` | `str` | Yes | `"llama"` | Hardcoded |
| `vocab_size` | `int` | Yes | — | `GPT.vocab_size` |
| `hidden_size` | `int` | Yes | — | `GPT.n_embd` |
| `intermediate_size` | `int` | Yes | — | `GPT.intermediate_size` |
| `num_hidden_layers` | `int` | Yes | — | `GPT.n_layer` |
| `num_attention_heads` | `int` | Yes | — | `GPT.n_head` |
| `num_key_value_heads` | `int` | No | `num_attention_heads` | Same as `n_head` (MHA) |
| `max_position_embeddings` | `int` | Yes | — | `GPT.block_size` |
| `hidden_act` | `str` | No | `"silu"` | Hardcoded |
| `rms_norm_eps` | `float` | No | `1e-5` | Matches engine's `1e-5` |
| `initializer_range` | `float` | No | `0.02` | Default (not configurable) |
| `use_cache` | `bool` | No | `true` | Default |
| `bos_token_id` | `int` | No | `1` | BOS token ID |
| `eos_token_id` | `int` | No | `2` | EOS token ID |
| `tie_word_embeddings` | `bool` | No | `false` | Not tied in anvil |
| `attention_bias` | `bool` | No | `false` | No biases in Llama |
| `mlp_bias` | `bool` | No | `false` | No biases in Llama |
| `attention_dropout` | `float` | No | `0.0` | Not used |
| `head_dim` | `int` | No | `hidden_size // num_attention_heads` | Derived; MUST be even (FR-017) |
| `rope_theta` | `float` | No | `10000.0` | RoPE base frequency — set EXPLICITLY to avoid version drift |
| `rope_scaling` | `null` | No | `null` | No RoPE scaling applied |

## Generator Function

```python
def generate_config(model: GPT) -> dict:
    return {
        "model_type": "llama",
        "vocab_size": model.vocab_size,
        "hidden_size": model.n_embd,
        "intermediate_size": model.intermediate_size,
        "num_hidden_layers": model.n_layer,
        "num_attention_heads": model.n_head,
        "num_key_value_heads": model.n_head,
        "max_position_embeddings": model.block_size,
        "hidden_act": "silu",
        "rms_norm_eps": 1e-5,
        "initializer_range": 0.02,
        "use_cache": True,
        "bos_token_id": 1,
        "eos_token_id": 2,
        "tie_word_embeddings": False,
        "attention_bias": False,
        "mlp_bias": False,
        "attention_dropout": 0.0,
        "head_dim": model.head_dim,
        "rope_theta": 10000.0,
        "rope_scaling": None,
    }
```

## Example Output

For `n_embd=16, n_head=4, n_layer=1, block_size=16, vocab_size=27`:

```json
{
  "model_type": "llama",
  "vocab_size": 27,
  "hidden_size": 16,
  "intermediate_size": 42,
  "num_hidden_layers": 1,
  "num_attention_heads": 4,
  "num_key_value_heads": 4,
  "max_position_embeddings": 16,
  "hidden_act": "silu",
  "rms_norm_eps": 1e-5,
  "initializer_range": 0.02,
  "use_cache": true,
  "bos_token_id": 1,
  "eos_token_id": 2,
  "tie_word_embeddings": false,
  "attention_bias": false,
  "mlp_bias": false,
  "attention_dropout": 0.0,
  "head_dim": 4,
  "rope_theta": 10000.0,
  "rope_scaling": null
}
```