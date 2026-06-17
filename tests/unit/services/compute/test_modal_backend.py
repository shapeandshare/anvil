"""Tests for ModalBackend with injected FakeModalRunner factory."""

from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import ANY, patch

import pytest

from anvil.services.compute.errors import ComputeBackendUnavailable
from anvil.services.compute.modal_backend import ModalBackend
from anvil.services.compute.result import ComputeResult, ComputeStatus


@dataclass
class FakeModalCall:
    """Simulates a Modal FunctionCall returned by .spawn()."""

    object_id: str = "job_mock_001"
    _status: str = "running"
    _result: dict = field(default_factory=lambda: {
        "artifact_uris": {"model": "s3://bucket/model.safetensors"},
        "mlflow_run_id": "mlflow_run_abc",
    })
    _error: str | None = None
    _cancelled: bool = False

    def get_status(self):
        return self._status

    def get(self):
        return self._result

    def get_error(self):
        return self._error

    def cancel(self):
        self._cancelled = True


class FakeModalRunner:
    """Simulates a Modal function that can be .spawn()ed."""

    def __init__(self, result_status: str = "success"):
        self.result_status = result_status
        self.last_call: FakeModalCall | None = None

    def spawn(self, docs: list[str], config: dict) -> FakeModalCall:
        call = FakeModalCall(_status=self.result_status)
        self.last_call = call
        return call


@pytest.fixture
def tiny_docs():
    return ["hello world", "goodbye moon"]


@pytest.fixture
def tiny_config():
    return {
        "num_steps": 2,
        "n_embd": 8,
        "n_head": 4,
        "n_layer": 1,
        "block_size": 8,
    }


class TestModalBackendAvailability:
    def test_is_available_returns_false_without_modal(self):
        """is_available() returns False when the modal package is not installed."""
        backend = ModalBackend(function_factory=lambda: FakeModalRunner())
        with patch("builtins.__import__", side_effect=ImportError("no modal")):
            # The import check will fail for any import, so we need
            # to use a more targeted patch
            pass

        # Better approach: patch the specific _modal_available check
        with patch("anvil.services.compute.modal_backend._MODAL_AVAILABLE", False):
            assert backend.is_available() is False

    def test_is_available_returns_true_when_modal_installed(self):
        """is_available() returns True when modal is installed."""
        backend = ModalBackend(function_factory=lambda: FakeModalRunner())
        with patch("anvil.services.compute.modal_backend._MODAL_AVAILABLE", True):
            assert backend.is_available() is True

    def test_name_property(self):
        backend = ModalBackend()
        assert backend.name == "modal"


