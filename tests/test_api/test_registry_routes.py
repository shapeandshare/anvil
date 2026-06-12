"""API tests for registry endpoints."""

import pytest


@pytest.mark.asyncio
async def test_register_model(client):
    r = await client.post(
        "/v1/registry/models",
        json={"experiment_id": 1, "name": "api-test-model"},
    )
    # Expect 400 if experiment 1 doesn't exist in test DB
    assert r.status_code in (201, 400)
    if r.status_code == 400:
        assert "experiment" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_list_registered_models(client):
    r = await client.get("/v1/registry/models")
    assert r.status_code == 200
    data = r.json()
    assert "models" in data


@pytest.mark.asyncio
async def test_list_with_search(client):
    r = await client.get("/v1/registry/models?search=test")
    assert r.status_code == 200
    assert "models" in r.json()


@pytest.mark.asyncio
async def test_get_nonexistent_model(client):
    r = await client.get("/v1/registry/models/99999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_nonexistent_version(client):
    r = await client.get("/v1/registry/models/1/versions/999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_nonexistent_model(client):
    r = await client.delete("/v1/registry/models/99999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_register_missing_fields(client):
    r = await client.post("/v1/registry/models", json={})
    assert r.status_code == 400

    r = await client.post("/v1/registry/models", json={"experiment_id": 1})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_inference_models_endpoint(client):
    r = await client.get("/v1/inference/models")
    assert r.status_code == 200
    data = r.json()
    assert "models" in data


@pytest.mark.asyncio
async def test_inference_sample_missing_fields(client):
    r = await client.post("/v1/inference/sample", json={})
    assert r.status_code == 400