# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""E2E tests for the Client SDK registry domain via ASGI transport."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from anvil.api.app import app
from anvil.api.deps import get_api_key_store
from anvil.client._shared.errors.not_found_error import NotFoundError
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
async def test_registry_list(asgi_client: AsyncClient) -> None:
    """Listing registered models returns a list (possibly empty)."""
    async with AnvilClient(_client=asgi_client) as ac:
        models = await ac.registry.list()
        assert isinstance(models, list)
        for model in models:
            assert isinstance(model, dict)


@pytest.mark.asyncio
async def test_get_non_existent_model(asgi_client: AsyncClient) -> None:
    """Getting a non-existent registered model raises NotFoundError."""
    async with AnvilClient(_client=asgi_client) as ac:
        with pytest.raises(NotFoundError):
            await ac.registry.get(model_id="99999")


@pytest.mark.asyncio
async def test_registry_list_with_search(asgi_client: AsyncClient) -> None:
    """Listing registered models with a search term returns a list."""
    async with AnvilClient(_client=asgi_client) as ac:
        models = await ac.registry.list(search="nonexistent")
        assert isinstance(models, list)