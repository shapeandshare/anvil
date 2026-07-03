"""Unit tests for TrainingRunService — persistence and MLflow registration.

Verifies that model artifacts are written to
``data/models/experiment_{id}.json`` and that MLflow registration is
called on completion, without actually running the training loop.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anvil.gpu import GpuInfo
from anvil.services.compute.training_engine import TrainingEngine
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
        result.adapter_id = None

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
        result.adapter_id = None

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
        result.adapter_id = None

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
        result.adapter_id = None

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


########################################################################
# StartTrainingRun
########################################################################


class TestStartTrainingRun:
    """Tests for TrainingRunService.start_training_run()."""

    @pytest.mark.asyncio
    async def test_creates_run_and_returns_metadata(self) -> None:
        """Returns run metadata dict on successful start."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_svc = _make_training_run_svc(tmpdir)
            config = TrainingRunConfig(method="full")

            with (
                patch.object(run_svc, "_log_dataset_metadata", AsyncMock()),
                patch.object(run_svc, "_validate_warm_start", AsyncMock()),
                patch(
                    "anvil.services.training.training_run_service.detect_gpu"
                ) as mock_detect,
                patch(
                    "anvil.services.training.training_run_service.resolve_backend"
                ) as mock_resolve,
                patch(
                    "anvil.services.training.training_run_service."
                    "MPSMetricsCollector.is_available",
                    return_value=False,
                ),
            ):
                mock_detect.return_value = GpuInfo(available=False)
                mock_resolve.return_value = {
                    "engine": TrainingEngine.STDLIB,
                    "device": "cpu",
                }

                result = await run_svc.start_training_run(config=config)

            assert result["run_id"] == 42
            assert result["mlflow_run_id"] == "mlflow_1"
            assert result["experiment_id"] == 99
            assert result["status"] == "running"
            assert result["tracking"] == "active"

            if 42 in run_svc._tasks:
                run_svc._tasks[42].cancel()

    @pytest.mark.asyncio
    async def test_creates_background_task(self) -> None:
        """Creates an asyncio.Task and registers in _tasks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_svc = _make_training_run_svc(tmpdir)
            config = TrainingRunConfig(method="full")

            with (
                patch.object(run_svc, "_log_dataset_metadata", AsyncMock()),
                patch.object(run_svc, "_validate_warm_start", AsyncMock()),
                patch(
                    "anvil.services.training.training_run_service.detect_gpu"
                ) as mock_detect,
                patch(
                    "anvil.services.training.training_run_service.resolve_backend"
                ) as mock_resolve,
                patch(
                    "anvil.services.training.training_run_service."
                    "MPSMetricsCollector.is_available",
                    return_value=False,
                ),
            ):
                mock_detect.return_value = GpuInfo(available=False)
                mock_resolve.return_value = {
                    "engine": TrainingEngine.STDLIB,
                    "device": "cpu",
                }

                await run_svc.start_training_run(config=config)

            assert 42 in run_svc._tasks
            assert isinstance(run_svc._tasks[42], asyncio.Task)

            run_svc._tasks[42].cancel()

    @pytest.mark.asyncio
    async def test_raises_on_invalid_hparams(self) -> None:
        """Raises ValueError when hparams validation fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_svc = _make_training_run_svc(tmpdir)
            config = TrainingRunConfig(n_embd=4, n_head=8, block_size=16)

            with (
                patch.object(run_svc, "_log_dataset_metadata", AsyncMock()),
                patch.object(run_svc, "_validate_warm_start", AsyncMock()),
                patch(
                    "anvil.services.training.training_run_service.detect_gpu"
                ) as mock_detect,
                patch(
                    "anvil.services.training.training_run_service.resolve_backend"
                ) as mock_resolve,
                patch(
                    "anvil.services.training.training_run_service."
                    "MPSMetricsCollector.is_available",
                    return_value=False,
                ),
            ):
                mock_detect.return_value = GpuInfo(available=False)
                mock_resolve.return_value = {
                    "engine": TrainingEngine.STDLIB,
                    "device": "cpu",
                }

                with pytest.raises(ValueError, match="exceeds"):
                    await run_svc.start_training_run(config=config)

    @pytest.mark.asyncio
    async def test_raises_on_invalid_method(self) -> None:
        """Raises ValueError when method validation fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_svc = _make_training_run_svc(tmpdir)
            config = TrainingRunConfig(method="full", lora_rank=4)

            with (
                patch.object(run_svc, "_log_dataset_metadata", AsyncMock()),
                patch.object(run_svc, "_validate_warm_start", AsyncMock()),
                patch(
                    "anvil.services.training.training_run_service.detect_gpu"
                ) as mock_detect,
                patch(
                    "anvil.services.training.training_run_service.resolve_backend"
                ) as mock_resolve,
                patch(
                    "anvil.services.training.training_run_service."
                    "MPSMetricsCollector.is_available",
                    return_value=False,
                ),
            ):
                mock_detect.return_value = GpuInfo(available=False)
                mock_resolve.return_value = {
                    "engine": TrainingEngine.STDLIB,
                    "device": "cpu",
                }

                with pytest.raises(ValueError, match="lora_\\*"):
                    await run_svc.start_training_run(config=config)

    @pytest.mark.asyncio
    async def test_calls_validate_warm_start_with_base_model_ref(self) -> None:
        """Calls _validate_warm_start when base_model_ref is set."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_svc = _make_training_run_svc(tmpdir)
            config = TrainingRunConfig(method="full", base_model_ref=1)

            mock_validate = AsyncMock()
            with (
                patch.object(run_svc, "_validate_warm_start", mock_validate),
                patch.object(run_svc, "_log_dataset_metadata", AsyncMock()),
                patch(
                    "anvil.services.training.training_run_service.detect_gpu"
                ) as mock_detect,
                patch(
                    "anvil.services.training.training_run_service.resolve_backend"
                ) as mock_resolve,
                patch(
                    "anvil.services.training.training_run_service."
                    "MPSMetricsCollector.is_available",
                    return_value=False,
                ),
            ):
                mock_detect.return_value = GpuInfo(available=False)
                mock_resolve.return_value = {
                    "engine": TrainingEngine.STDLIB,
                    "device": "cpu",
                }

                await run_svc.start_training_run(config=config)

            mock_validate.assert_called_once()
            if 42 in run_svc._tasks:
                run_svc._tasks[42].cancel()

    @pytest.mark.asyncio
    async def test_calls_resolve_backend_with_correct_params(self) -> None:
        """Calls resolve_backend with the right config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_svc = _make_training_run_svc(tmpdir)
            config = TrainingRunConfig(method="full", compute_backend="local-cpu")

            with (
                patch.object(run_svc, "_log_dataset_metadata", AsyncMock()),
                patch.object(run_svc, "_validate_warm_start", AsyncMock()),
                patch(
                    "anvil.services.training.training_run_service.detect_gpu"
                ) as mock_detect,
                patch(
                    "anvil.services.training.training_run_service.resolve_backend"
                ) as mock_resolve,
                patch(
                    "anvil.services.training.training_run_service."
                    "MPSMetricsCollector.is_available",
                    return_value=False,
                ),
            ):
                mock_detect.return_value = GpuInfo(available=False)
                mock_resolve.return_value = {
                    "engine": TrainingEngine.STDLIB,
                    "device": "cpu",
                }

                await run_svc.start_training_run(config=config)

            mock_resolve.assert_called_once_with(
                {"compute_backend": "local-cpu", "method": "full"}
            )

            if 42 in run_svc._tasks:
                run_svc._tasks[42].cancel()

    @pytest.mark.asyncio
    async def test_calls_estimate_memory_for_torch_backend(self) -> None:
        """Calls estimate_training_memory when engine is TORCH."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_svc = _make_training_run_svc(tmpdir)
            config = TrainingRunConfig(method="full", n_embd=16, n_head=4, n_layer=1)

            with (
                patch.object(run_svc, "_log_dataset_metadata", AsyncMock()),
                patch.object(run_svc, "_validate_warm_start", AsyncMock()),
                patch(
                    "anvil.services.training.training_run_service.detect_gpu"
                ) as mock_detect,
                patch(
                    "anvil.services.training.training_run_service.resolve_backend"
                ) as mock_resolve,
                patch(
                    "anvil.services.training.training_run_service."
                    "estimate_training_memory"
                ) as mock_mem,
                patch(
                    "anvil.services.training.training_run_service."
                    "MPSMetricsCollector.is_available",
                    return_value=False,
                ),
            ):
                mock_detect.return_value = GpuInfo(
                    available=True, backend="cuda", device_name="Test GPU"
                )
                mock_resolve.return_value = {
                    "engine": TrainingEngine.TORCH,
                    "device": "cuda:0",
                }
                mock_mem.return_value = MagicMock(
                    would_oom=False,
                    peak_gb=2.0,
                    available_gb=8.0,
                    device_backend="cuda",
                    device_name="Test GPU",
                    param_count=100_000,
                    weights_bytes=400_000,
                    gradients_bytes=400_000,
                    optimizer_bytes=800_000,
                    kv_cache_bytes=200_000,
                    warnings=[],
                )

                await run_svc.start_training_run(config=config)

            mock_mem.assert_called_once()

            if 42 in run_svc._tasks:
                run_svc._tasks[42].cancel()

    @pytest.mark.asyncio
    async def test_stores_run_metadata(self) -> None:
        """Calls store_run_metadata on the underlying svc."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_svc = _make_training_run_svc(tmpdir)
            config = TrainingRunConfig(method="full")

            with (
                patch.object(run_svc, "_log_dataset_metadata", AsyncMock()),
                patch.object(run_svc, "_validate_warm_start", AsyncMock()),
                patch(
                    "anvil.services.training.training_run_service.detect_gpu"
                ) as mock_detect,
                patch(
                    "anvil.services.training.training_run_service.resolve_backend"
                ) as mock_resolve,
                patch(
                    "anvil.services.training.training_run_service."
                    "MPSMetricsCollector.is_available",
                    return_value=False,
                ),
            ):
                mock_detect.return_value = GpuInfo(available=False)
                mock_resolve.return_value = {
                    "engine": TrainingEngine.STDLIB,
                    "device": "cpu",
                }

                await run_svc.start_training_run(config=config)

            run_svc._svc.store_run_metadata.assert_called_once_with(
                42,
                mlflow_run_id="mlflow_1",
                experiment_id=99,
            )

            if 42 in run_svc._tasks:
                run_svc._tasks[42].cancel()


########################################################################
# ValidateWarmStart
########################################################################


class TestValidateWarmStart:
    """Tests for TrainingRunService._validate_warm_start()."""

    @pytest.mark.asyncio
    async def test_passes_when_architecture_matches(self) -> None:
        """Passes when base model architecture matches config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_svc = _make_training_run_svc(tmpdir)
            config = TrainingRunConfig(
                method="full",
                base_model_ref=1,
                n_embd=64,
                n_layer=4,
                n_head=8,
                block_size=32,
            )

            mock_model = MagicMock()
            mock_model.model.n_embd = 64
            mock_model.model.n_layer = 4
            mock_model.model.n_head = 8
            mock_model.model.block_size = 32

            mock_inference = MagicMock()
            mock_inference.load_model = AsyncMock(return_value=mock_model)

            with patch(
                "anvil.services.training.training_run_service.InferenceService",
                return_value=mock_inference,
            ):
                await run_svc._validate_warm_start(config)

            mock_inference.load_model.assert_called_once_with(model_id=1)

    @pytest.mark.asyncio
    async def test_raises_when_n_embd_mismatch(self) -> None:
        """Raises ValueError when n_embd conflicts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_svc = _make_training_run_svc(tmpdir)
            config = TrainingRunConfig(
                method="full",
                base_model_ref=1,
                n_embd=128,
                n_layer=4,
                n_head=8,
                block_size=32,
            )

            mock_model = MagicMock()
            mock_model.model.n_embd = 64
            mock_model.model.n_layer = 4
            mock_model.model.n_head = 8
            mock_model.model.block_size = 32

            mock_inference = MagicMock()
            mock_inference.load_model = AsyncMock(return_value=mock_model)

            with patch(
                "anvil.services.training.training_run_service.InferenceService",
                return_value=mock_inference,
            ):
                with pytest.raises(ValueError, match="n_embd"):
                    await run_svc._validate_warm_start(config)

    @pytest.mark.asyncio
    async def test_raises_when_n_layer_mismatch(self) -> None:
        """Raises ValueError when n_layer conflicts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_svc = _make_training_run_svc(tmpdir)
            config = TrainingRunConfig(
                method="full",
                base_model_ref=1,
                n_embd=64,
                n_layer=8,
                n_head=8,
                block_size=32,
            )

            mock_model = MagicMock()
            mock_model.model.n_embd = 64
            mock_model.model.n_layer = 4
            mock_model.model.n_head = 8
            mock_model.model.block_size = 32

            mock_inference = MagicMock()
            mock_inference.load_model = AsyncMock(return_value=mock_model)

            with patch(
                "anvil.services.training.training_run_service.InferenceService",
                return_value=mock_inference,
            ):
                with pytest.raises(ValueError, match="n_layer"):
                    await run_svc._validate_warm_start(config)

    @pytest.mark.asyncio
    async def test_raises_when_n_head_mismatch(self) -> None:
        """Raises ValueError when n_head conflicts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_svc = _make_training_run_svc(tmpdir)
            config = TrainingRunConfig(
                method="full",
                base_model_ref=1,
                n_embd=64,
                n_layer=4,
                n_head=4,
                block_size=32,
            )

            mock_model = MagicMock()
            mock_model.model.n_embd = 64
            mock_model.model.n_layer = 4
            mock_model.model.n_head = 8
            mock_model.model.block_size = 32

            mock_inference = MagicMock()
            mock_inference.load_model = AsyncMock(return_value=mock_model)

            with patch(
                "anvil.services.training.training_run_service.InferenceService",
                return_value=mock_inference,
            ):
                with pytest.raises(ValueError, match="n_head"):
                    await run_svc._validate_warm_start(config)

    @pytest.mark.asyncio
    async def test_raises_when_block_size_mismatch(self) -> None:
        """Raises ValueError when block_size conflicts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_svc = _make_training_run_svc(tmpdir)
            config = TrainingRunConfig(
                method="full",
                base_model_ref=1,
                n_embd=64,
                n_layer=4,
                n_head=8,
                block_size=64,
            )

            mock_model = MagicMock()
            mock_model.model.n_embd = 64
            mock_model.model.n_layer = 4
            mock_model.model.n_head = 8
            mock_model.model.block_size = 32

            mock_inference = MagicMock()
            mock_inference.load_model = AsyncMock(return_value=mock_model)

            with patch(
                "anvil.services.training.training_run_service.InferenceService",
                return_value=mock_inference,
            ):
                with pytest.raises(ValueError, match="block_size"):
                    await run_svc._validate_warm_start(config)

    @pytest.mark.asyncio
    async def test_noop_when_base_model_ref_is_none(self) -> None:
        """Returns immediately when base_model_ref is None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_svc = _make_training_run_svc(tmpdir)
            config = TrainingRunConfig(method="full", base_model_ref=None)

            with patch(
                "anvil.services.training.training_run_service.InferenceService"
            ) as mock_inference_cls:
                await run_svc._validate_warm_start(config)
                mock_inference_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_noop_when_method_is_not_full(self) -> None:
        """Returns immediately when method is not 'full'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_svc = _make_training_run_svc(tmpdir)
            config = TrainingRunConfig(method="lora", base_model_ref=1, lora_rank=4)

            with patch(
                "anvil.services.training.training_run_service.InferenceService"
            ) as mock_inference_cls:
                await run_svc._validate_warm_start(config)
                mock_inference_cls.assert_not_called()


