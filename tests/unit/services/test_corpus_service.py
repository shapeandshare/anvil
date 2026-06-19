"""Tests for CorpusService."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.db.models.corpus import Corpus
from anvil.db.repositories.corpora import CorpusRepository
from anvil.services.datasets.corpora import CorpusService
from anvil.services.datasets.corpus_loader import CorpusLoader
from anvil.db.base import Base
from anvil.db.session import async_engine, AsyncSessionLocal


@pytest.fixture
async def db_session():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        yield session


@pytest.fixture
async def svc(db_session):
    repo = CorpusRepository(db_session)
    loader = CorpusLoader(block_size=16)
    return CorpusService(repo, loader)


@pytest.mark.asyncio
async def test_create_corpus(svc):
    c = await svc.create(
        name="test-svc", root_path="/tmp", description="test"
    )
    assert c.id is not None
    assert c.name == "test-svc"
    assert c.description == "test"
    assert c.chunking_strategy == "windowed"


@pytest.mark.asyncio
async def test_create_validates_strategy(svc):
    with pytest.raises(ValueError, match="chunking_strategy"):
        await svc.create(
            name="bad", root_path="/tmp", chunking_strategy="invalid"
        )


@pytest.mark.asyncio
async def test_create_validates_overlap(svc):
    with pytest.raises(ValueError, match="chunk_overlap"):
        await svc.create(
            name="bad2", root_path="/tmp", chunk_overlap=1.5
        )


@pytest.mark.asyncio
async def test_list_corpora(svc):
    await svc.create(name="a", root_path="/a")
    await svc.create(name="b", root_path="/b")
    corpora = await svc.list()
    assert len(corpora) >= 2


@pytest.mark.asyncio
async def test_get_corpus(svc):
    created = await svc.create(name="get-test", root_path="/tmp")
    fetched = await svc.get(created.id)
    assert fetched is not None
    assert fetched.name == "get-test"


@pytest.mark.asyncio
async def test_delete_corpus(svc):
    created = await svc.create(name="del-test", root_path="/tmp")
    assert await svc.delete(created.id) is True
    assert await svc.get(created.id) is None


@pytest.mark.asyncio
async def test_ingest_updates_counts(svc):
    import tempfile
    td = tempfile.mkdtemp()
    try:
        from pathlib import Path
        (Path(td) / "main.py").write_text("print('hello')\n")
        (Path(td) / "utils.py").write_text("import os\n")
        corpus = await svc.create(name="ingest-test", root_path=td)
        ingested, _ = await svc.ingest(corpus.id)
        assert ingested.file_count == 2
        assert ingested.document_count > 0
    finally:
        import shutil
        shutil.rmtree(td)


@pytest.mark.asyncio
async def test_load_docs(svc):
    import tempfile
    td = tempfile.mkdtemp()
    try:
        from pathlib import Path
        (Path(td) / "test.py").write_text("x=1\ny=2\n")
        corpus = await svc.create(
            name="load-test",
            root_path=td,
            chunking_strategy="line",
        )
        await svc.ingest(corpus.id)
        docs = await svc.load_docs(corpus.id)
        assert len(docs) == 2
        assert "x=1" in docs
        assert "y=2" in docs
    finally:
        import shutil
        shutil.rmtree(td)