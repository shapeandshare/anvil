# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for CorpusService."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.db.base import Base
from anvil.db.models.corpus import Corpus
from anvil.db.repositories.corpora import CorpusRepository
from anvil.db.session import AsyncSessionLocal, async_engine
from anvil.services.datasets.corpora import CorpusService
from anvil.services.datasets.corpus_loader import CorpusLoader


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
    c = await svc.create(name="test-svc", root_path="/test/corpus", description="test")
    assert c.id is not None
    assert c.name == "test-svc"
    assert c.description == "test"
    assert c.chunking_strategy == "windowed"


@pytest.mark.asyncio
async def test_create_validates_strategy(svc):
    with pytest.raises(ValueError, match="(?i)chunkingstrategy"):
        await svc.create(
            name="bad", root_path="/test/corpus", chunking_strategy="invalid"
        )


@pytest.mark.asyncio
async def test_create_validates_overlap(svc):
    with pytest.raises(ValueError, match="chunk_overlap"):
        await svc.create(name="bad2", root_path="/test/corpus", chunk_overlap=1.5)


@pytest.mark.asyncio
async def test_list_corpora(svc):
    await svc.create(name="a", root_path="/a")
    await svc.create(name="b", root_path="/b")
    corpora = await svc.list_all()
    assert len(corpora) >= 2


@pytest.mark.asyncio
async def test_get_corpus(svc):
    created = await svc.create(name="get-test", root_path="/test/corpus")
    fetched = await svc.get(created.id)
    assert fetched is not None
    assert fetched.name == "get-test"


@pytest.mark.asyncio
async def test_delete_corpus(svc):
    created = await svc.create(name="del-test", root_path="/test/corpus")
    assert await svc.delete(created.id) is True
    assert await svc.get(created.id) is None


@pytest.mark.asyncio
async def test_ingest_updates_counts(svc, tmp_path):
    (tmp_path / "main.py").write_text("print('hello')\n")
    (tmp_path / "utils.py").write_text("import os\n")
    corpus = await svc.create(name="ingest-test", root_path=str(tmp_path))
    ingested, _ = await svc.ingest(corpus.id)
    assert ingested.file_count == 2
    assert ingested.document_count > 0


@pytest.mark.asyncio
async def test_load_docs(svc, tmp_path):
    (tmp_path / "test.py").write_text("x=1\ny=2\n")
    corpus = await svc.create(
        name="load-test",
        root_path=str(tmp_path),
        chunking_strategy="line",
    )
    await svc.ingest(corpus.id)
    docs = await svc.load_docs(corpus.id)
    assert len(docs) == 2
    assert "x=1" in docs
    assert "y=2" in docs
