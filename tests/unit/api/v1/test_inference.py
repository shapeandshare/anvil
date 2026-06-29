"""Tests for inference API endpoints.

Covers all 9 routes in the inference router: tokenize, embeddings,
attention, sampling-distribution, forward-graph, backward-graph,
autograd-example, loss-breakdown, and model-params.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import anvil.api.v1.inference as inference_mod

SAMPLE_LOADED = MagicMock(name="loaded_model")

TOKENIZE_RESP = {
    "model": {"name": "demo"},
    "tokens": [{"char": "a", "id": 1}],
    "vocab_size": 27,
    "bos_id": 0,
}
EMBEDDINGS_RESP = {
    "model": {"name": "demo"},
    "tokens": [{"char": "a", "id": 1}],
    "vectors": [[0.1, 0.2]],
    "n_embd": 2,
    "projection": [{"x": 0.1, "y": 0.2, "label": "a"}],
}
ATTENTION_RESP = {
    "model": {"name": "demo"},
    "tokens": [{"char": "a", "id": 1}],
    "n_layer": 1,
    "n_head": 1,
    "weights": [[[0.5]]],
    "rope": {"cos_table": [1.0], "sin_table": [0.0], "head_dim": 4},
}
SAMPLING_RESP = {
    "model": {"name": "demo"},
    "tokens": [{"char": "a", "id": 1, "prob": 0.5}],
    "temperature": 0.5,
    "prompt": "a",
    "vocab_size": 27,
    "top_k": 27,
    "top_k_effective": 27,
}
FORWARD_GRAPH_RESP = {
    "model": {"name": "demo"},
    "nodes": [],
    "edges": [],
}
BACKWARD_GRAPH_RESP = {
    "model": {"name": "demo"},
    "nodes": [],
    "edges": [],
    "metadata": {
        "total_nodes": 0,
        "total_edges": 0,
        "max_depth": 0,
        "input_tokens": [],
        "loss_value": 0.0,
    },
}
AUTOGRAD_RESP = {
    "model": {"name": "demo"},
    "nodes": [],
    "edges": [],
    "metadata": {
        "total_nodes": 0,
        "total_edges": 0,
        "max_depth": 0,
        "input_tokens": [],
        "loss_value": 0.0,
    },
}
LOSS_RESP = {
    "model": {"name": "demo"},
    "tokens": [],
    "losses": [0.5],
    "average_loss": 0.5,
    "random_baseline": 3.3,
    "vocab_size": 27,
}
MODEL_PARAMS_RESP = {
    "model": {"name": "demo"},
    "total_params": 100,
    "n_embd": 2,
    "n_layer": 1,
    "n_head": 1,
    "block_size": 64,
    "vocab_size": 10,
    "groups": [],
}


####################################################################
# Fixture: mock the module-level _svc singleton
####################################################################


@pytest.fixture(autouse=True)
def _mock_svc():
    """Replace the module-level ``_svc`` singleton with a fresh mock.

    Each service-method attribute is pre-configured with a default
    return value.  Tests that need custom behaviour (e.g. raising)
    can reassign the attribute on the yielded mock.
    """
    with patch.object(inference_mod, "_svc") as svc:
        # load_model is async — must be AsyncMock
        svc.load_model = AsyncMock(return_value=SAMPLE_LOADED)
        # All remaining service methods are sync
        svc.tokenize = MagicMock(return_value=TOKENIZE_RESP)
        svc.embeddings = MagicMock(return_value=EMBEDDINGS_RESP)
        svc.attention = MagicMock(return_value=ATTENTION_RESP)
        svc.sampling_distribution = MagicMock(return_value=SAMPLING_RESP)
        svc.forward_graph = MagicMock(return_value=FORWARD_GRAPH_RESP)
        svc.backward_graph = MagicMock(return_value=BACKWARD_GRAPH_RESP)
        svc.autograd_example_graph = MagicMock(return_value=AUTOGRAD_RESP)
        svc.loss_breakdown = MagicMock(return_value=LOSS_RESP)
        svc.model_params = MagicMock(return_value=MODEL_PARAMS_RESP)
        yield svc


####################################################################
# Text-input POST endpoints (tokenize, embeddings, attention, etc.)
####################################################################

TEXT_BODY_ENDPOINTS = [
    ("tokenize", {"text": "hello"}, TOKENIZE_RESP),
    ("embeddings", {"text": "hello"}, EMBEDDINGS_RESP),
    ("attention", {"text": "hello"}, ATTENTION_RESP),
    ("backward-graph", {"text": "hello"}, BACKWARD_GRAPH_RESP),
    ("autograd-example", {"text": "hello"}, AUTOGRAD_RESP),
    ("loss-breakdown", {"text": "hello"}, LOSS_RESP),
]


class TestTextBodyEndpoints:
    """Parametrized tests for the six POST endpoints that accept
    a ``text`` body and wrap the service call in ``_call_or_400``.
    """

    @pytest.mark.parametrize("path_suffix,body,expected", TEXT_BODY_ENDPOINTS)
    async def test_success(
        self, client, _mock_svc, path_suffix: str, body: dict, expected: dict
    ):
        resp = await client.post(f"/v1/inference/{path_suffix}", json=body)
        assert resp.status_code == 200
        assert resp.json() == expected

    @pytest.mark.parametrize("path_suffix,body,expected", TEXT_BODY_ENDPOINTS)
    async def test_with_model_id(
        self, client, _mock_svc, path_suffix: str, body: dict, expected: dict
    ):
        resp = await client.post(
            f"/v1/inference/{path_suffix}",
            json={**body, "model_id": 42},
        )
        assert resp.status_code == 200
        assert resp.json() == expected
        _mock_svc.load_model.assert_called_with(42, None)

    @pytest.mark.parametrize("path_suffix,body,expected", TEXT_BODY_ENDPOINTS)
    async def test_model_not_found_value_error(
        self, client, _mock_svc, path_suffix: str, body: dict, expected: dict
    ):
        _mock_svc.load_model = AsyncMock(
            side_effect=ValueError("Model not found: model_id=99")
        )
        resp = await client.post(
            f"/v1/inference/{path_suffix}",
            json={**body, "model_id": 99},
        )
        assert resp.status_code == 404
        assert "Model not found" in resp.json()["detail"]

    @pytest.mark.parametrize("path_suffix,body,expected", TEXT_BODY_ENDPOINTS)
    async def test_model_not_found_file_not_found(
        self, client, _mock_svc, path_suffix: str, body: dict, expected: dict
    ):
        _mock_svc.load_model = AsyncMock(
            side_effect=FileNotFoundError("No such file")
        )
        resp = await client.post(
            f"/v1/inference/{path_suffix}",
            json={**body, "model_id": 99},
        )
        assert resp.status_code == 404
        assert "No such file" in resp.json()["detail"]

    @pytest.mark.parametrize("path_suffix,body,expected", TEXT_BODY_ENDPOINTS)
    async def test_key_error_400(
        self, client, _mock_svc, path_suffix: str, body: dict, expected: dict
    ):
        """Service methods wrapped in ``_call_or_400`` raise ``KeyError``
        for characters not in the vocabulary → HTTP 400."""
        # Map path_suffix → corresponding service attribute
        svc_attr = path_suffix.replace("-", "_")
        svc_method = {
            "tokenize": "tokenize",
            "embeddings": "embeddings",
            "attention": "attention",
            "backward_graph": "backward_graph",
            "autograd_example": "autograd_example_graph",
            "loss_breakdown": "loss_breakdown",
        }[svc_attr]

        # Determine the service attribute name
        svc_method_map = {
            "tokenize": _mock_svc.tokenize,
            "embeddings": _mock_svc.embeddings,
            "attention": _mock_svc.attention,
            "backward-graph": _mock_svc.backward_graph,
            "autograd-example": _mock_svc.autograd_example_graph,
            "loss-breakdown": _mock_svc.loss_breakdown,
        }
        svc_method_map[path_suffix].side_effect = KeyError("ñ")
        resp = await client.post(f"/v1/inference/{path_suffix}", json=body)
        assert resp.status_code == 400
        assert "ñ" in resp.json()["detail"]
        assert "not in the model's vocabulary" in resp.json()["detail"]

    @pytest.mark.parametrize("path_suffix,body,expected", TEXT_BODY_ENDPOINTS)
    async def test_empty_text_422(
        self, client, _mock_svc, path_suffix: str, body: dict, expected: dict
    ):
        """Pydantic ``min_length=1`` rejects empty ``text`` with 422."""
        resp = await client.post(
            f"/v1/inference/{path_suffix}",
            json={"text": ""},
        )
        assert resp.status_code == 422


####################################################################
# GET query-param endpoints (forward-graph, model-params)
####################################################################

QUERY_PARAM_ENDPOINTS = [
    ("forward-graph", FORWARD_GRAPH_RESP),
    ("model-params", MODEL_PARAMS_RESP),
]


class TestQueryParamEndpoints:
    """Parametrized tests for the two GET endpoints that accept query
    params (``model_id``, ``version``) and call the service directly
    (no ``_call_or_400`` wrapper).
    """

    @pytest.mark.parametrize("path_suffix,expected", QUERY_PARAM_ENDPOINTS)
    async def test_success(
        self, client, _mock_svc, path_suffix: str, expected: dict
    ):
        resp = await client.get(f"/v1/inference/{path_suffix}")
        assert resp.status_code == 200
        assert resp.json() == expected

    @pytest.mark.parametrize("path_suffix,expected", QUERY_PARAM_ENDPOINTS)
    async def test_with_model_id(
        self, client, _mock_svc, path_suffix: str, expected: dict
    ):
        resp = await client.get(
            f"/v1/inference/{path_suffix}?model_id=7&version=2"
        )
        assert resp.status_code == 200
        assert resp.json() == expected
        _mock_svc.load_model.assert_called_with(7, 2)

    @pytest.mark.parametrize("path_suffix,expected", QUERY_PARAM_ENDPOINTS)
    async def test_model_not_found(
        self, client, _mock_svc, path_suffix: str, expected: dict
    ):
        _mock_svc.load_model = AsyncMock(
            side_effect=ValueError("Model not found")
        )
        resp = await client.get(f"/v1/inference/{path_suffix}?model_id=99")
        assert resp.status_code == 404
        assert "Model not found" in resp.json()["detail"]


####################################################################
# POST /v1/inference/sampling-distribution
####################################################################


class TestSamplingDistribution:
    """Tests for the sampling-distribution endpoint, which has unique
    validation for ``prompt`` and ``temperature``.
    """

    async def test_success(self, client, _mock_svc):
        resp = await client.post(
            "/v1/inference/sampling-distribution",
            json={"prompt": "hello"},
        )
        assert resp.status_code == 200
        assert resp.json() == SAMPLING_RESP

    async def test_with_model_id_and_temperature(self, client, _mock_svc):
        resp = await client.post(
            "/v1/inference/sampling-distribution",
            json={"prompt": "hello", "temperature": 0.8, "top_k": 5, "model_id": 3},
        )
        assert resp.status_code == 200
        _mock_svc.load_model.assert_called_with(3, None)
        _mock_svc.sampling_distribution.assert_called_with(
            "hello", 0.8, 5, SAMPLE_LOADED
        )

    async def test_model_not_found(self, client, _mock_svc):
        _mock_svc.load_model = AsyncMock(
            side_effect=ValueError("Model not found")
        )
        resp = await client.post(
            "/v1/inference/sampling-distribution",
            json={"prompt": "hello", "model_id": 99},
        )
        assert resp.status_code == 404

    async def test_nonpositive_temperature_422(self, client, _mock_svc):
        """Pydantic's ``gt=0`` constraint rejects temperature ≤ 0."""
        resp = await client.post(
            "/v1/inference/sampling-distribution",
            json={"prompt": "hello", "temperature": 0},
        )
        assert resp.status_code == 422

    async def test_negative_temperature_422(self, client, _mock_svc):
        resp = await client.post(
            "/v1/inference/sampling-distribution",
            json={"prompt": "hello", "temperature": -1},
        )
        assert resp.status_code == 422

    async def test_empty_prompt_allowed(self, client, _mock_svc):
        """The schema allows empty prompt (``prompt: str = ""``),
        so the request succeeds."""
        resp = await client.post(
            "/v1/inference/sampling-distribution",
            json={"prompt": ""},
        )
        # Route checks isinstance(prompt, str) — "" passes → 200
        assert resp.status_code == 200


####################################################################
# Additional edge cases
####################################################################


class TestEdgeCases:
    """Scattered edge cases that don't fit the parametrized patterns."""

    async def test_tokenize_extra_fields_rejected(self, client, _mock_svc):
        """All schemas use ``extra="forbid"``."""
        resp = await client.post(
            "/v1/inference/tokenize",
            json={"text": "hi", "unknown_field": "x"},
        )
        assert resp.status_code == 422

    async def test_load_model_defaults_to_none(self, client, _mock_svc):
        """When neither ``model_id`` nor ``version`` are supplied,
        ``load_model`` is called with ``None, None``."""
        await client.post("/v1/inference/tokenize", json={"text": "hi"})
        _mock_svc.load_model.assert_called_with(None, None)

    async def test_param_overrides_svc_mock(
        self, client, _mock_svc
    ):
        """Test that reassigning ``_mock_svc.sampling_distribution``
        is respected by the route."""
        custom_resp = {"custom": True}
        _mock_svc.sampling_distribution = MagicMock(return_value=custom_resp)
        resp = await client.post(
            "/v1/inference/sampling-distribution",
            json={"prompt": "hi"},
        )
        assert resp.json() == custom_resp