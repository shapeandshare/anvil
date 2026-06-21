"""ContentSourceRepository — data access for categorised content origins.

Provides CRUD operations for the ``ContentSource`` entity via the async
SQLAlchemy repository pattern.
"""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.content_source import ContentSource


class ContentSourceRepository:
    """Repository for ``ContentSource`` entity CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with a database session.

        Parameters
        ----------
        session : AsyncSession
            SQLAlchemy async session used for all database operations.
        """
        self._session = session

    async def get(self, id: int) -> ContentSource | None:
        """Retrieve a content source by its primary key.

        Parameters
        ----------
        id : int
            The primary key of the source to retrieve.

        Returns
        -------
        ContentSource | None
            The matching ``ContentSource`` instance, or ``None`` if no
            record exists with the given ``id``.
        """
        return await self._session.get(ContentSource, id)

    async def get_by_slug(self, slug: str) -> ContentSource | None:
        """Retrieve a content source by its unique slug.

        Parameters
        ----------
        slug : str
            The unique machine-readable identifier to look up.

        Returns
        -------
        ContentSource | None
            The matching ``ContentSource`` instance, or ``None`` if no
            record exists with the given ``slug``.
        """
        result = await self._session.execute(
            select(ContentSource).where(ContentSource.slug == slug)
        )
        return result.scalar_one_or_none()

    async def get_all(self) -> Sequence[ContentSource]:
        """Retrieve all content sources, ordered by creation date descending.

        Returns
        -------
        Sequence[ContentSource]
            All ``ContentSource`` records, sorted with the most recently
            created first.
        """
        result = await self._session.execute(
            select(ContentSource).order_by(ContentSource.created_at.desc())
        )
        return result.scalars().all()

    async def add(self, source: ContentSource) -> ContentSource:
        """Persist a new content source and return it with a generated
        primary key.

        Parameters
        ----------
        source : ContentSource
            The unsaved ``ContentSource`` instance to add to the database.

        Returns
        -------
        ContentSource
            The same instance after flush and refresh, with its ``id``
            and server-side defaults populated.
        """
        self._session.add(source)
        await self._session.flush()
        await self._session.refresh(source)
        return source
