# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for LlamaModel.load and forward_introspect."""

import json
import tempfile

from anvil.core.engine import LlamaModel, softmax, train


def test_gpt_save_load_roundtrip():
    """LlamaModel.save followed by LlamaModel.load should produce identical model."""
    docs = ["emma", "olivia", "ava"]
    model, _, _, uchars = train(docs, num_steps=10, n_embd=8, n_head=2)

    with tempfile.NamedTemporaryFile(suffix=".json") as f:
        model.save(f.name, uchars)
        loaded = LlamaModel.load(f.name)

    assert loaded.vocab_size == model.vocab_size
    assert loaded.n_embd == model.n_embd
    assert loaded.n_head == model.n_head
    assert loaded.n_layer == model.n_layer
    assert loaded.block_size == model.block_size
    assert loaded.chars == uchars

    # Verify state_dict values are identical
    for k in model.state_dict:
        for i, row in enumerate(model.state_dict[k]):
            for j, val in enumerate(row):
                assert (
                    abs(val.data - loaded.state_dict[k][i][j].data) < 1e-12
                ), f"Mismatch at {k}[{i}][{j}]"


def test_gpt_load_returns_chars():
    """LlamaModel.load must attach chars from JSON to the model."""
    docs = ["test", "data"]
    model, _, _, uchars = train(docs, num_steps=5, n_embd=8, n_head=2)

    with tempfile.NamedTemporaryFile(suffix=".json") as f:
        model.save(f.name, uchars)
        loaded = LlamaModel.load(f.name)

    assert hasattr(loaded, "chars")
    assert loaded.chars == uchars


def test_gpt_load_without_chars():
    """LlamaModel.load should handle models saved without chars gracefully."""
    model = LlamaModel(vocab_size=10, n_embd=8, n_head=2, n_layer=1, block_size=8)
    with tempfile.NamedTemporaryFile(suffix=".json") as f:
        # Save without chars by writing directly
        data = {
            "vocab_size": model.vocab_size,
            "n_embd": model.n_embd,
            "n_head": model.n_head,
            "n_layer": model.n_layer,
            "block_size": model.block_size,
            "chars": None,
            "state_dict": {
                k: [[p.data for p in row] for row in mat]
                for k, mat in model.state_dict.items()
            },
        }
        with open(f.name, "w") as fp:
            json.dump(data, fp)
        loaded = LlamaModel.load(f.name)

    assert loaded.chars is None
    assert loaded.vocab_size == 10


def test_loaded_model_can_forward():
    """A loaded model should produce valid forward pass output."""
    docs = ["abc", "def"]
    model, _, _, uchars = train(docs, num_steps=5, n_embd=8, n_head=2)

    with tempfile.NamedTemporaryFile(suffix=".json") as f:
        model.save(f.name, uchars)
        loaded = LlamaModel.load(f.name)

    # Run a forward pass
    BOS = len(uchars)
    keys = [[] for _ in range(loaded.n_layer)]
    values = [[] for _ in range(loaded.n_layer)]
    logits = loaded.forward(BOS, 0, keys, values)

    assert len(logits) == loaded.vocab_size
    for logit in logits:
        assert isinstance(logit.data, float)


def test_forward_introspect_returns_correct_structure():
    """forward_introspect should return dict with keys: attention, logits, embeddings."""
    model = LlamaModel(vocab_size=10, n_embd=8, n_head=2, n_layer=1, block_size=8)
    result = model.forward_introspect([0, 1, 2])
    assert isinstance(result, dict)
    assert "attention" in result
    assert "logits" in result
    assert "embeddings" in result
    assert "n_layer" in result
    assert "n_head" in result
    assert "tokens" in result
    assert result["n_layer"] == 1
    assert result["n_head"] == 2


def test_forward_introspect_attention_row_sums():
    """Attention weights should have rows that sum to ~1.0 (softmax property)."""
    model = LlamaModel(vocab_size=10, n_embd=8, n_head=2, n_layer=2, block_size=16)
    result = model.forward_introspect([1, 2, 3, 4])
    weights = result["attention"]
    n_layer = result["n_layer"]
    n_head = result["n_head"]
    n_positions = len(result["tokens"])

    assert len(weights) == n_layer
    for li in range(n_layer):
        assert len(weights[li]) == n_head
        for hi in range(n_head):
            assert len(weights[li][hi]) == n_positions  # query positions
            for qi in range(n_positions):
                row = weights[li][hi][qi]
                assert len(row) == qi + 1  # key positions (non-causal, full prefix)
                row_sum = sum(row)
                assert (
                    abs(row_sum - 1.0) < 1e-5
                ), f"Layer {li} head {hi} query {qi} sum={row_sum}"


def test_forward_introspect_logits_valid():
    """Final-position logits should be a list of Value objects with valid data."""
    model = LlamaModel(vocab_size=10, n_embd=8, n_head=2, n_layer=1, block_size=8)
    result = model.forward_introspect([0, 1, 2])
    logits = result["logits"]
    assert len(logits) == model.vocab_size
    for logit in logits:
        assert hasattr(logit, "data")
        assert isinstance(logit.data, float)


def test_forward_introspect_embeddings_per_position():
    """Embeddings should be one per position, each with n_embd dimensions."""
    model = LlamaModel(vocab_size=10, n_embd=8, n_head=2, n_layer=1, block_size=8)
    tokens = [0, 1, 2, 4]
    result = model.forward_introspect(tokens)
    embeddings = result["embeddings"]
    assert len(embeddings) == len(tokens)
    for emb in embeddings:
        assert len(emb) == model.n_embd
        for val in emb:
            assert isinstance(val, float) or hasattr(val, "data")


def test_forward_introspect_does_not_mutate_forward():
    """Calling forward_introspect should not affect subsequent forward() calls."""
    model = LlamaModel(vocab_size=10, n_embd=8, n_head=2, n_layer=1, block_size=8)
    # Forward pass first
    keys = [[] for _ in range(model.n_layer)]
    values = [[] for _ in range(model.n_layer)]
    logits_before = model.forward(1, 0, keys, values)

    # Introspect
    model.forward_introspect([1, 2, 3])

    # Forward pass again should work
    keys2 = [[] for _ in range(model.n_layer)]
    values2 = [[] for _ in range(model.n_layer)]
    logits_after = model.forward(1, 0, keys2, values2)

    for lb, la in zip(logits_before, logits_after, strict=False):
        assert lb.data == la.data
