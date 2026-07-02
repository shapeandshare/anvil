"""Unit tests for TrainingRunService — persistence and MLflow registration.

Verifies that model artifacts are written to
``data/models/experiment_{id}.json`` and that MLflow registration is
called on completion, without actually running the training loop.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anvil.services.training.training_run_config import TrainingRunConfig
from anvil.services.training.training_run_service import TrainingRunService


def _make_training_run_svc(tmpdir: str) -> TrainingRunService:
    svc = MagicMock()
    svc.reserve_run.return_value = 42
    svc.allocate_experiment_id = AsyncMock(return_value=99)
    svc.get_queue.return_value = None
    svc.start_training = AsyncMock()

    tracking = MagicMock()
    tracking.start_run = AsyncMock(return_value="mlflow_1")
    tracking.is_degraded = False
    tracking.finish_run = AsyncMock()
    tracking.set_tag = AsyncMock()
    tracking.log_metric = AsyncMock()
    tracking.log_final_metric = AsyncMock()
    tracking.register_source_model = AsyncMock(return_value={})

    return TrainingRunService(
        svc=svc,
        tracking=tracking,
        models_dir=Path(tmpdir),
        tasks={},
    )


@pytest.mark.asyncio
async def test_on_complete_writes_model_artifact():
    """Model artifact is written to models_dir/experiment_{id}.json."""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_svc = _make_training_run_svc(tmpdir)

        result = MagicMock()
        result.final_loss = 0.05
        result.samples = ["hello", "world"]
        result.uchars = list("abcdefg")
        result.model = MagicMock()
        result.model.save = MagicMock()

        await run_svc._on_complete(
            result=result,
            config_dict={"base_model_ref": None},
            mlflow_run_id="mlflow_1",
            experiment_id=99,
            dataset_id=None,
            corpus_id=None,
            mps_thread=None,
            run_id=42,
        )

        expected_path = Path(tmpdir) / "experiment_99.json"
        # save is called twice: temp model.json + final experiment_99.json
        calls = result.model.save.call_args_list
        final_call_path = calls[-1][0][0]
        assert final_call_path == str(expected_path)


@pytest.mark.asyncio
async def test_on_complete_calls_mlflow_registration():
    """MLflow register_source_model is called on completion."""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_svc = _make_training_run_svc(tmpdir)

        result = MagicMock()
        result.final_loss = 0.05
        result.samples = []
        result.uchars = []
        result.model = MagicMock()
        result.model.save = MagicMock()

        await run_svc._on_complete(
            result=result,
            config_dict={},
            mlflow_run_id="mlflow_1",
            experiment_id=99,
            dataset_id=10,
            corpus_id=None,
            mps_thread=None,
            run_id=42,
        )

        # Registration is called
        assert run_svc._tracking.register_source_model.called

        run_svc._tracking.finish_run.assert_called_once_with("mlflow_1")
        run_svc._tracking.log_final_metric.assert_called_once_with(
            "mlflow_1", "final_loss", 0.05
        )


@pytest.mark.asyncio
async def test_on_complete_sets_finished_tags():
    """MLflow tags for status and final_loss are set."""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_svc = _make_training_run_svc(tmpdir)

        result = MagicMock()
        result.final_loss = 0.123
        result.samples = []
        result.uchars = []
        result.model = MagicMock()
        result.model.save = MagicMock()

        await run_svc._on_complete(
            result=result,
            config_dict={},
            mlflow_run_id="mlflow_1",
            experiment_id=99,
            dataset_id=None,
            corpus_id=None,
            mps_thread=None,
            run_id=42,
        )

        run_svc._tracking.set_tag.assert_any_call(
            "mlflow_1", "anvil.status", "finished"
        )
        run_svc._tracking.set_tag.assert_any_call(
            "mlflow_1", "anvil.final_loss", "0.123"
        )


@pytest.mark.asyncio
async def test_on_complete_warm_start_tags():
    """Warm-start lineage tags are set when base_model_ref is present."""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_svc = _make_training_run_svc(tmpdir)

        result = MagicMock()
        result.final_loss = 0.05
        result.samples = []
        result.uchars = []
        result.model = MagicMock()
        result.model.save = MagicMock()

        await run_svc._on_complete(
            result=result,
            config_dict={"base_model_ref": 1},
            mlflow_run_id="mlflow_1",
            experiment_id=99,
            dataset_id=None,
            corpus_id=None,
            mps_thread=None,
            run_id=42,
        )

        run_svc._tracking.set_tag.assert_any_call(
            "mlflow_1", "anvil.warm_start", "true"
        )
        run_svc._tracking.set_tag.assert_any_call(
            "mlflow_1", "anvil.base_model_ref", "1"
        )


@pytest.mark.asyncio
async def test_validate_hparams():
    """Static validation raises ValueError for invalid params."""
    with pytest.raises(ValueError, match="exceeds"):
        TrainingRunService._validate_hparams(n_embd=4, n_head=8, block_size=16)

    with pytest.raises(ValueError, match="divisible"):
        TrainingRunService._validate_hparams(n_embd=15, n_head=4, block_size=16)

    with pytest.raises(ValueError, match="odd"):
        TrainingRunService._validate_hparams(n_embd=12, n_head=4, block_size=16)

    # Valid params should not raise
    TrainingRunService._validate_hparams(n_embd=16, n_head=4, block_size=16)


@pytest.mark.asyncio
async def test_validate_method():
    """Static validation rejects LoRA fields for full method."""
    config = TrainingRunConfig(method="full", lora_rank=4)
    with pytest.raises(ValueError, match="lora_\\*"):
        TrainingRunService._validate_method(config)

    config2 = TrainingRunConfig(method="bogus")
    with pytest.raises(ValueError, match="Unknown"):
        TrainingRunService._validate_method(config2)

    config3 = TrainingRunConfig(method="full")
    TrainingRunService._validate_method(config3)  # no raise


@pytest.mark.asyncio
async def test_estimate_memory_returns_none_for_stdlib():
    gpu_info = MagicMock()
    config = TrainingRunConfig()
    result = TrainingRunService._estimate_memory(
        MagicMock(value="stdlib"), config, gpu_info
    )
    assert result is None


@pytest.mark.asyncio
async def test_run_active_and_remove():
    svc = _make_training_run_svc("/tmp")
    assert not svc.is_run_active(1)

    svc._tasks[1] = MagicMock()
    assert svc.is_run_active(1)

    svc._tasks.pop(1, None)
    assert not svc.is_run_active(1)
