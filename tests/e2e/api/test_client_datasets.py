# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""E2E tests for the Client SDK datasets domain via ASGI transport."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from anvil.api.app import app
from anvil.api.deps import get_api_key_store
from anvil.client._shared.not_found_error import NotFoundError
from anvil.client.anvil_client import AnvilClient
from anvil.db.base import Base
from anvil.db.session import async_engine


@pytest.fixture
async def asgi_client() -> AsyncGenerator[AsyncClient, None]:
    """Create an httpx client wired to the FastAPI app via ASGI transport.

    Initializes the database schema before each test and tears it
    down afterward, matching the pattern from ``tests/conftest.py``.
    """
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    api_key = get_api_key_store().key or ""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="https://test",
        headers={"X-API-Key": api_key},
    ) as client:
        yield client
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_create_and_get_dataset(asgi_client: AsyncClient) -> None:
    """Creating a dataset then fetching it by ID returns the correct record."""
    async with AnvilClient(_client=asgi_client) as ac:
        created = await ac.datasets.create(
            name="e2e-client-get-test",
            description="test description",
        )
        assert created["name"] == "e2e-client-get-test"
        assert isinstance(created["id"], int)
        assert created["id"] > 0
        assert created.get("description") == "test description"

        did: int = int(created["id"])  # type: ignore[arg-type]
        fetched = await ac.datasets.get(dataset_id=did)
        assert fetched["id"] == did
        assert fetched["name"] == "e2e-client-get-test"


@pytest.mark.asyncio
async def test_create_and_update_dataset(asgi_client: AsyncClient) -> None:
    """Creating a dataset then updating its name works correctly."""
    async with AnvilClient(_client=asgi_client) as ac:
        created = await ac.datasets.create(
            name="e2e-client-update-test",
            description="original",
        )
        did = int(created["id"])  # type: ignore[arg-type]

        updated = await ac.datasets.update(
            did,
            name="e2e-client-updated",
            description="updated desc",
        )
        assert updated["name"] == "e2e-client-updated"
        assert updated.get("description") == "updated desc"


@pytest.mark.asyncio
async def test_get_non_existent(asgi_client: AsyncClient) -> None:
    """Getting a non-existent dataset raises NotFoundError."""
    async with AnvilClient(_client=asgi_client) as ac:
        with pytest.raises(NotFoundError):
            await ac.datasets.get(dataset_id=99999)
