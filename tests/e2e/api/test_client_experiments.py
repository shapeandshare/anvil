# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""E2E tests for the Client SDK experiments domain via ASGI transport.

NOTE: Experiment tracking endpoints require a running MLflow sidecar.
When MLflow is absent, the ``TrackingService`` hangs on connection
retries. This file tests the SDK client property access and
configuration only — actual experiment API calls are covered by
``test_experiments.py`` (raw ASGI client), which uses degraded-mode
handling.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from anvil.api.app import app
from anvil.api.deps import get_api_key_store
from anvil.client.anvil_client import AnvilClient
from anvil.client.experiments.experiments_client import ExperimentsClient
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
async def test_experiments_client_property(asgi_client: AsyncClient) -> None:
    """AnvilClient.experiments property returns an ExperimentsClient."""
    async with AnvilClient(_client=asgi_client) as ac:
        client = ac.experiments
        assert isinstance(client, ExperimentsClient)


@pytest.mark.asyncio
async def test_experiments_client_config(asgi_client: AsyncClient) -> None:
    """AnvilClient has correct config after construction with ASGI client."""
    async with AnvilClient(_client=asgi_client) as ac:
        cfg = ac.config
        assert cfg is not None
        assert cfg.timeout == 30.0
        assert cfg.retry_count == 3