"""Performance benchmark tests for dataset operations."""

import time

import pytest


@pytest.mark.asyncio
async def test_import_100_performance(client):
    """SC-003 scaled: Import 100 samples should complete quickly (benchmark proxy)."""
    create = await client.post("/v1/datasets", json={"name": "perf-smoke"})
    d_id = create.json()["data"]["id"]
    text = "\n".join(f"sample {i} text" for i in range(100))
    start = time.time()
    resp = await client.post(
        f"/v1/datasets/{d_id}/import",
        json={"format": "txt", "text": text},
    )
    elapsed = time.time() - start
    assert resp.status_code == 200
    assert resp.json()["data"]["rows_imported"] == 100


@pytest.mark.asyncio
async def test_dedup_small_performance(client):
    """SC-005 scaled: Dedup on 100 samples should complete quickly."""
    create = await client.post("/v1/datasets", json={"name": "perf-dedup-sm"})
    d_id = create.json()["data"]["id"]
    text = "\n".join(f"sample {i // 2}" for i in range(100))
    await client.post(
        f"/v1/datasets/{d_id}/import",
        json={"format": "txt", "text": text},
    )
    start = time.time()
    resp = await client.post(f"/v1/datasets/{d_id}/curate/dedup")
    elapsed = time.time() - start
    assert resp.status_code == 200
    assert resp.json()["data"]["samples_removed"] >= 1