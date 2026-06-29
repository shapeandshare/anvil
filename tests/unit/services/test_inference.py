# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Mock-heavy tests for InferenceService — no real training or LlamaModel.

Mocks everything at the module/test level to avoid the real autograd
engine (which is exercised by core tests). Pure helper functions
(``_top_k_logits``, ``_project_to_2d``) are tested with real values.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anvil.core.autograd import Value

from anvil.services.inference.inference import _project_to_2d, _top_k_logits


# ============================================================================
# Pure helper function tests — no mocking needed, fast and real.
# ============================================================================


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


def test_top_k_logits_zero_k():
    logits = [0.5, 0.3, 0.1]
    result = _top_k_logits(logits, 0)
    assert result == logits


def test_top_k_logits_negative_k():
    logits = [0.5, 0.3, 0.1]
    result = _top_k_logits(logits, -1)
    assert result == logits


def test_top_k_logits_k_equals_one():
    logits = [0.1, 0.9, 0.5]
    result = _top_k_logits(logits, 1)
    assert result[1] == 0.9
    assert all(v <= -1e9 for i, v in enumerate(result) if i != 1)


def test_top_k_logits_k_larger_than_list():
    logits = [0.1, 0.2, 0.3]
    result = _top_k_logits(logits, 10)
    assert result == logits


def test_top_k_logits_k_exactly_one():
    logits = [0.1, 0.9, 0.5, 0.3]
    result = _top_k_logits(logits, 1)
    assert result[1] == 0.9
    assert all(v <= -1e9 for i, v in enumerate(result) if i != 1)


def test_projection_2d():
    vectors = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    result = _project_to_2d(vectors)
    assert len(result) == 3
    for p in result:
        assert "x" in p
        assert "y" in p


def test_projection_2d_empty():
    result = _project_to_2d([])
    assert result == []


def test_projection_2d_1d():
    vectors = [[1.0], [2.0], [3.0]]
    result = _project_to_2d(vectors)
    assert len(result) == 3
    for p in result:
        assert "x" in p
        assert "y" in p
        assert p["y"] == 0.0


def test_projection_2d_2d_already():
    vectors = [[1.0, 2.0], [3.0, 4.0]]
    result = _project_to_2d(vectors)
    assert len(result) == 2
    assert result[0] == {"x": 1.0, "y": 2.0}


def test_projection_2d_identical_vectors():
    vectors = [[1.0, 2.0, 3.0], [1.0, 2.0, 3.0], [1.0, 2.0, 3.0]]
    result = _project_to_2d(vectors)
    assert len(result) == 3
    for p in result:
        assert "x" in p
        assert "y" in p


def test_projection_2d_single_vector():
    vectors = [[0.5, 1.5, 2.5]]
    result = _project_to_2d(vectors)
    assert len(result) == 1
    assert "x" in result[0]
    assert "y" in result[0]


# ============================================================================
# Fixtures — everything mocked, nothing trained.
# ============================================================================


@pytest.fixture
def demo_service():
    """InferenceService with no pre-populated cache."""
    from anvil.services.inference.inference import InferenceService

    return InferenceService()


@pytest.fixture
def mock_model():
    """A fully-mocked LlamaModel with real Value objects for graph ops.

    ``forward()`` returns a small Value chain so that graph-traversal
    methods (forward_graph, backward_graph, loss_breakdown) work.
    """
    model = MagicMock()
    model.n_embd = 16
    model.n_layer = 2
    model.n_head = 4
    model.block_size = 64
    model.vocab_size = 5
    model.head_dim = 4

    # Small Value chain for graph ops: leaf → mul → add
    v_in = Value(0.5)
    v_mul = v_in * Value(0.8)
    v_add = v_mul + Value(0.1)
    graph_root = v_add
    _ = v_in
    _ = v_mul
    _ = v_add  # kept alive for reference

    # forward() returns list of Values; graph traversal starts at logits[-1]
    logits = [Value(i * 0.1 - 0.2) for i in range(model.vocab_size)]
    logits[-1] = graph_root  # replace last with the chain
    model.forward = MagicMock(return_value=logits)

    model.forward_introspect = MagicMock(
        return_value={
            "attention": [
                [[[0.25, 0.5, 0.25] for _ in range(3)] for _ in range(4)]
                for _ in range(model.n_layer)
            ],
        }
    )

    # state_dict for model_params
    model.state_dict = {
        "wte": [[Value(float(j + i * 4)) for j in range(4)] for i in range(5)],
        "lm_head": [[Value(float(j + i * 4 + 20)) for j in range(4)] for i in range(5)],
    }

    def get_matrix(key: str) -> list[list[Value]]:
        if key == "wte":
            return [[Value(float(j)) for j in range(4)] for _ in range(5)]
        return [[Value(float(j)) for j in range(4)] for _ in range(4)]

    model._get_matrix = MagicMock(side_effect=get_matrix)
    model._cos_table = [[0.5, 0.5] for _ in range(64)]
    model._sin_table = [[0.5, 0.5] for _ in range(64)]
    model.params = [Value(0.1) for _ in range(10)]
    return model


