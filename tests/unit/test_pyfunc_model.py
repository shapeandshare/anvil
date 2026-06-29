# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for AnvilPyfuncModel — MLflow pyfunc model wrapper.

Uses monkeypatch to mock torch, safetensors, and transformers for
verifying loading, predict, and generate paths without real deps.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from anvil._pyfunc_model import AnvilPyfuncModel


class _MockModule:
    """Generic module stand-in for mocking. Supports context manager
    protocol and subscript access via a stored ``_getitem`` lambda.
    """

    def __init__(self, **attrs: Any) -> None:
        for k, v in attrs.items():
            setattr(self, k, v)

    def __enter__(self) -> _MockModule:
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    def __getitem__(self, key: Any) -> Any:
        fn = getattr(self, "_getitem", None)
        if fn is not None:
            return fn(key)
        raise TypeError(f"'{type(self).__name__}' object is not subscriptable")


def _make_model_dir(tmp_path: Path, has_weights: bool = True) -> Path:
    model_dir = tmp_path / "model"
    model_dir.mkdir(parents=True)
    with open(model_dir / "config.json", "w") as f:
        json.dump({"model_type": "llama", "hidden_size": 16}, f)
    if has_weights:
        (model_dir / "model.safetensors").write_bytes(b"\x00" * 8)
    with open(model_dir / "tokenizer.json", "w") as f:
        json.dump(
            {
                "vocab": {"a": 0, "b": 1, "c": 2},
                "chars": ["a", "b", "c"],
                "bos_token_id": 0,
            },
            f,
        )
    return model_dir


class MockContext:
    def __init__(self, artifact_uri: str) -> None:
        self.artifact_uri = artifact_uri


def _mock_load_context_deps(monkeypatch: Any) -> None:
    """Insert mock modules into sys.modules for load_context's lazy imports."""
    import sys

    mock_torch = _MockModule(
        cuda=_MockModule(is_available=lambda: False),
        device=lambda d: "cpu",
    )
    monkeypatch.setitem(sys.modules, "torch", mock_torch)

    mock_safetensors_torch = _MockModule(load_file=lambda path: {})
    mock_safetensors = _MockModule(torch=mock_safetensors_torch)
    monkeypatch.setitem(sys.modules, "safetensors", mock_safetensors)
    monkeypatch.setitem(sys.modules, "safetensors.torch", mock_safetensors_torch)

    mock_llama_model = _MockModule(
        load_state_dict=lambda sd, strict: None,
        eval=lambda: None,
        to=lambda d: None,
    )
    mock_transformers = _MockModule(
        LlamaConfig=_MockModule(from_pretrained=lambda p: _MockModule()),
        LlamaForCausalLM=lambda cfg: mock_llama_model,
    )
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)


# ── load_context ──────────────────────────────────────────────────────────


def test_load_context_loads_all_artifacts(monkeypatch, tmp_path: Path) -> None:
    model_dir = _make_model_dir(tmp_path, has_weights=True)
    _mock_load_context_deps(monkeypatch)

    model = AnvilPyfuncModel()
    model.load_context(MockContext(str(model_dir)))

    assert model.vocab == {"a": 0, "b": 1, "c": 2}
    assert model.chars == ["a", "b", "c"]
    assert model.bos_token_id == 0
    assert model._reverse_vocab == {0: "a", 1: "b", 2: "c"}


def test_load_context_no_weights_file(monkeypatch, tmp_path: Path) -> None:
    model_dir = _make_model_dir(tmp_path, has_weights=False)
    _mock_load_context_deps(monkeypatch)

    model = AnvilPyfuncModel()
    model.load_context(MockContext(str(model_dir)))

    assert model.vocab == {"a": 0, "b": 1, "c": 2}
    assert model.chars == ["a", "b", "c"]


def test_load_context_no_tokenizer(monkeypatch, tmp_path: Path) -> None:
    model_dir = tmp_path / "model"
    model_dir.mkdir(parents=True)
    with open(model_dir / "config.json", "w") as f:
        json.dump({"model_type": "llama", "hidden_size": 16}, f)
    _mock_load_context_deps(monkeypatch)

    model = AnvilPyfuncModel()
    model.load_context(MockContext(str(model_dir)))

    assert model.vocab == {}
    assert model.chars == []
    assert model.bos_token_id is None
    assert model._reverse_vocab == {}


def test_load_context_raises_on_missing_deps() -> None:
    model = AnvilPyfuncModel()

    class _MinimalContext:
        artifact_uri = "/tmp/nonexistent"

    with pytest.raises(ImportError, match="torch, safetensors"):
        model.load_context(_MinimalContext())


# ── predict ───────────────────────────────────────────────────────────────


def _setup_mock_generate(model: AnvilPyfuncModel, token_id: int = 0) -> None:
    """Set up model._torch and model.model with mocks for predict/_generate."""
    tensor_obj = _MockModule(to=lambda d: _MockModule(), item=lambda: token_id)

    def _no_grad() -> _MockModule:
        return _MockModule()

    logits = _MockModule(
        _getitem=lambda key: _MockModule(_getitem=lambda key: tensor_obj),
    )

    def _mock_model(_input: Any) -> _MockModule:
        return _MockModule(logits=logits)

    def _tensor(data: Any) -> _MockModule:
        return _MockModule(to=lambda d: tensor_obj)

    model._torch = _MockModule(
        tensor=_tensor,
        no_grad=_no_grad,
        argmax=lambda x: _MockModule(item=lambda: token_id),
    )
    model.model = _mock_model
    model.device = "cpu"


def test_predict_returns_dataframe() -> None:
    model = AnvilPyfuncModel()
    model.vocab = {"a": 0, "b": 1}
    model.chars = ["a", "b"]
    model.bos_token_id = 0
    model._reverse_vocab = {0: "a", 1: "b"}
    _setup_mock_generate(model)

    df_in = pd.DataFrame({"text": ["ab"]})
    df_out = model.predict(None, df_in)

    assert isinstance(df_out, pd.DataFrame)
    assert "generated" in df_out.columns
    assert len(df_out) == 1


def test_predict_with_string_input() -> None:
    model = AnvilPyfuncModel()
    model.vocab = {"x": 0}
    model.chars = ["x"]
    model.bos_token_id = None
    model._reverse_vocab = {0: "x"}
    _setup_mock_generate(model, token_id=0)

    df_out = model.predict(None, "x")

    assert isinstance(df_out, pd.DataFrame)
    assert "generated" in df_out.columns
    assert len(df_out) == 1


# ── _generate ─────────────────────────────────────────────────────────────


def test_generate_with_bos_token() -> None:
    model = AnvilPyfuncModel()
    model.vocab = {"h": 0, "i": 1}
    model.bos_token_id = 99
    model._reverse_vocab = {0: "h", 1: "i"}
    _setup_mock_generate(model, token_id=1)

    result = model._generate("h", max_new_tokens=2)
    assert isinstance(result, str)


def test_generate_without_bos_token() -> None:
    model = AnvilPyfuncModel()
    model.vocab = {"a": 0, "b": 1}
    model.bos_token_id = None
    model._reverse_vocab = {0: "a", 1: "b"}
    _setup_mock_generate(model, token_id=0)

    result = model._generate("a", max_new_tokens=1)
    assert isinstance(result, str)
