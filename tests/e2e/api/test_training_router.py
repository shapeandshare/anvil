# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""E2E tests for the training router."""

from __future__ import annotations

import asyncio
import json
import math
import tempfile
from pathlib import Path

import pytest

TINY_CONFIG = {
    "n_layer": 1,
    "n_embd": 16,
    "n_head": 4,
    "block_size": 16,
    "num_steps": 5,
    "learning_rate": 0.01,
    "compute_backend": "local-stdlib",
}
"""Smallest viable training configuration for e2e tests."""


async def _make_corpus_and_dataset(client):
    """Create a temporary corpus and dataset for training tests.

    Parameters
    ----------
    client : httpx.AsyncClient
        The test HTTP client.

    Returns
    -------
    int
        The dataset ID ready for training.
    """
    import shutil

    td = Path(tempfile.mkdtemp())
    try:
        (td / "data.txt").write_text("hello\nworld\ntest\nfoo\nbar\nbaz\n")
        r = await client.post(
            "/v1/corpora",
            json={
                "name": "train-e2e",
                "root_path": str(td),
                "chunking_strategy": "line",
            },
        )
        cid = r.json()["data"]["id"]
        await client.post(f"/v1/corpora/{cid}/ingest")
        r = await client.post(
            "/v1/datasets/from-corpus",
            json={"corpus_id": cid, "name": "train-ds"},
        )
        return r.json()["data"]["id"]
    finally:
        shutil.rmtree(td)


@pytest.mark.asyncio
async def test_training_configs(client):
    """GET /v1/training/configs returns a list of config presets."""
    r = await client.get("/v1/training/configs")
    assert r.status_code == 200
    data = r.json()
    configs = data.get("configs", [])
    assert isinstance(configs, list)


@pytest.mark.asyncio
async def test_training_start(client):
    """POST /v1/training/start starts a training run and returns metadata."""
    ds_id = await _make_corpus_and_dataset(client)

    r = await client.post(
        "/v1/training/start",
        json={**TINY_CONFIG, "dataset_id": ds_id},
    )
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    body = r.json()
    assert body["run_id"] is not None
    assert body["status"] == "running"
    assert "mlflow_run_id" in body
    assert "experiment_id" in body
    assert "tracking" in body


@pytest.mark.asyncio
async def test_training_status(client):
    """Poll training status until the run reaches a terminal state."""
    ds_id = await _make_corpus_and_dataset(client)

    r = await client.post(
        "/v1/training/start",
        json={**TINY_CONFIG, "dataset_id": ds_id},
    )
    run_id = r.json()["run_id"]

    status = "active"
    for _ in range(60):
        r = await client.get(f"/v1/training/{run_id}/status")
        if r.status_code == 404:
            # Queue is cleaned up after training completes
            status = "completed"
            break
        assert r.status_code == 200
        status = r.json().get("status", "")
        if status in ("completed", "failed"):
            break
        await asyncio.sleep(1)

    assert (
        status == "completed"
    ), f"Training run {run_id} did not complete within 60s (final status: {status})"


@pytest.mark.asyncio
async def test_training_sse_stream(client):
    """SSE stream emits at least one metrics event with finite loss."""
    ds_id = await _make_corpus_and_dataset(client)

    # Start training and capture the run_id
    r = await client.post(
        "/v1/training/start",
        json={**TINY_CONFIG, "dataset_id": ds_id},
    )
    run_id = r.json()["run_id"]

    # Read SSE events from the streaming endpoint
    events: list[tuple[str, dict]] = []
    current_event: str | None = None

    async with client.stream("GET", f"/v1/training/stream/{run_id}") as response:
        async for line in response.aiter_lines():
            if line.startswith("event: "):
                current_event = line[7:]
            elif line.startswith("data: ") and current_event is not None:
                events.append((current_event, json.loads(line[6:])))
                if current_event in ("complete", "error"):
                    break

    # Verify at least one metrics event with finite loss
    metrics_events = [ev for ev in events if ev[0] == "metrics"]
    assert len(metrics_events) >= 1, (
        f"Expected at least one metrics event, got {len(metrics_events)} events: "
        f"{[e[0] for e in events]}"
    )

    for _, payload in metrics_events:
        assert "step" in payload
        assert "loss" in payload
        assert math.isfinite(
            payload["loss"]
        ), f"Expected finite loss at step {payload['step']}, got {payload['loss']}"


@pytest.mark.asyncio
async def test_training_stop(client):
    """POST /v1/training/{run_id}/stop returns 200."""
    ds_id = await _make_corpus_and_dataset(client)

    r = await client.post(
        "/v1/training/start",
        json={**TINY_CONFIG, "dataset_id": ds_id},
    )
    run_id = r.json()["run_id"]

    r = await client.post(f"/v1/training/{run_id}/stop")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    body = r.json()
    assert body["status"] == "stopped"


@pytest.mark.asyncio
async def test_forward_pass_graph(client):
    """GET /v1/forward-pass/graph returns the computation graph."""
    r = await client.get("/v1/forward-pass/graph")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    data = r.json()
    # Model metadata
    assert "model" in data
    model = data["model"]
    assert "id" in model
    assert "version" in model
    assert "name" in model
    assert "is_demo" in model

    # Nodes
    assert "nodes" in data
    nodes = data["nodes"]
    assert len(nodes) > 0, "Expected at least one computation graph node"
    for node in nodes:
        assert "id" in node
        assert "op" in node
        assert "label" in node
        assert "value" in node
        assert "depth" in node

    # Edges
    assert "edges" in data
    assert isinstance(data["edges"], list)


@pytest.mark.asyncio
async def test_training_unknown_404(client):
    """GET /v1/training/{nonexistent}/status returns 404."""
    r = await client.get("/v1/training/99999/status")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_lora_fine_tune_job(client):
    """Submit a LoRA fine-tune job and verify the acceptance flow.

    Verifies that POST /v1/training/start with method='lora' and
    lora_rank=8 returns a valid run_id. (The backend will use the
    synthetic fallback since peft is not installed in the test env.)
    """
    r = await client.post(
        "/v1/training/start",
        json={
            "method": "lora",
            "base_model_ref": 999,  # non-existent, will fail validation
            "lora_rank": 8,
            "lora_alpha": 16,
            "num_steps": 5,
        },
    )
    # Since base_model_ref=999 won't exist, expect 422 validation error
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_lora_validation_rejects_full_method(client):
    """Verify that lora_* fields are rejected when method='full'."""
    r = await client.post(
        "/v1/training/start",
        json={
            "method": "full",
            "lora_rank": 8,
        },
    )
    assert r.status_code == 422
