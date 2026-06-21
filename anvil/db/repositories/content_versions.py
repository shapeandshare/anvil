"""ContentVersionRepository — data access for immutable version snapshots.

Provides CRUD operations and domain-specific queries (digest lookup,
entry management, MLflow run ref linkage) for the ``ContentVersion``,
``ContentEntry``, and ``VersionRunRef`` entities via the async
SQLAlchemy repository pattern.
"""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.content_entry import ContentEntry
from ..models.content_version import ContentVersion
from ..models.content_version_run_ref import VersionRunRef


class ContentVersionRepository:
    """Repository for ``ContentVersion``, ``ContentEntry``, and
    ``VersionRunRef`` operations.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with a database session.

        Parameters
        ----------
        session : AsyncSession
            SQLAlchemy async session used for all database operations.
        """
        self._session = session

    # ---- Version CRUD ----

    async def get(self, id: int) -> ContentVersion | None:
        """Retrieve a content version by its primary key.

        Parameters
        ----------
        id : int
            The primary key of the version to retrieve.

        Returns
        -------
        ContentVersion | None
            The matching ``ContentVersion`` instance, or ``None`` if no
            record exists with the given ``id``.
        """
        return await self._session.get(ContentVersion, id)

    async def add(self, version: ContentVersion) -> ContentVersion:
        """Persist a new content version and return it with a generated
        primary key.

        Parameters
        ----------
        version : ContentVersion
            The unsaved ``ContentVersion`` instance to add to the database.

        Returns
        -------
        ContentVersion
            The same instance after flush and refresh, with its ``id``
            and server-side defaults populated.
        """
        self._session.add(version)
        await self._session.flush()
        await self._session.refresh(version)
        return version

    async def get_by_digest(
        self, corpus_id: int, digest: str
    ) -> ContentVersion | None:
        """Retrieve a version by its corpus and manifest digest.

        Parameters
        ----------
        corpus_id : int
            Primary key of the parent corpus.
        digest : str
            SHA-256 hex digest of the version manifest.

        Returns
        -------
        ContentVersion | None
            The matching ``ContentVersion`` instance, or ``None`` if no
            record exists with the given ``corpus_id`` and ``digest``.
        """
        result = await self._session.execute(
            select(ContentVersion).where(
                ContentVersion.corpus_id == corpus_id,
                ContentVersion.manifest_digest == digest,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_corpus(
        self, corpus_id: int
    ) -> Sequence[ContentVersion]:
        """List all versions belonging to a corpus, ordered by version
        number descending.

        Parameters
        ----------
        corpus_id : int
            Primary key of the parent corpus.

        Returns
        -------
        Sequence[ContentVersion]
            All ``ContentVersion`` records for the corpus, sorted with
            the most recent version number first.
        """
        result = await self._session.execute(
            select(ContentVersion)
            .where(ContentVersion.corpus_id == corpus_id)
            .order_by(ContentVersion.version_number.desc())
        )
        return result.scalars().all()

    # ---- Entry operations ----

    async def add_entry(self, entry: ContentEntry) -> ContentEntry:
        """Persist a new content entry and return it with a generated
        primary key.

        Parameters
        ----------
        entry : ContentEntry
            The unsaved ``ContentEntry`` instance to add to the database.

        Returns
        -------
        ContentEntry
            The same instance after flush and refresh, with its ``id``
            and server-side defaults populated.
        """
        self._session.add(entry)
        await self._session.flush()
        await self._session.refresh(entry)
        return entry

    async def get_entries(
        self, version_id: int
    ) -> Sequence[ContentEntry]:
        """Retrieve all entries belonging to a version, ordered by path.

        Parameters
        ----------
        version_id : int
            Primary key of the parent version.

        Returns
        -------
        Sequence[ContentEntry]
            All ``ContentEntry`` records for the version, sorted by
            ``path``.
        """
        result = await self._session.execute(
            select(ContentEntry)
            .where(ContentEntry.version_id == version_id)
            .order_by(ContentEntry.path)
        )
        return result.scalars().all()

    # ---- Run-ref operations ----

    async def add_run_ref(self, ref: VersionRunRef) -> VersionRunRef:
        """Persist a new version-run reference and return it with a
        generated primary key.

        Parameters
        ----------
        ref : VersionRunRef
            The unsaved ``VersionRunRef`` instance to add.

        Returns
        -------
        VersionRunRef
            The same instance after flush and refresh, with its ``id``
            and server-side defaults populated.
        """
        self._session.add(ref)
        await self._session.flush()
        await self._session.refresh(ref)
        return ref

    async def get_run_refs(
        self, version_id: int
    ) -> Sequence[VersionRunRef]:
        """Retrieve all run references for a version.

        Parameters
        ----------
        version_id : int
            Primary key of the version whose run refs to retrieve.

        Returns
        -------
        Sequence[VersionRunRef]
            All ``VersionRunRef`` records linked to the given version.
        """
        result = await self._session.execute(
            select(VersionRunRef).where(
                VersionRunRef.version_id == version_id
            )
        )
        return result.scalars().all()
