# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for ExternalModelRepository."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.db.base import Base
from anvil.db.models.external_model import ExternalModel
from anvil.db.repositories.external_models import ExternalModelRepository
from anvil.db.session import AsyncSessionLocal, async_engine
from anvil.services._shared.import_types import AssetState, RunnableStatus


@pytest.fixture
async def db_session():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        yield session
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_add_and_get(db_session):
    """Adding an ExternalModel and retrieving it by ID returns the same entry."""
    repo = ExternalModelRepository(db_session)

    model = ExternalModel(
        display_name="test-model",
        source_type="huggingface",
        source_identifier="org/test",
        architecture_family="LlamaForCausalLM",
        parameter_count=1_000_000,
        license="mit",
        tokenizer_family="sentencepiece",
        revision_sha="abc123",
        runnable_status=RunnableStatus.RUNNABLE.value,
        asset_availability=AssetState.METADATA_ONLY.value,
    )
    saved = await repo.add(model)
    assert saved.id is not None
    assert saved.display_name == "test-model"

    fetched = await repo.get(saved.id)
    assert fetched is not None
    assert fetched.source_identifier == "org/test"


@pytest.mark.asyncio
async def test_get_all_returns_newest_first(db_session):
    """get_all orders results by created_at descending."""
    repo = ExternalModelRepository(db_session)

    m1 = ExternalModel(
        display_name="a",
        source_type="huggingface",
        source_identifier="org/a",
        architecture_family="LlamaForCausalLM",
        parameter_count=100,
        license="mit",
        tokenizer_family="sentencepiece",
        revision_sha="aaa",
        runnable_status=RunnableStatus.RUNNABLE.value,
        asset_availability=AssetState.METADATA_ONLY.value,
    )
    m2 = ExternalModel(
        display_name="b",
        source_type="local",
        source_identifier="/tmp/b",
        architecture_family="LlamaForCausalLM",
        parameter_count=200,
        license="mit",
        tokenizer_family="tokenizers",
        revision_sha="bbb",
        runnable_status=RunnableStatus.RUNNABLE.value,
        asset_availability=AssetState.METADATA_ONLY.value,
    )
    await repo.add(m1)
    await repo.add(m2)

    all_models = await repo.get_all()
    assert len(all_models) >= 2
    names = {m.display_name for m in all_models}
    assert "a" in names
    assert "b" in names


@pytest.mark.asyncio
async def test_find_by_source_idempotency(db_session):
    """find_by_source finds existing entry with the same identity triple."""
    repo = ExternalModelRepository(db_session)

    model = ExternalModel(
        display_name="dup-test",
        source_type="huggingface",
        source_identifier="org/dup",
        architecture_family="LlamaForCausalLM",
        parameter_count=500,
        license="apache-2.0",
        tokenizer_family="sentencepiece",
        revision_sha="same-rev",
        runnable_status=RunnableStatus.RUNNABLE.value,
        asset_availability=AssetState.METADATA_ONLY.value,
    )
    await repo.add(model)
    await db_session.flush()

    found = await repo.find_by_source(
        source_type="huggingface",
        source_identifier="org/dup",
        revision_sha="same-rev",
    )
    assert found is not None
    assert found.display_name == "dup-test"

    # Different revision — should not match.
    # Different revision — should not match.
    not_found = await repo.find_by_source(
        source_type="huggingface",
        source_identifier="org/dup",
        revision_sha="other-rev",
    )
    assert not_found is None


@pytest.mark.asyncio
async def test_delete_removes_entry(db_session):
    """Deleting an entry makes get return None."""
    repo = ExternalModelRepository(db_session)

    model = ExternalModel(
        display_name="delete-me",
        source_type="local",
        source_identifier="/tmp/delete",
        architecture_family="LlamaForCausalLM",
        parameter_count=0,
        license="unknown",
        tokenizer_family="unknown",
        revision_sha="del",
        runnable_status=RunnableStatus.TRACK_ONLY.value,
        asset_availability=AssetState.METADATA_ONLY.value,
    )
    saved = await repo.add(model)
    await repo.delete(saved.id)

    fetched = await repo.get(saved.id)
    assert fetched is None
