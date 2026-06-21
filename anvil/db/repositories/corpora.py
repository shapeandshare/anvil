# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""CorpusRepository — data access for directory-based training corpora."""

from collections.abc import Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.corpus import Corpus
from ..models.corpus_file import CorpusFile


class CorpusRepository:
    """Repository for Corpus and CorpusFile entities."""

    def __init__(self, session: AsyncSession):
        """Initialize the repository with a database session.

        Parameters
        ----------
        session : AsyncSession
            SQLAlchemy async session used for all database operations.
        """
        self._session = session

    # ---- Corpus CRUD ----

    async def get(self, id: int) -> Corpus | None:
        """Retrieve a corpus by its primary key.

        Parameters
        ----------
        id : int
            The primary key of the corpus to retrieve.

        Returns
        -------
        Corpus | None
            The matching ``Corpus`` instance, or ``None`` if no record
            exists with the given ``id``.
        """
        return await self._session.get(Corpus, id)

    async def get_all(self) -> Sequence[Corpus]:
        """Retrieve all corpora, ordered by creation date descending.

        Returns
        -------
        Sequence[Corpus]
            All ``Corpus`` records in the database, sorted with the
            most recently created first.
        """
        result = await self._session.execute(
            select(Corpus).order_by(Corpus.created_at.desc())
        )
        return result.scalars().all()

    async def add(self, corpus: Corpus) -> Corpus:
        """Persist a new corpus and return it with a generated primary key.

        Parameters
        ----------
        corpus : Corpus
            The unsaved ``Corpus`` instance to add to the database.

        Returns
        -------
        Corpus
            The same instance after flush and refresh, with its ``id``
            and server-side defaults populated.
        """
        self._session.add(corpus)
        await self._session.flush()
        await self._session.refresh(corpus)
        return corpus

    async def get_by_name(self, name: str) -> Corpus | None:
        """Retrieve a corpus by its unique name.

        Parameters
        ----------
        name : str
            The exact name of the corpus to look up.

        Returns
        -------
        Corpus | None
            The matching ``Corpus`` instance, or ``None`` if no record
            exists with the given ``name``.
        """
        result = await self._session.execute(select(Corpus).where(Corpus.name == name))
        return result.scalar_one_or_none()

    async def count_by_origin(self, origin: str) -> int:
        """Count corpora with the given origin value.

        Parameters
        ----------
        origin : str
            The origin value to count (e.g., ``"bundled"`` or ``"user"``).

        Returns
        -------
        int
            Number of corpora with this origin.
        """
        stmt = select(func.count()).where(Corpus.origin == origin)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def delete(self, id: int) -> bool:
        """Delete a corpus by its primary key.

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
        result = await self._session.execute(delete(Corpus).where(Corpus.id == id))
        return result.rowcount > 0

    # ---- CorpusFile CRUD ----

    async def get_files(
        self, corpus_id: int, language: str | None = None
    ) -> Sequence[CorpusFile]:
        """Retrieve files belonging to a corpus, optionally filtered by
        language.

        Parameters
        ----------
        corpus_id : int
            Primary key of the parent corpus.
        language : str, optional
            If provided, only return files whose ``language`` matches
            this value. Defaults to ``None`` (no filter).

        Returns
        -------
        Sequence[CorpusFile]
            Matching ``CorpusFile`` records sorted by
            ``relative_path``.
        """
        query = (
            select(CorpusFile)
            .where(CorpusFile.corpus_id == corpus_id)
            .order_by(CorpusFile.relative_path)
        )
        if language:
            query = query.where(CorpusFile.language == language)
        result = await self._session.execute(query)
        return result.scalars().all()

    async def get_file(self, file_id: int) -> CorpusFile | None:
        """Retrieve a single corpus file by its primary key.

        Parameters
        ----------
        file_id : int
            Primary key of the ``CorpusFile`` to retrieve.

        Returns
        -------
        CorpusFile | None
            The matching ``CorpusFile`` instance, or ``None`` if no
            record exists with the given ``file_id``.
        """
        return await self._session.get(CorpusFile, file_id)

    async def add_file(self, file: CorpusFile) -> CorpusFile:
        """Persist a new corpus file and return it with a generated
        primary key.

        Parameters
        ----------
        file : CorpusFile
            The unsaved ``CorpusFile`` instance to add to the database.

        Returns
        -------
        CorpusFile
            The same instance after flush and refresh, with its ``id``
            and server-side defaults populated.
        """
        self._session.add(file)
        await self._session.flush()
        await self._session.refresh(file)
        return file

    async def delete_files_for_corpus(self, corpus_id: int) -> None:
        """Delete all ``CorpusFile`` records belonging to a corpus.

        Parameters
        ----------
        corpus_id : int
            Primary key of the parent corpus whose files should be
            deleted.

        Returns
        -------
        None
        """
        await self._session.execute(
            delete(CorpusFile).where(CorpusFile.corpus_id == corpus_id)
        )
