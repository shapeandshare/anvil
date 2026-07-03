# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for MLflowService — lifecycle, port cleanup, process management.

Covers the full MLflowService API:
- Initialisation with default paths and WorkspacePaths
- Port cleanup (zombie process detection and killing)
- Server start (subprocess launch, no-op guard, PID file)
- Server stop (SIGTERM, SIGKILL timeout, async variant)
- Status properties (is_running, tracking_uri)
"""

from __future__ import annotations

import asyncio
import signal
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, PropertyMock, call, patch

import pytest

from anvil.supervisor.services import MLflowService
from anvil.workspace.workspace_paths import WorkspacePaths


###############################################################################
# Fixtures
###############################################################################


@pytest.fixture
def mock_config(tmp_path):
    """Return a standard mock config dictionary rooted in *tmp_path*."""
    return {
        "log_dir": str(tmp_path / "logs"),
        "mlflow_port": 5001,
        "mlflow_uri": "http://127.0.0.1:5001",
        "mlflow_backend_store_uri": "sqlite:///mlruns/mlflow.db",
    }


@pytest.fixture
def service(mock_config, tmp_path, monkeypatch):
    """Create an MLflowService with a mocked config in an isolated temp dir.

    The current working directory is changed to *tmp_path* so that the
    default ``Path("mlruns")`` resolves inside the temp tree and no
    artifacts leak into the real project root.
    """
    monkeypatch.chdir(tmp_path)
    with patch("anvil.supervisor.services.get_config", return_value=mock_config):
        svc = MLflowService()
    return svc


@pytest.fixture
def mock_process():
    """Return a :class:`unittest.mock.MagicMock` representing a running subprocess."""
    proc = MagicMock(spec=subprocess.Popen)
    proc.pid = 12345
    proc.poll.return_value = None
    proc.wait.return_value = None
    return proc


###############################################################################
# MLflowService.__init__
###############################################################################


class TestInit:
    """MLflowService initialisation."""

    def test_default_paths(self, mock_config, tmp_path, monkeypatch):
        """Initialisation without WorkspacePaths uses sensible defaults."""
        monkeypatch.chdir(tmp_path)
        with patch("anvil.supervisor.services.get_config", return_value=mock_config):
            svc = MLflowService()

        assert svc.port == 5001
        assert svc._tracking_uri == "http://127.0.0.1:5001"
        assert svc._backend_store_uri == "sqlite:///mlruns/mlflow.db"
        assert svc.log_dir == tmp_path / "logs"
        assert svc.log_file == tmp_path / "logs" / "mlflow.log"
        assert svc.mlruns_dir == Path("mlruns")
        assert svc.process is None

    def test_with_workspace_paths(self, mock_config, tmp_path):
        """When WorkspacePaths is provided, ``mlruns_dir`` is derived from it."""
        ws_root = tmp_path / "workspace"
        ws_root.mkdir(parents=True)
        wp = WorkspacePaths(ws_root)
        cfg = {**mock_config, "log_dir": str(tmp_path / "other_logs")}

        with patch("anvil.supervisor.services.get_config", return_value=cfg):
            svc = MLflowService(workspace_paths=wp)

        assert svc.mlruns_dir == ws_root / "mlruns"
        assert svc.mlruns_dir.exists()

    def test_creates_directories(self, mock_config, tmp_path, monkeypatch):
        """Both ``log_dir`` and ``mlruns_dir`` are created during init."""
        monkeypatch.chdir(tmp_path)
        log_dir = tmp_path / "custom_logs"
        cfg = {**mock_config, "log_dir": str(log_dir)}
        assert not log_dir.exists()

        with patch("anvil.supervisor.services.get_config", return_value=cfg):
            MLflowService()

        assert log_dir.exists()
        assert (tmp_path / "mlruns").exists()


###############################################################################
# MLflowService._free_port
###############################################################################


class TestFreePort:
    """Port-cleanup logic."""

    def test_no_processes_on_port(self, service):
        """No-op when *lsof* returns no PIDs (empty stdout)."""
        with patch("anvil.supervisor.services.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="")
            service._free_port()

        mock_run.assert_called_once_with(
            ["lsof", "-ti", ":5001"],
            capture_output=True,
            text=True,
            timeout=5,
        )

    def test_kills_zombie_mlflow_process(self, service):
        """Matching python/mlflow/uvicorn process is killed with SIGTERM."""
        with (
            patch("anvil.supervisor.services.subprocess.run") as mock_run,
            patch("anvil.supervisor.services.os.kill") as mock_kill,
            patch("anvil.supervisor.services.time.monotonic") as mock_mono,
            patch("anvil.supervisor.services.time.sleep"),
        ):
            mock_run.side_effect = [
                MagicMock(stdout="123\n"),
                MagicMock(stdout="mlflow\n"),
            ]
            mock_mono.side_effect = [1.0, 1.1]

            def _kill_fn(pid, sig):
                if sig == 0:
                    msg = f"No process {pid}"
                    raise ProcessLookupError(msg)

            mock_kill.side_effect = _kill_fn
            service._free_port()

        mock_kill.assert_any_call(123, signal.SIGTERM)
        assert mock_run.call_count >= 2

    def test_skips_non_matching_process(self, service):
        """Non-matching commands (not python/mlflow/uvicorn) are not killed."""
        with (
            patch("anvil.supervisor.services.subprocess.run") as mock_run,
            patch("anvil.supervisor.services.os.kill") as mock_kill,
            patch("anvil.supervisor.services.time.monotonic") as mock_mono,
            patch("anvil.supervisor.services.time.sleep"),
        ):
            mock_run.side_effect = [
                MagicMock(stdout="999\n"),
                MagicMock(stdout="nginx\n"),
            ]
            mock_mono.side_effect = [1.0, 1.1]

            service._free_port()

        mock_kill.assert_not_called()

    def test_kills_multiple_zombies(self, service):
        """All matching PIDs are killed."""
        pids_str = "111\n222\n"
        with (
            patch("anvil.supervisor.services.subprocess.run") as mock_run,
            patch("anvil.supervisor.services.os.kill") as mock_kill,
            patch("anvil.supervisor.services.time.monotonic") as mock_mono,
            patch("anvil.supervisor.services.time.sleep"),
        ):
            mock_run.side_effect = [
                MagicMock(stdout=pids_str),
                MagicMock(stdout="python\n"),
                MagicMock(stdout="uvicorn\n"),
            ]

            def _kill_fn(pid, sig):
                if sig == 0:
                    msg = f"No process {pid}"
                    raise ProcessLookupError(msg)

            mock_kill.side_effect = _kill_fn
            mock_mono.side_effect = [1.0, 1.1]
            service._free_port()

        assert mock_kill.call_count >= 2
        mock_kill.assert_any_call(111, signal.SIGTERM)
        mock_kill.assert_any_call(222, signal.SIGTERM)

    def test_sigkill_fallback_when_process_stays_alive(self, service):
        """SIGKILL is sent when the process does not die after SIGTERM."""
        with (
            patch("anvil.supervisor.services.subprocess.run") as mock_run,
            patch("anvil.supervisor.services.os.kill") as mock_kill,
            patch("anvil.supervisor.services.time.monotonic") as mock_mono,
            patch("anvil.supervisor.services.time.sleep"),
        ):
            mock_run.side_effect = [
                MagicMock(stdout="456\n"),
                MagicMock(stdout="python\n"),
            ]
            # First call: deadline = 1.0 + 1.0 = 2.0; second call: 1.1 < 2.0 → enter loop
            # Third call: 100.0 < 2.0 → exit loop (deadline reached)
            mock_mono.side_effect = [1.0, 1.1, 100.0]

            mock_kill.return_value = None
            service._free_port()

        mock_kill.assert_any_call(456, signal.SIGTERM)
        mock_kill.assert_any_call(456, signal.SIGKILL)

    def test_sigterm_raises_process_lookup_error(self, service):
        """ProcessLookupError during initial SIGTERM is silently handled."""
        with (
            patch("anvil.supervisor.services.subprocess.run") as mock_run,
            patch("anvil.supervisor.services.os.kill") as mock_kill,
            patch("anvil.supervisor.services.time.monotonic") as mock_mono,
            patch("anvil.supervisor.services.time.sleep"),
        ):
            mock_run.side_effect = [
                MagicMock(stdout="789\n"),
                MagicMock(stdout="mlflow\n"),
            ]

            def _kill_fn(pid, sig):
                if sig == signal.SIGTERM:
                    msg = f"No process {pid}"
                    raise ProcessLookupError(msg)
                if sig == 0:
                    msg = f"No process {pid}"
                    raise ProcessLookupError(msg)

            mock_kill.side_effect = _kill_fn
            mock_mono.side_effect = [1.0, 1.1]
            service._free_port()

        # Should complete without raising
        mock_kill.assert_any_call(789, signal.SIGTERM)

    def test_handles_lsof_timeout(self, service):
        """subprocess.TimeoutExpired from lsof is silently handled."""
        with patch("anvil.supervisor.services.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="lsof", timeout=5)
            service._free_port()  # should not raise

    def test_handles_lsof_not_found(self, service):
        """FileNotFoundError when lsof is unavailable is silently handled."""
        with patch("anvil.supervisor.services.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            service._free_port()  # should not raise

    def test_handles_ps_timeout(self, service):
        """subprocess.TimeoutExpired from ps is silently handled (skips that PID)."""
        with (
            patch("anvil.supervisor.services.subprocess.run") as mock_run,
            patch("anvil.supervisor.services.os.kill") as mock_kill,
            patch("anvil.supervisor.services.time.monotonic") as mock_mono,
            patch("anvil.supervisor.services.time.sleep"),
        ):
            # First ps call times out; no matching processes → no kill.
            mock_run.side_effect = [
                MagicMock(stdout="111\n"),
                subprocess.TimeoutExpired(cmd="ps", timeout=3),
            ]
            mock_mono.side_effect = [1.0, 1.1]
            service._free_port()
            mock_kill.assert_not_called()

    def test_handles_invalid_pid_in_ps(self, service):
        """ValueError from int() conversion of ps output is silently handled."""
        with (
            patch("anvil.supervisor.services.subprocess.run") as mock_run,
            patch("anvil.supervisor.services.os.kill") as mock_kill,
            patch("anvil.supervisor.services.time.monotonic") as mock_mono,
            patch("anvil.supervisor.services.time.sleep"),
        ):
            # lsof returns non-numeric PID "abc"; ps matches so int("abc")
            # raises ValueError which is caught by the except clause.
            mock_run.side_effect = [
                MagicMock(stdout="abc\n"),
                MagicMock(stdout="python\n"),
            ]
            mock_mono.side_effect = [1.0, 1.1]
            service._free_port()
            mock_kill.assert_not_called()


###############################################################################
# MLflowService.start
###############################################################################


class TestStart:
    """Server subprocess launch."""

    def test_launches_mlflow_server(self, service, mock_process):
        """start() launches ``mlflow server`` with the expected arguments."""
        with (
            patch("anvil.supervisor.services.subprocess.Popen", return_value=mock_process) as mock_popen,
            patch("anvil.supervisor.services.Path.write_text") as mock_write,
            patch.object(service, "_free_port") as mock_free,
        ):
            service.start()

        mock_free.assert_called_once()
        mock_popen.assert_called_once()
        args, kwargs = mock_popen.call_args
        assert args[0][0].endswith("mlflow") or "mlflow" in args[0][0]
        assert "--port" in args[0]
        port_idx = args[0].index("--port")
        assert args[0][port_idx + 1] == "5001"
        assert "--host" in args[0]
        assert "0.0.0.0" in args[0]
        assert kwargs.get("preexec_fn") is not None

    def test_noop_if_already_running(self, service, mock_process):
        """start() is a no-op when the subprocess is already running."""
        service.process = mock_process
        with (
            patch("anvil.supervisor.services.subprocess.Popen") as mock_popen,
            patch.object(service, "_free_port") as mock_free,
        ):
            service.start()

        mock_free.assert_not_called()
        mock_popen.assert_not_called()

    def test_writes_pid_file(self, service, mock_process):
        """PID is written to ``{log_dir}/mlflow.pid`` on start."""
        with (
            patch("anvil.supervisor.services.subprocess.Popen", return_value=mock_process),
            patch.object(service, "_free_port"),
        ):
            service.start()

        pid_file = service.log_dir / "mlflow.pid"
        assert pid_file.read_text() == "12345"

    def test_sets_process_attribute(self, service, mock_process):
        """The ``process`` attribute is set to the Popen instance."""
        with (
            patch("anvil.supervisor.services.subprocess.Popen", return_value=mock_process),
            patch.object(service, "_free_port"),
        ):
            service.start()

        assert service.process is mock_process


###############################################################################
# MLflowService.stop
###############################################################################


class TestStop:
    """Synchronous server shutdown."""

    def test_sends_sigterm(self, service, mock_process):
        """stop() sends SIGTERM to the process group and clears state."""
        service.process = mock_process
        pid_file = service.log_dir / "mlflow.pid"
        pid_file.write_text("12345")

        with (
            patch("anvil.supervisor.services.os.killpg") as mock_killpg,
            patch("anvil.supervisor.services.os.getpgid", return_value=12345),
        ):
            service.stop()

        mock_killpg.assert_called_once_with(12345, signal.SIGTERM)
        assert service.process is None
        assert not pid_file.exists()

    def test_noop_if_process_none(self, service):
        """stop() is a no-op when ``process`` is ``None``."""
        pid_file = service.log_dir / "mlflow.pid"
        pid_file.write_text("12345")
        assert service.process is None

        with patch("anvil.supervisor.services.os.killpg") as mock_killpg:
            service.stop()

        mock_killpg.assert_not_called()
        assert not pid_file.exists()  # PID file removed

    def test_noop_if_process_exited(self, service, mock_process):
        """stop() is a no-op when the process has already exited."""
        mock_process.poll.return_value = 0  # process exited
        service.process = mock_process
        pid_file = service.log_dir / "mlflow.pid"
        pid_file.write_text("12345")

        with patch("anvil.supervisor.services.os.killpg") as mock_killpg:
            service.stop()

        mock_killpg.assert_not_called()
        assert service.process is mock_process  # still assigned (stop skips it)
        assert not pid_file.exists()

    def test_timeout_sends_sigkill(self, service, mock_process):
        """SIGKILL is sent when the process does not exit after SIGTERM within 10s."""
        mock_process.wait.side_effect = subprocess.TimeoutExpired(
            cmd="mlflow", timeout=10
        )
        service.process = mock_process

        with (
            patch("anvil.supervisor.services.os.killpg") as mock_killpg,
            patch("anvil.supervisor.services.os.getpgid", return_value=12345),
        ):
            service.stop()

        # First SIGTERM, then SIGKILL
        assert mock_killpg.call_count == 2
        mock_killpg.assert_has_calls(
            [call(12345, signal.SIGTERM), call(12345, signal.SIGKILL)]
        )
        assert service.process is None

    def test_sigkill_handles_process_lookup_error(self, service, mock_process):
        """ProcessLookupError during SIGKILL fallback is silently handled."""
        mock_process.wait.side_effect = ProcessLookupError()
        service.process = mock_process

        with (
            patch("anvil.supervisor.services.os.killpg") as mock_killpg,
            patch("anvil.supervisor.services.os.getpgid", return_value=12345),
        ):
            service.stop()

        assert mock_killpg.call_count == 2
        assert service.process is None

    def test_removes_pid_file_in_finally(self, service, mock_process):
        """PID file is always removed in the ``finally`` block."""
        mock_process.wait.side_effect = subprocess.TimeoutExpired(
            cmd="mlflow", timeout=10
        )
        service.process = mock_process
        pid_file = service.log_dir / "mlflow.pid"
        pid_file.write_text("12345")

        with (
            patch("anvil.supervisor.services.os.killpg"),
            patch("anvil.supervisor.services.os.getpgid", return_value=12345),
        ):
            service.stop()

        assert not pid_file.exists()


###############################################################################
# MLflowService.async_stop
###############################################################################


class TestAsyncStop:
    """Asynchronous server shutdown."""

    @pytest.mark.asyncio
    async def test_sends_sigterm(self, service, mock_process):
        """async_stop() sends SIGTERM and clears state."""
        service.process = mock_process
        pid_file = service.log_dir / "mlflow.pid"
        pid_file.write_text("12345")

        with (
            patch("anvil.supervisor.services.os.killpg") as mock_killpg,
            patch("anvil.supervisor.services.os.getpgid", return_value=12345),
            patch("anvil.supervisor.services.asyncio.to_thread", new_callable=AsyncMock),
        ):
            await service.async_stop()

        mock_killpg.assert_called_once_with(12345, signal.SIGTERM)
        assert service.process is None
        assert not pid_file.exists()

    @pytest.mark.asyncio
    async def test_noop_if_process_none(self, service):
        """async_stop() is a no-op when ``process`` is ``None``."""
        pid_file = service.log_dir / "mlflow.pid"
        pid_file.write_text("12345")
        assert service.process is None

        with patch("anvil.supervisor.services.os.killpg") as mock_killpg:
            await service.async_stop()

        mock_killpg.assert_not_called()
        assert not pid_file.exists()

    @pytest.mark.asyncio
    async def test_noop_if_process_exited(self, service, mock_process):
        """async_stop() is a no-op when the process has already exited."""
        mock_process.poll.return_value = 0
        service.process = mock_process
        pid_file = service.log_dir / "mlflow.pid"
        pid_file.write_text("12345")

        with patch("anvil.supervisor.services.os.killpg") as mock_killpg:
            await service.async_stop()

        mock_killpg.assert_not_called()
        assert not pid_file.exists()

    @pytest.mark.asyncio
    async def test_timeout_sends_sigkill(self, service, mock_process):
        """async_stop sends SIGKILL after timeout during threaded wait."""
        mock_process.wait.side_effect = subprocess.TimeoutExpired(
            cmd="mlflow", timeout=10
        )
        service.process = mock_process

        with (
            patch("anvil.supervisor.services.os.killpg") as mock_killpg,
            patch("anvil.supervisor.services.os.getpgid", return_value=12345),
            patch("anvil.supervisor.services.asyncio.to_thread") as mock_to_thread,
        ):
            # Make asyncio.to_thread actually call wait() so the side_effect fires
            async def _to_thread(fn, /, *args, **kwargs):
                return fn(*args, **kwargs)

            mock_to_thread.side_effect = _to_thread
            await service.async_stop()

        assert mock_killpg.call_count == 2
        mock_killpg.assert_has_calls(
            [call(12345, signal.SIGTERM), call(12345, signal.SIGKILL)]
        )
        assert service.process is None

    @pytest.mark.asyncio
    async def test_uses_to_thread(self, service, mock_process):
        """async_stop wraps the blocking ``wait`` in ``asyncio.to_thread``."""
        service.process = mock_process

        with (
            patch("anvil.supervisor.services.os.killpg"),
            patch("anvil.supervisor.services.os.getpgid", return_value=12345),
            patch("anvil.supervisor.services.asyncio.to_thread") as mock_to_thread,
        ):
            mock_to_thread.return_value = asyncio.sleep(0)
            await service.async_stop()

        mock_to_thread.assert_called_once()
        # First arg to to_thread should be the process.wait method
        args, _ = mock_to_thread.call_args
        assert args[0] == mock_process.wait

    @pytest.mark.asyncio
    async def test_sigkill_handles_process_lookup_error(self, service, mock_process):
        """ProcessLookupError during SIGKILL in async variant is handled."""
        mock_process.wait.side_effect = ProcessLookupError()
        service.process = mock_process

        with (
            patch("anvil.supervisor.services.os.killpg") as mock_killpg,
            patch("anvil.supervisor.services.os.getpgid", return_value=12345),
            patch("anvil.supervisor.services.asyncio.to_thread") as mock_to_thread,
        ):
            async def _to_thread(fn, /, *args, **kwargs):
                return fn(*args, **kwargs)

            mock_to_thread.side_effect = _to_thread
            await service.async_stop()

        assert mock_killpg.call_count == 2
        assert service.process is None


###############################################################################
# MLflowService properties
###############################################################################


class TestProperties:
    """Status properties."""

    def test_is_running_true(self, service, mock_process):
        """``is_running`` is ``True`` when the subprocess is alive."""
        service.process = mock_process
        assert service.is_running is True

    def test_is_running_false_when_none(self, service):
        """``is_running`` is ``False`` when ``process`` is ``None``."""
        assert service.process is None
        assert service.is_running is False

    def test_is_running_false_when_exited(self, service, mock_process):
        """``is_running`` is ``False`` when the subprocess has exited."""
        mock_process.poll.return_value = 0
        service.process = mock_process
        assert service.is_running is False

    def test_tracking_uri(self, service):
        """``tracking_uri`` returns the configured MLflow URI."""
        assert service.tracking_uri == "http://127.0.0.1:5001"