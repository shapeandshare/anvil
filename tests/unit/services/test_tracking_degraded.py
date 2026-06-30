"""Unit tests for TrackingService degraded mode — exception handling, state machine, run_id validation, thread safety, and logging.

These tests verify the refactored ``TrackingService`` that replaces the
boolean ``_degraded`` flag with a typed ``DegradedState`` state machine,
narrows exception handling to known MLflow exceptions, separates the
run_id validation gate from the degraded gate, and logs state transitions.
"""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import MagicMock, patch

import pytest

from anvil.services.tracking.tracking_status import (
    DegradedReason,
    DegradedState,
    TrackingStatus,
)


############################################################################
# Fixtures
############################################################################


@pytest.fixture
def mock_client_factory() -> MagicMock:
    """Return a factory that produces a mock MlflowClient."""
    factory = MagicMock()
    client = MagicMock()
    client.get_experiment_by_name.return_value = MagicMock(experiment_id="exp-001")
    factory.return_value = client
    return factory


@pytest.fixture
def tracking_service(mock_client_factory: MagicMock):
    """Return a TrackingService with a mock client factory."""
    from anvil.services.tracking.tracking import TrackingService

    svc = TrackingService(
        tracking_uri="http://mock:5000",
        client_factory=mock_client_factory,
    )
    return svc


############################################################################
# T003: Narrowed exception handling
############################################################################


class TestNarrowedExceptionHandling:
    """start_run and all other methods catch only known MLflow / transport
    exceptions.  TypeError, AttributeError and similar real bugs propagate.
    """

    @pytest.mark.asyncio
    async def test_start_run_enters_degraded_on_mlflow_exception(
        self, tracking_service
    ):
        """MlflowException sets degraded state."""
        from mlflow.exceptions import MlflowException

        with patch.object(
            tracking_service, "_lazy_init", side_effect=MlflowException("fail")
        ):
            run_id = await tracking_service.start_run(
                engine_backend="test", device="cpu"
            )
        assert run_id == ""
        assert tracking_service._state.status == "degraded"
        assert tracking_service._state.reason is not None

    @pytest.mark.asyncio
    async def test_start_run_enters_degraded_on_connection_error(
        self, tracking_service
    ):
        """ConnectionError sets degraded state with UNREACHABLE reason."""
        with patch.object(
            tracking_service, "_lazy_init", side_effect=ConnectionError("refused")
        ):
            run_id = await tracking_service.start_run(
                engine_backend="test", device="cpu"
            )
        assert run_id == ""
        assert tracking_service._state.reason == DegradedReason.UNREACHABLE

    @pytest.mark.asyncio
    async def test_start_run_enters_degraded_on_timeout(self, tracking_service):
        """TimeoutError sets degraded state with UNREACHABLE reason."""
        with patch.object(
            tracking_service, "_lazy_init", side_effect=TimeoutError("timed out")
        ):
            run_id = await tracking_service.start_run(
                engine_backend="test", device="cpu"
            )
        assert run_id == ""
        assert tracking_service._state.reason == DegradedReason.UNREACHABLE

    @pytest.mark.asyncio
    async def test_typeerror_propagates_in_start_run(self, tracking_service):
        """TypeError in start_run propagates — not silently caught."""
        with patch.object(
            tracking_service, "_lazy_init", side_effect=TypeError("bad type")
        ):
            with pytest.raises(TypeError):
                await tracking_service.start_run(engine_backend="test", device="cpu")

    @pytest.mark.asyncio
    async def test_typeerror_propagates_in_log_metric(self, tracking_service):
        """TypeError in log_metric propagates — not silently caught."""
        with patch.object(tracking_service, "_lazy_init", return_value=MagicMock()):
            # Force _client to be set so we get past the degraded gate
            tracking_service._client = MagicMock()

        with patch.object(
            tracking_service._client,
            "log_metric",
            side_effect=TypeError("bad arg"),
        ):
            with pytest.raises(TypeError):
                await tracking_service.log_metric("run-001", "loss", 0.5, step=1)

    @pytest.mark.asyncio
    async def test_log_metric_swallows_mlflow_exception(self, tracking_service):
        """MlflowException in log_metric is silently skipped (not propagated)."""
        from mlflow.exceptions import MlflowException

        tracking_service._client = MagicMock()
        tracking_service._client.log_metric.side_effect = MlflowException("fail")

        # Should not raise
        await tracking_service.log_metric("run-001", "loss", 0.5, step=1)

    @pytest.mark.asyncio
    async def test_attributeerror_propagates_in_finish_run(self, tracking_service):
        """AttributeError in finish_run propagates."""
        tracking_service._client = MagicMock()

        with patch.object(
            tracking_service._client,
            "set_terminated",
            side_effect=AttributeError("no attr"),
        ):
            with pytest.raises(AttributeError):
                await tracking_service.finish_run("run-001")

    @pytest.mark.asyncio
    async def test_valueerror_propagates_in_set_tag(self, tracking_service):
        """ValueError (non-empty run_id) in set_tag propagates."""
        tracking_service._client = MagicMock()

        with patch.object(
            tracking_service._client,
            "set_tag",
            side_effect=ValueError("bad value"),
        ):
            with pytest.raises(ValueError):
                await tracking_service.set_tag("run-001", "key", "value")


