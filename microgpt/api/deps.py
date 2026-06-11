"""FastAPI dependencies."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from microgpt.db.session import get_db


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    async for session in get_db():
        yield session
