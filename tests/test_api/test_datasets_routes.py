"""API tests for dataset deletion with demo data warnings."""

import pytest

pytestmark = pytest.mark.asyncio


async def test_delete_demo_dataset_returns_409(client):
    resp = await client.post(
        "/v1/datasets",
        json={"name": "Demo - test/my-set", "description": "test demo dataset"},
    )
    assert resp.status_code == 200
    ds_id = resp.json()["data"]["id"]

    delete_resp = await client.delete(f"/v1/datasets/{ds_id}")
    assert delete_resp.status_code == 409
    data = delete_resp.json()
    assert "demo" in data["detail"].lower()


async def test_force_delete_demo_dataset_succeeds(client):
    resp = await client.post(
        "/v1/datasets",
        json={"name": "Demo - test/force-set", "description": "test"},
    )
    assert resp.status_code == 200
    ds_id = resp.json()["data"]["id"]

    delete_resp = await client.delete(f"/v1/datasets/{ds_id}?force=true")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["data"]["message"] == "Dataset deleted"


async def test_delete_normal_dataset_succeeds_without_warning(client):
    resp = await client.post(
        "/v1/datasets",
        json={"name": "my-own-dataset", "description": "user created"},
    )
    assert resp.status_code == 200
    ds_id = resp.json()["data"]["id"]

    delete_resp = await client.delete(f"/v1/datasets/{ds_id}")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["data"]["message"] == "Dataset deleted"


async def test_delete_nonexistent_dataset_returns_404(client):
    resp = await client.delete("/v1/datasets/99999")
    assert resp.status_code == 404


async def test_demo_dataset_deleted_by_force_can_be_recreated(client):
    resp = await client.post(
        "/v1/datasets",
        json={"name": "Demo - test/recreate", "description": "test"},
    )
    assert resp.status_code == 200
    ds_id = resp.json()["data"]["id"]

    await client.delete(f"/v1/datasets/{ds_id}?force=true")

    resp2 = await client.post(
        "/v1/datasets",
        json={"name": "Demo - test/recreate", "description": "re-created"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["data"]["name"] == "Demo - test/recreate"