@pytest.fixture
def mock_loaded(mock_model):
    """LoadedModel wrapping the mock model, with a real Vocabulary."""
    from anvil.services.inference.loaded_model import LoadedModel

    chars = ["a", "b", "c", "d"]
    loaded = LoadedModel(mock_model, chars, 1, 1, "test")
    return loaded


# ============================================================================
# LoadedModel basics
# ============================================================================


def test_loaded_model_vocab():
    chars = ["a", "b", "c"]
    from anvil.core.vocabulary import Vocabulary

    vocab = Vocabulary.from_chars(chars)
    assert vocab.vocab_size == 4
    assert vocab.bos_id == 3


def test_loaded_model_info(mock_model):
    from anvil.services.inference.loaded_model import LoadedModel

    loaded = LoadedModel(mock_model, ["a", "b"], None, None, "no-id-test")
    info = loaded.info()
    assert info["id"] is None
    assert info["version"] is None
    assert info["name"] == "no-id-test"
    assert info["is_demo"] is False


# ============================================================================
# load_model — all I/O and MLflow mocked
# ============================================================================


def test_load_model_cache_hit(demo_service, mock_model):
    """load_model returns cached model without external calls."""
    chars = ["a", "b", "c"]
    demo_service._cache[(99, 1)] = (mock_model, chars)
    loaded = _run(demo_service.load_model(model_id=99))
    assert loaded.name == "cached"


def test_load_model_from_experiment_file(demo_service, mock_model):
    """load_model reads experiment_{id}.json when it exists."""
    with (
        patch.object(Path, "exists", return_value=True),
        patch(
            "anvil.services.inference.inference.LlamaModel.load",
            return_value=mock_model,
        ),
    ):
        loaded = _run(demo_service.load_model(model_id=42))
        assert loaded.model_id == 42
        assert loaded.version == 1
        assert loaded.model is mock_model


def test_load_model_no_chars(demo_service):
    """load_model raises when the loaded model has no chars."""
    no_chars_model = MagicMock()
    no_chars_model.chars = None
    with (
        patch.object(Path, "exists", return_value=True),
        patch(
            "anvil.services.inference.inference.LlamaModel.load",
            return_value=no_chars_model,
        ),
    ):
        with pytest.raises(ValueError, match="Model has no character mapping"):
            _run(demo_service.load_model(model_id=42))


def test_load_model_mlflow_fallback(demo_service, mock_model, tmp_path):
    """load_model falls back to MLflow when no experiment file exists."""
    # Create a real model.json so Path(model_file).exists() returns True
    model_file = tmp_path / "model.json"
    model_file.write_text("{}")

    with (
        patch(
            "anvil.services.inference.inference.LlamaModel.load",
            return_value=mock_model,
        ),
        patch(
            "anvil.services.inference.inference.TrackingService"
        ) as MockTracking,
        patch(
            "anvil.services.inference.inference.MlflowClient"
        ) as MockMlflowClient,
    ):
        mock_tracking = MockTracking.return_value
        mock_tracking.list_registered_models = AsyncMock(
            return_value=[{"name": "dataset-42", "id": 42}]
        )
        mock_version = MagicMock()
        mock_version.version = "1"
        mock_version.run_id = "run_999"
        mock_client = MagicMock()
        mock_client.search_model_versions.return_value = [mock_version]
        mock_client.download_artifacts.return_value = str(tmp_path)
        MockMlflowClient.return_value = mock_client

        loaded = _run(demo_service.load_model(model_id=42))
        assert loaded.model is mock_model
        assert loaded.name == "dataset-42"


def test_load_model_mlflow_no_candidate(demo_service):
    """load_model raises when MLflow returns no matching model name."""
    with (
        patch.object(Path, "exists", return_value=False),
        patch(
            "anvil.services.inference.inference.TrackingService"
        ) as MockTracking,
    ):
        mock_tracking = MockTracking.return_value
        mock_tracking.list_registered_models = AsyncMock(
            return_value=[{"name": "unrelated-model", "id": 99}]
        )
        with pytest.raises(ValueError, match="Model not found"):
            _run(demo_service.load_model(model_id=42))


