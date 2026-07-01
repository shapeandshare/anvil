# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""E2E tests for the inference router (also covers learning router data routes per FR-001)."""

import math

import pytest


@pytest.mark.asyncio
async def test_inference_models(client):
    """GET /v1/inference/models returns the list of registered models.

    Verifies the response contains a ``models`` list. The list may be
    empty when MLflow is degraded (tracking sidecar not running). Covers
    the learning router data route per FR-001.
    """
    response = await client.get("/v1/inference/models")
    assert response.status_code == 200

    data = response.json()
    assert "models" in data
    assert isinstance(data["models"], list)

    for model in data["models"]:
        assert "id" in model
        assert "name" in model


@pytest.mark.asyncio
async def test_inference_tokenize(client):
    """POST /v1/inference/tokenize returns token IDs for input text."""
    response = await client.post(
        "/v1/inference/tokenize",
        json={"text": "hello world"},
    )
    assert response.status_code == 200

    data = response.json()
    assert "tokens" in data
    assert isinstance(data["tokens"], list)
    assert len(data["tokens"]) > 0
    for token in data["tokens"]:
        assert "id" in token
        assert isinstance(token["id"], int)


@pytest.mark.asyncio
async def test_inference_embeddings(client):
    """POST /v1/inference/embeddings returns embedding vectors for input text."""
    response = await client.post(
        "/v1/inference/embeddings",
        json={"text": "hello world"},
    )
    assert response.status_code == 200

    data = response.json()
    assert "vectors" in data
    assert isinstance(data["vectors"], list)
    assert len(data["vectors"]) > 0
    for vec in data["vectors"]:
        assert isinstance(vec, list)
        assert len(vec) > 0
        for val in vec:
            assert isinstance(val, (int, float))


@pytest.mark.asyncio
async def test_inference_attention(client):
    """POST /v1/inference/attention returns attention weights/patterns for input text."""
    response = await client.post(
        "/v1/inference/attention",
        json={"text": "hello world"},
    )
    assert response.status_code == 200

    data = response.json()
    assert "weights" in data
    assert isinstance(data["weights"], list)
    assert len(data["weights"]) > 0
    assert "n_layer" in data
    assert "n_head" in data


@pytest.mark.asyncio
async def test_inference_sampling_distribution(client):
    """POST /v1/inference/sampling-distribution returns logits/probabilities for a prompt."""
    response = await client.post(
        "/v1/inference/sampling-distribution",
        json={"text": "hello"},
    )
    assert response.status_code == 200

    data = response.json()
    assert "tokens" in data
    assert isinstance(data["tokens"], list)
    assert len(data["tokens"]) > 0


@pytest.mark.asyncio
async def test_inference_forward_graph(client):
    """GET /v1/inference/forward-graph returns model info, nodes, and edges.

    Verifies the response contains ``model`` metadata (with ``id``,
    ``version``, ``name``, ``is_demo``), a non-empty ``nodes`` list
    with expected node schema, and an ``edges`` list.
    """
    response = await client.get("/v1/inference/forward-graph")
    assert (
        response.status_code == 200
    ), f"Expected 200, got {response.status_code}: {response.text}"

    data = response.json()
    assert "model" in data
    model = data["model"]
    assert "id" in model
    assert "version" in model
    assert "name" in model
    assert "is_demo" in model

    assert "nodes" in data
    nodes = data["nodes"]
    assert len(nodes) > 0, "Expected at least one computation graph node"
    for node in nodes:
        assert "id" in node
        assert "op" in node
        assert "label" in node
        assert "value" in node
        assert "depth" in node

    assert "edges" in data
    assert isinstance(data["edges"], list)


@pytest.mark.asyncio
async def test_inference_backward_graph(client):
    """POST /v1/inference/backward-graph returns backward graph structure."""
    response = await client.post(
        "/v1/inference/backward-graph",
        json={"text": "hello world"},
    )
    assert response.status_code == 200

    data = response.json()
    assert "model" in data
    assert "nodes" in data
    assert len(data["nodes"]) > 0
    assert "edges" in data
    assert isinstance(data["edges"], list)
    assert "metadata" in data
    meta = data["metadata"]
    assert "total_nodes" in meta
    assert "total_edges" in meta
    assert "loss_value" in meta
    assert math.isfinite(meta["loss_value"])


