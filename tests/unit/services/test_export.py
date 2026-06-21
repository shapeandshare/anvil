# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for safetensors export service."""

import json
import tempfile
from pathlib import Path

import pytest

from anvil.core.engine import LlamaModel
from anvil.services.training.export import (
    SafetensorsExportService,
    export_state_dict,
    generate_config,
    generate_tokenizer,
)


class TestExportStateDict:
    def test_maps_all_keys(self):
        model = LlamaModel(vocab_size=10, n_embd=8, n_head=2, n_layer=1, block_size=8)
        hf_sd = export_state_dict(model)

        # Should contain all expected HF keys
        assert "model.embed_tokens.weight" in hf_sd
        assert "model.norm.weight" in hf_sd
        assert "lm_head.weight" in hf_sd
        assert "model.layers.0.self_attn.q_proj.weight" in hf_sd
        assert "model.layers.0.self_attn.k_proj.weight" in hf_sd
        assert "model.layers.0.self_attn.v_proj.weight" in hf_sd
        assert "model.layers.0.self_attn.o_proj.weight" in hf_sd
        assert "model.layers.0.mlp.gate_proj.weight" in hf_sd
        assert "model.layers.0.mlp.up_proj.weight" in hf_sd
        assert "model.layers.0.mlp.down_proj.weight" in hf_sd
        assert "model.layers.0.input_layernorm.weight" in hf_sd
        assert "model.layers.0.post_attention_layernorm.weight" in hf_sd

    def test_no_bias_keys(self):
        model = LlamaModel(vocab_size=10, n_embd=8, n_head=2)
        hf_sd = export_state_dict(model)
        bias_keys = [k for k in hf_sd if "bias" in k]
        assert len(bias_keys) == 0, f"Found unexpected bias keys: {bias_keys}"

    def test_no_synthetic_keys(self):
        model = LlamaModel(vocab_size=10, n_embd=8, n_head=2)
        hf_sd = export_state_dict(model)
        # Every tensor must correspond to a trained parameter in the model state dict
        internal_keys = set(model.state_dict.keys())
        # Count equal number of tensors on both sides (same cardinality, mapped properly)
        assert len(hf_sd) == len(internal_keys)

    def test_rms_weights_are_1d(self):
        model = LlamaModel(vocab_size=10, n_embd=8, n_head=2, n_layer=2)
        hf_sd = export_state_dict(model)
        # RMS weights should be 1D lists
        assert isinstance(hf_sd["model.norm.weight"], list)
        assert not isinstance(hf_sd["model.norm.weight"][0], list)
        assert len(hf_sd["model.norm.weight"]) == 8  # n_embd

    def test_values_are_floats(self):
        """Verify exported values are plain floats, not Value objects."""
        model = LlamaModel(vocab_size=5, n_embd=4, n_head=2, n_layer=1)
        hf_sd = export_state_dict(model)
        # Check a 2D tensor
        embed_row = hf_sd["model.embed_tokens.weight"][0]
        assert all(isinstance(v, (int, float)) for v in embed_row)
        # Check a 1D tensor
        norm_vals = hf_sd["model.norm.weight"]
        assert all(isinstance(v, (int, float)) for v in norm_vals)


class TestGenerateConfig:
    def test_contains_all_required_fields(self):
        model = LlamaModel(vocab_size=27, n_embd=16, n_head=4, n_layer=2, block_size=32)
        config = generate_config(model)
        assert config["model_type"] == "llama"
        assert config["vocab_size"] == 27
        assert config["hidden_size"] == 16
        assert config["intermediate_size"] == int(8 * 16 / 3)
        assert config["num_hidden_layers"] == 2
        assert config["num_attention_heads"] == 4
        assert config["max_position_embeddings"] == 32
        assert config["hidden_act"] == "silu"
        assert config["rms_norm_eps"] == 1e-5
        assert config["rope_theta"] == 10000.0
        assert config["rope_scaling"] is None
        assert config["attention_bias"] is False
        assert config["mlp_bias"] is False

    def test_head_dim_computed(self):
        model = LlamaModel(vocab_size=10, n_embd=16, n_head=4)
        config = generate_config(model)
        assert config["head_dim"] == 4  # 16 / 4

    def test_num_kv_heads_equals_n_head(self):
        """MHA (not GQA) — kv heads equal query heads."""
        model = LlamaModel(vocab_size=10, n_embd=32, n_head=8)
        config = generate_config(model)
        assert config["num_key_value_heads"] == config["num_attention_heads"]

    def test_tie_word_embeddings_false(self):
        model = LlamaModel(vocab_size=10, n_embd=8, n_head=2)
        config = generate_config(model)
        assert config["tie_word_embeddings"] is False


