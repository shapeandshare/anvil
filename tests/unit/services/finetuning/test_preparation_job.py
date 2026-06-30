# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for preparation job runner."""

from __future__ import annotations

from datetime import UTC, datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.db.base import Base
from anvil.db.models.chat_template import ChatTemplate
from anvil.db.models.dataset import Dataset
from anvil.db.models.fine_tune_dataset import FineTuneDataset
from anvil.db.session import AsyncSessionLocal, async_engine
from anvil.services._shared.fine_tune_dataset_status import FineTuneDatasetStatus
from anvil.services.finetuning.preparation_job import run_preparation
from anvil.services.finetuning.preparation_result import PreparationResult


@pytest.fixture
async def db_session():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        yield session
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def dataset(db_session: AsyncSession) -> Dataset:
    ds = Dataset(
        name="prep-test",
        filename="test.jsonl",
        file_path="/tmp/test.jsonl",
    )
    db_session.add(ds)
    await db_session.flush()
    await db_session.refresh(ds)
    return ds


@pytest.fixture
async def template(db_session: AsyncSession) -> ChatTemplate:
    ct = ChatTemplate(
        name="test-prep-ct",
        template_string="{{ instruction }}\n{{ response }}",
        tokenizer_family="char",
    )
    db_session.add(ct)
    await db_session.flush()
    await db_session.refresh(ct)
    return ct


@pytest.fixture
async def ftd(
    db_session: AsyncSession, dataset: Dataset, template: ChatTemplate
) -> FineTuneDataset:
    entry = FineTuneDataset(
        dataset_id=dataset.id,
        chat_template_id=template.id,
        status=FineTuneDatasetStatus.PREPARING,
        record_type="sft",
        started_at=datetime.now(UTC),
    )
    db_session.add(entry)
    await db_session.flush()
    await db_session.refresh(entry)
    return entry


@pytest.mark.asyncio
async def test_run_preparation_completes_ready(
    db_session: AsyncSession,
    ftd: FineTuneDataset,
):
    """run_preparation transitions from preparing to ready with a summary."""
    records = [
        {"instruction": "Hello", "response": "World"},
        {"instruction": "Foo", "response": "Bar"},
    ]
    result = await run_preparation(
        session=db_session,
        fine_tune_dataset_id=ftd.id,
        records=records,
        template_string="{{ instruction }}\n{{ response }}",
        bos_token="",
        batch_size=100,
    )
    assert result is not None
    assert isinstance(result, PreparationResult)
    assert result.total == 2
    assert result.succeeded == 2
    assert result.failed == 0

    # Verify status in DB
    await db_session.refresh(ftd)
    assert ftd.status == FineTuneDatasetStatus.READY
    assert ftd.record_count == 2


@pytest.mark.asyncio
async def test_run_preparation_skip_invalid(
    db_session: AsyncSession,
    ftd: FineTuneDataset,
):
    """run_preparation skips invalid records and reports them in summary."""
    records = [
        {"instruction": "Valid", "response": "Pair"},
        {"instruction": "", "response": "Empty"},  # invalid
        {"instruction": "Partial", "response": ""},  # invalid
    ]
    result = await run_preparation(
        session=db_session,
        fine_tune_dataset_id=ftd.id,
        records=records,
        template_string="{{ instruction }}\n{{ response }}",
        bos_token="",
        batch_size=100,
    )
    assert result.total == 3
    assert result.succeeded == 1
    assert result.failed == 2
    assert len(result.errors) == 2

    await db_session.refresh(ftd)
    assert ftd.status == FineTuneDatasetStatus.READY
    assert ftd.record_count == 1


@pytest.mark.asyncio
async def test_run_preparation_empty_input(
    db_session: AsyncSession,
    ftd: FineTuneDataset,
):
    """Empty input completes as ready with total=0."""
    result = await run_preparation(
        session=db_session,
        fine_tune_dataset_id=ftd.id,
        records=[],
        template_string="{{ x }}",
        bos_token="",
        batch_size=100,
    )
    assert result.total == 0
    assert result.succeeded == 0
    assert result.failed == 0

    await db_session.refresh(ftd)
    assert ftd.status == FineTuneDatasetStatus.READY
    assert ftd.record_count == 0