############################################################################
# T004: Separated run_id gate
############################################################################


class TestRunIdGate:
    """Empty run_id raises ValueError instead of silent no-op."""

    @pytest.mark.asyncio
    async def test_empty_run_id_raises_value_error(self, tracking_service):
        """log_metric with empty run_id raises ValueError."""
        tracking_service._client = MagicMock()
        with pytest.raises(ValueError, match="run_id must not be empty"):
            await tracking_service.log_metric("", "loss", 0.5)

    @pytest.mark.asyncio
    async def test_empty_run_id_finish_run_raises(self, tracking_service):
        """finish_run with empty run_id raises ValueError."""
        tracking_service._client = MagicMock()
        with pytest.raises(ValueError, match="run_id must not be empty"):
            await tracking_service.finish_run("")

    @pytest.mark.asyncio
    async def test_empty_run_id_set_tag_raises(self, tracking_service):
        """set_tag with empty run_id raises ValueError."""
        tracking_service._client = MagicMock()
        with pytest.raises(ValueError, match="run_id must not be empty"):
            await tracking_service.set_tag("", "k", "v")

    @pytest.mark.asyncio
    async def test_empty_run_id_log_artifacts_raises(self, tracking_service):
        """log_artifacts with empty run_id raises ValueError."""
        tracking_service._client = MagicMock()
        with pytest.raises(ValueError, match="run_id must not be empty"):
            await tracking_service.log_artifacts("")

    @pytest.mark.asyncio
    async def test_empty_run_id_register_source_model_raises(self, tracking_service):
        """register_source_model with empty run_id raises ValueError."""
        tracking_service._client = MagicMock()
        with pytest.raises(ValueError, match="run_id must not be empty"):
            await tracking_service.register_source_model(run_id="")

    @pytest.mark.asyncio
    async def test_empty_run_id_get_safetensors_raises(self, tracking_service):
        """get_safetensors_artifacts with empty run_id raises ValueError."""
        with pytest.raises(ValueError, match="run_id must not be empty"):
            await tracking_service.get_safetensors_artifacts("")

    @pytest.mark.asyncio
    async def test_degraded_run_id_is_empty_ok(self, tracking_service):
        """When degraded, start_run returns '' — subsequent calls with
        that run_id are handled by the degraded gate, not the validation
        gate.  The empty-run-id check is only for buggy caller code.
        """
        tracking_service._state = DegradedState.degraded(
            DegradedReason.UNREACHABLE, "offline"
        )
        # These should be silently skipped (degraded gate), not raise
        await tracking_service.log_metric("", "loss", 0.5)  # no raise
        await tracking_service.finish_run("")  # no raise
        await tracking_service.set_tag("", "k", "v")  # no raise


############################################################################
# T005: Failure mode differentiation
############################################################################