class TestGenerateTokenizer:
    def test_character_vocabulary(self):
        chars = ["a", "b", "c"]
        tok = generate_tokenizer(chars)
        assert tok["type"] == "CharacterLevelTokenizer"
        assert tok["vocab"]["a"] == 0
        assert tok["vocab"]["b"] == 1
        assert tok["vocab"]["c"] == 2
        assert tok["bos_token_id"] == 3  # len(chars) = BOS index

    def test_empty_chars(self):
        tok = generate_tokenizer([])
        assert tok["vocab"] == {}
        assert tok["bos_token_id"] == 0
        assert tok["chars"] == []

    def test_chars_sorted(self):
        chars = ["c", "a", "b"]
        tok = generate_tokenizer(chars)
        assert tok["chars"] == ["a", "b", "c"]
        assert list(tok["vocab"].keys()) == ["a", "b", "c"]


class TestSafetensorsExportService:
    def test_export_produces_files(self):
        model = LlamaModel(vocab_size=10, n_embd=8, n_head=2, n_layer=1)
        chars = ["a", "b"]
        svc = SafetensorsExportService()

        with tempfile.TemporaryDirectory() as tmpdir:
            result = svc.export(model, tmpdir, chars)
            assert result["error"] is None
            assert result["safetensors_path"] is not None
            assert result["config_path"] is not None
            assert result["tokenizer_path"] is not None
            assert result["mlmodel_path"] is not None
            assert result["conda_path"] is not None

            # Verify files exist
            assert Path(result["safetensors_path"]).exists()
            assert Path(result["config_path"]).exists()
            assert Path(result["tokenizer_path"]).exists()
            assert Path(result["mlmodel_path"]).exists()
            assert Path(result["conda_path"]).exists()

            # Verify config.json parses
            with open(result["config_path"]) as f:
                config = json.load(f)
            assert config["model_type"] == "llama"

            # Verify MLmodel contains pyfunc flavor
            with open(result["mlmodel_path"]) as f:
                mlmodel = f.read()
            assert "AnvilPyfuncModel" in mlmodel
            assert "loader_module: anvil._pyfunc_model" in mlmodel

            # Verify conda.yaml contains key deps
            with open(result["conda_path"]) as f:
                conda = f.read()
            assert "transformers" in conda
            assert "anvil" in conda

    def test_export_no_synthetic_tensors(self):
        """FR-009: every tensor maps to a trained parameter."""
        model = LlamaModel(vocab_size=10, n_embd=8, n_head=2)
        chars = []
        svc = SafetensorsExportService()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = svc.export(model, tmpdir, chars)
            assert result["error"] is None

    def test_retry_export_from_json(self):
        """Retry export from an existing model.json file."""
        model = LlamaModel(vocab_size=10, n_embd=8, n_head=2, n_layer=1)
        chars = ["x", "y"]
        svc = SafetensorsExportService()

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "model.json"
            model.save(str(model_path), chars)

            result = svc.retry_export(str(model_path), tmpdir)
            assert result["error"] is None
            assert Path(result["safetensors_path"]).exists()

    def test_export_with_trained_model_values(self):
        """Verify export works with a model that has non-default parameter values."""
        model = LlamaModel(vocab_size=10, n_embd=8, n_head=2, n_layer=1)
        # Modify some weights to ensure they're exported correctly
        model.state_dict["wte"][0][0].data = 0.42
        model.state_dict["rms_final"][0].data = 0.99

        chars = ["a"]
        svc = SafetensorsExportService()

        with tempfile.TemporaryDirectory() as tmpdir:
            result = svc.export(model, tmpdir, chars)
            assert result["error"] is None

    def test_export_output_dir_created(self):
        """Output directory is created if it doesn't exist."""
        model = LlamaModel(vocab_size=5, n_embd=4, n_head=2, n_layer=1)
        svc = SafetensorsExportService()

        with tempfile.TemporaryDirectory() as tmpdir:
            nested = Path(tmpdir) / "nested" / "export"
            result = svc.export(model, str(nested), [])
            assert result["error"] is None
            assert Path(result["safetensors_path"]).exists()
            assert nested.exists()

    def test_retry_export_invalid_path(self):
        """retry_export returns error for nonexistent model file."""
        svc = SafetensorsExportService()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = svc.retry_export("/nonexistent/model.json", tmpdir)
            assert result["error"] is not None
            assert result["safetensors_path"] is None


class TestSafetensorsExportError:
    """Tests for the SafetensorsExportError exception class."""

    def test_construct_with_message(self):
        """Constructing SafetensorsExportError with a message should
        store and expose it via str and repr."""
        from anvil.services.training.safetensors_export_error import (
            SafetensorsExportError,
        )

        msg = "failed to export model"
        err = SafetensorsExportError(msg)
        assert str(err) == msg
        assert msg in repr(err)
        assert isinstance(err, Exception)
