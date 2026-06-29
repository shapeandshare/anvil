# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for MLflowService lifecycle management.

Tests MLflowService init, _free_port cleanup, start/stop lifecycle,
is_running property, and async_stop variant.  All subprocess and OS
signal calls are mocked.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import subprocess
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from anvil.config import get_config
from anvil.supervisor.services import MLflowService
from anvil.workspace.workspace_paths import WorkspacePaths

####################################################################
# Fixtures
####################################################################


@pytest.fixture
def mlflow_service(tmp_path: Path) -> MLflowService:
    """Create an MLflowService with a temp workspace and log dir.

    The WorkspacePaths mlruns_dir is pointed at a temp directory so
    tests do not leave ``./mlruns/`` or ``./logs/`` artifacts in the
        project root.
    """
    ws_paths = MagicMock(spec=WorkspacePaths)
    ws_paths.mlruns_dir = tmp_path / "mlruns"
    cfg = get_config()
    svc = MLflowService(workspace_paths=ws_paths)
    # Override log_dir to temp to avoid polluting project root
    svc.log_dir = tmp_path / "logs"
    svc.log_dir.mkdir(parents=True, exist_ok=True)
    svc.log_file = svc.log_dir / "mlflow.log"
    svc.port = cfg["mlflow_port"]
    return svc


def _proc_mock(
    pid: int = 99999,
    poll_return: int | None = None,
) -> MagicMock:
    """Build a minimal :class:`subprocess.Popen` mock.

    Parameters
    ----------
    pid : int
        Mock PID.
    poll_return : int or None
        ``poll()`` return value.  ``None`` means running.

    Returns
    -------
    MagicMock
        Mock process object.
    """
    m = MagicMock()
    m.pid = pid
    m.poll.return_value = poll_return
    return m


####################################################################
# __init__
####################################################################


class TestMLflowServiceInit:
    """MLflowService.__init__ reads config and sets up paths."""

    def test_init_defaults(self, mlflow_service: MLflowService) -> None:
        """Default port, tracking_uri, and backend_store_uri come from
        config.
        """
        cfg = get_config()
        assert mlflow_service.port == cfg["mlflow_port"]
        assert mlflow_service.tracking_uri == cfg["mlflow_uri"]
        assert mlflow_service._backend_store_uri == cfg["mlflow_backend_store_uri"]
        assert mlflow_service.process is None

    def test_init_mlruns_dir_from_workspace_paths(self, tmp_path: Path) -> None:
        """When workspace_paths is provided, mlruns_dir is derived from
        it.
        """
        ws_paths = MagicMock(spec=WorkspacePaths)
        custom_mlruns = tmp_path / "custom_mlruns"
        ws_paths.mlruns_dir = custom_mlruns
        svc = MLflowService(workspace_paths=ws_paths)
        assert svc.mlruns_dir == custom_mlruns
        assert custom_mlruns.exists()

    def test_init_default_mlruns_dir(self) -> None:
        """Without workspace_paths, mlruns_dir defaults to Path('mlruns')."""
        svc = MLflowService()
        assert svc.mlruns_dir == Path("mlruns")


####################################################################
# _free_port
####################################################################