def test_load_model_mlflow_server_error(demo_service):
    """load_model catches MLflow server errors and raises ValueError."""
    with (
        patch.object(Path, "exists", return_value=False),
        patch(
            "anvil.services.inference.inference.TrackingService"
        ) as MockTracking,
        patch(
            "anvil.services.inference.inference.MlflowClient"
        ) as MockMlflowClient,
    ):
        mock_tracking = MockTracking.return_value
        mock_tracking.list_registered_models = AsyncMock(
            return_value=[{"name": "dataset-42", "id": 42}]
        )
        mock_client = MagicMock()
        mock_client.search_model_versions.side_effect = ConnectionError(
            "MLflow down"
        )
        MockMlflowClient.return_value = mock_client
        with pytest.raises(ValueError, match="Model not found"):
            _run(demo_service.load_model(model_id=42))


def test_load_model_default_resolves(demo_service, mock_model):
    """load_model() with no args resolves default via _resolve_default_id."""
    demo_service._default_id = 7
    demo_service._cache[(7, 1)] = (mock_model, ["a", "b", "c"])
    loaded = _run(demo_service.load_model())
    assert loaded.model_id == 7
    assert loaded.name == "cached"


# ============================================================================
# _resolve_default_id
# ============================================================================


def test_resolve_default_id_cached(demo_service):
    demo_service._default_id = 42
    result = _run(demo_service._resolve_default_id())
    assert result == 42


def test_resolve_default_id_from_demo_model(demo_service):
    with patch(
        "anvil.services.inference.inference.TrackingService"
    ) as MockTracking:
        mock_tracking = MockTracking.return_value
        mock_tracking.list_registered_models = AsyncMock(
            return_value=[
                {"name": "some-other", "id": 1},
                {"name": "demo", "id": 99},
            ]
        )
        result = _run(demo_service._resolve_default_id())
        assert result == 99
        assert demo_service._default_id == 99


def test_resolve_default_id_fallback_to_first(demo_service):
    with patch(
        "anvil.services.inference.inference.TrackingService"
    ) as MockTracking:
        mock_tracking = MockTracking.return_value
        mock_tracking.list_registered_models = AsyncMock(
            return_value=[
                {"name": "model-alpha", "id": 10},
                {"name": "model-beta", "id": 20},
            ]
        )
        result = _run(demo_service._resolve_default_id())
        assert result == 10
        assert demo_service._default_id == 10


def test_resolve_default_id_skips_models_without_id(demo_service):
    with patch(
        "anvil.services.inference.inference.TrackingService"
    ) as MockTracking:
        mock_tracking = MockTracking.return_value
        mock_tracking.list_registered_models = AsyncMock(
            return_value=[
                {"name": "no-id-model"},
                {"name": "has-id", "id": 55},
            ]
        )
        result = _run(demo_service._resolve_default_id())
        assert result == 55


def test_resolve_default_id_filesystem_fallback(demo_service):
    with (
        patch(
            "anvil.services.inference.inference.TrackingService"
        ) as MockTracking,
        patch.object(Path, "exists", return_value=True),
        patch.object(Path, "iterdir", return_value=[]),
    ):
        mock_tracking = MockTracking.return_value
        mock_tracking.list_registered_models = AsyncMock(return_value=[])
        with patch.object(Path, "stem", new_callable=MagicMock) as mock_stem:
            mock_stem.split.return_value = ["experiment", "7"]
            result = _run(demo_service._resolve_default_id())
            assert result == 7


def test_resolve_default_id_raises_when_nothing_found(demo_service):
    with (
        patch(
            "anvil.services.inference.inference.TrackingService"
        ) as MockTracking,
        patch.object(Path, "exists", return_value=False),
    ):
        mock_tracking = MockTracking.return_value
        mock_tracking.list_registered_models = AsyncMock(return_value=[])
        with pytest.raises(
            ValueError, match="No models available. Train or bootstrap"
        ):
            _run(demo_service._resolve_default_id())


# ============================================================================
# tokenize
# ============================================================================


def test_tokenize_basic(demo_service, mock_loaded):
    result = demo_service.tokenize("abc", mock_loaded)
    assert "model" in result
    assert "tokens" in result
    assert "vocab_size" in result
    assert "bos_id" in result
    tokens = result["tokens"]
    assert len(tokens) > 0
    for t in tokens:
        assert "char" in t
        assert "id" in t


