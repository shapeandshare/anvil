# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Integration tests for dataset curation API."""

import pytest


@pytest.mark.asyncio
async def test_list_datasets(client):
    resp = await client.get("/v1/datasets")
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    assert "datasets" in data["data"]


@pytest.mark.asyncio
async def test_create_dataset(client):
    resp = await client.post(
        "/v1/datasets",
        json={"name": "test-dataset", "description": "integration test"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["name"] == "test-dataset"
    assert data["data"]["sample_count"] == 0
    assert data["data"]["status"] == "empty"


@pytest.mark.asyncio
async def test_get_dataset(client):
    create = await client.post("/v1/datasets", json={"name": "get-test"})
    d_id = create.json()["data"]["id"]
    resp = await client.get(f"/v1/datasets/{d_id}")
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "get-test"


@pytest.mark.asyncio
async def test_update_dataset(client):
    create = await client.post("/v1/datasets", json={"name": "update-test"})
    d_id = create.json()["data"]["id"]
    resp = await client.put(
        f"/v1/datasets/{d_id}",
        json={"name": "updated-name", "description": "updated desc"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "updated-name"


@pytest.mark.asyncio
async def test_delete_dataset(client):
    create = await client.post("/v1/datasets", json={"name": "delete-test"})
    d_id = create.json()["data"]["id"]
    resp = await client.delete(f"/v1/datasets/{d_id}")
    assert resp.status_code == 200
    get_resp = await client.get(f"/v1/datasets/{d_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_search_datasets(client):
    await client.post("/v1/datasets", json={"name": "aardvark"})
    await client.post("/v1/datasets", json={"name": "zebra"})
    resp = await client.get("/v1/datasets?q=aard")
    assert resp.status_code == 200
    names = [d["name"] for d in resp.json()["data"]["datasets"]]
    assert "aardvark" in names
    assert "zebra" not in names


@pytest.mark.asyncio
async def test_import_txt(client):
    create = await client.post("/v1/datasets", json={"name": "import-txt"})
    d_id = create.json()["data"]["id"]
    resp = await client.post(
        f"/v1/datasets/{d_id}/import",
        json={"format": "txt", "text": "hello\nworld\nthird"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["rows_imported"] == 3


@pytest.mark.asyncio
async def test_import_and_browse_samples(client):
    create = await client.post("/v1/datasets", json={"name": "browse-samples"})
    d_id = create.json()["data"]["id"]
    await client.post(
        f"/v1/datasets/{d_id}/import",
        json={"format": "txt", "text": "a\nb\nc\nd\ne"},
    )
    resp = await client.get(f"/v1/datasets/{d_id}/samples?limit=3")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["samples"]) == 3
    assert data["total"] == 5


@pytest.mark.asyncio
async def test_dedup(client):
    create = await client.post("/v1/datasets", json={"name": "dedup-test"})
    d_id = create.json()["data"]["id"]
    await client.post(
        f"/v1/datasets/{d_id}/import",
        json={"format": "txt", "text": "same\nunique\nsame\nother"},
    )
    resp = await client.post(f"/v1/datasets/{d_id}/curate/dedup")
    assert resp.status_code == 200
    result = resp.json()["data"]
    assert result["samples_removed"] >= 1


@pytest.mark.asyncio
async def test_length_filter(client):
    create = await client.post("/v1/datasets", json={"name": "filter-test"})
    d_id = create.json()["data"]["id"]
    await client.post(
        f"/v1/datasets/{d_id}/import",
        json={
            "format": "txt",
            "text": "short\nlonger text here\na\nvery long text indeed\n",
        },
    )
    resp = await client.post(
        f"/v1/datasets/{d_id}/curate/filter",
        json={"min_length": 3},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["samples_removed"] >= 1


@pytest.mark.asyncio
async def test_metrics(client):
    create = await client.post("/v1/datasets", json={"name": "metrics-test"})
    d_id = create.json()["data"]["id"]
    await client.post(
        f"/v1/datasets/{d_id}/import",
        json={"format": "txt", "text": "hello world\nfoo bar baz\n"},
    )
    resp = await client.get(f"/v1/datasets/{d_id}/metrics")
    assert resp.status_code == 200
    metrics = resp.json()["data"]
    assert metrics["sample_count"] == 2
    assert metrics["estimated_tokens"] >= 0


@pytest.mark.asyncio
async def test_operations_history(client):
    create = await client.post("/v1/datasets", json={"name": "ops-history"})
    d_id = create.json()["data"]["id"]
    await client.post(
        f"/v1/datasets/{d_id}/import",
        json={"format": "txt", "text": "line1\nline2\n"},
    )
    resp = await client.get(f"/v1/datasets/{d_id}/operations")
    assert resp.status_code == 200
    ops = resp.json()["data"]["operations"]
    assert len(ops) >= 1
    assert ops[0]["operation_type"] == "import"


@pytest.mark.asyncio
async def test_export_jsonl(client):
    create = await client.post("/v1/datasets", json={"name": "export-jsonl"})
    d_id = create.json()["data"]["id"]
    await client.post(
        f"/v1/datasets/{d_id}/import",
        json={"format": "txt", "text": "hello\nexport"},
    )
    resp = await client.get(f"/v1/datasets/{d_id}/export?format=jsonl")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/x-ndjson"


@pytest.mark.asyncio
async def test_delete_dataset_blocked(client):
    create = await client.post("/v1/datasets", json={"name": "blocked-del"})
    d_id = create.json()["data"]["id"]
    resp = await client.delete(f"/v1/datasets/{d_id}")
    assert resp.status_code == 200
