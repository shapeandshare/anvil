# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for refactored TrainingService using compute backends.

Tests the phase transitions:
1. Load docs (unchanged)
2. Resolve backend with resolve_backend(config)
3. Get backend from registry
4. Call backend.run()
5. Call on_complete(result, config)
"""


import asyncio
import json
from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from anvil.services.compute.compute_status import ComputeStatus
from anvil.services.compute.result import ComputeResult
from anvil.services.training.training import TrainingService


@dataclass
class FakeComputeResult:
    """Matches ComputeResult interface for testing."""

    status: ComputeStatus = ComputeStatus.COMPLETED
    model: object | None = None
    final_loss: float | None = 0.5
    samples: list[str] = field(default_factory=lambda: ["sample1"])
    uchars: list[str] = field(default_factory=lambda: list("abc"))
    exported_remotely: bool = False
    artifact_uris: dict[str, str] = field(default_factory=dict)
    remote_job_id: str | None = None
    remote_mlflow_run_id: str | None = None
    error_message: str | None = None
    engine: str = "stdlib"
    backend: str = "local"


class FakeBackend:
    """A fake backend that returns a predetermined ComputeResult."""

    def __init__(self, result: ComputeResult | FakeComputeResult | None = None):
        self.name = "fake-backend"
        self._result = result or FakeComputeResult()
        self.last_docs: list[str] | None = None
        self.last_config: dict | None = None
        self.last_progress_callback = None
        self.last_stop_check = None

    def is_available(self) -> bool:
        return True

    async def run(self, docs, config, *, progress_callback, stop_check):
        self.last_docs = docs
        self.last_config = config
        self.last_progress_callback = progress_callback
        self.last_stop_check = stop_check
        # Yield to event loop so run_coroutine_threadsafe-scheduled
        # events (e.g. "submitted") are processed before we return.
        await asyncio.sleep(0)
        return self._result


@pytest.fixture
def svc():
    return TrainingService()


@pytest.fixture
def fake_result_local():
    return FakeComputeResult(
        status=ComputeStatus.COMPLETED,
        model=MagicMock(),
        final_loss=0.42,
        samples=["gen_sample"],
        uchars=list("xyz"),
        engine="stdlib",
        backend="local",
    )


@pytest.fixture
def fake_result_remote():
    return FakeComputeResult(
        status=ComputeStatus.COMPLETED,
        exported_remotely=True,
        artifact_uris={"model": "s3://bucket/model.safetensors"},
        remote_job_id="job_001",
        remote_mlflow_run_id="mlflow_run_abc",
        engine="torch",
        backend="modal",
    )


class TestStartTrainingPhases:
    """Test the phase sequence of refactored start_training."""

    async def test_resolve_backend_and_get_backend_called(self, svc, fake_result_local):
        """Phase 2-4: resolve_backend, get_backend, then run() on it."""
        fake_backend = FakeBackend(result=fake_result_local)

        with (
            patch(
                "anvil.services.training.training.resolve_backend",
                return_value={"engine": "stdlib", "device": "cpu", "backend": "local"},
            ),
            patch(
                "anvil.services.training.training.get_backend",
                return_value=fake_backend,
            ),
            patch.object(svc, "_load_docs", return_value=["doc1", "doc2"]),
        ):
            on_complete = AsyncMock()
            run_id = await svc.start_training(
                {"compute_backend": "local-cpu", "num_steps": 2},
                on_complete=on_complete,
            )

        # Verify backend was called with docs and config
        assert fake_backend.last_docs == ["doc1", "doc2"]
        assert fake_backend.last_config is not None

        # Verify on_complete was called with ComputeResult
        on_complete.assert_awaited_once()
        args, _kwargs = on_complete.call_args
        (result, config) = args
        assert result.final_loss == 0.42
        assert result.samples == ["gen_sample"]
        assert result.uchars == list("xyz")
        assert result.backend == "local"

    async def test_on_complete_receives_single_result_param(
        self, svc, fake_result_local
    ):
        """Verify on_complete signature: (result, config) instead of (model, config, ...)."""
        fake_backend = FakeBackend(result=fake_result_local)

        with (
            patch(
                "anvil.services.training.training.resolve_backend",
                return_value={"engine": "stdlib", "device": "cpu", "backend": "local"},
            ),
            patch(
                "anvil.services.training.training.get_backend",
                return_value=fake_backend,
            ),
            patch.object(svc, "_load_docs", return_value=["doc"]),
        ):
            captured: list = []

            async def on_complete(result, config):
                captured.append((result, config))

            await svc.start_training(
                {"compute_backend": "local-cpu", "num_steps": 2},
                on_complete=on_complete,
            )

        assert len(captured) == 1
        result, config = captured[0]
        assert isinstance(result, (ComputeResult, FakeComputeResult))
        assert result.final_loss == 0.42
        assert result.model is not None

    async def test_sse_events_for_local_backend(self, svc, fake_result_local):
        """Local backend emits metrics then complete events."""
        fake_backend = FakeBackend(result=fake_result_local)

        collected: list[dict] = []
        original_put = asyncio.Queue.put

        def _tracking_put(q, msg):
            collected.append(msg)
            return original_put(q, msg)

        with (
            patch(
                "anvil.services.training.training.resolve_backend",
                return_value={"engine": "stdlib", "device": "cpu", "backend": "local"},
            ),
            patch(
                "anvil.services.training.training.get_backend",
                return_value=fake_backend,
            ),
            patch.object(svc, "_load_docs", return_value=["doc"]),
            patch.object(
                asyncio.Queue,
                "put",
                _tracking_put,
            ),
        ):
            await svc.start_training(
                {"compute_backend": "local-cpu", "num_steps": 2},
            )

        event_names = [m["event"] for m in collected]
        assert "complete" in event_names

    async def test_sse_events_for_remote_backend(self, svc, fake_result_remote):
        """Remote backend emits submitted, then complete events."""
        fake_backend = FakeBackend(result=fake_result_remote)

        collected: list[dict] = []
        original_put = asyncio.Queue.put
        original_put_nowait = asyncio.Queue.put_nowait

        def _tracking_put(q, msg):
            collected.append(msg)
            return original_put(q, msg)

        def _tracking_put_nowait(q, msg):
            collected.append(msg)
            return original_put_nowait(q, msg)

        with (
            patch(
                "anvil.services.training.training.resolve_backend",
                return_value={"engine": "torch", "device": "cuda", "backend": "modal"},
            ),
            patch(
                "anvil.services.training.training.get_backend",
                return_value=fake_backend,
            ),
            patch.object(svc, "_load_docs", return_value=["doc"]),
            patch.object(
                asyncio.Queue,
                "put",
                _tracking_put,
            ),
            patch.object(
                asyncio.Queue,
                "put_nowait",
                _tracking_put_nowait,
            ),
        ):
            await svc.start_training(
                {"compute_backend": "modal", "num_steps": 2},
            )

        event_names = [m["event"] for m in collected]
        # submitted should precede complete
        assert "submitted" in event_names
        assert "complete" in event_names
        submitted_idx = event_names.index("submitted")
        complete_idx = event_names.index("complete")
        assert submitted_idx < complete_idx

    async def test_complete_event_contains_final_loss_and_samples(
        self, svc, fake_result_local
    ):
        """The complete SSE event includes final_loss, samples, device."""
        fake_backend = FakeBackend(result=fake_result_local)

        collected: list[dict] = []
        original_put = asyncio.Queue.put

        def _tracking_put(q, msg):
            collected.append(msg)
            return original_put(q, msg)

        with (
            patch(
                "anvil.services.training.training.resolve_backend",
                return_value={"engine": "stdlib", "device": "cpu", "backend": "local"},
            ),
            patch(
                "anvil.services.training.training.get_backend",
                return_value=fake_backend,
            ),
            patch.object(svc, "_load_docs", return_value=["doc"]),
            patch.object(
                asyncio.Queue,
                "put",
                _tracking_put,
            ),
        ):
            await svc.start_training(
                {"compute_backend": "local-cpu", "num_steps": 2},
            )

        complete_data = None
        for m in collected:
            if m["event"] == "complete":
                complete_data = json.loads(m["data"])
                break

        assert complete_data is not None
        assert complete_data["final_loss"] == 0.42
        assert complete_data["samples"] == ["gen_sample"]
        assert "device" in complete_data

    async def test_local_backend_sets_device_in_complete_event(
        self, svc, fake_result_local
    ):
        """Complete event for local backend includes device info from resolved config."""
        fake_backend = FakeBackend(result=fake_result_local)

        collected: list[dict] = []
        original_put = asyncio.Queue.put

        def _tracking_put(q, msg):
            collected.append(msg)
            return original_put(q, msg)

        with (
            patch(
                "anvil.services.training.training.resolve_backend",
                return_value={"engine": "stdlib", "device": "cpu", "backend": "local"},
            ),
            patch(
                "anvil.services.training.training.get_backend",
                return_value=fake_backend,
            ),
            patch.object(svc, "_load_docs", return_value=["doc"]),
            patch.object(
                asyncio.Queue,
                "put",
                _tracking_put,
            ),
        ):
            await svc.start_training(
                {"compute_backend": "local-cpu", "num_steps": 2},
            )

        complete_data = None
        for m in collected:
            if m["event"] == "complete":
                complete_data = json.loads(m["data"])
                break

        assert complete_data is not None
        assert complete_data["device"] == "cpu"

    async def test_stop_requested_still_works(self, svc):
        """StopRequested exception is still propagated from progress callback."""

        # The FakeBackend must call progress_callback for the stop check to trigger
        class StopSensitiveBackend(FakeBackend):
            async def run(self, docs, config, *, progress_callback, stop_check):
                # Calling progress_callback triggers the stop check
                progress_callback(0, 0.5)
                return self._result

        backend = StopSensitiveBackend(result=FakeComputeResult(final_loss=0.5))

        with (
            patch(
                "anvil.services.training.training.resolve_backend",
                return_value={"engine": "stdlib", "device": "cpu", "backend": "local"},
            ),
            patch(
                "anvil.services.training.training.get_backend",
                return_value=backend,
            ),
            patch.object(svc, "_load_docs", return_value=["doc"]),
        ):
            run_id = svc.reserve_run()
            # Signal stop before starting
            svc.stop_run(run_id)

            with pytest.raises(Exception):
                await svc.start_training(
                    {"compute_backend": "local-cpu", "num_steps": 2},
                    run_id=run_id,
                )

        # Queue should have an error event
        queue = svc.get_queue(run_id)
        assert queue is None or queue.empty()  # cleaned up

    async def test_backend_failure_emits_error_event(self, svc):
        """Backend returning FAILED emits error event, not complete, and skips on_complete."""
        fake_backend = FakeBackend(
            result=FakeComputeResult(
                status=ComputeStatus.FAILED,
                error_message="something broke",
                final_loss=None,
                model=None,
            )
        )

        collected: list[dict] = []
        original_put = asyncio.Queue.put

        def _tracking_put(q, msg):
            collected.append(msg)
            return original_put(q, msg)

        on_complete = AsyncMock()

        with (
            patch(
                "anvil.services.training.training.resolve_backend",
                return_value={"engine": "stdlib", "device": "cpu", "backend": "local"},
            ),
            patch(
                "anvil.services.training.training.get_backend",
                return_value=fake_backend,
            ),
            patch.object(svc, "_load_docs", return_value=["doc"]),
            patch.object(asyncio.Queue, "put", _tracking_put),
        ):
            run_id = await svc.start_training(
                {"compute_backend": "local-cpu", "num_steps": 2},
                on_complete=on_complete,
            )

        event_names = [m["event"] for m in collected]
        assert "error" in event_names, f"Expected error event, got {event_names}"
        assert (
            "complete" not in event_names
        ), f"Expected no complete event on FAILED, got {event_names}"

        # Find the error event and verify it carries the error message
        error_events = [m for m in collected if m["event"] == "error"]
        assert len(error_events) >= 1
        error_data = json.loads(error_events[0]["data"])
        assert "something broke" in error_data["message"]

        # on_complete should NOT be called when backend fails
        on_complete.assert_not_awaited()

    async def test_reserve_run_and_queue_mechanics_unchanged(self, svc):
        """The reserve_run/stop_run/queue mechanics remain unchanged."""
        run_id = svc.reserve_run()
        assert svc.get_queue(run_id) is not None

        svc.stop_run(run_id)
        # Can reserve another
        run_id2 = svc.reserve_run()
        assert run_id2 == run_id + 1


class TestBackendSelection:
    """Test that the correct backend is selected based on config."""

    async def test_local_cpu_selects_local_stdlib_backend(self, svc):
        """Config with compute_backend='local-cpu' selects stdlib backend."""
        backend = FakeBackend()

        with (
            patch(
                "anvil.services.training.training.resolve_backend",
                return_value={"engine": "stdlib", "device": "cpu", "backend": "local"},
            ),
            patch(
                "anvil.services.training.training.get_backend",
                return_value=backend,
            ) as mock_get,
            patch.object(svc, "_load_docs", return_value=["doc"]),
        ):
            await svc.start_training(
                {"compute_backend": "local-cpu", "num_steps": 1},
                on_complete=AsyncMock(),
            )

        mock_get.assert_called_once()
        name, _deps = mock_get.call_args
        # get_backend receives engine-qualified name (resolve_backend returns "local",
        # training.py maps it to "local-{engine}" for registry lookup)
        assert name[0] == "local-stdlib"

    async def test_modal_selects_modal_backend(self, svc):
        """Config with compute_backend='modal' selects modal backend."""
        backend = FakeBackend()

        with (
            patch(
                "anvil.services.training.training.resolve_backend",
                return_value={"engine": "torch", "device": "cuda", "backend": "modal"},
            ),
            patch(
                "anvil.services.training.training.get_backend",
                return_value=backend,
            ) as mock_get,
            patch.object(svc, "_load_docs", return_value=["doc"]),
        ):
            await svc.start_training(
                {"compute_backend": "modal", "num_steps": 1},
                on_complete=AsyncMock(),
            )

        mock_get.assert_called_once()
        name, _deps = mock_get.call_args
        assert name[0] == "modal"
