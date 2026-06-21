"""ContentBlobRepository — data access for content-addressed blob metadata.

Provides upsert, existence checks, reachable-hash enumeration, and
unreferenced blob pruning for the ``ContentBlob`` entity via the async
SQLAlchemy repository pattern.
"""

from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.content_blob import ContentBlob


class ContentBlobRepository:
    """Repository for ``ContentBlob`` metadata operations including
    upsert, reachability queries, and GC pruning.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with a database session.

        Parameters
        ----------
        session : AsyncSession
            SQLAlchemy async session used for all database operations.
        """
        self._session = session

    async def upsert(self, blob: ContentBlob) -> ContentBlob:
        """Insert a blob metadata row or update its size if the hash
        already exists.

        Parameters
        ----------
        blob : ContentBlob
            A ``ContentBlob`` instance whose ``content_hash`` is used
            as the merge key. Must have both ``content_hash`` and
            ``size_bytes`` set.

        Returns
        -------
        ContentBlob
            The merged ``ContentBlob`` instance after flush and refresh.
        """
        await self._session.merge(blob)
        await self._session.flush()
        return blob

    async def exists(self, content_hash: str) -> bool:
        """Check whether a blob hash is already registered.

        Parameters
        ----------
        content_hash : str
            SHA-256 hex digest to check.

        Returns
        -------
        bool
            ``True`` if a blob with the given hash exists in the table.
        """
        result = await self._session.execute(
            select(ContentBlob).where(
                ContentBlob.content_hash == content_hash
            )
        )
        return result.scalar_one_or_none() is not None

    async def get_all_content_hashes(self) -> Sequence[str]:
        """Retrieve all registered blob content hashes.

        Used by the garbage collector to enumerate all blobs known to
        the metadata layer.

        Returns
        -------
        Sequence[str]
            All ``content_hash`` values currently in the table.
        """
        result = await self._session.execute(
            select(ContentBlob.content_hash)
        )
        return result.scalars().all()

    async def delete_unreferenced(
        self, keep_hashes: set[str]
    ) -> int:
        """Delete blob rows whose hash is not in the keep set.

        Parameters
        ----------
        keep_hashes : set of str
            Set of content hashes that should be retained.

        Returns
        -------
        int
            Number of blob rows deleted.
        """
        result = await self._session.execute(
            delete(ContentBlob).where(
                ContentBlob.content_hash.notin_(keep_hashes)  # type: ignore[operator]
            )
        )
        return result.rowcount