########################################################################
# ResolveTrainingBackend
########################################################################


class TestResolveTrainingBackend:
    """Tests for TrainingRunService._resolve_training_backend()."""

    @pytest.mark.asyncio
    async def test_resolves_auto_backend(self) -> None:
        """Returns (engine, device) for 'auto' backend."""
        with patch(
            "anvil.services.training.training_run_service.resolve_backend"
        ) as mock_resolve:
            mock_resolve.return_value = {
                "engine": TrainingEngine.STDLIB,
                "device": "cpu",
            }
            engine, device = TrainingRunService._resolve_training_backend("auto")
            assert engine == TrainingEngine.STDLIB
            assert device == "cpu"

    @pytest.mark.asyncio
    async def test_resolves_local_cpu_backend(self) -> None:
        """Returns (engine, device) for 'local-cpu' backend."""
        with patch(
            "anvil.services.training.training_run_service.resolve_backend"
        ) as mock_resolve:
            mock_resolve.return_value = {
                "engine": TrainingEngine.STDLIB,
                "device": "cpu",
            }
            engine, device = TrainingRunService._resolve_training_backend("local-cpu")
            assert engine == TrainingEngine.STDLIB
            assert device == "cpu"

    @pytest.mark.asyncio
    async def test_resolves_local_gpu_backend(self) -> None:
        """Returns (engine, device) for 'local-gpu' backend."""
        with patch(
            "anvil.services.training.training_run_service.resolve_backend"
        ) as mock_resolve:
            mock_resolve.return_value = {
                "engine": TrainingEngine.TORCH,
                "device": "cuda:0",
            }
            engine, device = TrainingRunService._resolve_training_backend("local-gpu")
            assert engine == TrainingEngine.TORCH
            assert device == "cuda:0"

    @pytest.mark.asyncio
    async def test_passes_method_to_resolve_backend(self) -> None:
        """Forwards the method parameter to resolve_backend."""
        with patch(
            "anvil.services.training.training_run_service.resolve_backend"
        ) as mock_resolve:
            mock_resolve.return_value = {
                "engine": TrainingEngine.STDLIB,
                "device": "cpu",
            }
            TrainingRunService._resolve_training_backend("auto", method="lora")
            mock_resolve.assert_called_once_with(
                {"compute_backend": "auto", "method": "lora"}
            )


