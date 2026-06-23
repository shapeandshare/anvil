# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""E2E tests for the Client SDK training domain via ASGI transport."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from anvil.api.app import app
from anvil.api.deps import get_api_key_store
from anvil.client.anvil_client import AnvilClient
from anvil.client.training.training_config import TrainingConfig
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
async def test_training_config_validation(asgi_client: AsyncClient) -> None:
    """TrainingConfig with valid n_embd/n_head instantiates correctly."""
    config = TrainingConfig(n_embd=16, n_head=4)
    assert config.n_embd == 16
    assert config.n_head == 4
    assert config.n_layer == 1
    assert config.num_steps == 1000


@pytest.mark.asyncio
async def test_training_config_invalid_n_head(asgi_client: AsyncClient) -> None:
    """TrainingConfig with invalid n_head raises ValueError."""
    with pytest.raises(ValueError, match="n_head=5 must divide n_embd=16"):
        TrainingConfig(n_embd=16, n_head=5)


@pytest.mark.asyncio
async def test_training_config_minimal(asgi_client: AsyncClient) -> None:
    """TrainingConfig can be created with only keyword overrides."""
    config = TrainingConfig(
        n_embd=32,
        n_head=8,
        n_layer=2,
        num_steps=10,
        learning_rate=0.001,
    )
    assert config.n_embd == 32
    assert config.n_head == 8
    assert config.n_layer == 2
    assert config.num_steps == 10
    assert config.learning_rate == 0.001
    assert config.compute_backend == "auto"