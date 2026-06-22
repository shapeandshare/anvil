# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for inference API endpoints."""

import pytest


@pytest.mark.skip(
    reason="Requires bootstrapped demo model — remove experiment_1.json fallback"
)
@pytest.mark.asyncio
async def test_inference_tokenize_demo(client):
    """Demo inference tokenize.

    Requires a bootstrapped demo model (via MLflow or warm-up).
    """
    resp = await client.post("/v1/inference/tokenize", json={"text": "abc"})
    assert resp.status_code == 200
    data = resp.json()
    assert "model" in data
    assert data["model"]["is_demo"] is True
    assert data["model"]["name"] == "demo"
    assert "tokens" in data
    assert "vocab_size" in data
    assert "bos_id" in data
    assert len(data["tokens"]) > 0
    assert data["tokens"][0]["char"] == "<BOS>"


@pytest.mark.asyncio
async def test_inference_tokenize_empty_text(client):
    resp = await client.post("/v1/inference/tokenize", json={"text": ""})
    assert resp.status_code == 422  # Pydantic validation: min_length=1


@pytest.mark.asyncio
async def test_inference_tokenize_no_text(client):
    resp = await client.post("/v1/inference/tokenize", json={})
    assert resp.status_code == 422  # Pydantic validation: required field


@pytest.mark.skip(reason="Requires bootstrapped demo model")
@pytest.mark.asyncio
async def test_inference_embeddings_demo(client):
    resp = await client.post("/v1/inference/embeddings", json={"text": "abc"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["model"]["is_demo"] is True
    assert "vectors" in data
    assert "projection" in data
    assert "n_embd" in data
    assert len(data["vectors"]) == len(data["projection"])
    assert len(data["vectors"]) == len(data["tokens"])


@pytest.mark.skip(reason="Requires bootstrapped demo model")
@pytest.mark.asyncio
async def test_inference_attention_demo(client):
    resp = await client.post("/v1/inference/attention", json={"text": "abc"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["model"]["is_demo"] is True
    assert "weights" in data
    assert "n_layer" in data
    assert "n_head" in data
    assert "tokens" in data
    n_layer = data["n_layer"]
    n_head = data["n_head"]
    assert len(data["weights"]) == n_layer
    assert len(data["weights"][0]) == n_head


@pytest.mark.skip(reason="Requires bootstrapped demo model")
@pytest.mark.asyncio
async def test_inference_sampling_distribution_demo(client):
    resp = await client.post(
        "/v1/inference/sampling-distribution",
        json={"prompt": "a", "temperature": 0.5},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["model"]["is_demo"] is True
    assert "tokens" in data
    assert "temperature" in data
    assert data["temperature"] == 0.5
    assert data["prompt"] == "a"
    assert data["vocab_size"] > 0
    assert data["top_k"] == data["vocab_size"]
    assert data["top_k_effective"] == data["vocab_size"]
    assert len(data["tokens"]) > 0
    for t in data["tokens"]:
        assert "char" in t
        assert "id" in t
        assert "prob" in t
        assert "raw_logit" in t
        assert "scaled_logit" in t
        assert "prob_pre_top_k" in t
        assert "prob_final" in t
        assert "in_top_k" in t
        assert t["prob"] == t["prob_final"]
    probs = [t["prob"] for t in data["tokens"]]
    assert abs(sum(probs) - 1.0) < 1e-4
    prob_pre = [t["prob_pre_top_k"] for t in data["tokens"]]
    assert abs(sum(prob_pre) - 1.0) < 1e-4
    assert all(t["in_top_k"] for t in data["tokens"])


@pytest.mark.asyncio
async def test_inference_sampling_distribution_with_top_k(client):
    resp = await client.post(
        "/v1/inference/sampling-distribution",
        json={"prompt": "a", "temperature": 1.0, "top_k": 3},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["top_k"] == 3
    assert data["top_k_effective"] >= 3
    assert sum(1 for t in data["tokens"] if t["in_top_k"]) == data["top_k_effective"]
    for t in data["tokens"]:
        if t["in_top_k"]:
            assert t["prob_final"] > 0
        else:
            assert t["prob_final"] < 1e-6


@pytest.mark.asyncio
async def test_inference_sampling_distribution_full_pipeline(client):
    resp = await client.post(
        "/v1/inference/sampling-distribution",
        json={"prompt": "ab", "temperature": 0.8},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["prompt"] == "ab"
    assert data["vocab_size"] > 0
    # no top_k passed → full distribution
    assert data["top_k"] == data["vocab_size"]
    assert data["top_k_effective"] == data["vocab_size"]
    assert all(t["in_top_k"] for t in data["tokens"])
    for t in data["tokens"]:
        assert abs(t["scaled_logit"] - t["raw_logit"] / data["temperature"]) < 1e-6
    # prob_pre_top_k sums to 1
    prob_pre = [t["prob_pre_top_k"] for t in data["tokens"]]
    assert abs(sum(prob_pre) - 1.0) < 1e-4
    # prob_final sums to 1
    prob_final_vals = [t["prob_final"] for t in data["tokens"]]
    assert abs(sum(prob_final_vals) - 1.0) < 1e-4
    # prob == prob_final
    assert all(t["prob"] == t["prob_final"] for t in data["tokens"])


@pytest.mark.skip(reason="Requires bootstrapped demo model")
@pytest.mark.asyncio
async def test_inference_forward_graph_demo(client):
    resp = await client.get("/v1/inference/forward-graph")
    assert resp.status_code == 200
    data = resp.json()
    assert data["model"]["is_demo"] is True
    assert "nodes" in data
    assert "edges" in data
    assert len(data["nodes"]) > 0
    for n in data["nodes"]:
        assert "id" in n
        assert "op" in n
        assert "depth" in n


@pytest.mark.asyncio
async def test_forward_pass_graph_backward_compat(client):
    resp = await client.get("/v1/forward-pass/graph")
    assert resp.status_code == 200
    data = resp.json()
    assert "nodes" in data
    assert "edges" in data
    assert len(data["nodes"]) > 0


@pytest.mark.asyncio
async def test_inference_invalid_temperature(client):
    resp = await client.post(
        "/v1/inference/sampling-distribution",
        json={"prompt": "a", "temperature": 0},
    )
    assert resp.status_code == 422  # Pydantic validation: gt=0


@pytest.mark.asyncio
async def test_inference_attention_empty_text(client):
    resp = await client.post("/v1/inference/attention", json={"text": ""})
    assert resp.status_code == 422  # Pydantic validation: min_length=1
