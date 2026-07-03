# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""pytest configuration and fixtures."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# Use a local in-memory SQLite URI for MLflow tracking to avoid the 7-retry
# HTTP timeout (up to 100s) that occurs when the default URI
# http://127.0.0.1:5001 points to a non-running server.  The empty-string
# fallback does not work because config.py defaults to the HTTP URI when
# ANVIL_MLFLOW_URI is empty.
os.environ.setdefault("ANVIL_MLFLOW_URI", "sqlite:///:memory:")

from anvil.api.app import app  # import must follow env var for MLFLOW_URI
from anvil.api.deps import get_api_key_store
from anvil.db import models
from anvil.db.base import Base
from anvil.db.models import backup_operation
from anvil.db.session import AsyncSessionLocal, async_engine


@pytest.fixture
async def client():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    transport = ASGITransport(app=app)
    api_key = get_api_key_store().key or ""
    async with AsyncClient(
        transport=transport,
        base_url="https://test",
        headers={"X-API-Key": api_key},
    ) as ac:
        yield ac
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as sess:
        yield sess
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
