"""API tests for managed evaluation dataset routes."""

from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from anvil.services.capability_unavailable import CapabilityUnavailable


@pytest.mark.asyncio
async def test_create_eval_dataset_when_available(client):
    svc_mock = MagicMock()
    svc_mock.create_eval_dataset = AsyncMock(return_value=MagicMock(name="my_eval"))
    caps = MagicMock()
    caps.genai_datasets = True
    caps.server_backed = True
    svc_mock.capabilities = AsyncMock(return_value=caps)

    import anvil.api.v1.eval_datasets as ed

    original = ed._tracking_svc
    ed._tracking_svc = svc_mock
    try:
        resp = await client.post("/v1/eval-datasets", json={"name": "my_eval"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert data["name"] == "my_eval"
    finally:
        ed._tracking_svc = original


@pytest.mark.asyncio
async def test_create_eval_dataset_unavailable(client):
    svc_mock = MagicMock()
    svc_mock.create_eval_dataset = AsyncMock(
        side_effect=CapabilityUnavailable("genai not available")
    )
    caps = MagicMock()
    caps.genai_datasets = False
    caps.server_backed = False
    svc_mock.capabilities = AsyncMock(return_value=caps)

    import anvil.api.v1.eval_datasets as ed

    original = ed._tracking_svc
    ed._tracking_svc = svc_mock
    try:
        resp = await client.post("/v1/eval-datasets", json={"name": "my_eval"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is False
        assert "reason" in data
    finally:
        ed._tracking_svc = original


@pytest.mark.asyncio
async def test_append_eval_records_when_available(client):
    svc_mock = MagicMock()
    svc_mock.append_eval_records = AsyncMock(return_value=3)
    caps = MagicMock()
    caps.genai_datasets = True
    caps.server_backed = True
    svc_mock.capabilities = AsyncMock(return_value=caps)

    import anvil.api.v1.eval_datasets as ed

    original = ed._tracking_svc
    ed._tracking_svc = svc_mock
    try:
        resp = await client.post(
            "/v1/eval-datasets/my_eval/records",
            json={"records": [{"input": "hello", "output": "world"}]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert data["appended"] == 3
    finally:
        ed._tracking_svc = original


@pytest.mark.asyncio
async def test_append_eval_records_unavailable(client):
    svc_mock = MagicMock()
    svc_mock.append_eval_records = AsyncMock(
        side_effect=CapabilityUnavailable("genai not available")
    )
    caps = MagicMock()
    caps.genai_datasets = False
    caps.server_backed = False
    svc_mock.capabilities = AsyncMock(return_value=caps)

    import anvil.api.v1.eval_datasets as ed

    original = ed._tracking_svc
    ed._tracking_svc = svc_mock
    try:
        resp = await client.post(
            "/v1/eval-datasets/my_eval/records",
            json={"records": [{"input": "hello"}]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is False
        assert "reason" in data
    finally:
        ed._tracking_svc = original


@pytest.mark.asyncio
async def test_get_eval_dataset_when_available(client):
    svc_mock = MagicMock()
    ds_mock = MagicMock(name="my_eval")
    svc_mock.get_eval_dataset = AsyncMock(return_value=ds_mock)
    caps = MagicMock()
    caps.genai_datasets = True
    caps.server_backed = True
    svc_mock.capabilities = AsyncMock(return_value=caps)

    import anvil.api.v1.eval_datasets as ed

    original = ed._tracking_svc
    ed._tracking_svc = svc_mock
    try:
        resp = await client.get("/v1/eval-datasets/my_eval")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert "dataset" in data
    finally:
        ed._tracking_svc = original


@pytest.mark.asyncio
async def test_get_eval_dataset_not_found(client):
    svc_mock = MagicMock()
    svc_mock.get_eval_dataset = AsyncMock(return_value=None)
    caps = MagicMock()
    caps.genai_datasets = True
    caps.server_backed = True
    svc_mock.capabilities = AsyncMock(return_value=caps)

    import anvil.api.v1.eval_datasets as ed

    original = ed._tracking_svc
    ed._tracking_svc = svc_mock
    try:
        resp = await client.get("/v1/eval-datasets/nonexistent")
        assert resp.status_code == 404
    finally:
        ed._tracking_svc = original


@pytest.mark.asyncio
async def test_get_eval_dataset_unavailable(client):
    svc_mock = MagicMock()
    svc_mock.get_eval_dataset = AsyncMock(
        side_effect=CapabilityUnavailable("genai not available")
    )
    caps = MagicMock()
    caps.genai_datasets = False
    caps.server_backed = False
    svc_mock.capabilities = AsyncMock(return_value=caps)

    import anvil.api.v1.eval_datasets as ed

    original = ed._tracking_svc
    ed._tracking_svc = svc_mock
    try:
        resp = await client.get("/v1/eval-datasets/my_eval")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is False
        assert "reason" in data
    finally:
        ed._tracking_svc = original


@pytest.mark.asyncio
async def test_create_eval_dataset_missing_name(client):
    svc_mock = MagicMock()
    svc_mock.create_eval_dataset = AsyncMock()
    caps = MagicMock()
    caps.genai_datasets = True
    caps.server_backed = True
    svc_mock.capabilities = AsyncMock(return_value=caps)

    import anvil.api.v1.eval_datasets as ed

    original = ed._tracking_svc
    ed._tracking_svc = svc_mock
    try:
        resp = await client.post("/v1/eval-datasets", json={})
        assert resp.status_code == 400
    finally:
        ed._tracking_svc = original