class TestFreePort:
    """_free_port kills zombie processes on the configured port."""

    def _patch_free_port_deps(
        self,
        lsof_stdout: str = "",
        ps_stdout: str = "",
        ps_error: Exception | None = None,
        lsof_error: Exception | None = None,
        kill_sigterm_ok: bool = True,
        kill_zero_ok: bool = True,
        kill_sigkill_ok: bool = True,
        monotonic_values: list[float] | None = None,
    ) -> dict:
        """Helper to apply all patches needed for a _free_port test.

        Parameters
        ----------
        lsof_stdout : str
            stdout from the ``lsof`` subprocess call.
        ps_stdout : str
            stdout from the ``ps`` subprocess call.
        ps_error : type[Exception] or None
            If set, the ``ps`` call raises this exception.
        lsof_error : type[Exception] or None
            If set, the ``lsof`` call raises this exception.
        kill_sigterm_ok : bool
            If True, ``os.kill(pid, SIGTERM)`` succeeds.
        kill_zero_ok : bool
            If True, ``os.kill(pid, 0)`` succeeds (process still alive).
        monotonic_values : list[float] or None
            Sequence of return values for ``time.monotonic()``.

        Returns
        -------
        dict
            ``{"kill_calls": list, "patches": list[patcher]}`` — caller
            must call ``p.start()`` for each patcher and ``p.stop()``
            afterwards, or use as context managers.
        """
        kill_calls: list[tuple[int, int]] = []

        def _mock_kill(pid: int, sig: int) -> None:
            kill_calls.append((pid, sig))
            if sig == signal.SIGTERM and not kill_sigterm_ok:
                raise ProcessLookupError(f"pid {pid} not found")
            if sig == signal.SIGTERM and kill_sigterm_ok:
                return
            if sig == 0 and not kill_zero_ok:
                raise ProcessLookupError(f"pid {pid} not found")
            if sig == 0 and kill_zero_ok:
                return
            if sig == signal.SIGKILL and not kill_sigkill_ok:
                raise ProcessLookupError(f"pid {pid} not found")
            if sig == signal.SIGKILL and kill_sigkill_ok:
                return

        # Build subprocess.run side effects
        run_side_effects = []
        if lsof_error is not None:
            run_side_effects.append(lsof_error)
        else:
            run_side_effects.append(
                subprocess.CompletedProcess([], 0, stdout=lsof_stdout, stderr="")
            )

        if lsof_stdout.strip() and ps_error is None:
            run_side_effects.append(
                subprocess.CompletedProcess([], 0, stdout=ps_stdout, stderr="")
            )
        elif lsof_stdout.strip() and ps_error is not None:
            run_side_effects.append(ps_error)

        if monotonic_values is None:
            monotonic_values = [0.0]

        patches_ = [
            patch("subprocess.run", side_effect=run_side_effects),
            patch("os.kill", side_effect=_mock_kill),
            patch("time.monotonic", side_effect=monotonic_values),
            patch("time.sleep"),
        ]

        return {"kill_calls": kill_calls, "patches": patches_}

    def test_free_port_free(self, mlflow_service: MLflowService) -> None:
        """No processes on the port — no kills occur."""
        deps = self._patch_free_port_deps(lsof_stdout="")
        with contextlib.ExitStack() as stack:
            for p in deps["patches"]:
                stack.enter_context(p)
            mlflow_service._free_port()
        assert deps["kill_calls"] == []

    def test_free_port_zombie_found(self, mlflow_service: MLflowService) -> None:
        """Zombie process found and responds to SIGTERM."""
        deps = self._patch_free_port_deps(
            lsof_stdout="12345\n",
            ps_stdout="python\n",
            kill_sigterm_ok=True,
            kill_zero_ok=False,  # SIGTERM works → process gone on 0-check
            monotonic_values=[0.0, 0.0],
        )
        with contextlib.ExitStack() as stack:
            for p in deps["patches"]:
                stack.enter_context(p)
            mlflow_service._free_port()
        # SIGTERM sent, then signal-0 check shows process gone
        assert deps["kill_calls"] == [
            (12345, signal.SIGTERM),
            (12345, 0),
        ]

    def test_free_port_zombie_ignores_sigterm(
        self, mlflow_service: MLflowService
    ) -> None:
        """Zombie ignores SIGTERM — SIGKILL sent as fallback."""
        deps = self._patch_free_port_deps(
            lsof_stdout="12345\n",
            ps_stdout="mlflow\n",
            kill_sigterm_ok=True,
            kill_zero_ok=True,  # SIGTERM ignored → still alive on 0-check
            monotonic_values=[0.0, 0.0, 1.5],  # exit loop after 1 iteration
        )
        with contextlib.ExitStack() as stack:
            for p in deps["patches"]:
                stack.enter_context(p)
            mlflow_service._free_port()
        # SIGTERM sent, signal-0 alive, SIGKILL sent, loop exits
        assert deps["kill_calls"] == [
            (12345, signal.SIGTERM),
            (12345, 0),
            (12345, signal.SIGKILL),
        ]

    def test_free_port_lsof_not_available(self, mlflow_service: MLflowService) -> None:
        """Lsof not on PATH — _free_port silently returns."""
        deps = self._patch_free_port_deps(
            lsof_error=FileNotFoundError("lsof not found"),
        )
        with contextlib.ExitStack() as stack:
            for p in deps["patches"]:
                stack.enter_context(p)
            mlflow_service._free_port()  # should not raise
        assert deps["kill_calls"] == []

    def test_free_port_lsof_timeout(self, mlflow_service: MLflowService) -> None:
        """Lsof subprocess times out — _free_port silently returns."""
        deps = self._patch_free_port_deps(
            lsof_error=subprocess.TimeoutExpired(cmd="lsof", timeout=5),
        )
        with contextlib.ExitStack() as stack:
            for p in deps["patches"]:
                stack.enter_context(p)
            mlflow_service._free_port()
        assert deps["kill_calls"] == []

    def test_free_port_ps_timeout(self, mlflow_service: MLflowService) -> None:
        """Ps subprocess times out — PID is skipped."""
        deps = self._patch_free_port_deps(
            lsof_stdout="12345\n",
            ps_error=subprocess.TimeoutExpired(cmd="ps", timeout=3),
        )
        with contextlib.ExitStack() as stack:
            for p in deps["patches"]:
                stack.enter_context(p)
            mlflow_service._free_port()
        # No pids collected → no kills
        assert deps["kill_calls"] == []

    def test_free_port_sigterm_process_lookup_error(
        self, mlflow_service: MLflowService
    ) -> None:
        """Process disappears between lsof and os.kill(SIGTERM) — not
        an error.
        """
        deps = self._patch_free_port_deps(
            lsof_stdout="12345\n",
            ps_stdout="python\n",
            kill_sigterm_ok=False,  # SIGTERM raises ProcessLookupError
            kill_zero_ok=False,  # already gone
            monotonic_values=[0.0, 0.0],
        )
        with contextlib.ExitStack() as stack:
            for p in deps["patches"]:
                stack.enter_context(p)
            mlflow_service._free_port()
        # SIGTERM fails → signal-0 also fails → return early
        assert (12345, signal.SIGTERM) in deps["kill_calls"]
        assert (12345, 0) in deps["kill_calls"]

    def test_free_port_sigkill_process_lookup_error(
        self, mlflow_service: MLflowService
    ) -> None:
        """SIGKILL on remaining zombie raises ProcessLookupError —
        handled gracefully.
        """
        deps = self._patch_free_port_deps(
            lsof_stdout="12345\n",
            ps_stdout="mlflow\n",
            kill_sigterm_ok=True,
            kill_zero_ok=True,  # still alive after SIGTERM
            kill_sigkill_ok=False,  # SIGKILL raises ProcessLookupError
            monotonic_values=[0.0, 0.0, 1.5],
        )
        with contextlib.ExitStack() as stack:
            for p in deps["patches"]:
                stack.enter_context(p)
            mlflow_service._free_port()  # should not raise
        assert (12345, signal.SIGTERM) in deps["kill_calls"]
        assert (12345, 0) in deps["kill_calls"]
        assert (12345, signal.SIGKILL) in deps["kill_calls"]

    def test_free_port_non_matching_process(
        self, mlflow_service: MLflowService
    ) -> None:
        """Process on port doesn't match python/mlflow/uvicorn — not
        killed.
        """
        deps = self._patch_free_port_deps(
            lsof_stdout="12345\n",
            ps_stdout="nginx\n",  # not filtered keywords
        )
        with contextlib.ExitStack() as stack:
            for p in deps["patches"]:
                stack.enter_context(p)
            mlflow_service._free_port()
        assert deps["kill_calls"] == []


