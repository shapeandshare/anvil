"""Unit tests for TeachingService.

Mocks all dependencies (repo, training_runs, inference, tracking, datasets)
so no real DB, training, or MLflow code runs.  Focuses on session CRUD,
start_round validation, chain-head updates, and rollback.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.db.models.teaching_session import TeachingSession
from anvil.db.models.teaching_session_status import TeachingSessionStatus
from anvil.db.repositories.teaching_session_repository import TeachingSessionRepository
from anvil.services.datasets.datasets import DatasetService
from anvil.services.inference.inference import InferenceService
from anvil.services.teaching.teaching_service import TeachingService
from anvil.services.training.training_run_service import TrainingRunService


@pytest.fixture
def mock_session():
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def mock_repo():
    repo = MagicMock(spec=TeachingSessionRepository)
    repo.add = AsyncMock()
    repo.get = AsyncMock()
    repo.list = AsyncMock(return_value=([], 0))
    repo.update_status = AsyncMock()
    repo.update_current_base_experiment_id = AsyncMock()
    repo.delete = AsyncMock(return_value=True)
    return repo


@pytest.fixture
def mock_training_runs():
    svc = MagicMock(spec=TrainingRunService)
    svc.start_training_run = AsyncMock(
        return_value={
            "run_id": 1,
            "mlflow_run_id": "mlflow_1",
            "experiment_id": 99,
            "status": "running",
            "tracking": "active",
        }
    )
    return svc


@pytest.fixture
def mock_inference():
    return MagicMock(spec=InferenceService)


@pytest.fixture
def mock_tracking():
    svc = MagicMock()
    svc.set_tag = AsyncMock()
    svc.is_degraded = False
    return svc


@pytest.fixture
def mock_datasets():
    svc = MagicMock(spec=DatasetService)
    svc.create_dataset = AsyncMock()
    return svc


@pytest.fixture
def teaching_service(
    mock_session,
    mock_repo,
    mock_training_runs,
    mock_inference,
    mock_tracking,
    mock_datasets,
):
    return TeachingService(
        session=mock_session,
        repo=mock_repo,
        training_runs=mock_training_runs,
        inference=mock_inference,
        tracking=mock_tracking,
        datasets=mock_datasets,
    )


########################################################################
# Session CRUD
########################################################################


@pytest.mark.asyncio
async def test_create_session(teaching_service, mock_repo):
    mock_repo.add.return_value = TeachingSession(
        id=1,
        name="my-session",
        description="desc",
        seed_experiment_id=42,
        current_base_experiment_id=42,
        status=TeachingSessionStatus.DRAFT,
    )
    result = await teaching_service.create_session(
        name="my-session",
        description="desc",
        seed_experiment_id=42,
    )
    assert result.id == 1
    assert result.name == "my-session"
    assert result.seed_experiment_id == 42
    mock_repo.add.assert_called_once()


@pytest.mark.asyncio
async def test_get_session(teaching_service, mock_repo):
    mock_repo.get.return_value = TeachingSession(
        id=1, name="s", status=TeachingSessionStatus.DRAFT
    )
    result = await teaching_service.get_session(1)
    assert result is not None
    assert result.id == 1
    mock_repo.get.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_get_session_not_found(teaching_service, mock_repo):
    mock_repo.get.return_value = None
    result = await teaching_service.get_session(999)
    assert result is None


@pytest.mark.asyncio
async def test_list_sessions(teaching_service, mock_repo):
    mock_repo.list.return_value = (
        [TeachingSession(id=1, name="s1", status=TeachingSessionStatus.ACTIVE)],
        1,
    )
    sessions, total = await teaching_service.list_sessions(
        status=TeachingSessionStatus.ACTIVE
    )
    assert len(sessions) == 1
    assert total == 1
    mock_repo.list.assert_called_once_with(
        status=TeachingSessionStatus.ACTIVE, limit=20, offset=0
    )


@pytest.mark.asyncio
async def test_update_status(teaching_service, mock_repo):
    mock_repo.update_status.return_value = TeachingSession(
        id=1, name="s", status=TeachingSessionStatus.ACTIVE
    )
    result = await teaching_service.update_status(1, TeachingSessionStatus.ACTIVE)
    assert result is not None
    assert result.status == TeachingSessionStatus.ACTIVE


@pytest.mark.asyncio
async def test_delete_session(teaching_service, mock_repo):
    result = await teaching_service.delete_session(1)
    assert result is True
    mock_repo.delete.assert_called_once_with(1)


########################################################################
# start_round
########################################################################


@pytest.mark.asyncio
async def test_start_round_rejects_lora(teaching_service, mock_repo):
    mock_repo.get.return_value = TeachingSession(
        id=1, name="s", status=TeachingSessionStatus.DRAFT
    )
    with pytest.raises(ValueError, match="method='full'"):
        await teaching_service.start_round(
            session_id=1,
            examples=["hello world"],
            training_config={"method": "lora", "num_steps": 10},
        )


@pytest.mark.asyncio
async def test_start_round_creates_dataset(teaching_service, mock_repo, mock_datasets):
    mock_repo.get.return_value = TeachingSession(
        id=1,
        name="s",
        current_base_experiment_id=None,
        status=TeachingSessionStatus.DRAFT,
    )
    mock_repo.update_status.return_value = TeachingSession(
        id=1, name="s", status=TeachingSessionStatus.ACTIVE
    )
    mock_datasets.create_dataset.return_value = MagicMock(id=100)

    with patch(
        "anvil.services.teaching.teaching_service.DatasetImportService"
    ) as mock_import_cls:
        mock_import = MagicMock()
        mock_import.commit_docs_import = AsyncMock()
        mock_import_cls.return_value = mock_import

        result = await teaching_service.start_round(
            session_id=1,
            examples=["hello world"],
            training_config={"method": "full", "num_steps": 10},
        )

    mock_datasets.create_dataset.assert_called_once()
    assert mock_datasets.create_dataset.call_args[1]["origin"] == "teaching"

    mock_import.commit_docs_import.assert_called_once_with(
        docs=["hello world"], source_label="teaching", source_format="docs"
    )

    assert result["status"] == "running"
    assert result["round_experiment_id"] == 99


@pytest.mark.asyncio
async def test_start_round_sets_base_model_ref(
    teaching_service, mock_repo, mock_datasets, mock_training_runs
):
    mock_repo.get.return_value = TeachingSession(
        id=1,
        name="s",
        current_base_experiment_id=42,
        status=TeachingSessionStatus.DRAFT,
    )
    mock_repo.update_status.return_value = TeachingSession(
        id=1, name="s", status=TeachingSessionStatus.ACTIVE
    )
    mock_datasets.create_dataset.return_value = MagicMock(id=100)
    mock_repo.update_current_base_experiment_id = AsyncMock()

    with patch(
        "anvil.services.teaching.teaching_service.DatasetImportService"
    ) as mock_import_cls:
        mock_import = MagicMock()
        mock_import.commit_docs_import = AsyncMock()
        mock_import_cls.return_value = mock_import

        await teaching_service.start_round(
            session_id=1,
            examples=["hello"],
            training_config={"method": "full", "num_steps": 10},
        )

    call_kwargs = mock_training_runs.start_training_run.call_args[0][0]
    assert call_kwargs.base_model_ref == 42


@pytest.mark.asyncio
async def test_start_round_updates_chain_head_on_complete(
    teaching_service, mock_repo, mock_datasets, mock_training_runs
):
    mock_repo.get.return_value = TeachingSession(
        id=1,
        name="s",
        current_base_experiment_id=42,
        status=TeachingSessionStatus.ACTIVE,
    )
    mock_datasets.create_dataset.return_value = MagicMock(id=100)
    mock_repo.update_current_base_experiment_id = AsyncMock()

    with patch(
        "anvil.services.teaching.teaching_service.DatasetImportService"
    ) as mock_import_cls:
        mock_import = MagicMock()
        mock_import.commit_docs_import = AsyncMock()
        mock_import_cls.return_value = mock_import

        await teaching_service.start_round(
            session_id=1,
            examples=["hello"],
            training_config={"method": "full", "num_steps": 10},
        )

    _, kwargs = mock_training_runs.start_training_run.call_args
    on_complete_extra = kwargs["on_complete_extra"]

    assert on_complete_extra is not None

    await on_complete_extra(MagicMock(), {"experiment_id": 99})

    mock_repo.update_current_base_experiment_id.assert_called_once_with(1, 99)


@pytest.mark.asyncio
async def test_start_round_rejects_qlora(teaching_service, mock_repo):
    mock_repo.get.return_value = TeachingSession(
        id=1, name="s", status=TeachingSessionStatus.DRAFT
    )
    with pytest.raises(ValueError, match="method='full'"):
        await teaching_service.start_round(
            session_id=1,
            examples=["hello"],
            training_config={"method": "qlora", "num_steps": 10},
        )


########################################################################
# Round inspection, comparison, rollback
########################################################################


@pytest.mark.asyncio
async def test_inspect_round(teaching_service, mock_inference):
    mock_loaded = MagicMock()
    mock_inference.load_model = AsyncMock(return_value=mock_loaded)
    mock_inference.generate = MagicMock(side_effect=["result1", "result2"])

    results = await teaching_service.inspect_round(
        experiment_id=99,
        prompts=["hello", "world"],
        temperature=0.5,
        max_tokens=50,
    )

    assert len(results) == 2
    assert results[0]["prompt"] == "hello"
    assert results[0]["generated"] == "result1"
    assert results[1]["prompt"] == "world"
    assert results[1]["generated"] == "result2"

    mock_inference.load_model.assert_called_once_with(model_id=99)


@pytest.mark.asyncio
async def test_compare_rounds(teaching_service, mock_inference):
    mock_left = MagicMock()
    mock_right = MagicMock()
    mock_inference.load_model = AsyncMock(side_effect=[mock_left, mock_right])
    mock_inference.generate = MagicMock(side_effect=["left_out", "right_out"])

    results = await teaching_service.compare_rounds(
        left_experiment_id=1,
        right_experiment_id=2,
        prompts=["test"],
    )

    assert len(results) == 1
    assert results[0]["prompt"] == "test"
    assert results[0]["left"] == "left_out"
    assert results[0]["right"] == "right_out"


@pytest.mark.asyncio
async def test_rollback_to_round(teaching_service, mock_repo):
    mock_repo.update_current_base_experiment_id.return_value = TeachingSession(
        id=1,
        name="s",
        current_base_experiment_id=10,
        status=TeachingSessionStatus.ACTIVE,
    )
    result = await teaching_service.rollback_to_round(
        session_id=1, target_experiment_id=10
    )
    assert result is not None
    assert result.current_base_experiment_id == 10
    mock_repo.update_current_base_experiment_id.assert_called_once_with(1, 10)
