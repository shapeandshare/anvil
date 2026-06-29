# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for MPSSamplerThread — background MPS metrics sampling.

Tests the thread lifecycle (start, stop, metrics collection and
logging) by mocking ``MPSMetricsCollector`` and ``TrackingService``
so that no real subprocess or MLflow calls are made.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anvil.services.tracking.mps_sampler_thread import MPSSamplerThread


########################################################################
# Helpers
########################################################################


def _make_tracking_svc() -> MagicMock:
    """Return a MagicMock that quacks like a TrackingService with async
    ``log_metric``.
    """
    svc = MagicMock()
    svc.log_metric = AsyncMock()
    return svc


########################################################################
# MPSSamplerThread tests
########################################################################


class TestMPSSamplerThread:
    """Thread lifecycle and metric-sampling behaviour."""

    def test_thread_created_as_daemon(self) -> None:
        """The thread is created as a daemon with the expected name."""
        svc = _make_tracking_svc()
        t = MPSSamplerThread(svc, run_id="test-run", interval=0.01)
        assert t.daemon is True
        assert t.name == "mps-metrics-sampler"
        assert t._run_id == "test-run"
        assert t._interval == 0.01

    def test_stop_before_start(self) -> None:
        """Calling stop() before start() is a no-op (event is simply
        set).
        """
        svc = _make_tracking_svc()
        t = MPSSamplerThread(svc, run_id="test-run")
        t.stop()  # must not raise
        assert t._stop_event.is_set()

    def test_stop_sets_event(self) -> None:
        """stop() sets the internal stop event."""
        svc = _make_tracking_svc()
        t = MPSSamplerThread(svc, run_id="test-run")
        t.stop()
        assert t._stop_event.is_set()

    @patch(
        "anvil.services.tracking.mps_sampler_thread.MPSMetricsCollector.get_utilization",
        return_value=42.0,
    )
    @patch(
        "anvil.services.tracking.mps_sampler_thread.MPSMetricsCollector.get_memory_gb",
        return_value=2.5,
    )
    def test_run_logs_metrics(
        self,
        mock_mem: MagicMock,
        mock_util: MagicMock,
    ) -> None:
        """The thread collects metrics and logs them via the tracking
        service during each iteration.
        """
        svc = _make_tracking_svc()
        t = MPSSamplerThread(svc, run_id="test-run", interval=0.01)

        # Start thread — it will loop and log metrics
        t.start()

        # Wait a bit for at least one iteration
        import time

        time.sleep(0.05)
        t.stop()
        t.join(timeout=2)

        # At least one log_metric call should have happened for each
        # metric name
        assert svc.log_metric.await_count >= 2

    @patch(
        "anvil.services.tracking.mps_sampler_thread.MPSMetricsCollector.get_utilization",
        return_value=None,
    )
    @patch(
        "anvil.services.tracking.mps_sampler_thread.MPSMetricsCollector.get_memory_gb",
        return_value=None,
    )
    def test_run_skips_when_none(
        self,
        mock_mem: MagicMock,
        mock_util: MagicMock,
    ) -> None:
        """When collectors return None, log_metric is not called."""
        svc = _make_tracking_svc()
        t = MPSSamplerThread(svc, run_id="test-run", interval=0.01)

        t.start()
        import time

        time.sleep(0.05)
        t.stop()
        t.join(timeout=2)

        # log_metric should NOT have been called (both values None)
        assert svc.log_metric.await_count == 0

    @patch(
        "anvil.services.tracking.mps_sampler_thread.MPSMetricsCollector.get_utilization",
        return_value=55.0,
    )
    @patch(
        "anvil.services.tracking.mps_sampler_thread.MPSMetricsCollector.get_memory_gb",
        side_effect=RuntimeError("ioreg failed"),
    )
    def test_collector_exception_caught(
        self,
        mock_mem: MagicMock,
        mock_util: MagicMock,
    ) -> None:
        """An exception in a collector is caught by the broad except
        in ``run()`` — the thread exits gracefully.
        """
        svc = _make_tracking_svc()
        t = MPSSamplerThread(svc, run_id="test-run", interval=0.01)

        t.start()
        import time

        time.sleep(0.05)
        t.stop()
        t.join(timeout=2)

        # Thread should have exited without propagating the exception
        assert not t.is_alive()

    def test_logs_metrics_with_incrementing_step(
        self,
    ) -> None:
        """log_metric is called with a step counter that increments."""
        svc = _make_tracking_svc()

        with (
            patch(
                "anvil.services.tracking.mps_sampler_thread.MPSMetricsCollector.get_utilization",
                return_value=30.0,
            ),
            patch(
                "anvil.services.tracking.mps_sampler_thread.MPSMetricsCollector.get_memory_gb",
                return_value=1.0,
            ),
        ):
            t = MPSSamplerThread(svc, run_id="test-run", interval=0.01)
            t.start()
            import time

            time.sleep(0.05)
            t.stop()
            t.join(timeout=2)

            # Verify log_metric was called with step=0 for the first call
            calls = svc.log_metric.await_args_list
            # Filter calls for the util metric
            util_calls = [
                c for c in calls if c.args[1] == "system/gpu_util_pct"
            ]
            assert len(util_calls) >= 1
            # First call should have step=0 in kwargs
            assert util_calls[0].kwargs.get("step") == 0
