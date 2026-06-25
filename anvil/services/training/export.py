# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Safetensors export service — converts trained models to HF-compatible artifacts."""

import json
from pathlib import Path
from typing import Any

import numpy as np
from safetensors.numpy import save_file

from ...core.engine import LlamaModel

# ── Name mapping: anvil internal keys → HF LlamaForCausalLM keys ──

# Maps anvil internal parameter names to HuggingFace ``LlamaForCausalLM``
# tensor names. Layer-specific keys (attention, MLP, RMSNorm) are
# generated dynamically in ``export_state_dict()``.
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


def export_state_dict(model: LlamaModel) -> dict[str, list[Any]]:
    """Map anvil internal state dict to HF-compatible tensor names.

    Converts anvil's internal parameter naming convention (e.g.
    ``layer0.attn_wq``) to HuggingFace ``LlamaForCausalLM`` convention
    (e.g. ``model.layers.0.self_attn.q_proj.weight``). 2D matrices yield
    ``list[list[float]]``, 1D norm scales yield ``list[float]``.

    Parameters
    ----------
    model : LlamaModel
        The trained model whose state dict to convert.

    Returns
    -------
    dict[str, list]
        Mapping from HF-convention tensor names to raw value lists.
        No biases are included (Llama has bias-free linear layers).
    """
    hf_sd: dict[str, list[Any]] = {}
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
                proj_map = {
                    "attn_wq": "q_proj",
                    "attn_wk": "k_proj",
                    "attn_wv": "v_proj",
                    "attn_wo": "o_proj",
                }
                hf_key = (
                    f"model.layers.{layer_idx}.self_attn.{proj_map[sub_key]}.weight"
                )
            elif sub_key.startswith("mlp_"):
                proj_map = {
                    "mlp_gate": "gate_proj",
                    "mlp_up": "up_proj",
                    "mlp_down": "down_proj",
                }
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
            hf_sd[hf_key] = [[p.data for p in row] for row in mat]  # type: ignore[union-attr]
        else:
            # 1D vector: list[Value] → list[float]
            hf_sd[hf_key] = [p.data for p in mat]  # type: ignore[union-attr]

    return hf_sd


def generate_config(model: LlamaModel) -> dict[str, Any]:
    """Generate a ``LlamaConfig``-compatible JSON dict from model hyperparameters.

    Parameters
    ----------
    model : LlamaModel
        The trained model whose hyperparameters to serialise.

    Returns
    -------
    dict[str, Any]
        Configuration dict with keys matching HuggingFace's
        ``LlamaConfig`` (``hidden_size``, ``intermediate_size``,
        ``num_hidden_layers``, etc.).
    """
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
    """Generate tokenizer metadata in anvil's character-level format.

    Parameters
    ----------
    chars : list[str]
        Sorted list of unique characters in the vocabulary.

    Returns
    -------
    dict[str, Any]
        Tokenizer metadata with ``"type"``, ``"vocab"``,
        ``"bos_token"``, ``"bos_token_id"``, and ``"chars"`` keys.
    """
    return {
        "type": "CharacterLevelTokenizer",
        "vocab": {ch: i for i, ch in enumerate(sorted(chars))},
        "bos_token": "<BOS>",
        "bos_token_id": len(chars),  # BOS is the last index
        "chars": sorted(chars),
    }


def _generate_mlmodel_yaml() -> str:
    """Generate the ``MLmodel`` YAML for MLflow pyfunc loading.

    The ``loader_module`` points to ``anvil._pyfunc_model`` so the
    ``anvil`` package must be importable at inference time.

    Returns
    -------
    str
        YAML string describing the MLflow pyfunc model flavour.
    """
    return """artifact_path: ""
flavors:
  python_function:
    model:
      loader_module: anvil._pyfunc_model
      python_model: AnvilPyfuncModel
    env:
      conda: conda.yaml
"""


def _generate_conda_yaml() -> str:
    """Generate a minimal ``conda.yaml`` for MLflow environment reproduction.

    Returns
    -------
    str
        YAML string specifying the conda environment with Python
        and pip dependencies.
    """
    return """channels:
  - conda-forge
dependencies:
  - python=3.11
  - pip
  - pip:
    - anvil>=0.1.0
    - transformers>=4.30.0
    - torch>=2.0.0
    - safetensors>=0.4.0
    - numpy>=1.24.0
    - pandas
"""


class SafetensorsExportService:
    """Converts a trained Llama model to safetensors checkpoint artifacts."""

    def export(
        self, model: LlamaModel, output_dir: str | Path, chars: list[str]
    ) -> dict[str, str | None]:
        """Run full export: safetensors + config + tokenizer + MLflow MLmodel.

        Returns dict with keys: safetensors_path, config_path, tokenizer_path,
        mlmodel_path, conda_path, error
        On success, error is None. On failure, error is the message.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 1. Map state dict to HF names
            hf_sd = export_state_dict(model)

            # 2. Convert to numpy arrays and write safetensors
            np_tensors: dict[str, np.ndarray[Any, Any]] = {}
            for name, data in hf_sd.items():
                arr = np.array(data, dtype=np.float32)
                if not arr.flags["C_CONTIGUOUS"]:
                    arr = np.ascontiguousarray(arr)
                np_tensors[name] = arr

            safetensors_path = output_dir / "model.safetensors"
            save_file(
                np_tensors,
                str(safetensors_path),
                metadata={"format": "anvil", "architecture": "llama"},
            )

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

            # 5. Write MLflow MLmodel for pyfunc loading
            mlmodel_path = output_dir / "MLmodel"
            with open(mlmodel_path, "w") as f:
                f.write(_generate_mlmodel_yaml())

            # 6. Write conda env spec
            conda_path = output_dir / "conda.yaml"
            with open(conda_path, "w") as f:
                f.write(_generate_conda_yaml())

            return {
                "safetensors_path": str(safetensors_path),
                "config_path": str(config_path),
                "tokenizer_path": str(tokenizer_path),
                "mlmodel_path": str(mlmodel_path),
                "conda_path": str(conda_path),
                "error": None,
            }

        except ImportError as e:
            msg = f"safetensors export requires 'safetensors' and 'numpy' packages. Install with: pip install safetensors numpy. Original error: {e}"
            return {
                "safetensors_path": None,
                "config_path": None,
                "tokenizer_path": None,
                "mlmodel_path": None,
                "conda_path": None,
                "error": msg,
            }

        except Exception as e:  # pylint: disable=broad-exception-caught
            return {
                "safetensors_path": None,
                "config_path": None,
                "tokenizer_path": None,
                "mlmodel_path": None,
                "conda_path": None,
                "error": str(e),
            }

    def retry_export(
        self, model_path: str, output_dir: str | Path
    ) -> dict[str, str | None]:
        """Retry safetensors export from an existing model.json file.

        Useful for re-exporting a previously trained model without
        re-running training.

        Parameters
        ----------
        model_path : str
            Path to the saved ``model.json`` file.
        output_dir : str or Path
            Directory to write the exported artifacts to.

        Returns
        -------
        dict[str, str | None]
            Result dict with paths to exported artifacts and an
            ``"error"`` key (``None`` on success).
        """
        output_dir = Path(output_dir)
        try:
            model = LlamaModel.load(model_path)
            chars = model.chars or []
            return self.export(model, output_dir, chars)
        except Exception as e:  # pylint: disable=broad-exception-caught
            return {
                "safetensors_path": None,
                "config_path": None,
                "tokenizer_path": None,
                "mlmodel_path": None,
                "conda_path": None,
                "error": str(e),
            }