####################################################################
# start
####################################################################


class TestMLflowServiceStart:
    """MLflowService.start lifecycle."""

    def test_start_already_running(self, mlflow_service: MLflowService) -> None:
        """Start is a no-op when the process is already running."""
        mock_proc = _proc_mock(pid=99999, poll_return=None)
        mlflow_service.process = mock_proc

        with patch.object(mlflow_service, "_free_port") as mock_free:
            mlflow_service.start()

        mock_free.assert_not_called()
        assert mlflow_service.process is mock_proc  # unchanged

    def test_start_cold(self, mlflow_service: MLflowService) -> None:
        """Cold start opens Popen and writes PID file."""
        mock_proc = _proc_mock(pid=44444, poll_return=None)

        with (
            patch.object(mlflow_service, "_free_port") as mock_free,
            patch("subprocess.Popen", return_value=mock_proc) as mock_popen,
        ):
            mlflow_service.start()

        mock_free.assert_called_once()
        mock_popen.assert_called_once()
        # Verify Popen args include mlflow server
        args, kwargs = mock_popen.call_args
        assert args[0][1] == "server"
        assert "preexec_fn" in kwargs  # os.setsid

        assert mlflow_service.process is mock_proc
        assert mlflow_service.is_running is True

        # PID file was written
        pid_file = mlflow_service.log_dir / "mlflow.pid"
        assert pid_file.exists()
        assert pid_file.read_text().strip() == "44444"