def test_tokenize_empty_text(demo_service, mock_loaded):
    result = demo_service.tokenize("", mock_loaded)
    tokens = result["tokens"]
    assert len(tokens) == 2
    assert tokens[0]["char"] == "<BOS>"
    assert tokens[-1]["char"] == "<BOS>"


def test_tokenize_unknown_chars(demo_service, mock_loaded):
    result = demo_service.tokenize("xyz", mock_loaded)
    tokens = result["tokens"]
    # BOS (x2) — none of x/y/z are in vocab
    assert len(tokens) == 2
    assert tokens[0]["char"] == "<BOS>"


# ============================================================================
# embeddings
# ============================================================================


def test_embeddings_basic(demo_service, mock_loaded):
    result = demo_service.embeddings("abc", mock_loaded)
    assert result["n_embd"] == 16
    assert len(result["vectors"]) > 0
    assert len(result["projection"]) == len(result["vectors"])
    assert len(result["tokens"]) == len(result["vectors"])
    for p in result["projection"]:
        assert "x" in p
        assert "y" in p
        assert "label" in p


def test_embeddings_empty_text(demo_service, mock_loaded):
    result = demo_service.embeddings("", mock_loaded)
    assert len(result["vectors"]) == 2
    assert len(result["projection"]) == 2
    assert len(result["tokens"]) == 2
    assert result["tokens"][0]["char"] == "<BOS>"


def test_embeddings_counts_match(demo_service, mock_loaded):
    result = demo_service.embeddings("abc", mock_loaded)
    assert len(result["vectors"]) == len(result["projection"])
    assert len(result["vectors"]) == len(result["tokens"])


# ============================================================================
# attention
# ============================================================================


def test_attention_basic(demo_service, mock_loaded):
    result = demo_service.attention("abc", mock_loaded)
    assert result["n_layer"] == 2
    assert result["n_head"] == 4
    assert "weights" in result
    assert "rope" in result
    assert "cos_table" in result["rope"]
    assert "sin_table" in result["rope"]
    assert result["rope"]["head_dim"] == 4


def test_attention_long_input_trimmed(demo_service, mock_loaded):
    result = demo_service.attention("a" * 300, mock_loaded)
    assert len(result["tokens"]) <= 256


# ============================================================================
# sampling_distribution
# ============================================================================


def test_sampling_distribution_basic(demo_service, mock_loaded):
    result = demo_service.sampling_distribution(
        "a", 0.5, None, mock_loaded
    )
    assert "model" in result
    assert "tokens" in result
    assert result["temperature"] == 0.5
    tokens = result["tokens"]
    for t in tokens:
        assert "char" in t
        assert "id" in t
        assert "prob" in t
    probs = [t["prob"] for t in tokens]
    assert abs(sum(probs) - 1.0) < 1e-5


def test_sampling_with_top_k(demo_service, mock_loaded):
    result = demo_service.sampling_distribution(
        "a", 1.0, 2, mock_loaded
    )
    tokens = result["tokens"]
    nonzero = sum(1 for t in tokens if t["prob"] > 0)
    assert nonzero <= 2


def test_sampling_distribution_empty_prompt(demo_service, mock_loaded):
    result = demo_service.sampling_distribution(
        "", 1.0, None, mock_loaded
    )
    tokens = result["tokens"]
    probs = [t["prob"] for t in tokens]
    assert abs(sum(probs) - 1.0) < 1e-5


def test_sampling_distribution_low_temperature(demo_service, mock_loaded):
    result = demo_service.sampling_distribution(
        "a", 0.01, 1, mock_loaded
    )
    nonzero = sum(1 for t in result["tokens"] if t["prob"] > 0)
    assert nonzero == 1


def test_sampling_distribution_metadata(demo_service, mock_loaded):
    result = demo_service.sampling_distribution(
        "ab", 0.8, 10, mock_loaded
    )
    assert result["prompt"] == "ab"
    assert result["temperature"] == 0.8
    assert result["top_k"] == 10
    assert result["top_k_effective"] <= 10
    for t in result["tokens"]:
        assert "raw_logit" in t
        assert "scaled_logit" in t
        assert "prob_pre_top_k" in t
        assert "prob_final" in t
        assert "in_top_k" in t


# ============================================================================
# forward_graph
# ============================================================================


