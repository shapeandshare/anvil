# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for CorpusService — CRUD and scanning operations.

Tests the CorpusService methods: list, get, get_by_name, create,
delete, get_files, fork, load_docs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from anvil.db.repositories.corpora import CorpusRepository
from anvil.services.datasets.chunking_strategy import ChunkingStrategy
from anvil.services.datasets.corpora import CorpusService


@pytest.fixture
async def corpus_svc(in_memory_session):
    """Build a CorpusService backed by an in-memory DB."""
    repo = CorpusRepository(in_memory_session)
    return CorpusService(repo)


class TestCorpusService:
    """CRUD and scanning tests for CorpusService."""

    async def test_list_empty(self, corpus_svc):
        """List should return empty sequence when no corpora exist."""
        result = await corpus_svc.list_all()
        assert len(result) == 0

    async def test_create_and_get(self, corpus_svc, tmp_path):
        """Create should persist a corpus; get should retrieve it."""
        saved = await corpus_svc.create(
            name="test-corpus",
            root_path=str(tmp_path),
            description="test",
        )
        assert saved.id is not None
        assert saved.name == "test-corpus"

        fetched = await corpus_svc.get(saved.id)
        assert fetched is not None
        assert fetched.name == "test-corpus"

    async def test_get_nonexistent(self, corpus_svc):
        """Get should return None for a non-existent id."""
        result = await corpus_svc.get(9999)
        assert result is None

    async def test_list_after_create(self, corpus_svc, tmp_path):
        """List should include created corpora."""
        await corpus_svc.create(name="c1", root_path=str(tmp_path))
        await corpus_svc.create(name="c2", root_path=str(tmp_path))
        result = await corpus_svc.list_all()

    async def test_delete(self, corpus_svc, tmp_path):
        """Delete should remove a corpus by id."""
        saved = await corpus_svc.create(name="delete-me", root_path=str(tmp_path))
        await corpus_svc.delete(saved.id)
        result = await corpus_svc.get(saved.id)
        assert result is None

    async def test_delete_nonexistent(self, corpus_svc):
        """Delete should not raise for a non-existent corpus."""
        await corpus_svc.delete(9999)

    async def test_get_files_empty(self, corpus_svc, tmp_path):
        """get_files should return empty list for a corpus with no
        files.
        """
        saved = await corpus_svc.create(name="files", root_path=str(tmp_path))
        files = await corpus_svc.get_files(saved.id)
        assert files == []


class TestCorpusServiceCreate:
    async def test_create_with_string_strategy(self, corpus_svc, tmp_path):
        saved = await corpus_svc.create(
            name="str-strat",
            root_path=str(tmp_path),
            chunking_strategy="line",
        )
        assert saved.chunking_strategy == "line"

    async def test_create_invalid_strategy_type(self, corpus_svc, tmp_path):
        import pytest
        with pytest.raises(TypeError):
            await corpus_svc.create(name="bad", root_path=str(tmp_path), chunking_strategy=123)

    async def test_create_invalid_overlap(self, corpus_svc, tmp_path):
        import pytest
        with pytest.raises(ValueError):
            await corpus_svc.create(name="bad", root_path=str(tmp_path), chunk_overlap=1.5)

    async def test_create_with_patterns(self, corpus_svc, tmp_path):
        saved = await corpus_svc.create(
            name="patterned",
            root_path=str(tmp_path),
            include_patterns=["*.py"],
            exclude_patterns=["*.md"],
        )
        assert saved.include_patterns is not None
        assert saved.exclude_patterns is not None


class TestCorpusServiceFork:
    async def test_fork_from_existing(self, corpus_svc, tmp_path):
        source = await corpus_svc.create(name="src", root_path=str(tmp_path))
        fork = await corpus_svc.fork(source.id, name="forked")
        assert fork.name == "forked"
        assert fork.parent_id == source.id
        assert fork.root_path == source.root_path

    async def test_fork_missing_source(self, corpus_svc):
        import pytest
        with pytest.raises(ValueError, match="not found"):
            await corpus_svc.fork(9999, name="ghost")

    async def test_fork_with_overrides(self, corpus_svc, tmp_path):
        source = await corpus_svc.create(
            name="src", root_path=str(tmp_path), chunking_strategy="line", block_size=32
        )
        fork = await corpus_svc.fork(
            source.id, name="overridden", chunking_strategy="file", block_size=64
        )
        assert fork.chunking_strategy == "file"
        assert fork.block_size == 64


class TestCorpusServiceList:
    async def test_list_alias(self, corpus_svc):
        result = await corpus_svc.list_all()
        assert result == []

    async def test_list_multiple(self, corpus_svc, tmp_path):
        await corpus_svc.create(name="a", root_path=str(tmp_path))
        await corpus_svc.create(name="b", root_path=str(tmp_path))
        all_c = await corpus_svc.list_all()
        assert len(all_c) == 2


class TestCorpusServiceGetFile:
    async def test_get_file_nonexistent(self, corpus_svc):
        result = await corpus_svc.get_file(9999)
        assert result is None

    async def test_get_files_by_language(self, corpus_svc):
        result = await corpus_svc.get_files(9999, language="python")
        assert result == []


class TestCorpusServiceIngest:
    async def test_ingest_missing_corpus(self, corpus_svc):
        import pytest
        with pytest.raises(ValueError, match="not found"):
            await corpus_svc.ingest(9999)

    async def test_load_docs_missing(self, corpus_svc):
        import pytest
        with pytest.raises(ValueError, match="not found"):
            await corpus_svc.load_docs(9999)

    async def test_scan_and_chunk_missing(self, corpus_svc):
        import pytest
        with pytest.raises(ValueError, match="not found"):
            await corpus_svc.scan_and_chunk(9999)
