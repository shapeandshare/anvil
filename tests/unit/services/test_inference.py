# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for InferenceService and DemoModelProvider."""

import asyncio
import tempfile
from pathlib import Path

import pytest

from anvil.core._tokenizer_base import Tokenizer
from anvil.core.engine import LlamaModel, train
from anvil.core.vocabulary import Vocabulary
from anvil.services.inference.demo_model_provider import DemoModelProvider
from anvil.services.inference.inference import (
    InferenceService,
    _project_to_2d,
    _top_k_logits,
)
from anvil.services.inference.loaded_model import LoadedModel


def _make_tokenizer(chars: list[str]) -> Tokenizer:
    """Build a Vocabulary-based tokenizer, matching how InferenceService builds one."""
    return Vocabulary.from_chars(chars)


@pytest.fixture
def demo_service():
    return InferenceService()


@pytest.fixture
def trained_loaded_model():
    docs = ["abc", "def", "ghi"]
    model, _, _, uchars = train(docs, num_steps=20, n_embd=8, n_head=2)
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        model.save(f.name, uchars)
        fpath = f.name
    gpt = LlamaModel.load(fpath)
    tokenizer = _make_tokenizer(uchars)
    loaded = LoadedModel(gpt, tokenizer, None, None, "test", is_demo=True)
    yield loaded
    Path(fpath).unlink(missing_ok=True)


def test_demo_provider_provisions():
    provider = DemoModelProvider()
    model, chars = provider.get_model()
    assert model is not None
    assert len(chars) > 0
    assert model.vocab_size == len(chars) + 1
    info = provider.info()
    assert info["is_demo"] is True
    assert info["id"] is None


def test_demo_provider_cached():
    provider = DemoModelProvider()
    m1, c1 = provider.get_model()
    m2, c2 = provider.get_model()
    assert m1 is m2
    assert c1 == c2


def test_loaded_model_vocab():
    docs = ["hello", "world"]
    model, _, _, uchars = train(docs, num_steps=5, n_embd=8, n_head=2)
    tokenizer = _make_tokenizer(uchars)
    loaded = LoadedModel(model, tokenizer, 1, 1, "test")
    assert loaded.tokenizer.vocab_size == len(uchars) + 1
    assert loaded.bos_id == len(uchars)
    assert loaded.info()["id"] == 1
    assert loaded.info()["is_demo"] is False


def test_inference_service_load_by_id(demo_service):
    """load_model(ID, version) loads from experiment_{ID}.json on disk."""
    import tempfile
    from pathlib import Path

    docs = ["abc", "def", "ghi"]
    model, _, _, uchars = train(docs, num_steps=20, n_embd=8, n_head=2)

    models_dir = Path("data/models")
    models_dir.mkdir(parents=True, exist_ok=True)
    model_path = models_dir / "experiment_99.json"
    model.save(str(model_path), uchars)
    try:
        loaded = asyncio.run(demo_service.load_model(model_id=99))
        assert loaded.model_id == 99
        assert loaded.version == 1
        assert loaded.model is not None
        assert len(loaded.chars) > 0
    finally:
        model_path.unlink(missing_ok=True)


def test_inference_service_tokenize(demo_service, trained_loaded_model):
    result = demo_service.tokenize("abc", trained_loaded_model)
    assert "model" in result
    assert "tokens" in result
    assert "vocab_size" in result
    assert "bos_id" in result
    tokens = result["tokens"]
    assert len(tokens) > 0
    assert tokens[0]["char"] == "<BOS>"
    assert tokens[-1]["char"] == "<BOS>"
    for t in tokens:
        assert "char" in t
        assert "id" in t


def test_inference_service_embeddings(demo_service, trained_loaded_model):
    result = demo_service.embeddings("abc", trained_loaded_model)
    assert result["n_embd"] == 8
    assert len(result["vectors"]) > 0
    assert len(result["projection"]) == len(result["vectors"])
    assert len(result["tokens"]) == len(result["vectors"])
    for p in result["projection"]:
        assert "x" in p
        assert "y" in p
        assert "label" in p


def test_inference_service_attention(demo_service, trained_loaded_model):
    result = demo_service.attention("abc", trained_loaded_model)
    assert result["n_layer"] == 1
    assert result["n_head"] == 2
    weights = result["weights"]
    assert len(weights) == 1
    assert len(weights[0]) == 2
    n_tokens = len(result["tokens"])
    for hi in range(2):
        assert len(weights[0][hi]) == n_tokens
        for qi in range(n_tokens):
            row = weights[0][hi][qi]
            assert abs(sum(row) - 1.0) < 1e-5


