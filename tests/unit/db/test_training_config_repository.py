# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for TrainingConfigRepository — CRUD operations.

Tests cover all repository methods: get, get_all, add, delete,
including edge cases like non-existent records.
"""

from __future__ import annotations

import pytest

from anvil.db.models.training_config import TrainingConfig
from anvil.db.repositories.training_configs import TrainingConfigRepository


class TestTrainingConfigRepository:
    """CRUD tests for TrainingConfigRepository using in-memory SQLite."""

    async def test_add_and_get(self, in_memory_session):
        """Adding a config and retrieving it by id should return the same
        record with a generated primary key.
        """
        repo = TrainingConfigRepository(in_memory_session)
        config = TrainingConfig(name="test-config", n_layer=2, n_embd=32, n_head=4)
        saved = await repo.add(config)
        assert saved.id is not None
        assert saved.name == "test-config"
        assert saved.n_layer == 2
        assert saved.n_embd == 32

        fetched = await repo.get(saved.id)
        assert fetched is not None
        assert fetched.name == "test-config"
        assert fetched.n_layer == 2

    async def test_get_nonexistent(self, in_memory_session):
        """Getting a non-existent id should return None."""
        repo = TrainingConfigRepository(in_memory_session)
        result = await repo.get(9999)
        assert result is None

    async def test_get_all(self, in_memory_session):
        """get_all should return all added configs."""
        repo = TrainingConfigRepository(in_memory_session)
        c1 = TrainingConfig(name="c1", n_layer=1)
        c2 = TrainingConfig(name="c2", n_layer=2)
        await repo.add(c1)
        await repo.add(c2)

        all_configs = await repo.get_all()
        names = [c.name for c in all_configs]
        assert "c1" in names
        assert "c2" in names
        assert len(all_configs) == 2

    async def test_get_all_empty(self, in_memory_session):
        """get_all on an empty table should return an empty sequence."""
        repo = TrainingConfigRepository(in_memory_session)
        result = await repo.get_all()
        assert len(result) == 0

    async def test_delete(self, in_memory_session):
        """Deleting a config should remove it and subsequent get returns
        None.
        """
        repo = TrainingConfigRepository(in_memory_session)
        config = TrainingConfig(name="delete-me")
        saved = await repo.add(config)
        cid = saved.id

        await repo.delete(cid)
        assert await repo.get(cid) is None

    async def test_delete_nonexistent(self, in_memory_session):
        """Deleting a non-existent id should not raise."""
        repo = TrainingConfigRepository(in_memory_session)
        await repo.delete(9999)  # should not raise
