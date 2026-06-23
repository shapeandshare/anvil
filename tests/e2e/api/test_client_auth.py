# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""E2E tests for the Client SDK auth via ASGI transport."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from anvil.api.app import app
from anvil.api.deps import get_api_key_store
from anvil.client._shared.errors.authentication_error import (
    AuthenticationError,
)
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
async def test_api_key_auth(asgi_client: AsyncClient) -> None:
    """Client configured with a valid API key can make authenticated requests."""
    async with AnvilClient(_client=asgi_client) as ac:
        result = await ac.datasets.list()
        assert result is not None


@pytest.mark.asyncio
async def test_unauthenticated_client_raises_error() -> None:
    """Client without API key gets AuthenticationError on protected routes."""
    transport = ASGITransport(app=app)
    unauth_client = AsyncClient(transport=transport, base_url="https://test")
    async with AnvilClient(_client=unauth_client) as ac:
        with pytest.raises(AuthenticationError):
            await ac.datasets.list()


@pytest.mark.asyncio
async def test_unauthenticated_health_still_works() -> None:
    """Health endpoint remains accessible without auth."""
    transport = ASGITransport(app=app)
    unauth_client = AsyncClient(transport=transport, base_url="https://test")
    async with AnvilClient(_client=unauth_client) as ac:
        result = await ac.health.get()
        assert result is not None