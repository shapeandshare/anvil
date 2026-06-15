"""CorpusRepository — data access for directory-based training corpora."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.db.models.corpus import Corpus, CorpusFile


class CorpusRepository:
    """Repository for Corpus and CorpusFile entities."""

    def __init__(self, session: AsyncSession):
        self._session = session

    # ---- Corpus CRUD ----

    async def get(self, id: int) -> Corpus | None:
        return await self._session.get(Corpus, id)

    async def get_all(self) -> Sequence[Corpus]:
        result = await self._session.execute(
            select(Corpus).order_by(Corpus.created_at.desc())
        )
        return result.scalars().all()

    async def add(self, corpus: Corpus) -> Corpus:
        self._session.add(corpus)
        await self._session.flush()
        await self._session.refresh(corpus)
        return corpus

    async def get_by_name(self, name: str) -> Corpus | None:
        result = await self._session.execute(
            select(Corpus).where(Corpus.name == name)
        )
        return result.scalar_one_or_none()

    async def delete(self, id: int) -> bool:
        result = await self._session.execute(
            delete(Corpus).where(Corpus.id == id)
        )
        return result.rowcount > 0

    # ---- CorpusFile CRUD ----

    async def get_files(
        self, corpus_id: int, language: str | None = None
    ) -> Sequence[CorpusFile]:
        query = select(CorpusFile).where(
            CorpusFile.corpus_id == corpus_id
        ).order_by(CorpusFile.relative_path)
        if language:
            query = query.where(CorpusFile.language == language)
        result = await self._session.execute(query)
        return result.scalars().all()

    async def get_file(self, file_id: int) -> CorpusFile | None:
        return await self._session.get(CorpusFile, file_id)

    async def add_file(self, file: CorpusFile) -> CorpusFile:
        self._session.add(file)
        await self._session.flush()
        await self._session.refresh(file)
        return file

    async def delete_files_for_corpus(self, corpus_id: int) -> None:
        await self._session.execute(
            delete(CorpusFile).where(CorpusFile.corpus_id == corpus_id)
        )