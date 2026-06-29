"""Unit tests for the UserSecret repository."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.db.models.user_secret import UserSecret
from anvil.db.repositories.user_secret_repository import UserSecretRepository


@pytest.mark.asyncio
async def test_upsert_and_get(in_memory_session: AsyncSession) -> None:
    repo = UserSecretRepository(in_memory_session)
    saved = await repo.upsert("user1", "hf_token", "encrypted_value_1")
    assert saved.id is not None

    found = await repo.get("user1", "hf_token")
    assert found is not None
    assert found.encrypted_value == "encrypted_value_1"


@pytest.mark.asyncio
async def test_upsert_updates_existing(in_memory_session: AsyncSession) -> None:
    repo = UserSecretRepository(in_memory_session)
    await repo.upsert("user1", "hf_token", "old_value")
    await repo.upsert("user1", "hf_token", "new_value")

    found = await repo.get("user1", "hf_token")
    assert found is not None
    assert found.encrypted_value == "new_value"


@pytest.mark.asyncio
async def test_get_all_for_user(in_memory_session: AsyncSession) -> None:
    repo = UserSecretRepository(in_memory_session)
    await repo.upsert("user1", "hf_token", "val1")
    await repo.upsert("user1", "openai_key", "val2")

    secrets = await repo.get_all_for_user("user1")
    assert len(secrets) == 2
    keys = [s.key for s in secrets]
    assert "hf_token" in keys
    assert "openai_key" in keys


@pytest.mark.asyncio
async def test_get_other_user_not_returned(in_memory_session: AsyncSession) -> None:
    repo = UserSecretRepository(in_memory_session)
    await repo.upsert("user1", "hf_token", "val1")

    secrets = await repo.get_all_for_user("user2")
    assert len(secrets) == 0


@pytest.mark.asyncio
async def test_delete(in_memory_session: AsyncSession) -> None:
    repo = UserSecretRepository(in_memory_session)
    await repo.upsert("user1", "hf_token", "val1")
    assert await repo.get("user1", "hf_token") is not None

    await repo.delete("user1", "hf_token")
    assert await repo.get("user1", "hf_token") is None


@pytest.mark.asyncio
async def test_delete_idempotent(in_memory_session: AsyncSession) -> None:
    repo = UserSecretRepository(in_memory_session)
    await repo.delete("user1", "nonexistent")
    assert True  # no exception raised


@pytest.mark.asyncio
async def test_get_nonexistent(in_memory_session: AsyncSession) -> None:
    repo = UserSecretRepository(in_memory_session)
    found = await repo.get("user1", "nonexistent")
    assert found is None
