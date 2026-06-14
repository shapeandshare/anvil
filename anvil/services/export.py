"""Safetensors export service — converts trained models to HF-compatible artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from safetensors.numpy import save_file

from anvil.core.engine import GPT


# ── Name mapping: anvil internal keys → HF LlamaForCausalLM keys ──

ANVIL_TO_HF: dict[str, str] = {
    "wte": "model.embed_tokens.weight",
    "lm_head": "lm_head.weight",
    "rms_final": "model.norm.weight",
}
# Layer keys are generated dynamically in export_state_dict:
# layer{i}.attn_wq → model.layers.{i}.self_attn.q_proj.weight
# layer{i}.attn_wk → model.layers.{i}.self_attn.k_proj.weight
# layer{i}.attn_wv → model.layers.{i}.self_attn.v_proj.weight
# layer{i}.attn_wo → model.layers.{i}.self_attn.o_proj.weight
# layer{i}.mlp_gate → model.layers.{i}.mlp.gate_proj.weight
# layer{i}.mlp_up → model.layers.{i}.mlp.up_proj.weight
# layer{i}.mlp_down → model.layers.{i}.mlp.down_proj.weight
# layer{i}.rms_1 → model.layers.{i}.input_layernorm.weight
# layer{i}.rms_2 → model.layers.{i}.post_attention_layernorm.weight


def export_state_dict(model: GPT) -> dict[str, list]:
    """Map anvil internal state dict to HF-compatible tensor names.

    Returns dict mapping HF-convention tensor names to raw value lists.
    2D matrices are list[list[float]], 1D norm scales are list[float].
    No biases included (Llama has bias-free linear layers).
    """
    hf_sd: dict[str, list] = {}
    for internal_key, mat in model.state_dict.items():
        if internal_key == "wte":
            hf_key = "model.embed_tokens.weight"
        elif internal_key == "lm_head":
            hf_key = "lm_head.weight"
        elif internal_key == "rms_final":
            hf_key = "model.norm.weight"
        elif internal_key.startswith("layer"):
            parts = internal_key.split(".")
            layer_idx = parts[0].replace("layer", "")
            sub_key = parts[1]
            if sub_key.startswith("attn_"):
                proj_map = {"attn_wq": "q_proj", "attn_wk": "k_proj", "attn_wv": "v_proj", "attn_wo": "o_proj"}
                hf_key = f"model.layers.{layer_idx}.self_attn.{proj_map[sub_key]}.weight"
            elif sub_key.startswith("mlp_"):
                proj_map = {"mlp_gate": "gate_proj", "mlp_up": "up_proj", "mlp_down": "down_proj"}
                hf_key = f"model.layers.{layer_idx}.mlp.{proj_map[sub_key]}.weight"
            elif sub_key == "rms_1":
                hf_key = f"model.layers.{layer_idx}.input_layernorm.weight"
            elif sub_key == "rms_2":
                hf_key = f"model.layers.{layer_idx}.post_attention_layernorm.weight"
            else:
                continue  # skip unknown keys
        else:
            continue  # skip unknown keys

        # Convert: Value objects → float data
        if isinstance(mat[0], list):
            # 2D matrix: list[list[Value]] → list[list[float]]
            hf_sd[hf_key] = [[p.data for p in row] for row in mat]
        else:
            # 1D vector: list[Value] → list[float]
            hf_sd[hf_key] = [p.data for p in mat]

    return hf_sd


def generate_config(model: GPT) -> dict[str, Any]:
    """Generate LlamaConfig-compatible JSON dict from GPT hyperparameters."""
    return {
        "model_type": "llama",
        "vocab_size": model.vocab_size,
        "hidden_size": model.n_embd,
        "intermediate_size": model.intermediate_size,
        "num_hidden_layers": model.n_layer,
        "num_attention_heads": model.n_head,
        "num_key_value_heads": model.n_head,  # MHA (not GQA)
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


def generate_tokenizer(chars: list[str]) -> dict[str, Any]:
    """Generate tokenizer metadata in anvil's character-level format."""
    return {
        "type": "CharacterLevelTokenizer",
        "vocab": {ch: i for i, ch in enumerate(sorted(chars))},
        "bos_token": "<BOS>",
        "bos_token_id": len(chars),  # BOS is the last index
        "chars": sorted(chars),
    }


class SafetensorsExportError(Exception):
    """Raised when safetensors export fails."""

    pass


class SafetensorsExportService:
    """Converts a trained GPT model to safetensors checkpoint artifacts."""

    def export(self, model: GPT, output_dir: str | Path, chars: list[str]) -> dict[str, str | None]:
        """Run full export: safetensors + config + tokenizer.

        Returns dict with keys: safetensors_path, config_path, tokenizer_path, error
        On success, error is None. On failure, error is the message.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 1. Map state dict to HF names
            hf_sd = export_state_dict(model)

            # 2. Convert to numpy arrays and write safetensors
            np_tensors: dict[str, np.ndarray] = {}
            for name, data in hf_sd.items():
                arr = np.array(data, dtype=np.float32)
                if not arr.flags["C_CONTIGUOUS"]:
                    arr = np.ascontiguousarray(arr)
                np_tensors[name] = arr

            safetensors_path = output_dir / "model.safetensors"
            save_file(np_tensors, str(safetensors_path),
                      metadata={"format": "anvil", "architecture": "llama"})

            # 3. Write config.json
            config = generate_config(model)
            config_path = output_dir / "config.json"
            with open(config_path, "w") as f:
                json.dump(config, f, indent=2)

            # 4. Write tokenizer file
            tokenizer_data = generate_tokenizer(chars)
            tokenizer_path = output_dir / "tokenizer.json"
            with open(tokenizer_path, "w") as f:
                json.dump(tokenizer_data, f, indent=2)

            return {
                "safetensors_path": str(safetensors_path),
                "config_path": str(config_path),
                "tokenizer_path": str(tokenizer_path),
                "error": None,
            }

        except ImportError as e:
            msg = f"safetensors export requires 'safetensors' and 'numpy' packages. Install with: pip install safetensors numpy. Original error: {e}"
            return {"safetensors_path": None, "config_path": None, "tokenizer_path": None, "error": msg}

        except Exception as e:
            return {"safetensors_path": None, "config_path": None, "tokenizer_path": None, "error": str(e)}

    def retry_export(self, model_path: str, output_dir: str | Path) -> dict[str, str | None]:
        """Retry safetensors export from an existing model.json file."""
        output_dir = Path(output_dir)
        try:
            model = GPT.load(model_path)
            chars = model.chars or []
            return self.export(model, output_dir, chars)
        except Exception as e:
            return {"safetensors_path": None, "config_path": None, "tokenizer_path": None, "error": str(e)}