def test_forward_graph_basic(demo_service, mock_loaded):
    result = demo_service.forward_graph(mock_loaded)
    assert "model" in result
    assert "nodes" in result
    assert "edges" in result
    assert len(result["nodes"]) > 0


def test_forward_graph_with_max_nodes(demo_service, mock_loaded):
    result = demo_service.forward_graph(mock_loaded, max_nodes=5)
    assert len(result["nodes"]) <= 5


def test_forward_graph_node_structure(demo_service, mock_loaded):
    result = demo_service.forward_graph(mock_loaded)
    for n in result["nodes"]:
        assert "id" in n
        assert "op" in n
        assert "label" in n
        assert "value" in n
        assert "depth" in n


# ============================================================================
# backward_graph
# ============================================================================


def test_backward_graph_basic(demo_service, mock_loaded):
    text = "abc"
    result = demo_service.backward_graph(text, mock_loaded)
    assert "model" in result
    assert "nodes" in result
    assert "edges" in result
    assert "metadata" in result
    assert len(result["nodes"]) > 0
    meta = result["metadata"]
    assert "total_nodes" in meta
    assert "total_edges" in meta
    assert "max_depth" in meta
    assert "input_tokens" in meta
    assert "loss_value" in meta


def test_backward_graph_single_token(demo_service, mock_loaded):
    result = demo_service.backward_graph("a", mock_loaded)
    assert len(result["nodes"]) > 0
    assert "loss_value" in result["metadata"]


def test_backward_graph_has_grads(demo_service, mock_loaded):
    result = demo_service.backward_graph("abc", mock_loaded)
    for n in result["nodes"]:
        assert "grad" in n
        assert "local_grads" in n
        assert "value" in n


# ============================================================================
# autograd_example_graph
# ============================================================================


def test_autograd_example_graph_basic(demo_service, mock_loaded):
    result = demo_service.autograd_example_graph("abc", mock_loaded)
    assert "model" in result
    assert "nodes" in result
    assert "edges" in result
    assert "metadata" in result
    assert len(result["nodes"]) > 0


def test_autograd_example_graph_has_grads(demo_service, mock_loaded):
    result = demo_service.autograd_example_graph("abc", mock_loaded)
    for n in result["nodes"]:
        assert "grad" in n
        assert "local_grads" in n
        assert "value" in n


def test_autograd_example_graph_ops(demo_service, mock_loaded):
    result = demo_service.autograd_example_graph("abc", mock_loaded)
    ops = {n["op"] for n in result["nodes"]}
    assert "input" in ops
    assert "mul" in ops
    assert "add" in ops
    assert "silu" in ops
    assert "pow" in ops


def test_autograd_example_graph_empty_text(demo_service, mock_loaded):
    result = demo_service.autograd_example_graph("", mock_loaded)
    assert len(result["nodes"]) > 0


# ============================================================================
# loss_breakdown
# ============================================================================


def test_loss_breakdown_basic(demo_service, mock_loaded):
    text = "abc"
    result = demo_service.loss_breakdown(text, mock_loaded)
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


def test_loss_breakdown_single_char(demo_service, mock_loaded):
    result = demo_service.loss_breakdown("a", mock_loaded)
    assert len(result["losses"]) == 2


def test_loss_breakdown_empty_text(demo_service, mock_loaded):
    result = demo_service.loss_breakdown("", mock_loaded)
    assert len(result["losses"]) == 1
    assert result["average_loss"] > 0
    assert result["random_baseline"] > 0


# ============================================================================
# model_params
# ============================================================================


def test_model_params_basic(demo_service, mock_loaded):
    result = demo_service.model_params(mock_loaded)
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


def test_model_params_categories(demo_service, mock_loaded):
    result = demo_service.model_params(mock_loaded)
    categories = {g["category"] for g in result["groups"]}
    expected = {"embedding", "output"}
    assert expected.issubset(categories)


def test_model_params_percentages_sum(demo_service, mock_loaded):
    result = demo_service.model_params(mock_loaded)
    total = sum(g["percentage"] for g in result["groups"])
    assert abs(total - 100.0) < 1.0


def test_model_params_hyperparameters(demo_service, mock_loaded):
    result = demo_service.model_params(mock_loaded)
    assert result["n_embd"] == 16
    assert result["n_layer"] == 2
    assert result["n_head"] == 4
    assert result["block_size"] > 0
    assert result["vocab_size"] > 0


# ============================================================================
# Helpers
# ============================================================================


def _run(coro):
    """Run an async coroutine synchronously."""
    import asyncio

    return asyncio.run(coro)