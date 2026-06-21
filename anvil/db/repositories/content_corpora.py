"""ContentCorpusRepository — data access for versioned content corpora.

Provides CRUD operations and domain-specific queries (slug lookup,
current version management, origin counting) for the ``ContentCorpus``
entity via the async SQLAlchemy repository pattern.
"""

from collections.abc import Sequence

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.content_corpus import ContentCorpus


class ContentCorpusRepository:
    """Repository for ``ContentCorpus`` entity CRUD and domain queries."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with a database session.

        Parameters
        ----------
        session : AsyncSession
            SQLAlchemy async session used for all database operations.
        """
        self._session = session

    # ---- CRUD ----

    async def get(self, id: int) -> ContentCorpus | None:
        """Retrieve a content corpus by its primary key.

        Parameters
        ----------
        id : int
            The primary key of the corpus to retrieve.

        Returns
        -------
        ContentCorpus | None
            The matching ``ContentCorpus`` instance, or ``None`` if no
            record exists with the given ``id``.
        """
        return await self._session.get(ContentCorpus, id)

    async def get_by_slug(self, slug: str) -> ContentCorpus | None:
        """Retrieve a content corpus by its unique slug.

        Parameters
        ----------
        slug : str
            The unique machine-readable identifier to look up.

        Returns
        -------
        ContentCorpus | None
            The matching ``ContentCorpus`` instance, or ``None`` if no
            record exists with the given ``slug``.
        """
        result = await self._session.execute(
            select(ContentCorpus).where(ContentCorpus.slug == slug)
        )
        return result.scalar_one_or_none()

    async def get_all(self) -> Sequence[ContentCorpus]:
        """Retrieve all content corpora, ordered by creation date descending.

        Returns
        -------
        Sequence[ContentCorpus]
            All ``ContentCorpus`` records, sorted with the most recently
            created first.
        """
        result = await self._session.execute(
            select(ContentCorpus).order_by(ContentCorpus.created_at.desc())
        )
        return result.scalars().all()

    async def add(self, corpus: ContentCorpus) -> ContentCorpus:
        """Persist a new content corpus and return it with a generated
        primary key.

        Parameters
        ----------
        corpus : ContentCorpus
            The unsaved ``ContentCorpus`` instance to add to the database.

        Returns
        -------
        ContentCorpus
            The same instance after flush and refresh, with its ``id``
            and server-side defaults populated.
        """
        self._session.add(corpus)
        await self._session.flush()
        await self._session.refresh(corpus)
        return corpus

    async def delete(self, id: int) -> bool:
        """Delete a content corpus by its primary key.

        Parameters
        ----------
        id : int
            The primary key of the corpus to delete.

        Returns
        -------
        bool
            ``True`` if a row was deleted, ``False`` if no row matched
            the given ``id``.
        """
        result = await self._session.execute(
            delete(ContentCorpus).where(ContentCorpus.id == id)
        )
        return result.rowcount > 0

    # ---- Domain operations ----

    async def set_current_version(
        self, corpus_id: int, version_id: int
    ) -> None:
        """Set the current (canonical) version for a corpus.

        Parameters
        ----------
        corpus_id : int
            Primary key of the corpus to update.
        version_id : int
            Primary key of the ``ContentVersion`` to set as current.

        Returns
        -------
        None
        """
        await self._session.execute(
            update(ContentCorpus)
            .where(ContentCorpus.id == corpus_id)
            .values(current_version_id=version_id)
        )

    async def count_by_origin(self, origin: str) -> int:
        """Count content corpora with the given origin value.

        Parameters
        ----------
        origin : str
            The origin value to count (e.g., ``"bundled"`` or ``"user"``).

        Returns
        -------
        int
            Number of ``ContentCorpus`` records with this origin.
        """
        stmt = select(func.count()).where(ContentCorpus.origin == origin)
        result = await self._session.execute(stmt)
        return result.scalar_one()
