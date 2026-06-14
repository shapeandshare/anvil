"""Tests for CorpusRepository."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.db.models.corpus import Corpus, CorpusFile
from anvil.db.repositories.corpora import CorpusRepository
from anvil.db.base import Base
from anvil.db.session import async_engine, AsyncSessionLocal


@pytest.fixture
async def db_session():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        yield session


@pytest.mark.asyncio
async def test_add_and_get_corpus(db_session):
    repo = CorpusRepository(db_session)
    c = Corpus(name="repo-test", root_path="/tmp",
               chunking_strategy="line", chunk_overlap=0.0,
               file_count=0, document_count=0)
    saved = await repo.add(c)
    assert saved.id is not None
    assert saved.name == "repo-test"

    fetched = await repo.get(saved.id)
    assert fetched is not None
    assert fetched.name == "repo-test"


@pytest.mark.asyncio
async def test_get_all_corpora(db_session):
    repo = CorpusRepository(db_session)
    c1 = Corpus(name="c1", root_path="/a",
                chunking_strategy="line", chunk_overlap=0.0,
                file_count=0, document_count=0)
    c2 = Corpus(name="c2", root_path="/b",
                chunking_strategy="line", chunk_overlap=0.0,
                file_count=0, document_count=0)
    await repo.add(c1)
    await repo.add(c2)
    all_c = await repo.get_all()
    names = [c.name for c in all_c]
    assert "c1" in names
    assert "c2" in names


@pytest.mark.asyncio
async def test_delete_corpus(db_session):
    repo = CorpusRepository(db_session)
    c = Corpus(name="delete-me", root_path="/tmp",
               chunking_strategy="line", chunk_overlap=0.0,
               file_count=0, document_count=0)
    saved = await repo.add(c)
    cid = saved.id
    deleted = await repo.delete(cid)
    assert deleted is True
    assert await repo.get(cid) is None


@pytest.mark.asyncio
async def test_add_and_get_files(db_session):
    repo = CorpusRepository(db_session)
    c = Corpus(name="files-test", root_path="/tmp",
               chunking_strategy="line", chunk_overlap=0.0,
               file_count=0, document_count=0)
    saved = await repo.add(c)
    f = CorpusFile(corpus_id=saved.id, relative_path="a.py", language="Python")
    saved_f = await repo.add_file(f)
    assert saved_f.id is not None
    files = await repo.get_files(saved.id)
    assert len(files) == 1
    assert files[0].relative_path == "a.py"


@pytest.mark.asyncio
async def test_delete_files_for_corpus(db_session):
    repo = CorpusRepository(db_session)
    c = Corpus(name="del-files", root_path="/tmp",
               chunking_strategy="line", chunk_overlap=0.0,
               file_count=0, document_count=0)
    saved = await repo.add(c)
    await repo.add_file(CorpusFile(corpus_id=saved.id, relative_path="a.py"))
    await repo.add_file(CorpusFile(corpus_id=saved.id, relative_path="b.py"))
    await repo.delete_files_for_corpus(saved.id)
    remaining = await repo.get_files(saved.id)
    assert len(remaining) == 0