####################################################################
# stop
####################################################################


class TestMLflowServiceStop:
    """MLflowService.stop lifecycle."""

    def test_stop_already_stopped(self, mlflow_service: MLflowService) -> None:
        """Stop is a no-op when process is None."""
        pid_file = mlflow_service.log_dir / "mlflow.pid"
        pid_file.write_text("99999")

        mlflow_service.stop()

        assert mlflow_service.process is None
        # PID file should be cleaned up
        assert not pid_file.exists()

    def test_stop_already_exited(self, mlflow_service: MLflowService) -> None:
        """Stop is a no-op when process has already exited (poll not
        None).
        """
        mock_proc = _proc_mock(pid=99999, poll_return=0)
        mlflow_service.process = mock_proc
        pid_file = mlflow_service.log_dir / "mlflow.pid"
        pid_file.write_text("99999")

        with patch("os.killpg") as mock_killpg:
            mlflow_service.stop()

        mock_killpg.assert_not_called()
        assert mlflow_service.process is mock_proc

    def test_stop_normal(self, mlflow_service: MLflowService) -> None:
        """Normal stop sends SIGTERM, waits, then clears."""
        mock_proc = _proc_mock(pid=99999, poll_return=None)
        mock_proc.wait.return_value = 0
        mlflow_service.process = mock_proc
        pid_file = mlflow_service.log_dir / "mlflow.pid"
        pid_file.write_text("99999")

        killpg_calls: list[int] = []

        def _track_killpg(pgid: int, sig: int) -> None:
            killpg_calls.append(sig)

        with (
            patch("os.killpg", side_effect=_track_killpg),
            patch("os.getpgid", return_value=888),
        ):
            mlflow_service.stop()

        assert killpg_calls == [signal.SIGTERM]
        mock_proc.wait.assert_called_once_with(timeout=10)
        assert mlflow_service.process is None
        assert not pid_file.exists()

    def test_stop_timeout(self, mlflow_service: MLflowService) -> None:
        """SIGTERM timeout triggers SIGKILL fallback."""
        mock_proc = _proc_mock(pid=99999, poll_return=None)
        mock_proc.wait.side_effect = subprocess.TimeoutExpired(cmd="mock", timeout=10)
        mlflow_service.process = mock_proc

        killpg_calls: list[int] = []

        def _track_killpg(pgid: int, sig: int) -> None:
            killpg_calls.append(sig)

        with (
            patch("os.killpg", side_effect=_track_killpg),
            patch("os.getpgid", return_value=888),
        ):
            mlflow_service.stop()

        assert killpg_calls == [signal.SIGTERM, signal.SIGKILL]
        assert mlflow_service.process is None

    def test_stop_process_lookup_error(self, mlflow_service: MLflowService) -> None:
        """ProcessLookupError on SIGTERM triggers SIGKILL; SIGKILL also
        raises ProcessLookupError (process already gone).
        """
        mock_proc = _proc_mock(pid=99999, poll_return=None)
        mock_proc.wait.side_effect = ProcessLookupError()
        mlflow_service.process = mock_proc

        killpg_calls: list[int] = []

        def _track_killpg(pgid: int, sig: int) -> None:
            killpg_calls.append(sig)
            if sig == signal.SIGKILL:
                raise ProcessLookupError("already gone")

        with (
            patch("os.killpg", side_effect=_track_killpg),
            patch("os.getpgid", return_value=888),
        ):
            mlflow_service.stop()  # should not raise

        assert killpg_calls == [signal.SIGTERM, signal.SIGKILL]
        assert mlflow_service.process is None


####################################################################
# is_running
####################################################################


