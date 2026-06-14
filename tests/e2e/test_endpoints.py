"""e2e HTTP endpoint tests."""

import pytest


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_list_datasets(client):
    r = await client.get("/v1/datasets")
    assert r.status_code == 200
    assert "datasets" in r.json().get("data", r.json())


@pytest.mark.asyncio
async def test_list_experiments(client):
    r = await client.get("/v1/experiments")
    assert r.status_code == 200
    assert "experiments" in r.json()