@pytest.mark.asyncio
async def test_run_preparation_creates_audit(
    db_session: AsyncSession,
    ftd: FineTuneDataset,
):
    """run_preparation records a CurationOperation audit entry."""
    from anvil.db.models.curation_operation import CurationOperation

    records = [{"instruction": "A", "response": "B"}]
    await run_preparation(
        session=db_session,
        fine_tune_dataset_id=ftd.id,
        records=records,
        template_string="{{ instruction }}\n{{ response }}",
        bos_token="",
        batch_size=100,
    )

    # Check for the audit entry
    from sqlalchemy import select

    result = await db_session.execute(
        select(CurationOperation).where(CurationOperation.dataset_id == ftd.dataset_id)
    )
    ops = result.scalars().all()
    assert len(ops) >= 1
    assert ops[0].operation_type == "prepare"


@pytest.mark.asyncio
async def test_run_preparation_persists_summary_json(
    db_session: AsyncSession,
    ftd: FineTuneDataset,
):
    """run_preparation persists the summary report on the dataset (SC-005)."""
    import json

    records = [
        {"instruction": "A", "response": "1"},
        {"instruction": "", "response": "bad"},
    ]
    await run_preparation(
        session=db_session,
        fine_tune_dataset_id=ftd.id,
        records=records,
        template_string="{{ instruction }}\n{{ response }}",
        bos_token="",
        batch_size=100,
    )
    await db_session.refresh(ftd)
    assert ftd.summary_json is not None
    summary = json.loads(ftd.summary_json)
    assert summary["total"] == 2
    assert summary["succeeded"] == 1
    assert summary["failed"] == 1
    assert len(summary["errors"]) == 1


@pytest.mark.asyncio
async def test_run_preparation_writes_output_file(
    db_session: AsyncSession,
    ftd: FineTuneDataset,
    tmp_path,
):
    """run_preparation writes rendered records to the store and sets the path."""
    from anvil.storage.local import LocalFileStore

    store = LocalFileStore(str(tmp_path))
    records = [{"instruction": "Hi", "response": "There"}]
    output_path = "prepared/out.jsonl"

    await run_preparation(
        session=db_session,
        fine_tune_dataset_id=ftd.id,
        records=records,
        template_string="{{ instruction }}\n{{ response }}",
        bos_token="",
        batch_size=100,
        store=store,
        output_path=output_path,
    )
    await db_session.refresh(ftd)
    assert ftd.prepared_file_path == output_path
    written = (tmp_path / "prepared" / "out.jsonl").read_text()
    assert "Hi" in written
    assert "There" in written


@pytest.mark.asyncio
async def test_run_preparation_preference_dispatch(
    db_session: AsyncSession,
    dataset: Dataset,
    template: ChatTemplate,
    tmp_path,
):
    """run_preparation renders preference records as prompt/chosen/rejected."""
    import json

    from anvil.storage.local import LocalFileStore

    entry = FineTuneDataset(
        dataset_id=dataset.id,
        chat_template_id=template.id,
        status=FineTuneDatasetStatus.PREPARING,
        record_type="preference",
    )
    db_session.add(entry)
    await db_session.flush()
    await db_session.refresh(entry)

    store = LocalFileStore(str(tmp_path))
    records = [{"chosen": "Good", "rejected": "Bad", "context": "Q?"}]
    await run_preparation(
        session=db_session,
        fine_tune_dataset_id=entry.id,
        records=records,
        template_string="{{ context }}",
        bos_token="",
        record_type="preference",
        batch_size=100,
        store=store,
        output_path="pref/out.jsonl",
    )
    result = (tmp_path / "pref" / "out.jsonl").read_text()
    row = json.loads(result)
    assert row["rendered"]["chosen"] == "Good"
    assert row["rendered"]["rejected"] == "Bad"