class TestModalBackendRun:
    async def test_submit_poll_complete_cycle(self, tiny_docs, tiny_config):
        """Happy path: submit, poll, get successful result."""
        runner = FakeModalRunner(result_status="success")
        backend = ModalBackend(function_factory=lambda: runner)

        progress_calls: list[tuple[int, float]] = []

        def progress_cb(step: int, loss: float) -> None:
            progress_calls.append((step, loss))

        result = await backend.run(
            tiny_docs, tiny_config,
            progress_callback=progress_cb,
            stop_check=lambda: False,
        )

        assert runner.last_call is not None
        assert runner.last_call.object_id == "job_mock_001"

        assert isinstance(result, ComputeResult)
        assert result.status == ComputeStatus.COMPLETED
        assert result.exported_remotely is True
        assert result.remote_job_id == "job_mock_001"
        assert result.remote_mlflow_run_id == "mlflow_run_abc"
        assert result.artifact_uris == {"model": "s3://bucket/model.safetensors"}
        assert result.backend == "modal"
        assert result.engine == "torch"
        assert result.model is None  # No local model for remote

    async def test_error_path_returns_failed(self, tiny_docs, tiny_config):
        """When remote job fails, return ComputeResult with FAILED status."""
        runner = FakeModalRunner(result_status="failed")
        backend = ModalBackend(function_factory=lambda: runner)

        result = await backend.run(
            tiny_docs, tiny_config,
            progress_callback=lambda s, l: None,
            stop_check=lambda: False,
        )

        assert result.status == ComputeStatus.FAILED
        assert result.exported_remotely is True
        assert result.remote_job_id == "job_mock_001"
        assert result.error_message is not None

    async def test_stop_check_cancels_remote_job(self, tiny_docs, tiny_config):
        """When stop_check returns True, cancel the remote job."""
        runner = FakeModalRunner(result_status="running")
        backend = ModalBackend(function_factory=lambda: runner)

        cancelled = False

        async def run_with_stop():
            nonlocal cancelled
            result = await backend.run(
                tiny_docs, tiny_config,
                progress_callback=lambda s, l: None,
                stop_check=lambda: True,  # Always stop
            )
            return result

        # With stop always True, the poll loop should cancel immediately
        result = await backend.run(
            tiny_docs, tiny_config,
            progress_callback=lambda s, l: None,
            stop_check=lambda: True,
        )

        assert result.status == ComputeStatus.FAILED
        assert result.error_message is not None
        assert result.remote_job_id == "job_mock_001"

    async def test_progress_callback_receives_updates(self, tiny_docs, tiny_config):
        """progress_callback gets called with step/loss during polling."""
        runner = FakeModalRunner(result_status="running")
        backend = ModalBackend(function_factory=lambda: runner)

        calls: list[tuple[int, float]] = []

        # We need to make the poll loop terminate. Use a call counter.
        loop_count = 0

        def progress_cb(step: int, loss: float) -> None:
            nonlocal loop_count
            loop_count += 1
            calls.append((step, loss))

        # Patch asyncio.sleep to raise StopIteration after 1 iteration
        import asyncio

        original_sleep = asyncio.sleep

        class _StopPoll(Exception):
            pass

        async def _fake_sleep(duration: float) -> None:
            nonlocal loop_count
            loop_count += 1
            if loop_count > 3:
                raise _StopPoll("stop polling in test")

        # We'll test progress_callback by checking it's wired in
        # Let's use a different approach: mock to complete immediately
        pass

        # Simpler: use a runner that transitions to success
        class TransitioningCall(FakeModalCall):
            def __init__(self):
                super().__init__(_status="running")
                self.poll_count = 0

            def get_status(self):
                self.poll_count += 1
                if self.poll_count >= 2:
                    return "success"
                return "running"

            def get(self):
                return {"artifact_uris": {}, "mlflow_run_id": "run_1"}

        class TransitioningRunner:
            def spawn(self, docs, config):
                return TransitioningCall()

        backend2 = ModalBackend(function_factory=lambda: TransitioningRunner())

        with patch("asyncio.sleep", return_value=None):
            result = await backend2.run(
                tiny_docs, tiny_config,
                progress_callback=progress_cb,
                stop_check=lambda: False,
            )

        assert result.status == ComputeStatus.COMPLETED
        assert len(calls) >= 1  # At least one progress update for submission

    async def test_registered_in_registry(self):
        """ModalBackend is auto-registered in the compute registry."""
        from anvil.services.compute.registry import get_backend

        backend = get_backend("modal")
        assert isinstance(backend, ModalBackend)


class TestModalNoSecretsInPayload:
    """Ensure no secret/credential info leaks into SSE events or result data."""

    async def test_result_does_not_contain_secrets(self, tiny_docs, tiny_config):
        """ComputeResult from ModalBackend never contains secret fields."""
        runner = FakeModalRunner(result_status="success")
        backend = ModalBackend(function_factory=lambda: runner)

        result = await backend.run(
            tiny_docs, tiny_config,
            progress_callback=lambda s, l: None,
            stop_check=lambda: False,
        )

        # Check that no secret-like keys appear in the result
        sensitive_keys = {"password", "secret", "token", "credential", "api_key", "auth"}
        result_dict = {
            k: v for k, v in result.__dict__.items()
            if not k.startswith("_")
        }
        result_keys = set(str(k).lower() for k in result_dict.keys())
        assert len(result_keys & sensitive_keys) == 0, (
            f"Result contains sensitive keys: {result_keys & sensitive_keys}"
        )

        # Check artifact URIs don't contain credentials
        for uri in result.artifact_uris.values():
            assert "://" in uri, f"URI missing scheme: {uri}"
            # No inline credentials in URIs (Modal handles auth)
            assert "@" not in uri.replace("://", "___"), (
                f"URI appears to contain inline credentials: {uri}"
            )