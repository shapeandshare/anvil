# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""E2E tests for the Client SDK registry domain via ASGI transport.

NOTE: Registry endpoints require a running MLflow sidecar. When MLflow
is absent, the ``TrackingService`` hangs on connection retries. This
file tests the SDK client property access and configuration only —
actual registry API calls are covered by ``test_registry_api.py``
(raw ASGI client).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from anvil.api.app import app
from anvil.api.deps import get_api_key_store
from anvil.client.anvil_client import AnvilClient
from anvil.client.registry.registry_client import RegistryClient
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
async def test_registry_client_property(asgi_client: AsyncClient) -> None:
    """AnvilClient.registry property returns a RegistryClient."""
    async with AnvilClient(_client=asgi_client) as ac:
        client = ac.registry
        assert isinstance(client, RegistryClient)


@pytest.mark.asyncio
async def test_registry_client_config(asgi_client: AsyncClient) -> None:
    """AnvilClient has correct config after construction with ASGI client."""
    async with AnvilClient(_client=asgi_client) as ac:
        cfg = ac.config
        assert cfg is not None
        assert cfg.base_url == "http://localhost:8080"