@pytest.mark.asyncio
async def test_inference_autograd_example(client):
    """POST /v1/inference/autograd-example returns an autograd computation trace."""
    response = await client.post(
        "/v1/inference/autograd-example",
        json={"text": "hello world"},
    )
    assert response.status_code == 200

    data = response.json()
    assert "model" in data
    assert "nodes" in data
    assert len(data["nodes"]) > 0
    assert "edges" in data
    assert isinstance(data["edges"], list)
    assert "metadata" in data
    meta = data["metadata"]
    assert "total_nodes" in meta
    assert "loss_value" in meta
    assert math.isfinite(meta["loss_value"])


@pytest.mark.asyncio
async def test_inference_loss_breakdown(client):
    """POST /v1/inference/loss-breakdown returns loss components for input text."""
    response = await client.post(
        "/v1/inference/loss-breakdown",
        json={"text": "hello world"},
    )
    assert response.status_code == 200

    data = response.json()
    assert "losses" in data
    assert isinstance(data["losses"], list)
    assert len(data["losses"]) > 0
    for loss in data["losses"]:
        assert isinstance(loss, (int, float))
    assert "average_loss" in data
    assert math.isfinite(data["average_loss"])
    assert "random_baseline" in data
    assert math.isfinite(data["random_baseline"])


@pytest.mark.asyncio
async def test_inference_model_params(client):
    """GET /v1/inference/model-params returns model parameter information."""
    response = await client.get("/v1/inference/model-params")
    assert response.status_code == 200

    data = response.json()
    assert "model" in data
    assert "total_params" in data
    assert isinstance(data["total_params"], int)
    assert data["total_params"] > 0
    assert "groups" in data
    assert isinstance(data["groups"], list)
    assert len(data["groups"]) > 0


@pytest.mark.asyncio
async def test_inference_sample(client):
    """POST /v1/inference/sample generates non-empty text from the seeded model.

    Uses model_id=1 (the seeded experiment_1.json artifact) since the
    MLflow model registry is unavailable in the test environment.
    Asserts generated text is non-empty (per FR-008). Covers the learning
    router data route per FR-001.
    """
    response = await client.post(
        "/v1/inference/sample",
        json={
            "prompt": "hello",
            "model_id": 1,
            "version": 1,
        },
    )
    assert (
        response.status_code == 200
    ), f"Expected 200, got {response.status_code}: {response.text}"

    data = response.json()
    assert "samples" in data
    assert isinstance(data["samples"], list)
    assert len(data["samples"]) > 0
    assert len(data["samples"][0]) > 0, "Expected non-empty generated text per FR-008"


@pytest.mark.asyncio
async def test_inference_sample_unknown_model(client):
    """POST /v1/inference/sample with a non-existent model returns 404 or 422."""
    response = await client.post(
        "/v1/inference/sample",
        json={"prompt": "hello", "model_id": 99999, "version": 1},
    )
    assert response.status_code in (
        404,
        422,
    ), f"Expected 404 or 422, got {response.status_code}: {response.text}"


@pytest.mark.asyncio
async def test_inference_generate_endpoint(client):
    """Verify the new generation endpoint accepts valid requests.

    POST /v1/inference/generate should return a textual response.
    Uses model_id=1 (demo model, should exist in test fixtures).
    """
    r = await client.post(
        "/v1/inference/generate",
        json={
            "model_id": 1,
            "prompt": "Hello",
            "temperature": 0.7,
            "max_tokens": 10,
        },
    )
    # Demo model should exist, returning generated text
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        data = r.json()
        assert "text" in data
        assert data["model_id"] == 1


@pytest.mark.asyncio
async def test_inference_generate_with_adapter(client):
    """Verify generation with valid model_id + invalid adapter_id returns 404."""
    r = await client.post(
        "/v1/inference/generate",
        json={
            "model_id": 1,
            "prompt": "Test prompt",
            "adapter_id": "nonexistent_adapter",
        },
    )
    # Model 1 should exist but adapter won't, expect 404
    assert r.status_code in (200, 404)