class TestIsRunning:
    """MLflowService.is_running property."""

    def test_is_running_true(self, mlflow_service: MLflowService) -> None:
        """Returns True when process is set and poll() returns None."""
        mock_proc = _proc_mock(poll_return=None)
        mlflow_service.process = mock_proc
        assert mlflow_service.is_running is True

    def test_is_running_false_no_process(self, mlflow_service: MLflowService) -> None:
        """Returns False when process is None."""
        mlflow_service.process = None
        assert mlflow_service.is_running is False

    def test_is_running_false_exited(self, mlflow_service: MLflowService) -> None:
        """Returns False when process has exited (poll returns 0)."""
        mock_proc = _proc_mock(poll_return=0)
        mlflow_service.process = mock_proc
        assert mlflow_service.is_running is False


####################################################################
# async_stop
####################################################################


class TestAsyncStop:
    """MLflowService.async_stop wraps stop in asyncio.to_thread."""

    @pytest.mark.asyncio
    async def test_async_stop_already_stopped(
        self, mlflow_service: MLflowService
    ) -> None:
        """async_stop is a no-op when process is None."""
        pid_file = mlflow_service.log_dir / "mlflow.pid"
        pid_file.write_text("99999")

        await mlflow_service.async_stop()

        assert not pid_file.exists()

    @pytest.mark.asyncio
    async def test_async_stop_normal(self, mlflow_service: MLflowService) -> None:
        """async_stop sends SIGTERM, awaits wait via to_thread, then
        clears.
        """
        mock_proc = _proc_mock(pid=99999, poll_return=None)

        async def _mock_to_thread(func, *args, **kwargs):
            return func(*args, **kwargs)

        mlflow_service.process = mock_proc
        killpg_calls: list[int] = []

        def _track_killpg(pgid: int, sig: int) -> None:
            killpg_calls.append(sig)

        with (
            patch("os.killpg", side_effect=_track_killpg),
            patch("os.getpgid", return_value=888),
            patch("asyncio.to_thread", _mock_to_thread),
        ):
            await mlflow_service.async_stop()

        assert killpg_calls == [signal.SIGTERM]
        mock_proc.wait.assert_called_once_with(timeout=10)
        assert mlflow_service.process is None

    @pytest.mark.asyncio
    async def test_async_stop_timeout(self, mlflow_service: MLflowService) -> None:
        """async_stop SIGTERM timeout triggers SIGKILL."""
        mock_proc = _proc_mock(pid=99999, poll_return=None)

        async def _mock_to_thread(func, *args, **kwargs):
            return func(*args, **kwargs)

        mock_proc.wait.side_effect = subprocess.TimeoutExpired(cmd="mock", timeout=10)
        mlflow_service.process = mock_proc
        killpg_calls: list[int] = []

        def _track_killpg(pgid: int, sig: int) -> None:
            killpg_calls.append(sig)

        with (
            patch("os.killpg", side_effect=_track_killpg),
            patch("os.getpgid", return_value=888),
            patch("asyncio.to_thread", _mock_to_thread),
        ):
            await mlflow_service.async_stop()

        assert killpg_calls == [signal.SIGTERM, signal.SIGKILL]
        assert mlflow_service.process is None

    @pytest.mark.asyncio
    async def test_async_stop_sigkill_process_lookup_error(
        self, mlflow_service: MLflowService
    ) -> None:
        """async_stop SIGTERM timeout, SIGKILL also raises
        ProcessLookupError — handled gracefully.
        """
        mock_proc = _proc_mock(pid=99999, poll_return=None)

        async def _mock_to_thread(func, *args, **kwargs):
            return func(*args, **kwargs)

        mock_proc.wait.side_effect = ProcessLookupError("already gone")
        mlflow_service.process = mock_proc
        killpg_calls: list[int] = []

        def _track_killpg(pgid: int, sig: int) -> None:
            killpg_calls.append(sig)
            if sig == signal.SIGKILL:
                raise ProcessLookupError("already gone")

        with (
            patch("os.killpg", side_effect=_track_killpg),
            patch("os.getpgid", return_value=888),
            patch("asyncio.to_thread", _mock_to_thread),
        ):
            await mlflow_service.async_stop()  # should not raise

        assert killpg_calls == [signal.SIGTERM, signal.SIGKILL]
        assert mlflow_service.process is None