def test_inference_service_sampling_distribution(demo_service, trained_loaded_model):
    result = demo_service.sampling_distribution("a", 0.5, None, trained_loaded_model)
    assert "model" in result
    assert "tokens" in result
    assert "temperature" in result
    assert result["temperature"] == 0.5
    tokens = result["tokens"]
    for t in tokens:
        assert "char" in t
        assert "id" in t
        assert "prob" in t
    probs = [t["prob"] for t in tokens]
    assert abs(sum(probs) - 1.0) < 1e-5


def test_inference_service_sampling_with_top_k(demo_service, trained_loaded_model):
    result = demo_service.sampling_distribution("a", 1.0, 5, trained_loaded_model)
    tokens = result["tokens"]
    probs = [t["prob"] for t in tokens]
    nonzero = sum(1 for p in probs if p > 0)
    assert nonzero <= 5


def test_top_k_logits():
    logits = [0.5, 0.3, 0.1, 0.05, 0.05]
    result = _top_k_logits(logits, 2)
    assert result[0] == 0.5
    assert result[1] == 0.3
    assert all(v <= -1e9 for v in result[2:])


def test_top_k_logits_none():
    logits = [0.5, 0.3, 0.1]
    result = _top_k_logits(logits, None)
    assert result == logits


def test_projection_2d():
    vectors = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    result = _project_to_2d(vectors)
    assert len(result) == 3
    for p in result:
        assert "x" in p
        assert "y" in p


def test_forward_graph(demo_service, trained_loaded_model):
    result = demo_service.forward_graph(trained_loaded_model)
    assert "model" in result
    assert "nodes" in result
    assert "edges" in result
    assert len(result["nodes"]) > 0
    assert len(result["edges"]) > 0
    for n in result["nodes"]:
        assert "id" in n
        assert "op" in n
        assert "depth" in n


def test_forward_graph_with_max_nodes(demo_service, trained_loaded_model):
    """forward_graph respects the max_nodes limit."""
    result = demo_service.forward_graph(trained_loaded_model, max_nodes=5)
    assert len(result["nodes"]) <= 5


def test_inference_service_backward_graph(demo_service, trained_loaded_model):
    """backward_graph returns computation graph with gradients."""
    text = "abc"
    result = demo_service.backward_graph(text, trained_loaded_model)
    assert "model" in result
    assert "nodes" in result
    assert "edges" in result
    assert "metadata" in result
    assert len(result["nodes"]) > 0
    assert len(result["edges"]) > 0
    meta = result["metadata"]
    assert "total_nodes" in meta
    assert "total_edges" in meta
    assert "max_depth" in meta
    assert "input_tokens" in meta
    assert "loss_value" in meta
    assert meta["total_nodes"] > 0
    # Every node should have a gradient after backward pass
    for n in result["nodes"]:
        assert "grad" in n
        assert "local_grads" in n
        assert "value" in n


def test_inference_service_backward_graph_single_token(
    demo_service, trained_loaded_model
):
    """backward_graph with single character still produces a graph."""
    result = demo_service.backward_graph("a", trained_loaded_model)
    assert len(result["nodes"]) > 0
    assert "loss_value" in result["metadata"]


def test_inference_service_autograd_example_graph(demo_service, trained_loaded_model):
    """autograd_example_graph returns a small teaching graph."""
    result = demo_service.autograd_example_graph("abc", trained_loaded_model)
    assert "model" in result
    assert "nodes" in result
    assert "edges" in result
    assert "metadata" in result
    assert len(result["nodes"]) > 0
    assert len(result["edges"]) > 0
    meta = result["metadata"]
    assert "total_nodes" in meta
    assert "total_edges" in meta
    assert "max_depth" in meta
    assert "input_tokens" in meta
    assert "loss_value" in meta
    # Nodes should have distinct ops: input, mul, add, silu, pow
    ops = {n["op"] for n in result["nodes"]}
    assert "input" in ops
    assert "mul" in ops
    assert "add" in ops
    assert "silu" in ops
    assert "pow" in ops


def test_inference_service_autograd_example_with_empty_text(
    demo_service, trained_loaded_model
):
    """autograd_example_graph handles empty text gracefully."""
    result = demo_service.autograd_example_graph("", trained_loaded_model)
    assert len(result["nodes"]) > 0


def test_inference_service_loss_breakdown(demo_service, trained_loaded_model):
    """loss_breakdown returns per-token cross-entropy losses."""
    text = "abc"
    result = demo_service.loss_breakdown(text, trained_loaded_model)
    assert "model" in result
    assert "tokens" in result
    assert "losses" in result
    assert "average_loss" in result
    assert "random_baseline" in result
    assert "vocab_size" in result
    assert len(result["losses"]) > 0
    assert result["average_loss"] > 0
    assert result["random_baseline"] > 0
    assert len(result["tokens"]) == len(result["losses"]) + 1