########################################################################
# EstimateMemory
########################################################################


class TestEstimateMemory:
    """Tests for TrainingRunService._estimate_memory()."""

    @pytest.mark.asyncio
    async def test_returns_none_for_stdlib_backend(self) -> None:
        """Returns None when engine_backend is not TORCH."""
        gpu_info = MagicMock()
        config = TrainingRunConfig()
        result = TrainingRunService._estimate_memory(
            TrainingEngine.STDLIB, config, gpu_info
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_estimate_for_torch_backend(self) -> None:
        """Returns MemoryEstimate for TORCH engine backends."""
        gpu_info = GpuInfo(available=True, backend="cuda")
        config = TrainingRunConfig(n_embd=64, n_head=4, n_layer=2, block_size=32)

        with patch(
            "anvil.services.training.training_run_service.estimate_training_memory"
        ) as mock_estimate:
            mock_estimate.return_value = MagicMock(
                would_oom=False,
                peak_gb=1.5,
                available_gb=8.0,
                device_backend="cuda",
                device_name="Test GPU",
                param_count=50_000,
                weights_bytes=200_000,
                gradients_bytes=200_000,
                optimizer_bytes=400_000,
                kv_cache_bytes=100_000,
                warnings=[],
            )

            result = TrainingRunService._estimate_memory(
                TrainingEngine.TORCH, config, gpu_info
            )

            assert result is not None
            assert result.peak_gb == 1.5

    @pytest.mark.asyncio
    async def test_raises_when_would_oom(self) -> None:
        """Raises ValueError when model would OOM the GPU."""
        gpu_info = GpuInfo(
            available=True,
            backend="cuda",
            device_name="Small GPU",
        )
        config = TrainingRunConfig(n_embd=256, n_head=8, n_layer=4, block_size=64)

        with patch(
            "anvil.services.training.training_run_service.estimate_training_memory"
        ) as mock_estimate:
            mock_estimate.return_value = MagicMock(
                would_oom=True,
                peak_gb=16.0,
                available_gb=4.0,
                device_backend="cuda",
                device_name="Small GPU",
                param_count=1_000_000,
                weights_bytes=4_000_000,
                gradients_bytes=4_000_000,
                optimizer_bytes=8_000_000,
                kv_cache_bytes=2_000_000,
                warnings=["Model may exceed GPU memory"],
            )

            with pytest.raises(ValueError, match="OOM"):
                TrainingRunService._estimate_memory(
                    TrainingEngine.TORCH, config, gpu_info
                )


########################################################################
# SetupMlflowRun
########################################################################


class TestSetupMlflowRun:
    """Tests for TrainingRunService._setup_mlflow_run()."""

    @pytest.mark.asyncio
    async def test_logs_hyperparameters_as_params(self) -> None:
        """Logs hyperparameters via tracking.start_run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_svc = _make_training_run_svc(tmpdir)
            config = TrainingRunConfig(
                method="full",
                n_embd=32,
                n_layer=2,
                n_head=4,
                block_size=16,
                num_steps=500,
                learning_rate=0.01,
                beta1=0.85,
                beta2=0.99,
                temperature=0.5,
                compute_backend="auto",
                dataset_id=None,
                corpus_id=None,
                content_version_id=None,
            )
            gpu_info = GpuInfo(available=False)
            engine_backend = TrainingEngine.STDLIB
            device = "cpu"

            mlflow_run_id, experiment_id = await run_svc._setup_mlflow_run(
                config=config,
                run_id=42,
                engine_backend=engine_backend,
                device=device,
                gpu_info=gpu_info,
            )

            assert mlflow_run_id == "mlflow_1"
            assert experiment_id == 99

            run_svc._tracking.start_run.assert_called_once()
            call_kwargs = run_svc._tracking.start_run.call_args[1]
            assert call_kwargs["engine_backend"] == TrainingEngine.STDLIB
            assert call_kwargs["device"] == "cpu"
            params = call_kwargs["params"]
            assert params["n_embd"] == 32
            assert params["n_layer"] == 2
            assert params["num_steps"] == 500
            assert params["learning_rate"] == 0.01

    @pytest.mark.asyncio
    async def test_sets_anvil_status_running_tag(self) -> None:
        """Sets anvil.status=running tag on the MLflow run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_svc = _make_training_run_svc(tmpdir)
            config = TrainingRunConfig(method="full")
            gpu_info = GpuInfo(available=False)
            engine_backend = TrainingEngine.STDLIB
            device = "cpu"

            await run_svc._setup_mlflow_run(
                config=config,
                run_id=42,
                engine_backend=engine_backend,
                device=device,
                gpu_info=gpu_info,
            )

            run_svc._tracking.set_tag.assert_any_call(
                "mlflow_1", "anvil.status", "running"
            )

    @pytest.mark.asyncio
    async def test_sets_anvil_experiment_id_tag(self) -> None:
        """Sets anvil.experiment_id tag on the MLflow run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_svc = _make_training_run_svc(tmpdir)
            config = TrainingRunConfig(method="full")
            gpu_info = GpuInfo(available=False)
            engine_backend = TrainingEngine.STDLIB
            device = "cpu"

            await run_svc._setup_mlflow_run(
                config=config,
                run_id=42,
                engine_backend=engine_backend,
                device=device,
                gpu_info=gpu_info,
            )

            run_svc._tracking.set_tag.assert_any_call(
                "mlflow_1", "anvil.experiment_id", "99"
            )

    @pytest.mark.asyncio
    async def test_includes_gpu_info_in_params(self) -> None:
        """Includes GPU availability and device name in hyperparams."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_svc = _make_training_run_svc(tmpdir)
            config = TrainingRunConfig(method="full")
            gpu_info = GpuInfo(
                available=True,
                backend="cuda",
                device_name="NVIDIA Test GPU",
                torch_version="2.1.0",
            )
            engine_backend = TrainingEngine.TORCH
            device = "cuda:0"

            await run_svc._setup_mlflow_run(
                config=config,
                run_id=42,
                engine_backend=engine_backend,
                device=device,
                gpu_info=gpu_info,
            )

            call_kwargs = run_svc._tracking.start_run.call_args[1]
            params = call_kwargs["params"]
            assert params["gpu_available"] == "True"
            assert params["gpu_backend"] == "cuda"
            assert params["gpu_device_name"] == "NVIDIA Test GPU"
            assert params["torch_version"] == "2.1.0"

    @pytest.mark.asyncio
    async def test_empty_mlflow_run_id_skips_tags(self) -> None:
        """Skips tag-setting when tracking.start_run returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_svc = _make_training_run_svc(tmpdir)
            run_svc._tracking.start_run = AsyncMock(return_value=None)
            config = TrainingRunConfig(method="full")
            gpu_info = GpuInfo(available=False)
            engine_backend = TrainingEngine.STDLIB
            device = "cpu"

            mlflow_run_id, experiment_id = await run_svc._setup_mlflow_run(
                config=config,
                run_id=42,
                engine_backend=engine_backend,
                device=device,
                gpu_info=gpu_info,
            )

            assert mlflow_run_id is None
            for call_args in run_svc._tracking.set_tag.call_args_list:
                tag_key = call_args[0][1]
                assert "anvil.status" not in tag_key


########################################################################
# IsRunActive
########################################################################


class TestIsRunActive:
    """Tests for TrainingRunService.is_run_active()."""

    @pytest.mark.asyncio
    async def test_returns_true_when_task_registered(self) -> None:
        """Returns True when run_id has a registered task."""
        svc = _make_training_run_svc("/tmp")
        task = asyncio.get_event_loop().create_task(asyncio.sleep(10))
        svc._tasks[42] = task
        assert svc.is_run_active(42)
        task.cancel()

    @pytest.mark.asyncio
    async def test_returns_false_when_no_task(self) -> None:
        """Returns False when run_id has no registered task."""
        svc = _make_training_run_svc("/tmp")
        assert not svc.is_run_active(99)

    @pytest.mark.asyncio
    async def test_returns_false_when_task_popped(self) -> None:
        """Returns False after task is removed from _tasks."""
        svc = _make_training_run_svc("/tmp")
        task = asyncio.get_event_loop().create_task(asyncio.sleep(10))
        svc._tasks[42] = task
        assert svc.is_run_active(42)
        svc._tasks.pop(42, None)
        assert not svc.is_run_active(42)
        task.cancel()

    @pytest.mark.asyncio
    async def test_returns_false_on_empty_tasks(self) -> None:
        """Returns False when _tasks dict is empty."""
        svc = _make_training_run_svc("/tmp")
        assert svc._tasks == {}
        assert not svc.is_run_active(1)


########################################################################
# Tasks property
########################################################################


class TestTasks:
    """Tests for the TrainingRunService.tasks property."""

    @pytest.mark.asyncio
    async def test_returns_empty_dict_initially(self) -> None:
        """Returns empty dict when no tasks are registered."""
        svc = _make_training_run_svc("/tmp")
        assert svc.tasks == {}

    @pytest.mark.asyncio
    async def test_returns_registered_tasks(self) -> None:
        """Returns dict with run_id keys and task references."""
        svc = _make_training_run_svc("/tmp")
        task = asyncio.get_event_loop().create_task(asyncio.sleep(10))
        svc._tasks[1] = task
        assert svc.tasks[1] is task
        task.cancel()

    @pytest.mark.asyncio
    async def test_reflects_task_additions(self) -> None:
        """Reflects newly added tasks."""
        svc = _make_training_run_svc("/tmp")
        task = asyncio.get_event_loop().create_task(asyncio.sleep(10))
        svc._tasks[2] = task
        assert 2 in svc.tasks
        task.cancel()

    @pytest.mark.asyncio
    async def test_reflects_task_removals(self) -> None:
        """Reflects removed tasks."""
        svc = _make_training_run_svc("/tmp")
        task = asyncio.get_event_loop().create_task(asyncio.sleep(10))
        svc._tasks[3] = task
        assert 3 in svc.tasks
        svc._tasks.pop(3, None)
        assert 3 not in svc.tasks
        if not task.done():
            task.cancel()
