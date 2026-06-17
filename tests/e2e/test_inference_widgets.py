"""End-to-end tests for learning content enrichment endpoints and widgets."""

import pytest


@pytest.mark.asyncio
async def test_backward_graph_endpoint(client):
    """T008: backward-graph returns valid graph with .grad populated."""
    r = await client.post("/v1/inference/backward-graph", json={"text": "hi"})
    assert r.status_code == 200
    data = r.json()
    assert "nodes" in data
    assert "edges" in data
    assert "metadata" in data
    assert len(data["nodes"]) > 0
    assert any(abs(n["grad"]) > 0 for n in data["nodes"] if n["grad"] != 0)
    assert data["metadata"]["total_nodes"] == len(data["nodes"])
    assert data["metadata"]["total_nodes"] <= 400


@pytest.mark.asyncio
async def test_loss_breakdown_endpoint(client):
    """T009: loss-breakdown returns per-token losses with baseline."""
    r = await client.post("/v1/inference/loss-breakdown", json={"text": "emma"})
    assert r.status_code == 200
    data = r.json()
    assert "tokens" in data
    assert "losses" in data
    assert len(data["losses"]) == len(data["tokens"]) - 1
    assert all(l > 0 for l in data["losses"])
    assert data["random_baseline"] > 0
    assert abs(data["average_loss"] - sum(data["losses"]) / len(data["losses"])) < 1e-6
    assert data["vocab_size"] > 0


@pytest.mark.asyncio
async def test_model_params_endpoint(client):
    """T010: model-params returns grouped parameter breakdown."""
    r = await client.get("/v1/inference/model-params")
    assert r.status_code == 200
    data = r.json()
    assert "groups" in data
    assert "total_params" in data
    group_sum = sum(g["num_params"] for g in data["groups"])
    assert group_sum == data["total_params"]
    cats = {g["category"] for g in data["groups"]}
    assert "embedding" in cats
    assert "attention projections" in cats
    assert "SwiGLU MLP" in cats
    assert "output" in cats
    assert "RMSNorm scales" in cats


@pytest.mark.asyncio
async def test_lesson_routes_return_200(client):
    """T046: All lesson page routes return 200 with valid HTML."""
    lessons = [
        "/v1/learn/autograd",
        "/v1/learn/loss",
        "/v1/learn/parameters",
        "/v1/learn/adam",
        "/v1/learn/faq",
        "/v1/learn/attention",
    ]
    for path in lessons:
        r = await client.get(path)
        assert r.status_code == 200, f"{path} returned {r.status_code}"
        assert "text/html" in r.headers.get("content-type", ""), f"{path} not HTML"


@pytest.mark.asyncio
async def test_backward_graph_demo_fallback(client):
    """T053: FR-019 — backward-graph works without model_id (demo fallback)."""
    r = await client.post("/v1/inference/backward-graph", json={"text": "test"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("model", {}).get("is_demo", False) is True


@pytest.mark.asyncio
async def test_loss_breakdown_demo_fallback(client):
    """T053: FR-019 — loss-breakdown works without model_id."""
    r = await client.post("/v1/inference/loss-breakdown", json={"text": "test"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("model", {}).get("is_demo", False) is True


@pytest.mark.asyncio
async def test_model_params_demo_fallback(client):
    """T053: FR-019 — model-params works without model_id."""
    r = await client.get("/v1/inference/model-params", params={})
    assert r.status_code == 200
    data = r.json()
    assert data.get("model", {}).get("is_demo", False) is True


@pytest.mark.asyncio
async def test_backward_graph_oov_skipped(client):
    """T054: FR-020 — OOV characters are silently skipped, endpoint returns 200."""
    r = await client.post("/v1/inference/backward-graph", json={"text": "hello \U0001f60a world"})
    assert r.status_code == 200
    data = r.json()
    assert "nodes" in data
    assert "edges" in data


@pytest.mark.asyncio
async def test_loss_breakdown_oov_skipped(client):
    """T054: FR-020 — OOV characters are silently skipped for loss-breakdown."""
    r = await client.post("/v1/inference/loss-breakdown", json={"text": "hi \u2603 snow"})
    assert r.status_code == 200
    data = r.json()
    assert "tokens" in data
    assert "losses" in data


@pytest.mark.asyncio
async def test_architecture_page_returns_200(client):
    """TARCH: Architecture lesson page returns 200 with expected structure."""
    r = await client.get("/v1/learn/architecture")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    html = r.text
    assert 'id="arch-experience"' in html
    assert 'id="arch-steps"' in html
    assert "Architecture" in html
    assert "the-big-picture" in html


@pytest.mark.asyncio
async def test_attention_oov_skipped(client):
    """T054: FR-020 — OOV characters are silently skipped for attention endpoint."""
    r = await client.post("/v1/inference/attention", json={"text": "test \U0001f436"})
    assert r.status_code == 200
    data = r.json()
    assert "tokens" in data
    assert "weights" in data


@pytest.mark.asyncio
async def test_autograd_example_is_small_and_complete(client):
    """Pedagogical autograd graph stays tiny and legible, unlike the full model graph."""
    r = await client.post("/v1/inference/autograd-example", json={"text": "hi"})
    assert r.status_code == 200
    data = r.json()
    nodes = data["nodes"]
    assert 0 < len(nodes) <= 50
    assert data["metadata"]["total_nodes"] == len(nodes)
    assert data["metadata"]["max_depth"] <= 12


@pytest.mark.asyncio
async def test_autograd_example_teaches_every_concept(client):
    """Graph must exercise each lesson concept: ops, real gradients, and accumulation."""
    from collections import Counter

    r = await client.post("/v1/inference/autograd-example", json={"text": "hi"})
    assert r.status_code == 200
    data = r.json()
    nodes, edges = data["nodes"], data["edges"]

    ops = {n["op"] for n in nodes}
    assert {"input", "mul", "add", "silu", "pow"} <= ops

    assert any(n["grad"] != 0 for n in nodes)

    incoming = Counter(e["to"] for e in edges)
    assert any(count >= 2 for count in incoming.values())


@pytest.mark.asyncio
async def test_autograd_example_demo_fallback(client):
    """FR-019 — autograd-example works without model_id (demo fallback)."""
    r = await client.post("/v1/inference/autograd-example", json={"text": "test"})
    assert r.status_code == 200
    assert r.json().get("model", {}).get("is_demo", False) is True


@pytest.mark.asyncio
async def test_autograd_example_oov_skipped(client):
    """FR-020 — OOV characters are silently skipped, endpoint still returns a graph."""
    r = await client.post(
        "/v1/inference/autograd-example", json={"text": "hi \U0001f60a there"}
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["nodes"]) > 0