def test_inference_service_loss_breakdown_single_char(
    demo_service, trained_loaded_model
):
    """loss_breakdown handles single character input."""
    result = demo_service.loss_breakdown("a", trained_loaded_model)
    assert len(result["losses"]) == 2


def test_inference_service_model_params(demo_service, trained_loaded_model):
    """model_params returns parameter breakdown with groups."""
    result = demo_service.model_params(trained_loaded_model)
    assert "model" in result
    assert "total_params" in result
    assert "groups" in result
    assert "n_embd" in result
    assert "n_layer" in result
    assert "n_head" in result
    assert result["total_params"] > 0
    assert len(result["groups"]) > 0
    for g in result["groups"]:
        assert "name" in g
        assert "category" in g
        assert "shape" in g
        assert "num_params" in g
        assert "percentage" in g
    categories = {g["category"] for g in result["groups"]}
    assert "embedding" in categories
    assert "output" in categories


# ── Pure function edge cases ──


def test_top_k_logits_zero_k():
    """top_k returns all logits unchanged when k is 0."""
    logits = [0.5, 0.3, 0.1]
    result = _top_k_logits(logits, 0)
    assert result == logits


def test_top_k_logits_negative_k():
    """top_k returns all logits unchanged when k is negative."""
    logits = [0.5, 0.3, 0.1]
    result = _top_k_logits(logits, -1)
    assert result == logits


def test_top_k_logits_k_equals_one():
    """top_k only keeps the single highest logit."""
    logits = [0.1, 0.9, 0.5]
    result = _top_k_logits(logits, 1)
    assert result[1] == 0.9
    assert all(v <= -1e9 for i, v in enumerate(result) if i != 1)


def test_projection_2d_empty():
    """_project_to_2d returns empty list for empty input."""
    result = _project_to_2d([])
    assert result == []


def test_projection_2d_1d():
    """_project_to_2d handles 1-dimensional vectors."""
    vectors = [[1.0], [2.0], [3.0]]
    result = _project_to_2d(vectors)
    assert len(result) == 3
    for p in result:
        assert "x" in p
        assert "y" in p
        assert p["y"] == 0.0


def test_projection_2d_2d_already():
    """_project_to_2d returns existing x/y coordinates for 2D input."""
    vectors = [[1.0, 2.0], [3.0, 4.0]]
    result = _project_to_2d(vectors)
    assert len(result) == 2
    assert result[0] == {"x": 1.0, "y": 2.0}


# ── LoadedModel edge cases ──


def test_loaded_model_no_id():
    """LoadedModel with None model_id reports None in info."""
    import tempfile
    from pathlib import Path

    from anvil.core.engine import LlamaModel, train

    docs = ["abc"]
    model, _, _, uchars = train(docs, num_steps=5, n_embd=8, n_head=2)
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        model.save(f.name, uchars)
        fpath = f.name
    gpt = LlamaModel.load(fpath)
    tokenizer = _make_tokenizer(uchars)
    loaded = LoadedModel(gpt, tokenizer, None, None, "no-id-test")
    info = loaded.info()
    assert info["id"] is None
    assert info["version"] is None
    assert info["name"] == "no-id-test"
    assert info["is_demo"] is False
    Path(fpath).unlink(missing_ok=True)


# ── InferenceService load_model cache ──


def test_load_model_cache_hit(demo_service, trained_loaded_model):
    """Calling load_model with already-loaded ID+version uses cache."""
    import asyncio

    # Manually populate the cache
    demo_service._cache[(99, 1)] = (
        trained_loaded_model.model,
        trained_loaded_model.tokenizer,
    )
    loaded = asyncio.run(demo_service.load_model(model_id=99))
    assert loaded.name == "cached"


def test_load_model_raises_on_missing(demo_service):
    """load_model raises ValueError when no model is found."""
    import asyncio

    with pytest.raises(ValueError, match="Model not found"):
        asyncio.run(demo_service.load_model(model_id=999999))


def test_demo_provider_trains_on_fallback(monkeypatch, tmp_path):
    """DemoModelProvider trains on fallback corpus when DB unavailable."""
    # Force DEMO_MODEL_PATH to non-existent location
    import importlib

    import anvil.services.inference.demo_model_provider as dmp

    monkeypatch.setattr(dmp, "DEMO_MODEL_PATH", tmp_path / "nonexistent" / "model.json")

    provider = DemoModelProvider()
    model, chars = provider.get_model()
    assert model is not None
    assert len(chars) > 0
    info = provider.info()
    assert info["is_demo"] is True
    assert info["id"] is None
