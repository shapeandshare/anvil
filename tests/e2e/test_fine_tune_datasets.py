# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""e2e tests for fine-tune dataset preparation and chat template endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_chat_template_and_list(client: AsyncClient):
    """POST and GET chat templates works."""
    r = await client.post(
        "/v1/chat-templates",
        json={
            "name": "e2e-test-tpl",
            "template_string": "{{ instruction }}\n{{ response }}",
            "tokenizer_family": "char",
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "e2e-test-tpl"

    # List
    r = await client.get("/v1/chat-templates")
    assert r.status_code == 200
    items = r.json()["items"]
    names = [t["name"] for t in items]
    assert "e2e-test-tpl" in names


@pytest.mark.asyncio
async def test_create_fine_tune_dataset_happy_path(client: AsyncClient):
    """Creating a fine-tune dataset returns 202 with job_id."""
    # First create a source dataset
    r = await client.post(
        "/v1/datasets",
        json={"name": "e2e-ftd-source", "description": "test"},
    )
    assert r.status_code == 200, f"Dataset creation failed: {r.text}"
    dataset_id = r.json()["data"]["id"]

    # Create a chat template
    r = await client.post(
        "/v1/chat-templates",
        json={
            "name": "e2e-ftd-tpl",
            "template_string": "{{ instruction }}\n{{ response }}",
            "tokenizer_family": "char",
        },
    )
    assert r.status_code == 201
    tpl_id = r.json()["id"]

    # Create fine-tune dataset
    r = await client.post(
        "/v1/fine-tune-datasets",
        json={
            "dataset_id": dataset_id,
            "chat_template_id": tpl_id,
            "record_type": "sft",
        },
    )
    assert r.status_code == 202
    data = r.json()
    assert data["status"] == "preparing"
    assert "job_id" in data

    # Poll status
    job_id = data["job_id"]
    r = await client.get(f"/v1/fine-tune-datasets/jobs/{job_id}/status")
    assert r.status_code == 200
    status_data = r.json()
    assert status_data["job_id"] == job_id


@pytest.mark.asyncio
async def test_concurrent_preparation_returns_409(client: AsyncClient):
    """Concurrent preparation of the same dataset returns 409."""
    r = await client.post(
        "/v1/datasets",
        json={"name": "e2e-concurrent", "description": "test"},
    )
    assert r.status_code == 200
    dataset_id = r.json()["data"]["id"]

    r = await client.post(
        "/v1/chat-templates",
        json={
            "name": "e2e-concurrent-tpl",
            "template_string": "{{ x }}",
            "tokenizer_family": "char",
        },
    )
    assert r.status_code == 201
    tpl_id = r.json()["id"]

    # First submission
    r = await client.post(
        "/v1/fine-tune-datasets",
        json={"dataset_id": dataset_id, "chat_template_id": tpl_id},
    )
    assert r.status_code == 202

    # Second submission — should be 409
    r = await client.post(
        "/v1/fine-tune-datasets",
        json={"dataset_id": dataset_id, "chat_template_id": tpl_id},
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_fine_tune_dataset_not_found(client: AsyncClient):
    """Getting a non-existent fine-tune dataset returns 404."""
    r = await client.get("/v1/fine-tune-datasets/999999")
    assert r.status_code == 404

    r = await client.get("/v1/fine-tune-datasets/jobs/999999/status")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_chat_template_duplicate_name(client: AsyncClient):
    """Creating a template with a duplicate name returns 409."""
    r = await client.post(
        "/v1/chat-templates",
        json={
            "name": "duplicate-name-test",
            "template_string": "{{ x }}",
            "tokenizer_family": "char",
        },
    )
    assert r.status_code == 201

    r = await client.post(
        "/v1/chat-templates",
        json={
            "name": "duplicate-name-test",
            "template_string": "{{ y }}",
            "tokenizer_family": "char",
        },
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_empty_fine_tune_dataset_list(client: AsyncClient):
    """GET /fine-tune-datasets returns empty list initially."""
    r = await client.get("/v1/fine-tune-datasets")
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_preparation_completes_with_summary(client: AsyncClient):
    """Awaiting the background job yields a ready status with a summary (SC-005)."""
    import asyncio

    from anvil.api.v1 import fine_tune_datasets as ftd_routes

    r = await client.post(
        "/v1/datasets",
        json={"name": "e2e-await-source", "description": "test"},
    )
    assert r.status_code == 200
    dataset_id = r.json()["data"]["id"]

    r = await client.post(
        "/v1/chat-templates",
        json={
            "name": "e2e-await-tpl",
            "template_string": "{{ instruction }}\n{{ response }}",
            "tokenizer_family": "char",
        },
    )
    assert r.status_code == 201
    tpl_id = r.json()["id"]

    r = await client.post(
        "/v1/fine-tune-datasets",
        json={"dataset_id": dataset_id, "chat_template_id": tpl_id},
    )
    assert r.status_code == 202
    job_id = r.json()["job_id"]

    task = ftd_routes._tasks.get(job_id)
    if task is not None:
        await task

    r = await client.get(f"/v1/fine-tune-datasets/jobs/{job_id}/status")
    assert r.status_code == 200
    status_data = r.json()
    assert status_data["status"] == "ready"
    assert status_data["summary"] is not None
    assert status_data["summary"]["total"] == 0
