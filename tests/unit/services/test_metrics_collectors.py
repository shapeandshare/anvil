import asyncio
import threading
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

FAKE_IOREG_OUTPUT = (
    '"PerformanceStatistics" = {"Tiler Utilization %" = 5,'
    '"Device Utilization %" = 23,"Renderer Utilization %" = 22,'
    '"In use system memory" = 458113024,"Alloc system memory" = 3730522112}'
)

FAKE_IOREG_EMPTY = ""


class FakeCompletedProcess:
    def __init__(self, stdout: str, returncode: int = 0):
        self.stdout = stdout
        self.stderr = ""
        self.returncode = returncode


@pytest.fixture(autouse=True)
def fake_platform():
    with (
        patch("platform.system", return_value="Darwin"),
        patch("platform.processor", return_value="arm"),
    ):
        yield


def _svc_and_mock_run():
    import anvil.services.metrics_collectors as mc

    return mc


class TestMPSMetricsCollector:
    def test_get_utilization_returns_float_when_ioreg_valid(self):
        mc_mod = _svc_and_mock_run()
        with patch(
            "subprocess.run", return_value=FakeCompletedProcess(FAKE_IOREG_OUTPUT)
        ):
            result = mc_mod.MPSMetricsCollector.get_utilization()
            assert isinstance(result, float)
            assert 0.0 <= result <= 100.0
            assert result == 23.0

    def test_get_utilization_returns_none_when_ioreg_fails(self):
        mc_mod = _svc_and_mock_run()
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = mc_mod.MPSMetricsCollector.get_utilization()
            assert result is None

    def test_get_utilization_returns_none_when_ioreg_empty(self):
        mc_mod = _svc_and_mock_run()
        with patch(
            "subprocess.run", return_value=FakeCompletedProcess(FAKE_IOREG_EMPTY)
        ):
            result = mc_mod.MPSMetricsCollector.get_utilization()
            assert result is None

    def test_get_memory_gb_returns_float_when_ioreg_valid(self):
        mc_mod = _svc_and_mock_run()
        with patch(
            "subprocess.run", return_value=FakeCompletedProcess(FAKE_IOREG_OUTPUT)
        ):
            result = mc_mod.MPSMetricsCollector.get_memory_gb()
            assert isinstance(result, float)
            assert result == pytest.approx(0.4266, rel=0.01)

    def test_get_memory_gb_returns_none_when_ioreg_fails(self):
        mc_mod = _svc_and_mock_run()
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = mc_mod.MPSMetricsCollector.get_memory_gb()
            assert result is None

    def test_is_available_returns_true_on_macos_arm(self):
        mc_mod = _svc_and_mock_run()
        assert mc_mod.MPSMetricsCollector.is_available() is True

    def test_is_available_returns_false_on_non_apple(self):
        with (
            patch("platform.system", return_value="Linux"),
            patch("platform.processor", return_value="x86_64"),
        ):
            mc_mod = _svc_and_mock_run()
            assert mc_mod.MPSMetricsCollector.is_available() is False

    def test_graceful_degradation_when_not_apple_silicon(self):
        with patch("platform.system", return_value="Linux"):
            mc_mod = _svc_and_mock_run()
            util = mc_mod.MPSMetricsCollector.get_utilization()
            mem = mc_mod.MPSMetricsCollector.get_memory_gb()
            assert util is None
            assert mem is None

    def test_parse_ioreg_parses_correctly(self):
        mc_mod = _svc_and_mock_run()
        parsed = mc_mod.MPSMetricsCollector._parse_ioreg(FAKE_IOREG_OUTPUT)
        assert parsed["utilization_pct"] == 23.0
        assert parsed["memory_gb"] == pytest.approx(0.4266, rel=0.01)

    def test_parse_ioreg_empty_returns_nones(self):
        mc_mod = _svc_and_mock_run()
        parsed = mc_mod.MPSMetricsCollector._parse_ioreg("")
        assert parsed["utilization_pct"] is None
        assert parsed["memory_gb"] is None


class TestMPSSamplerThread:
    @pytest.mark.asyncio
    async def test_sampler_logs_metrics_at_intervals(self):
        mc_mod = _svc_and_mock_run()
        mock_tracking = MagicMock()
        mock_tracking.log_metric = AsyncMock()

        thread = mc_mod.MPSSamplerThread(mock_tracking, "run_123", interval=0.05)

        with (
            patch.object(
                mc_mod.MPSMetricsCollector, "get_utilization", return_value=45.0
            ),
            patch.object(mc_mod.MPSMetricsCollector, "get_memory_gb", return_value=1.5),
        ):
            thread.start()
            await asyncio.sleep(0.12)
            thread.stop()
            thread.join(timeout=2)

            assert mock_tracking.log_metric.await_count >= 2

    @pytest.mark.asyncio
    async def test_sampler_does_not_log_when_metrics_none(self):
        mc_mod = _svc_and_mock_run()
        mock_tracking = MagicMock()
        mock_tracking.log_metric = AsyncMock()

        thread = mc_mod.MPSSamplerThread(mock_tracking, "run_123", interval=0.05)

        with (
            patch.object(
                mc_mod.MPSMetricsCollector, "get_utilization", return_value=None
            ),
            patch.object(
                mc_mod.MPSMetricsCollector, "get_memory_gb", return_value=None
            ),
        ):
            thread.start()
            await asyncio.sleep(0.12)
            thread.stop()
            thread.join(timeout=2)

            assert mock_tracking.log_metric.await_count == 0

    @pytest.mark.asyncio
    async def test_sampler_graceful_on_exception(self):
        mc_mod = _svc_and_mock_run()
        mock_tracking = MagicMock()
        mock_tracking.log_metric = AsyncMock()

        thread = mc_mod.MPSSamplerThread(mock_tracking, "run_123", interval=0.05)

        with patch.object(
            mc_mod.MPSMetricsCollector,
            "get_utilization",
            side_effect=RuntimeError("crash"),
        ):
            thread.start()
            await asyncio.sleep(0.12)
            thread.stop()
            thread.join(timeout=2)

            assert True
