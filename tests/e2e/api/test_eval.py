# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""E2E tests for the eval and eval-datasets routers."""

import asyncio
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


@pytest.mark.asyncio
async def test_create_eval_dataset(client):
    """POST /v1/eval-datasets creates a new eval dataset."""
    r = await client.post(
        "/v1/eval-datasets",
        json={"name": "e2e-test-eval"},
    )
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    body = r.json()
    assert body.get("available") is True
    assert body.get("name") == "e2e-test-eval"
    assert body.get("dataset") is not None


@pytest.mark.asyncio
async def test_add_eval_records(client):
    """POST /v1/eval-datasets/{name}/records appends records to a dataset."""
    # Create the dataset first
    r = await client.post(
        "/v1/eval-datasets",
        json={"name": "e2e-test-records"},
    )
    assert r.status_code == 200

    # Append records
    r = await client.post(
        "/v1/eval-datasets/e2e-test-records/records",
        json={"records": [{"text": "test input"}]},
    )
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    body = r.json()
    assert body.get("available") is True
    assert body.get("appended") == 1


@pytest.mark.asyncio
async def test_get_eval_dataset(client):
    """GET /v1/eval-datasets/{name} returns a dataset with its records."""
    ds_name = "e2e-test-get"
    # Create the dataset
    r = await client.post(
        "/v1/eval-datasets",
        json={"name": ds_name},
    )
    assert r.status_code == 200

    # Append records
    records = [{"text": "hello world"}, {"text": "test text"}]
    r = await client.post(
        f"/v1/eval-datasets/{ds_name}/records",
        json={"records": records},
    )
    assert r.status_code == 200

    # Retrieve the dataset
    r = await client.get(f"/v1/eval-datasets/{ds_name}")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    body = r.json()
    assert body.get("available") is True
    assert body.get("name") == ds_name
    assert body.get("dataset") is not None


@pytest.mark.asyncio
async def test_perplexity(client):
    """POST /v1/eval/perplexity computes finite perplexity on a trained model.

    Trains a tiny model, waits for completion, then evaluates it against
    text from an eval dataset. Asserts perplexity is finite per FR-008.
    """
    td = tempfile.mkdtemp()
    try:
        (Path(td) / "data.txt").write_text("hello world test corpus for perplexity\n")

        # Create corpus
        r = await client.post(
            "/v1/corpora",
            json={
                "name": "perp-e2e",
                "root_path": td,
                "chunking_strategy": "line",
            },
        )
        assert r.status_code == 200
        cid = r.json()["data"]["id"]

        # Ingest corpus
        r = await client.post(f"/v1/corpora/{cid}/ingest")
        assert r.status_code == 200

        # Create dataset from corpus
        r = await client.post(
            "/v1/datasets/from-corpus",
            json={"corpus_id": cid, "name": "perp-ds"},
        )
        assert r.status_code == 200
        ds_id = r.json()["data"]["id"]

        # Start training
        r = await client.post(
            "/v1/training/start",
            json={**TINY_CONFIG, "dataset_id": ds_id},
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        body = r.json()
        assert body["status"] == "running"
        run_id = body["run_id"]
        experiment_id = body["experiment_id"]

        # Wait for training to complete
        for _ in range(60):
            r = await client.get(f"/v1/training/{run_id}/status")
            if r.status_code == 404:
                # Queue cleaned up — training finished
                break
            await asyncio.sleep(1)
        else:
            pytest.fail(f"Training run {run_id} did not complete within 60s")

        # Allow model write to flush to disk
        await asyncio.sleep(0.5)

        # Create eval dataset and add text records
        r = await client.post(
            "/v1/eval-datasets",
            json={"name": "perp-eval"},
        )
        assert r.status_code == 200

        r = await client.post(
            "/v1/eval-datasets/perp-eval/records",
            json={"records": [{"text": "hello world test"}]},
        )
        assert r.status_code == 200

        # Compute perplexity using the trained model
        r = await client.post(
            "/v1/eval/perplexity",
            json={
                "model_id": experiment_id,
                "version": 1,
                "text": "hello world test",
            },
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        result = r.json()

        # FR-008: perplexity must be finite
        perplexity = result["perplexity"]
        assert math.isfinite(
            perplexity
        ), f"Expected finite perplexity, got {perplexity}"
        assert "avg_loss" in result
        assert "num_positions" in result
        assert "vocab_size" in result
        assert "model_config" in result

    finally:
        import shutil

        shutil.rmtree(td)
