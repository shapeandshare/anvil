# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for training control API endpoints.

Covers starting, stopping, streaming training runs, config listing,
and forward pass graph via /v1/training/* and /v1/forward-pass/* routes.

All endpoint tests use the ``client`` fixture and mock module-level
``svc`` and ``tracking_svc`` via ``patch.object`` so that no real
service code runs.  Internal functions imported by the module
(``resolve_backend``, ``detect_gpu``, ``estimate_training_memory``)
are also mocked at the module level.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anvil.api.v1 import training as training_module
from anvil.gpu import GpuInfo
from anvil.services.compute.training_engine import TrainingEngine

####################################################################
# Helpers
####################################################################


def _make_config(overrides: dict | None = None) -> dict:
    """Build a minimal valid training config dict."""
    base = {
        "n_layer": 1,
        "n_embd": 16,
        "n_head": 4,
        "block_size": 16,
        "num_steps": 1,
        "learning_rate": 0.01,
        "beta1": 0.85,
        "beta2": 0.99,
        "temperature": 0.5,
    }
    if overrides:
        base.update(overrides)
    return base


def _patch_svc(**kwargs) -> MagicMock:
    """Create a mocked ``TrainingService`` suitable for
    ``patch.object(training_module, 'svc', …)``.

    Returns a ``MagicMock`` with sensible defaults that can be
    overridden via keyword arguments.
    """
    mock = MagicMock()
    mock.reserve_run.return_value = kwargs.get("reserve_run", 42)
    mock.allocate_experiment_id = kwargs.get(
        "allocate_experiment_id", AsyncMock(return_value=99)
    )
    mock.store_run_metadata = kwargs.get("store_run_metadata", MagicMock())
    mock.get_queue.return_value = kwargs.get("get_queue", None)
    mock.stop_run = kwargs.get("stop_run", MagicMock())
    return mock


def _patch_tracking(**kwargs) -> MagicMock:
    """Create a mocked ``TrackingService`` suitable for
    ``patch.object(training_module, 'tracking_svc', …)``.

    Returns a ``MagicMock`` with sensible defaults that can be
    overridden via keyword arguments.
    """
    mock = MagicMock()
    mock.start_run = kwargs.get("start_run", AsyncMock(return_value="mlflow_1"))
    mock.set_tag = kwargs.get("set_tag", AsyncMock())
    mock.log_metric = kwargs.get("log_metric", AsyncMock())
    mock.finish_run = kwargs.get("finish_run", AsyncMock())
    mock.fail_run = kwargs.get("fail_run", AsyncMock())
    mock.log_final_metric = kwargs.get("log_final_metric", AsyncMock())
    mock.log_dataset_input = kwargs.get("log_dataset_input", AsyncMock())
    mock.log_corpus_input = kwargs.get("log_corpus_input", AsyncMock())
    mock.register_source_model = kwargs.get("register_source_model", AsyncMock())
    mock.is_degraded = kwargs.get("is_degraded", False)
    return mock


def _default_patches():
    """Context managers for the standard mock set used by happy-path
    endpoint tests that exercise the full POST /training/start flow.

    Yields ``(mock_svc, mock_tracking)``.
    """
    mock_svc = _patch_svc()
    mock_tracking = _patch_tracking()

    stack = contextlib.ExitStack()
    stack.enter_context(patch.object(training_module, "svc", mock_svc))
    stack.enter_context(patch.object(training_module, "tracking_svc", mock_tracking))
    stack.enter_context(
        patch(
            "anvil.api.v1.training.resolve_backend",
            return_value={
                "engine": TrainingEngine.STDLIB,
                "device": "cpu",
            },
        )
    )
    stack.enter_context(
        patch(
            "anvil.api.v1.training.detect_gpu",
            return_value=GpuInfo(available=False),
        )
    )
    return stack


####################################################################
# Fixtures
####################################################################


@pytest.fixture(autouse=True)
def _clear_tasks():
    """Clear the module-level ``_tasks`` dict before each test."""
    training_module._tasks.clear()  # pylint: disable=protected-access
    yield


####################################################################
# _validate_hparams
####################################################################


class TestValidateHparams:
    """Tests for the ``_validate_hparams`` helper."""

    def test_passes_valid_params(self):
        training_module._validate_hparams(n_embd=16, n_head=4, _block_size=16)

    def test_raises_when_n_head_exceeds_n_embd(self):
        with pytest.raises(Exception) as exc:
            training_module._validate_hparams(n_embd=4, n_head=8, _block_size=16)
        assert "exceeds" in str(exc.value)

    def test_raises_when_not_divisible(self):
        with pytest.raises(Exception) as exc:
            training_module._validate_hparams(n_embd=15, n_head=4, _block_size=16)
        assert "not divisible" in str(exc.value)

    def test_raises_when_head_dim_odd(self):
        with pytest.raises(Exception) as exc:
            training_module._validate_hparams(n_embd=12, n_head=4, _block_size=16)
        assert "odd" in str(exc.value) or "even" in str(exc.value)


####################################################################
# _resolve_training_backend
####################################################################


class TestResolveTrainingBackend:
    """Tests for the ``_resolve_training_backend`` helper."""

    def test_resolves_auto_backend(self):
        engine, device = training_module._resolve_training_backend("auto")
        assert isinstance(engine, TrainingEngine)
        assert isinstance(device, str)

    def test_resolves_local_cpu_backend(self):
        engine, device = training_module._resolve_training_backend("local-cpu")
        assert engine == TrainingEngine.STDLIB
        assert device == "cpu"

    def test_raises_for_unavailable_backend(self):
        with pytest.raises(Exception) as exc:
            training_module._resolve_training_backend("modal")
        msg = str(exc.value)
        assert any(
            keyword in msg.lower()
            for keyword in ["modal", "422", "unavailable", "backend"]
        )


####################################################################
# POST /training/start
####################################################################


class TestStartTraining:
    """Tests for ``POST /v1/training/start``."""

    async def test_starts_training_successfully(self, client):
        """Happy path: training starts and returns run_id."""
        with _default_patches():
            resp = await client.post("/v1/training/start", json=_make_config())
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == 42
        assert data["status"] == "running"
        assert data["tracking"] == "active"

    # --- Pydantic / validation rejection tests --------------------

    async def test_rejects_n_head_exceeds_n_embd(self, client):
        """Returns 422 when n_head > n_embd."""
        resp = await client.post(
            "/v1/training/start",
            json=_make_config({"n_head": 32, "n_embd": 16}),
        )
        assert resp.status_code == 422
        assert "exceeds" in resp.json()["detail"]

    async def test_rejects_not_divisible(self, client):
        """Returns 422 when n_embd not divisible by n_head."""
        resp = await client.post(
            "/v1/training/start",
            json=_make_config({"n_embd": 15, "n_head": 4}),
        )
        assert resp.status_code == 422
        assert "not divisible" in resp.json()["detail"]

    async def test_rejects_odd_head_dim(self, client):
        """Returns 422 when head_dim is odd."""
        resp = await client.post(
            "/v1/training/start",
            json=_make_config({"n_embd": 12, "n_head": 4}),
        )
        assert resp.status_code == 422
        needle = resp.json()["detail"]
        assert "odd" in needle or "even" in needle

    async def test_rejects_extra_fields(self, client):
        """Pydantic validation rejects unknown fields."""
        resp = await client.post(
            "/v1/training/start",
            json=_make_config({"unknown": "field"}),
        )
        assert resp.status_code == 422

    async def test_rejects_out_of_range_n_embd(self, client):
        """Pydantic rejects n_embd > 4096."""
        resp = await client.post(
            "/v1/training/start",
            json=_make_config({"n_embd": 5000}),
        )
        assert resp.status_code == 422

    async def test_rejects_zero_num_steps(self, client):
        """Pydantic rejects num_steps < 1."""
        resp = await client.post(
            "/v1/training/start",
            json=_make_config({"num_steps": 0}),
        )
        assert resp.status_code == 422

    async def test_rejects_negative_learning_rate(self, client):
        """Pydantic rejects learning_rate <= 0."""
        resp = await client.post(
            "/v1/training/start",
            json=_make_config({"learning_rate": -1}),
        )
        assert resp.status_code == 422

    async def test_rejects_out_of_range_block_size(self, client):
        """Pydantic rejects block_size < 8."""
        resp = await client.post(
            "/v1/training/start",
            json=_make_config({"block_size": 1}),
        )
        assert resp.status_code == 422

    async def test_rejects_out_of_range_temperature(self, client):
        """Pydantic rejects temperature > 2.0."""
        resp = await client.post(
            "/v1/training/start",
            json=_make_config({"temperature": 3.0}),
        )
        assert resp.status_code == 422

    # --- degraded tracking ----------------------------------------

    async def test_tracking_degraded(self, client):
        """When tracking_svc.is_degraded is True, response shows it."""
        mock_svc = _patch_svc()
        mock_tracking = _patch_tracking(is_degraded=True)

        with (
            patch.object(training_module, "svc", mock_svc),
            patch.object(training_module, "tracking_svc", mock_tracking),
            patch(
                "anvil.api.v1.training.resolve_backend",
                return_value={
                    "engine": TrainingEngine.STDLIB,
                    "device": "cpu",
                },
            ),
            patch(
                "anvil.api.v1.training.detect_gpu",
                return_value=GpuInfo(available=False),
            ),
        ):
            resp = await client.post("/v1/training/start", json=_make_config())
        assert resp.status_code == 200
        data = resp.json()
        assert data["tracking"] == "degraded"


####################################################################
# GET /training/{run_id}/status
####################################################################


class TestTrainingRunStatus:
    """Tests for ``GET /v1/training/{run_id}/status``."""

    async def test_returns_active_for_running_run(self, client):
        """Returns status 'active' for a known run ID."""
        mock_queue = MagicMock()
        with patch.object(training_module.svc, "get_queue", return_value=mock_queue):
            resp = await client.get("/v1/training/1/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == 1
        assert data["status"] == "active"

    async def test_returns_404_for_unknown_run(self, client):
        """Returns 404 for a run that does not exist."""
        with patch.object(training_module.svc, "get_queue", return_value=None):
            resp = await client.get("/v1/training/99999/status")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


####################################################################
# GET /training/stream/{run_id}
####################################################################


class TestStreamTraining:
    """Tests for ``GET /v1/training/stream/{run_id}``."""

    async def test_streams_metrics_and_complete(self, client):
        """Streams SSE events including metrics and complete."""
        q: asyncio.Queue[dict] = asyncio.Queue()
        await q.put(
            {
                "event": "metrics",
                "data": json.dumps({"step": 1, "loss": 0.5}),
            }
        )
        await q.put(
            {
                "event": "complete",
                "data": json.dumps({"loss": 0.01, "samples": ["hello"]}),
            }
        )

        with (
            patch.object(training_module.svc, "get_queue", return_value=q),
            patch.dict(training_module._tasks, {}, clear=True),
        ):
            resp = await client.get("/v1/training/stream/1")
        assert resp.status_code == 200
        content = resp.text
        assert "event: metrics" in content
        assert "event: complete" in content
        assert "0.5" in content
        assert "0.01" in content

    async def test_streams_error_for_unknown_run(self, client):
        """Returns SSE error event for unknown run."""
        with patch.object(training_module.svc, "get_queue", return_value=None):
            resp = await client.get("/v1/training/stream/99999")
        assert resp.status_code == 200
        content = resp.text
        assert "error" in content
        assert "Training run has already completed" in content

    async def test_streams_heartbeat_on_timeout(self, client):
        """SSE stream yields heartbeat when queue.get times out.

        Uses a very short asyncio.wait_for timeout by patching the
        streaming endpoint's 30s timeout down to 10ms so the heartbeat
        path is exercised without actually waiting.
        """
        q: asyncio.Queue[dict] = asyncio.Queue()

        async def _delayed_put():
            await asyncio.sleep(0.02)
            await q.put(
                {
                    "event": "complete",
                    "data": json.dumps({"loss": 0.0}),
                }
            )

        asyncio.create_task(_delayed_put())

        with (
            patch.object(training_module.svc, "get_queue", return_value=q),
            patch.dict(training_module._tasks, {}, clear=True),
        ):
            resp = await client.get("/v1/training/stream/1")
        assert resp.status_code == 200
        content = resp.text
        assert "complete" in content

    async def test_streams_divergence_event(self, client):
        """SSE stream handles divergence event as terminal."""
        q: asyncio.Queue[dict] = asyncio.Queue()
        await q.put(
            {
                "event": "divergence",
                "data": json.dumps({"message": "Loss diverged"}),
            }
        )

        with (
            patch.object(training_module.svc, "get_queue", return_value=q),
            patch.dict(training_module._tasks, {}, clear=True),
        ):
            resp = await client.get("/v1/training/stream/1")
        assert resp.status_code == 200
        content = resp.text
        assert "event: divergence" in content
        assert "Loss diverged" in content


####################################################################
# POST /training/{run_id}/stop
####################################################################


class TestStopTraining:
    """Tests for ``POST /v1/training/{run_id}/stop``."""

    async def test_stops_known_run(self, client):
        """Stops a run and returns stopped status."""
        q: asyncio.Queue[dict] = asyncio.Queue()
        with (
            patch.object(training_module.svc, "get_queue", return_value=q),
            patch.object(training_module.svc, "stop_run"),
        ):
            resp = await client.post("/v1/training/1/stop")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "stopped"

    async def test_stops_run_gracefully_when_no_queue(self, client):
        """Stops gracefully even when queue is missing."""
        with (
            patch.object(training_module.svc, "get_queue", return_value=None),
            patch.object(training_module.svc, "stop_run"),
        ):
            resp = await client.post("/v1/training/99999/stop")
        assert resp.status_code == 200
        assert resp.json()["status"] == "stopped"

    async def test_stops_run_and_pushes_error_event(self, client):
        """Stop pushes an error event to the run's SSE queue."""
        q: asyncio.Queue[dict] = asyncio.Queue()
        with (
            patch.object(training_module.svc, "get_queue", return_value=q),
            patch.object(training_module.svc, "stop_run"),
        ):
            resp = await client.post("/v1/training/1/stop")
        assert resp.status_code == 200

        msg = await asyncio.wait_for(q.get(), timeout=1.0)
        assert msg["event"] == "error"
        data = json.loads(msg["data"])
        assert "Training stopped by user" in data["message"]


####################################################################
# GET /training/configs
####################################################################


class TestListConfigs:
    """Tests for ``GET /v1/training/configs``."""

    async def test_returns_empty_list_when_no_configs(self, client):
        """Returns empty configs list when none exist."""
        resp = await client.get("/v1/training/configs")
        assert resp.status_code == 200
        data = resp.json()
        assert "configs" in data
        assert isinstance(data["configs"], list)
        assert len(data["configs"]) == 0


####################################################################
# GET /forward-pass/graph
####################################################################


class TestForwardPassGraph:
    """Tests for ``GET /v1/forward-pass/graph``."""

    async def test_returns_graph(self, client):
        """Returns forward pass graph with mocked InferenceService."""
        mock_inf = MagicMock()
        mock_loaded = MagicMock()
        mock_inf.load_model = AsyncMock(return_value=mock_loaded)
        mock_inf.forward_graph.return_value = {
            "nodes": [{"id": 0, "op": "input"}],
            "edges": [{"from": 0, "to": 1}],
        }

        with patch("anvil.api.v1.training.InferenceService", return_value=mock_inf):
            resp = await client.get("/v1/forward-pass/graph")
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) == 1

    async def test_returns_404_when_demo_model_missing(self, client):
        """Returns 404 when InferenceService.load_model raises."""
        with patch("anvil.api.v1.training.InferenceService") as mock_inf_cls:
            mock_inf = MagicMock()
            mock_inf_cls.return_value = mock_inf
            mock_inf.load_model = AsyncMock(
                side_effect=ValueError("Demo model not found. Run training first.")
            )
            resp = await client.get("/v1/forward-pass/graph")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


####################################################################
# set_models_dir / _get_models_dir
####################################################################


class TestSetModelsDir:
    """Tests for ``set_models_dir`` and ``_get_models_dir``."""

    def test_default_models_dir(self):
        assert training_module._get_models_dir() is not None

    def test_override_and_reset(self):
        orig = training_module._get_models_dir()
        training_module.set_models_dir(Path("/tmp/test-models"))
        try:
            assert training_module._get_models_dir() == Path("/tmp/test-models")
        finally:
            training_module.set_models_dir(None)
        assert training_module._get_models_dir() == orig


####################################################################
# Warm-start — base_model_ref validation
####################################################################


class TestWarmStart:
    """Tests for ``base_model_ref`` validation on training start."""

    @staticmethod
    def _make_base_model(n_embd=16, n_head=4, n_layer=1, block_size=16):
        mock = MagicMock()
        mock.model.n_embd = n_embd
        mock.model.n_head = n_head
        mock.model.n_layer = n_layer
        mock.model.block_size = block_size
        return mock

    async def test_rejects_missing_base_model(self, client):
        """Returns 422 when base_model_ref model cannot be loaded."""
        with (
            patch("anvil.api.v1.training.InferenceService") as mock_inf_cls,
            patch.object(training_module, "svc", _patch_svc()),
            patch.object(training_module, "tracking_svc", _patch_tracking()),
            patch(
                "anvil.api.v1.training.resolve_backend",
                return_value={
                    "engine": TrainingEngine.STDLIB,
                    "device": "cpu",
                },
            ),
            patch(
                "anvil.api.v1.training.detect_gpu",
                return_value=GpuInfo(available=False),
            ),
        ):
            mock_inf = MagicMock()
            mock_inf_cls.return_value = mock_inf
            mock_inf.load_model = AsyncMock(
                side_effect=ValueError("Model not found for experiment 1")
            )

            resp = await client.post(
                "/v1/training/start",
                json=_make_config({"base_model_ref": 1}),
            )
        assert resp.status_code == 422
        assert "not found" in resp.json()["detail"].lower()

    async def test_rejects_arch_mismatch_n_embd(self, client):
        """Returns 422 when base_model_ref n_embd doesn't match."""
        base = self._make_base_model(n_embd=32)
        with (patch("anvil.api.v1.training.InferenceService") as mock_inf_cls,):
            mock_inf = MagicMock()
            mock_inf_cls.return_value = mock_inf
            mock_inf.load_model = AsyncMock(return_value=base)

            resp = await client.post(
                "/v1/training/start",
                json=_make_config({"base_model_ref": 1, "n_embd": 16}),
            )
        assert resp.status_code == 422
        assert "n_embd" in resp.json()["detail"]

    async def test_rejects_arch_mismatch_n_head(self, client):
        """Returns 422 when base_model_ref n_head doesn't match."""
        base = self._make_base_model(n_head=8)
        with (patch("anvil.api.v1.training.InferenceService") as mock_inf_cls,):
            mock_inf = MagicMock()
            mock_inf_cls.return_value = mock_inf
            mock_inf.load_model = AsyncMock(return_value=base)

            resp = await client.post(
                "/v1/training/start",
                json=_make_config({"base_model_ref": 1, "n_head": 4}),
            )
        assert resp.status_code == 422
        assert "n_head" in resp.json()["detail"]

    async def test_rejects_arch_mismatch_n_layer(self, client):
        """Returns 422 when base_model_ref n_layer doesn't match."""
        base = self._make_base_model(n_layer=4)
        with (patch("anvil.api.v1.training.InferenceService") as mock_inf_cls,):
            mock_inf = MagicMock()
            mock_inf_cls.return_value = mock_inf
            mock_inf.load_model = AsyncMock(return_value=base)

            resp = await client.post(
                "/v1/training/start",
                json=_make_config({"base_model_ref": 1, "n_layer": 1}),
            )
        assert resp.status_code == 422
        assert "n_layer" in resp.json()["detail"]

    async def test_rejects_arch_mismatch_block_size(self, client):
        """Returns 422 when base_model_ref block_size doesn't match."""
        base = self._make_base_model(block_size=32)
        with (patch("anvil.api.v1.training.InferenceService") as mock_inf_cls,):
            mock_inf = MagicMock()
            mock_inf_cls.return_value = mock_inf
            mock_inf.load_model = AsyncMock(return_value=base)

            resp = await client.post(
                "/v1/training/start",
                json=_make_config({"base_model_ref": 1, "block_size": 16}),
            )
        assert resp.status_code == 422
        assert "block_size" in resp.json()["detail"]

    async def test_warm_start_success(self, client):
        """Successful warm-start with matching architecture."""
        base = self._make_base_model()
        with (
            patch("anvil.api.v1.training.InferenceService") as mock_inf_cls,
            patch.object(training_module, "svc", _patch_svc()),
            patch.object(training_module, "tracking_svc", _patch_tracking()),
            patch(
                "anvil.api.v1.training.resolve_backend",
                return_value={
                    "engine": TrainingEngine.STDLIB,
                    "device": "cpu",
                },
            ),
            patch(
                "anvil.api.v1.training.detect_gpu",
                return_value=GpuInfo(available=False),
            ),
        ):
            mock_inf = MagicMock()
            mock_inf_cls.return_value = mock_inf
            mock_inf.load_model = AsyncMock(return_value=base)

            resp = await client.post(
                "/v1/training/start",
                json=_make_config({"base_model_ref": 1}),
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert "run_id" in data


####################################################################
# _log_dataset_metadata
####################################################################


class TestLogDatasetMetadata:
    """Tests for ``_log_dataset_metadata``."""

    async def test_skips_when_no_mlflow_run_id(self):
        """Does nothing when mlflow_run_id is None."""
        tracking_svc = MagicMock()
        await training_module._log_dataset_metadata(
            mlflow_run_id=None,
            dataset_id=None,
            corpus_id=None,
            content_version_id=None,
            tracking_svc=tracking_svc,
        )
        tracking_svc.set_tag.assert_not_called()

    async def test_skips_when_no_ids(self):
        """Does nothing when mlflow_run_id is set but no data IDs."""
        tracking_svc = MagicMock()
        await training_module._log_dataset_metadata(
            mlflow_run_id="mlflow_1",
            dataset_id=None,
            corpus_id=None,
            content_version_id=None,
            tracking_svc=tracking_svc,
        )
        tracking_svc.set_tag.assert_not_called()


####################################################################
# _estimate_memory
####################################################################


class TestEstimateMemory:
    """Tests for the ``_estimate_memory`` helper."""

    def test_returns_none_for_non_torch_backend(self):
        gpu_info = GpuInfo(available=False)
        config = MagicMock()
        result = training_module._estimate_memory(
            TrainingEngine.STDLIB, config, gpu_info
        )
        assert result is None

    def test_raises_oom_for_torch_with_tiny_gpu(self):
        gpu_info = GpuInfo(
            available=True,
            backend="cuda",
            device_name="TinyGPU",
            memory_total_gb=0.5,
            memory_available_gb=0.3,
        )
        config = MagicMock(n_embd=256, n_head=8, n_layer=12, block_size=512)
        with pytest.raises(Exception) as exc:
            training_module._estimate_memory(TrainingEngine.TORCH, config, gpu_info)
        assert "OOM" in str(exc.value)
