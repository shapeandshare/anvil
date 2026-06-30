# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for FineTuneDatasetRepository."""

from __future__ import annotations

from datetime import UTC

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.db.base import Base
from anvil.db.models.chat_template import ChatTemplate
from anvil.db.models.dataset import Dataset
from anvil.db.models.external_model import ExternalModel
from anvil.db.models.fine_tune_dataset import FineTuneDataset
from anvil.db.repositories.fine_tune_datasets import FineTuneDatasetRepository
from anvil.db.session import AsyncSessionLocal, async_engine
from anvil.services._shared.asset_state import AssetState
from anvil.services._shared.fine_tune_dataset_status import FineTuneDatasetStatus
from anvil.services._shared.runnable_status import RunnableStatus


@pytest.fixture
async def db_session():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        yield session
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def source_dataset(db_session: AsyncSession) -> Dataset:
    ds = Dataset(
        name="test-source",
        filename="test.jsonl",
        file_path="/tmp/test.jsonl",
        sample_count=0,
        total_size_bytes=0,
    )
    db_session.add(ds)
    await db_session.flush()
    await db_session.refresh(ds)
    return ds


@pytest.fixture
async def source_model(db_session: AsyncSession) -> ExternalModel:
    model = ExternalModel(
        display_name="test-model",
        source_type="huggingface",
        source_identifier="org/test",
        architecture_family="LlamaForCausalLM",
        parameter_count=1_000_000,
        license="mit",
        tokenizer_family="subword",
        revision_sha="abc123",
        runnable_status=RunnableStatus.RUNNABLE.value,
        asset_availability=AssetState.METADATA_ONLY.value,
    )
    db_session.add(model)
    await db_session.flush()
    await db_session.refresh(model)
    return model


@pytest.fixture
async def chat_template(db_session: AsyncSession) -> ChatTemplate:
    ct = ChatTemplate(
        name="test-ct",
        template_string="{{ bos_token }}",
        tokenizer_family="subword",
    )
    db_session.add(ct)
    await db_session.flush()
    await db_session.refresh(ct)
    return ct


@pytest.mark.asyncio
async def test_add_and_get(
    db_session: AsyncSession,
    source_dataset: Dataset,
    chat_template: ChatTemplate,
    source_model: ExternalModel,
):
    """Adding a FineTuneDataset and retrieving it by ID returns the same entry."""
    repo = FineTuneDatasetRepository(db_session)

    ftd = FineTuneDataset(
        dataset_id=source_dataset.id,
        chat_template_id=chat_template.id,
        base_model_ref=source_model.id,
        status=FineTuneDatasetStatus.PREPARING,
        record_type="sft",
    )
    saved = await repo.add(ftd)
    assert saved.id is not None
    assert saved.status == FineTuneDatasetStatus.PREPARING
    assert saved.record_type == "sft"

    fetched = await repo.get(saved.id)
    assert fetched is not None
    assert fetched.dataset_id == source_dataset.id


@pytest.mark.asyncio
async def test_get_active_for_dataset(
    db_session: AsyncSession,
    source_dataset: Dataset,
    chat_template: ChatTemplate,
    source_model: ExternalModel,
):
    """get_active_for_dataset returns the preparing entry for a dataset."""
    repo = FineTuneDatasetRepository(db_session)

    active = FineTuneDataset(
        dataset_id=source_dataset.id,
        chat_template_id=chat_template.id,
        base_model_ref=source_model.id,
        status=FineTuneDatasetStatus.PREPARING,
        record_type="sft",
    )
    await repo.add(active)

    found = await repo.get_active_for_dataset(source_dataset.id)
    assert found is not None
    assert found.id == active.id
    assert found.status == FineTuneDatasetStatus.PREPARING

    # After completion, no active entry
    active.status = FineTuneDatasetStatus.READY
    await db_session.flush()

    not_found = await repo.get_active_for_dataset(source_dataset.id)
    assert not_found is None


@pytest.mark.asyncio
async def test_list_with_filters(
    db_session: AsyncSession,
    source_dataset: Dataset,
    chat_template: ChatTemplate,
    source_model: ExternalModel,
):
    """List filters by dataset, status, and model."""
    repo = FineTuneDatasetRepository(db_session)

    ftd1 = FineTuneDataset(
        dataset_id=source_dataset.id,
        status=FineTuneDatasetStatus.READY,
        record_type="sft",
    )
    ftd2 = FineTuneDataset(
        dataset_id=source_dataset.id,
        status=FineTuneDatasetStatus.FAILED,
        record_type="sft",
        base_model_ref=source_model.id,
    )
    await repo.add(ftd1)
    await repo.add(ftd2)

    # Filter by status
    ready = await repo.get_all(status=FineTuneDatasetStatus.READY)
    assert len(ready) == 1
    assert ready[0].id == ftd1.id

    # Filter by dataset
    by_dataset = await repo.get_all(dataset_id=source_dataset.id)
    assert len(by_dataset) == 2

    # Filter by model
    by_model = await repo.get_all(base_model_ref=source_model.id)
    assert len(by_model) == 1


@pytest.mark.asyncio
async def test_update_status(
    db_session: AsyncSession,
    source_dataset: Dataset,
):
    """update_status transitions the job status and sets timestamps."""
    repo = FineTuneDatasetRepository(db_session)

    ftd = FineTuneDataset(
        dataset_id=source_dataset.id,
        status=FineTuneDatasetStatus.PREPARING,
        record_type="sft",
    )
    saved = await repo.add(ftd)

    from datetime import datetime, timezone

    now = datetime.now(UTC)
    updated = await repo.update_status(
        id=saved.id,
        status=FineTuneDatasetStatus.READY,
        record_count=42,
        prepared_file_path="data/datasets/1/prepared/42.jsonl",
        summary_json='{"total": 42, "succeeded": 40, "failed": 2, "errors": []}',
        started_at=now,
        finished_at=now,
    )
    assert updated is not None
    assert updated.status == FineTuneDatasetStatus.READY
    assert updated.record_count == 42
    assert updated.prepared_file_path == "data/datasets/1/prepared/42.jsonl"
    assert updated.summary_json is not None
