"""Unit tests for CorpusService — CRUD and scanning operations.

Tests the CorpusService methods: list, get, get_by_name, create,
delete, get_files, fork, load_docs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from anvil.db.repositories.corpora import CorpusRepository
from anvil.services.datasets.corpora import CorpusService
from anvil.services.datasets.chunking_strategy import ChunkingStrategy


@pytest.fixture
async def corpus_svc(in_memory_session):
    """Build a CorpusService backed by an in-memory DB."""
    repo = CorpusRepository(in_memory_session)
    return CorpusService(repo)


class TestCorpusService:
    """CRUD and scanning tests for CorpusService."""

    async def test_list_empty(self, corpus_svc):
        """list should return empty sequence when no corpora exist."""
        result = await corpus_svc.list()
        assert len(result) == 0

    async def test_create_and_get(self, corpus_svc):
        """create should persist a corpus; get should retrieve it."""
        saved = await corpus_svc.create(
            name="test-corpus",
            root_path="/tmp",
            description="test",
        )
        assert saved.id is not None
        assert saved.name == "test-corpus"

        fetched = await corpus_svc.get(saved.id)
        assert fetched is not None
        assert fetched.name == "test-corpus"

    async def test_get_nonexistent(self, corpus_svc):
        """get should return None for a non-existent id."""
        result = await corpus_svc.get(9999)
        assert result is None

    async def test_list_after_create(self, corpus_svc):
        """list should include created corpora."""
        await corpus_svc.create(name="c1", root_path="/tmp")
        await corpus_svc.create(name="c2", root_path="/tmp")
        result = await corpus_svc.list()
        assert len(result) == 2

    async def test_delete(self, corpus_svc):
        """delete should remove a corpus by id."""
        saved = await corpus_svc.create(
            name="delete-me", root_path="/tmp"
        )
        await corpus_svc.delete(saved.id)
        result = await corpus_svc.get(saved.id)
        assert result is None

    async def test_delete_nonexistent(self, corpus_svc):
        """delete should not raise for a non-existent corpus."""
        await corpus_svc.delete(9999)

    async def test_get_files_empty(self, corpus_svc):
        """get_files should return empty list for a corpus with no
        files."""
        saved = await corpus_svc.create(name="files", root_path="/tmp")
        files = await corpus_svc.get_files(saved.id)
        assert files == []