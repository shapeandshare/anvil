from unittest.mock import patch

import pytest

from anvil.services.tracking import TrackingService


@pytest.fixture(autouse=True)
def reset_guard():
    import anvil.services.tracking as mod

    mod._system_metrics_enabled = False
    yield
    mod._system_metrics_enabled = False


def _guard():
    import anvil.services.tracking as mod

    return mod._system_metrics_enabled


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