class TestFailureModeDifferentiation:
    """Each DegradedReason maps to the correct exception type."""

    @pytest.mark.asyncio
    async def test_connection_error_maps_to_unreachable(self, tracking_service):
        """ConnectionError produces UNREACHABLE reason."""
        with patch.object(
            tracking_service, "_lazy_init", side_effect=ConnectionError()
        ):
            await tracking_service.start_run(engine_backend="test", device="cpu")
        assert tracking_service._state.reason == DegradedReason.UNREACHABLE

    @pytest.mark.asyncio
    async def test_timeout_error_maps_to_unreachable(self, tracking_service):
        """TimeoutError produces UNREACHABLE reason."""
        with patch.object(tracking_service, "_lazy_init", side_effect=TimeoutError()):
            await tracking_service.start_run(engine_backend="test", device="cpu")
        assert tracking_service._state.reason == DegradedReason.UNREACHABLE

    @pytest.mark.asyncio
    async def test_oserror_maps_to_unreachable(self, tracking_service):
        """OSError produces UNREACHABLE reason."""
        with patch.object(
            tracking_service, "_lazy_init", side_effect=OSError("socket closed")
        ):
            await tracking_service.start_run(engine_backend="test", device="cpu")
        assert tracking_service._state.reason == DegradedReason.UNREACHABLE


############################################################################
# T006: Thread safety
############################################################################


class TestThreadSafety:
    """Concurrent tracking calls don't corrupt state."""

    @pytest.mark.asyncio
    async def test_concurrent_start_run_does_not_corrupt(self, tracking_service):
        """Multiple concurrent start_run calls with MlflowException
        don't leave the state machine in an inconsistent state.
        """
        from mlflow.exceptions import MlflowException

        with patch.object(
            tracking_service, "_lazy_init", side_effect=MlflowException("fail")
        ):
            results = await asyncio_gather_safe(
                [tracking_service.start_run(engine_backend="test", device="cpu")] * 5
            )

        # All should return empty string (degraded)
        assert all(r == "" for r in results)
        # State should be consistently degraded
        assert tracking_service._state.status == "degraded"
        assert tracking_service._state.reason is not None


async def asyncio_gather_safe(coros: list) -> list:
    """Run coroutines and return results, ignoring task-group issues."""
    import asyncio

    return await asyncio.gather(*coros, return_exceptions=True)


############################################################################
# T007: Logging on state transitions
############################################################################


class TestLoggingOnTransitions:
    """WARN-level log is emitted on degraded entry/exit."""

    @pytest.mark.asyncio
    async def test_degraded_entry_logs_warn(self, tracking_service, caplog):
        """Entering degraded mode produces a WARN log."""
        caplog.set_level(logging.WARN)

        with patch.object(
            tracking_service, "_lazy_init", side_effect=ConnectionError("refused")
        ):
            await tracking_service.start_run(engine_backend="test", device="cpu")

        warn_records = [r for r in caplog.records if r.levelno == logging.WARN]
        assert any("degraded" in r.getMessage().lower() for r in warn_records), (
            f"No WARN log about degraded entry found. Records: {[r.getMessage() for r in warn_records]}"
        )


############################################################################
# T014: Retry logic (US1)
############################################################################


class TestRetryLogic:
    """Automatic reconnection with exponential backoff + jitter."""

    @pytest.mark.asyncio
    async def test_active_state_returns_immediately(self, tracking_service):
        """When already active, no reconnect needed."""
        # Should return True without sleeping
        from anvil.services.tracking.tracking import _BACKOFF_INITIAL

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, tracking_service._maybe_reconnect_sync
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_non_retryable_reason_returns_false(self, tracking_service):
        """Permanent failures (auth, version mismatch) don't retry."""
        tracking_service._state = DegradedState.degraded(
            DegradedReason.AUTH_FAILURE, "bad auth"
        )
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, tracking_service._maybe_reconnect_sync
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_unreachable_retries_and_succeeds(
        self, mock_client_factory, tracking_service
    ):
        """_maybe_reconnect_sync retries and recovers when MLflow responds."""
        tracking_service._state = DegradedState.degraded(
            DegradedReason.UNREACHABLE, "offline"
        )
        tracking_service._client_factory = mock_client_factory

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, tracking_service._maybe_reconnect_sync
        )
        assert result is True
        assert tracking_service._state.status == "active"

    @pytest.mark.asyncio
    async def test_unreachable_retry_increments_count(self, tracking_service):
        """Failed retry increments retry_count."""
        tracking_service._state = DegradedState.degraded(
            DegradedReason.UNREACHABLE, "offline"
        )
        original_count = tracking_service._state.retry_count

        # Force the client factory to raise
        tracking_service._client_factory = MagicMock(
            side_effect=ConnectionError("still down")
        )

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, tracking_service._maybe_reconnect_sync
        )
        assert result is False
        assert tracking_service._state.retry_count == original_count + 1
