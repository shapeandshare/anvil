# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from unittest.mock import patch

import pytest

from anvil.services.tracking.tracking import TrackingService


@pytest.fixture(autouse=True)
def reset_guard():
    from anvil.services.tracking import tracking

    tracking._system_metrics_enabled = False
    yield
    tracking._system_metrics_enabled = False


def _guard():
    from anvil.services.tracking import tracking

    return tracking._system_metrics_enabled


class TestEnableSystemMetrics:
    def test_calls_enable_system_metrics_logging_once(self):
        with patch("mlflow.enable_system_metrics_logging") as mock_enable:
            TrackingService.enable_system_metrics()
            mock_enable.assert_called_once()

    def test_idempotent_does_not_call_twice(self):
        with patch("mlflow.enable_system_metrics_logging") as mock_enable:
            TrackingService.enable_system_metrics()
            TrackingService.enable_system_metrics()
            mock_enable.assert_called_once()

    def test_graceful_degradation_on_exception(self):
        with patch(
            "mlflow.enable_system_metrics_logging", side_effect=RuntimeError("no MPS")
        ):
            TrackingService.enable_system_metrics()
        assert _guard() is False

    def test_sets_guard_flag_on_success(self):
        with patch("mlflow.enable_system_metrics_logging"):
            TrackingService.enable_system_metrics()
        assert _guard() is True
