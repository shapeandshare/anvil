"""Tests for InferenceService and DemoModelProvider."""

import tempfile
from pathlib import Path

import pytest

from anvil.core.engine import LlamaModel, train
from anvil.core.tokenizer import Vocabulary
from anvil.services.inference import (
    DemoModelProvider,
    InferenceService,
    LoadedModel,
    _project_to_2d,
    _top_k_logits,
)


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
    loaded = LoadedModel(gpt, uchars, None, None, "test", is_demo=True)
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
    loaded = LoadedModel(model, uchars, 1, 1, "test")
    assert loaded.vocab.vocab_size == len(uchars) + 1
    assert loaded.vocab.bos_id == len(uchars)
    assert loaded.info()["id"] == 1
    assert loaded.info()["is_demo"] is False


def test_inference_service_load_demo(demo_service):
    import asyncio
    loaded = asyncio.run(demo_service.load_model())
    assert loaded.is_demo is True
    assert loaded.model_id is None
    assert loaded.model is not None
    assert len(loaded.chars) > 0


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