# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""API tests for registry endpoints."""

import asyncio
from unittest.mock import patch

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
    """GET /v1/inference/models returns 200 with ``models`` list.

    The list may be empty when MLflow is degraded (no sidecar in
    test environment). Verifies the endpoint responds successfully
    through the ``asyncio.wait_for`` wrapper.
    """
    r = await client.get("/v1/inference/models")
    assert r.status_code == 200
    data = r.json()
    assert "models" in data


@pytest.mark.asyncio
async def test_inference_models_timeout_returns_503(client):
    """GET /v1/inference/models returns 503 when tracking service times out.

    Patches ``asyncio.wait_for`` in the learning module to raise
    ``TimeoutError``, simulating an unresponsive MLflow sidecar.
    """
    with patch(
        "anvil.api.v1.learning.asyncio.wait_for",
        side_effect=TimeoutError(),
    ):
        r = await client.get("/v1/inference/models")
    assert r.status_code == 503
    detail = r.json()["detail"]
    assert "unavailable" in detail.lower()
    assert "MLflow" in detail or "tracking" in detail.lower()


@pytest.mark.asyncio
async def test_inference_sample_missing_fields(client):
    r = await client.post("/v1/inference/sample", json={})
    assert r.status_code == 400
