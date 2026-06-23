# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""E2E tests for the Client SDK health endpoints via ASGI transport."""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport

from anvil.api.app import app
from anvil.api.deps import get_api_key_store
from anvil.client.anvil_client import AnvilClient


@pytest.fixture
def asgi_client() -> httpx.AsyncClient:
    """Create an httpx client wired to the FastAPI app via ASGI transport."""
    api_key = get_api_key_store().key or ""
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(
        transport=transport,
        base_url="https://test",
        headers={"X-API-Key": api_key},
    )


@pytest.mark.asyncio
async def test_health_get_succeeds(asgi_client: httpx.AsyncClient) -> None:
    """AnvilClient.health.get() returns success when server is reachable."""
    async with AnvilClient(_client=asgi_client) as ac:
        result = await ac.health.get()
        assert result is not None


@pytest.mark.asyncio
async def test_health_get_unauthenticated(asgi_client: httpx.AsyncClient) -> None:
    """Health check succeeds without authentication (FR-010)."""
    transport = ASGITransport(app=app)
    unauth_client = httpx.AsyncClient(transport=transport, base_url="https://test")
    async with AnvilClient(_client=unauth_client) as ac:
        result = await ac.health.get()
        assert result is not None


@pytest.mark.asyncio
async def test_health_detailed_succeeds(asgi_client: httpx.AsyncClient) -> None:
    """HealthDetailedCommand returns success."""
    async with AnvilClient(_client=asgi_client) as ac:
        result = await ac.health.detailed()
        assert result is not None
