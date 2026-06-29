"""Tests for MLflowService — subprocess lifecycle management.

All subprocess and OS calls are mocked to avoid real side effects.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from anvil.supervisor.services import MLflowService


@pytest.fixture
def mock_config():
    with patch("anvil.supervisor.services.get_config") as mc:
        mc.return_value = {
            "log_dir": "/tmp/logs",
            "mlflow_port": 5001,
            "mlflow_uri": "http://127.0.0.1:5001",
            "mlflow_backend_store_uri": "sqlite:///mlruns/mlflow.db",
        }
        yield mc


@pytest.fixture
def mock_paths():
    paths = MagicMock()
    paths.mlruns_dir = Path("/tmp/mlruns")
    return paths


class TestInit:
    def test_defaults(self, mock_config, tmp_path):
        cfg = mock_config.return_value
        cfg["log_dir"] = str(tmp_path / "logs")
        svc = MLflowService()
        assert svc.port == 5001
        assert svc.process is None
        assert svc.mlruns_dir == Path("mlruns")

    def test_with_workspace_paths(self, mock_config, mock_paths, tmp_path):
        cfg = mock_config.return_value
        cfg["log_dir"] = str(tmp_path / "logs")
        svc = MLflowService(workspace_paths=mock_paths)
        assert svc.mlruns_dir == mock_paths.mlruns_dir


class TestIsRunning:
    def test_no_process(self, mock_config, tmp_path):
        cfg = mock_config.return_value
        cfg["log_dir"] = str(tmp_path / "logs")
        svc = MLflowService()
        assert svc.is_running is False

    def test_process_running(self, mock_config, tmp_path):
        cfg = mock_config.return_value
        cfg["log_dir"] = str(tmp_path / "logs")
        svc = MLflowService()
        svc.process = MagicMock()
        svc.process.poll.return_value = None
        assert svc.is_running is True

    def test_process_exited(self, mock_config, tmp_path):
        cfg = mock_config.return_value
        cfg["log_dir"] = str(tmp_path / "logs")
        svc = MLflowService()
        svc.process = MagicMock()
        svc.process.poll.return_value = 0
        assert svc.is_running is False


class TestTrackingUri:
    def test_returns_configured_uri(self, mock_config, tmp_path):
        cfg = mock_config.return_value
        cfg["log_dir"] = str(tmp_path / "logs")
        svc = MLflowService()
        assert svc.tracking_uri == "http://127.0.0.1:5001"


class TestStart:
    def test_noop_when_running(self, mock_config, tmp_path):
        cfg = mock_config.return_value
        cfg["log_dir"] = str(tmp_path / "logs")
        svc = MLflowService()
        svc.process = MagicMock()
        svc.process.poll.return_value = None
        with patch.object(svc, "_free_port") as fp:
            svc.start()
            fp.assert_not_called()

    def test_starts_subprocess(self, mock_config, tmp_path):
        cfg = mock_config.return_value
        cfg["log_dir"] = str(tmp_path / "logs")
        (tmp_path / "logs").mkdir(parents=True)
        svc = MLflowService()
        with (
            patch.object(svc, "_free_port"),
            patch("anvil.supervisor.services.subprocess.Popen") as popen,
        ):
            mock_proc = MagicMock()
            mock_proc.pid = 12345
            popen.return_value = mock_proc
            svc.start()
            popen.assert_called_once()
            pid_file = tmp_path / "logs" / "mlflow.pid"
            assert pid_file.read_text() == "12345"


class TestStop:
    def test_noop_when_not_running(self, mock_config, tmp_path):
        cfg = mock_config.return_value
        cfg["log_dir"] = str(tmp_path / "logs")
        (tmp_path / "logs").mkdir()
        svc = MLflowService()
        svc.stop()
        assert svc.process is None

    def test_stops_running_process(self, mock_config, tmp_path):
        cfg = mock_config.return_value
        cfg["log_dir"] = str(tmp_path / "logs")
        (tmp_path / "logs").mkdir()
        svc = MLflowService()
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_process.pid = 12345
        svc.process = mock_process
        with patch("anvil.supervisor.services.os") as mock_os:
            mock_os.killpg = MagicMock()
            mock_os.getpgid.return_value = 9999
            svc.stop()
            mock_os.killpg.assert_called_once()
            mock_process.wait.assert_called_once_with(timeout=10)
            assert svc.process is None

    def test_stop_timeout_kills(self, mock_config, tmp_path):
        cfg = mock_config.return_value
        cfg["log_dir"] = str(tmp_path / "logs")
        (tmp_path / "logs").mkdir()
        import subprocess
        svc = MLflowService()
        svc.process = MagicMock()
        svc.process.poll.return_value = None
        svc.process.pid = 12345
        svc.process.wait.side_effect = subprocess.TimeoutExpired(cmd="mlflow", timeout=10)
        with patch("anvil.supervisor.services.os") as mock_os:
            mock_os.killpg = MagicMock()
            mock_os.getpgid.return_value = 9999
            svc.stop()
            assert mock_os.killpg.call_count == 2
            assert svc.process is None


class TestAsyncStop:
    async def test_async_stop(self, mock_config, tmp_path):
        cfg = mock_config.return_value
        cfg["log_dir"] = str(tmp_path / "logs")
        (tmp_path / "logs").mkdir()
        svc = MLflowService()
        svc.process = MagicMock()
        svc.process.poll.return_value = None
        svc.process.pid = 12345
        with (
            patch("anvil.supervisor.services.os.killpg"),
            patch("anvil.supervisor.services.asyncio.to_thread"),
        ):
            await svc.async_stop()
            assert svc.process is None


class TestFreePort:
    def test_free_port_no_zombies(self, mock_config, tmp_path):
        cfg = mock_config.return_value
        cfg["log_dir"] = str(tmp_path / "logs")
        result = MagicMock()
        result.stdout = ""
        with patch("anvil.supervisor.services.subprocess.run", return_value=result):
            svc = MLflowService()
            svc._free_port()

    def test_free_port_kills_zombies(self, mock_config, tmp_path):
        cfg = mock_config.return_value
        cfg["log_dir"] = str(tmp_path / "logs")
        lsof_result = MagicMock()
        lsof_result.stdout = "9876\n"
        ps_result = MagicMock()
        ps_result.stdout = "python3\n"
        with (
            patch(
                "anvil.supervisor.services.subprocess.run",
                side_effect=[lsof_result, ps_result],
            ),
            patch("anvil.supervisor.services.os.kill") as kill,
            patch("anvil.supervisor.services.time.monotonic", side_effect=[0, 2]),
            patch("anvil.supervisor.services.time.sleep"),
        ):
            svc = MLflowService()
            svc._free_port()
            kill.assert_any_call(9876, 15)

    def test_free_port_no_python_process(self, mock_config, tmp_path):
        cfg = mock_config.return_value
        cfg["log_dir"] = str(tmp_path / "logs")
        lsof_result = MagicMock()
        lsof_result.stdout = "9876\n"
        ps_result = MagicMock()
        ps_result.stdout = "chrome\n"
        with (
            patch(
                "anvil.supervisor.services.subprocess.run",
                side_effect=[lsof_result, ps_result],
            ),
            patch("anvil.supervisor.services.os.kill") as kill,
        ):
            svc = MLflowService()
            svc._free_port()
            kill.assert_not_called()