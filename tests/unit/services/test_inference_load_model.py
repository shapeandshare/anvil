# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for InferenceService.load_model and _resolve_default_id.

Covers disk-artifact loading, MLflow registry fallback, default-ID
resolution, and the silent ``except Exception: pass`` catch.
"""

from __future__ import annotations

import asyncio
import json
import math
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from anvil.core.engine import LlamaModel, train
from anvil.core.vocabulary import Vocabulary
from anvil.services.inference.inference import InferenceService
from anvil.services.inference.loaded_model import LoadedModel
from anvil.services.tracking.tracking import TrackingService


def _train_tiny_model(tmp_path: Path) -> tuple[Path, list[str], str]:
    """Train a tiny model and save it to a JSON file.

    Parameters
    ----------
    tmp_path : Path
        Temporary directory for the output file.

    Returns
    -------
    tuple of (Path, list[str], str)
        ``(saved_path, chars, serialized_data_str)``.
    """
    docs = ["abc", "def", "ghi"]
    model, _, _, uchars = train(docs, num_steps=20, n_embd=8, n_head=2, block_size=16)
    model_path = tmp_path / "train_save.json"
    model.save(str(model_path), uchars)
    with open(model_path, encoding="utf-8") as f:
        raw = json.load(f)
    return model_path, uchars, raw


######################################################################
# load_model - disk artifact path
######################################################################


def test_load_model_disk_artifact_path(monkeypatch, tmp_path):
    """load_model loads from ``data/models/experiment_{id}.json``."""
    docs = ["abc", "def", "ghi"]
    model, _, _, uchars = train(docs, num_steps=20, n_embd=8, n_head=2, block_size=16)
    models_dir = Path("data/models")
    models_dir.mkdir(parents=True, exist_ok=True)
    model_path = models_dir / "experiment_88.json"
    model.save(str(model_path), uchars)

    # Prevent fallback into MLflow path
    async def no_models(self, search=None):
        return []

    monkeypatch.setattr(TrackingService, "list_registered_models", no_models)

    service = InferenceService()
    loaded = asyncio.run(service.load_model(model_id=88))
    try:
        assert loaded.model_id == 88
        assert loaded.version == 1
        assert loaded.model is not None
        assert len(loaded.chars) > 0
        assert "experiment-88" in loaded.name
    finally:
        model_path.unlink(missing_ok=True)


######################################################################
# load_model - MLflow model registry fallback
######################################################################


def test_load_model_mlflow_registry(monkeypatch, tmp_path):
    """load_model falls back to MLflow Model Registry when no disk
    artifact exists.
    """
    # Train and save model → place it as a "downloaded" MLflow artifact
    model_path, uchars, _ = _train_tiny_model(tmp_path)

    dst_dir = tmp_path / "mlflow_artifacts"
    dst_dir.mkdir(parents=True, exist_ok=True)
    # Copy model.json to the fake artifact directory
    import shutil

    shutil.copy(str(model_path), str(dst_dir / "model.json"))

    # Mock TrackingService - return a model that matches candidate name
    async def mock_list_models(self, search=None):
        return [
            {
                "name": "dataset-99",
                "id": 99,
                "version": "2",
                "run_id": "mock-run-id",
            }
        ]

    monkeypatch.setattr(TrackingService, "list_registered_models", mock_list_models)

    # Mock MlflowClient and get_mlflow_uri
    mock_client = MagicMock()

    mock_version = MagicMock()
    mock_version.version = "2"
    mock_version.run_id = "mock-run-id"
    mock_client.search_model_versions.return_value = [mock_version]
    mock_client.download_artifacts.return_value = str(dst_dir)

    with (
        patch(
            "anvil.services.inference.inference.MlflowClient",
            return_value=mock_client,
        ),
        patch(
            "anvil.services.inference.inference.get_mlflow_uri",
            return_value="http://test-mlflow:5000",
        ),
    ):
        service = InferenceService()
        loaded = asyncio.run(service.load_model(model_id=99))

    assert loaded.model_id == 99
    assert loaded.version == 1  # default version when model_id is not None
    assert loaded.model is not None
    assert len(loaded.chars) > 0
    assert "dataset-99" in loaded.name

    # Verify MLflow was contacted
    mock_client.search_model_versions.assert_called_once()
    mock_client.download_artifacts.assert_called_once_with(
        run_id="mock-run-id", path="", dst_path=None
    )


######################################################################
# load_model - silent exception catch
######################################################################


def test_load_model_exception_catch(monkeypatch):
    """Broad ``except Exception: pass`` in the MLflow path is exercised
    and load_model raises ``ValueError`` afterward.
    """

    async def mock_list_models(self, search=None):
        return [{"name": "dataset-42", "id": 42, "version": "1", "run_id": "r1"}]

    monkeypatch.setattr(TrackingService, "list_registered_models", mock_list_models)

    # Make MlflowClient construction succeed, but search_model_versions
    # raise inside the try block (the except Exception: pass catches it)
    mock_client = MagicMock()
    mock_client.search_model_versions.side_effect = RuntimeError(
        "search_model_versions failed"
    )

    with (
        patch(
            "anvil.services.inference.inference.MlflowClient",
            return_value=mock_client,
        ),
        patch(
            "anvil.services.inference.inference.get_mlflow_uri",
            return_value="http://test:5000",
        ),
    ):
        service = InferenceService()
        with pytest.raises(ValueError, match="Model not found"):
            asyncio.run(service.load_model(model_id=42))


######################################################################
# _resolve_default_id - cache hit
######################################################################


def test_resolve_default_id_cache_hit():
    """_resolve_default_id returns cached value immediately."""
    service = InferenceService()
    service._default_id = 77
    result = asyncio.run(service._resolve_default_id())
    assert result == 77


######################################################################
# _resolve_default_id - MLflow lookup found
######################################################################


def test_resolve_default_id_mlflow_found(monkeypatch):
    """_resolve_default_id picks the ``demo`` model from MLflow
    registry when no cache exists.
    """

    async def mock_list_models(self, search=None):
        return [{"name": "demo", "id": 42, "version": 1}]

    monkeypatch.setattr(TrackingService, "list_registered_models", mock_list_models)

    service = InferenceService()
    result = asyncio.run(service._resolve_default_id())
    assert result == 42
    assert service._default_id == 42


######################################################################
# _resolve_default_id - filesystem scan found
######################################################################


def test_resolve_default_id_fs_fallback(monkeypatch, tmp_path):
    """_resolve_default_id scans ``data/models/`` when MLflow returns
    nothing.
    """

    async def no_models(self, search=None):
        return []

    monkeypatch.setattr(TrackingService, "list_registered_models", no_models)

    # Create a model file on disk for the fallback scan
    models_dir = Path("data/models")
    models_dir.mkdir(parents=True, exist_ok=True)
    artifact = models_dir / "experiment_5.json"
    try:
        # Write minimal valid model JSON
        vocab_size = 5
        n_embd = 4
        n_head = 2
        n_layer = 1
        block_size = 16
        dummy = {
            "vocab_size": vocab_size,
            "n_embd": n_embd,
            "n_head": n_head,
            "n_layer": n_layer,
            "block_size": block_size,
            "tokenizer_family": "char",
            "serialization_type": "char_json",
            "chars": ["a", "b", "c", "d"],
            "state_dict": {
                "wte": [[0.1] * n_embd for _ in range(vocab_size)],
                "lm_head": [[0.1] * n_embd for _ in range(vocab_size)],
                "layer0.attn_wq": [[0.1] * n_embd for _ in range(n_embd)],
                "layer0.attn_wk": [[0.1] * n_embd for _ in range(n_embd)],
                "layer0.attn_wv": [[0.1] * n_embd for _ in range(n_embd)],
                "layer0.attn_wo": [[0.1] * n_embd for _ in range(n_embd)],
                "layer0.mlp_gate": [[0.1] * n_embd for _ in range(4)],
                "layer0.mlp_up": [[0.1] * n_embd for _ in range(4)],
                "layer0.mlp_down": [[0.1] * 4 for _ in range(n_embd)],
                "layer0.rms_1": [1.0] * n_embd,
                "layer0.rms_2": [1.0] * n_embd,
                "rms_final": [1.0] * n_embd,
            },
        }
        with open(artifact, "w", encoding="utf-8") as f:
            json.dump(dummy, f)

        service = InferenceService()
        result = asyncio.run(service._resolve_default_id())
        assert result == 5
        assert service._default_id == 5
    finally:
        artifact.unlink(missing_ok=True)


######################################################################
# _resolve_default_id - nothing found
######################################################################


def test_resolve_default_id_nothing_found(monkeypatch):
    """_resolve_default_id raises ValueError when no model is
    available anywhere.
    """

    async def no_models(self, search=None):
        return []

    monkeypatch.setattr(TrackingService, "list_registered_models", no_models)

    service = InferenceService()
    with pytest.raises(ValueError, match="No models available"):
        asyncio.run(service._resolve_default_id())
