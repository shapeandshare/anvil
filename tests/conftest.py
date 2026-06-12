"""pytest configuration and fixtures."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from microgpt.api.app import app
from microgpt.db import models
from microgpt.db.base import Base
from microgpt.db.session import AsyncSessionLocal, async_engine


@pytest.fixture
async def client():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def session() -> AsyncSession:
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as sess:
        yield sess
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
