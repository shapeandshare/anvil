# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for supervisor module — PID helpers and ProcessSupervisor.

Tests write_pid, read_pid, kill_pid_file, and the full
ProcessSupervisor lifecycle (start, stop, status, stop_all).
"""

from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from anvil.supervisor.supervisor import (
    ProcessSupervisor,
    kill_pid_file,
    read_pid,
    write_pid,
)

########################################################################
# PID file helpers
########################################################################


class TestWriteReadPid:
    """Round-trip write_pid / read_pid."""

    def test_write_and_read(self, tmp_path: Path) -> None:
        """write_pid creates a file that read_pid can parse."""
        path = write_pid("test-proc", pid_dir=str(tmp_path))
        assert path.exists()
        assert path.name == "test-proc.pid"
        pid = read_pid("test-proc", pid_dir=str(tmp_path))
        assert pid == os.getpid()

    def test_read_nonexistent(self, tmp_path: Path) -> None:
        """read_pid returns None for a non-existent PID file."""
        pid = read_pid("ghost", pid_dir=str(tmp_path))
        assert pid is None

    def test_write_creates_parent_dirs(self, tmp_path: Path) -> None:
        """write_pid creates the pid_dir if it does not exist."""
        nested = tmp_path / "sub" / "pids"
        write_pid("nested", pid_dir=str(nested))
        assert nested.exists()
        assert (nested / "nested.pid").exists()

    def test_write_returns_path(self, tmp_path: Path) -> None:
        """write_pid returns the correct Path to the PID file."""
        expected = tmp_path / "my-app.pid"
        result = write_pid("my-app", pid_dir=str(tmp_path))
        assert result == expected

    def test_read_strips_whitespace(self, tmp_path: Path) -> None:
        """read_pid handles whitespace around the PID value."""
        pid_file = tmp_path / "whitespace.pid"
        pid_file.write_text("  12345  \n")
        result = read_pid("whitespace", pid_dir=str(tmp_path))
        assert result == 12345


class TestKillPidFile:
    """kill_pid_file behaviour for existing and missing processes."""

    def test_kill_nonexistent_returns_false(self, tmp_path: Path) -> None:
        """kill_pid_file returns False when the PID file does not exist."""
        result = kill_pid_file("ghost", pid_dir=str(tmp_path))
        assert result is False

    def test_kill_successful_returns_true(self, tmp_path: Path) -> None:
        """kill_pid_file sends the signal, cleans up, and returns True."""
        pid_file = tmp_path / "real.pid"
        pid_file.write_text("99999")
        with patch.object(os, "kill") as mock_kill:
            result = kill_pid_file("real", pid_dir=str(tmp_path))
        assert result is True
        mock_kill.assert_called_once_with(99999, signal.SIGTERM)
        assert not pid_file.exists()

    def test_kill_with_custom_signal(self, tmp_path: Path) -> None:
        """kill_pid_file sends a user-specified signal."""
        pid_file = tmp_path / "custom.pid"
        pid_file.write_text("88888")
        with patch.object(os, "kill") as mock_kill:
            kill_pid_file("custom", sig=signal.SIGHUP, pid_dir=str(tmp_path))
        mock_kill.assert_called_once_with(88888, signal.SIGHUP)

    def test_kill_process_lookup_error_cleans_up(self, tmp_path: Path) -> None:
        """kill_pid_file catches ProcessLookupError, cleans up, returns False."""
        pid_file = tmp_path / "gone.pid"
        pid_file.write_text("999999")
        with patch.object(os, "kill", side_effect=ProcessLookupError):
            result = kill_pid_file("gone", pid_dir=str(tmp_path))
        assert result is False
        assert not pid_file.exists()

    def test_kill_file_not_found_error_cleans_up(self, tmp_path: Path) -> None:
        """kill_pid_file catches FileNotFoundError on kill, cleans up, returns False."""
        pid_file = tmp_path / "noproc.pid"
        pid_file.write_text("11111")
        with patch.object(os, "kill", side_effect=FileNotFoundError):
            result = kill_pid_file("noproc", pid_dir=str(tmp_path))
        assert result is False
        assert not pid_file.exists()


########################################################################
# ProcessSupervisor
########################################################################


class TestProcessSupervisorInit:
    """ProcessSupervisor.__init__ behaviour."""

    def test_init_creates_log_dir(self, tmp_path: Path) -> None:
        """__init__ creates the log directory if it does not exist."""
        log_dir = tmp_path / "my-logs"
        assert not log_dir.exists()
        ProcessSupervisor(log_dir=str(log_dir))
        assert log_dir.exists()

    def test_init_uses_get_config_fallback(self) -> None:
        """__init__ falls back to get_config() when no log_dir given."""
        fake_log_dir = str(Path("/tmp/anvil-supervisor-test"))
        with (
            patch("anvil.supervisor.supervisor.get_config") as mock_config,
            patch.object(Path, "mkdir") as mock_mkdir,
        ):
            mock_config.return_value = {"log_dir": fake_log_dir}
            sv = ProcessSupervisor()
            assert str(sv.log_dir) == fake_log_dir
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    def test_init_initializes_empty_processes(self, tmp_path: Path) -> None:
        """__init__ starts with an empty _processes dict."""
        sv = ProcessSupervisor(log_dir=str(tmp_path))
        assert sv._processes == {}


class TestProcessSupervisorLifecycle:
    """ProcessSupervisor start / stop / status / stop_all."""

    def test_status_stopped_initially(self, tmp_path: Path) -> None:
        """A supervisor with no started processes reports 'stopped'."""
        sv = ProcessSupervisor(log_dir=str(tmp_path))
        assert sv.status("nonexistent") == "stopped"
        assert sv.is_running("nonexistent") is False

    def test_start_launches_subprocess(self, tmp_path: Path) -> None:
        """start() calls subprocess.Popen with the right arguments."""
        sv = ProcessSupervisor(log_dir=str(tmp_path))
        mock_proc = MagicMock()
        mock_proc.pid = 42
        mock_proc.poll.return_value = None

        with patch(
            "anvil.supervisor.supervisor.subprocess.Popen", return_value=mock_proc
        ) as mock_popen:
            sv.start("worker", ["sleep", "60"])

        mock_popen.assert_called_once()
        args, kwargs = mock_popen.call_args
        assert args[0] == ["sleep", "60"]
        assert kwargs["preexec_fn"] == os.setsid
        assert kwargs["stderr"] == subprocess.STDOUT
        assert sv._processes["worker"] is mock_proc

    def test_start_duplicate_is_noop(self, tmp_path: Path) -> None:
        """Starting a process that is already running is a no-op."""
        sv = ProcessSupervisor(log_dir=str(tmp_path))
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None

        with patch(
            "anvil.supervisor.supervisor.subprocess.Popen", return_value=mock_proc
        ):
            sv.start("dup", ["sleep", "60"])
            sv.start("dup", ["sleep", "999"])

        assert sv._processes["dup"] is mock_proc

    def test_start_creates_log_file(self, tmp_path: Path) -> None:
        """start() creates a log file and opens it for stdout."""
        sv = ProcessSupervisor(log_dir=str(tmp_path))
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None

        with patch(
            "anvil.supervisor.supervisor.subprocess.Popen", return_value=mock_proc
        ) as mock_popen:
            sv.start("logger", ["echo", "hello"])

        log_path = tmp_path / "logger.log"
        assert log_path.exists()
        args, kwargs = mock_popen.call_args
        stdout_handle = kwargs["stdout"]
        assert stdout_handle.name == str(log_path)

    def test_stop_nonexistent_is_noop(self, tmp_path: Path) -> None:
        """Stopping a process that was never started does not raise."""
        sv = ProcessSupervisor(log_dir=str(tmp_path))
        sv.stop("never-started")

    def test_stop_terminates_process(self, tmp_path: Path) -> None:
        """stop() sends SIGTERM and removes the process from tracking."""
        sv = ProcessSupervisor(log_dir=str(tmp_path))
        mock_proc = MagicMock()
        mock_proc.pid = 42
        mock_proc.poll.return_value = None

        sv._processes["test"] = mock_proc

        with (
            patch.object(os, "killpg") as mock_killpg,
            patch.object(os, "getpgid", return_value=999),
        ):
            sv.stop("test")

        mock_killpg.assert_called_once_with(999, signal.SIGTERM)
        mock_proc.wait.assert_called_once_with(timeout=10)
        assert "test" not in sv._processes

    def test_stop_already_exited_is_noop(self, tmp_path: Path) -> None:
        """stop() does nothing when the process has already exited."""
        sv = ProcessSupervisor(log_dir=str(tmp_path))
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0

        sv._processes["test"] = mock_proc

        with (
            patch.object(os, "killpg") as mock_killpg,
            patch.object(os, "getpgid") as mock_getpgid,
        ):
            sv.stop("test")

        mock_killpg.assert_not_called()
        mock_getpgid.assert_not_called()

    def test_stop_timeout_sends_sigkill(self, tmp_path: Path) -> None:
        """SIGTERM timeout triggers SIGKILL fallback."""
        sv = ProcessSupervisor(log_dir=str(tmp_path))
        mock_proc = MagicMock()
        mock_proc.pid = 42
        mock_proc.poll.return_value = None
        mock_proc.wait.side_effect = subprocess.TimeoutExpired(cmd="mock", timeout=10)

        sv._processes["test"] = mock_proc

        killpg_signals: list[int] = []

        def _tracking_killpg(pgid: int, sig: int) -> None:
            killpg_signals.append(sig)

        with (
            patch.object(os, "getpgid", return_value=999),
            patch.object(os, "killpg", _tracking_killpg),
        ):
            sv.stop("test")

        assert len(killpg_signals) == 2
        assert killpg_signals[0] == signal.SIGTERM
        assert killpg_signals[1] == signal.SIGKILL
        assert "test" not in sv._processes

    def test_stop_process_lookup_raises_sigkill(self, tmp_path: Path) -> None:
        """When os.killpg raises ProcessLookupError, SIGKILL is sent as fallback."""
        sv = ProcessSupervisor(log_dir=str(tmp_path))
        mock_proc = MagicMock()
        mock_proc.pid = 42
        mock_proc.poll.return_value = None

        sv._processes["test"] = mock_proc

        killpg_signals: list[int] = []

        def _raising_killpg(pgid: int, sig: int) -> None:
            killpg_signals.append(sig)
            if sig == signal.SIGTERM:
                raise ProcessLookupError(f"no process with PGID {pgid}")

        with (
            patch.object(os, "getpgid", return_value=999),
            patch.object(os, "killpg", _raising_killpg),
        ):
            sv.stop("test")

        assert len(killpg_signals) == 2
        assert killpg_signals[0] == signal.SIGTERM
        assert killpg_signals[1] == signal.SIGKILL
        assert "test" not in sv._processes

    def test_stop_all(self, tmp_path: Path) -> None:
        """stop_all stops every tracked process."""
        sv = ProcessSupervisor(log_dir=str(tmp_path))
        mock_a = MagicMock()
        mock_a.pid = 10
        mock_a.poll.return_value = None
        mock_b = MagicMock()
        mock_b.pid = 20
        mock_b.poll.return_value = None
        sv._processes["a"] = mock_a
        sv._processes["b"] = mock_b

        with (
            patch.object(os, "killpg"),
            patch.object(os, "getpgid", return_value=999),
        ):
            sv.stop_all()

        assert "a" not in sv._processes
        assert "b" not in sv._processes

    def test_status_running(self, tmp_path: Path) -> None:
        """status() returns 'running' for a running process."""
        sv = ProcessSupervisor(log_dir=str(tmp_path))
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        sv._processes["live"] = mock_proc
        assert sv.status("live") == "running"

    def test_status_exited(self, tmp_path: Path) -> None:
        """status() returns 'exited(N)' for a finished process."""
        sv = ProcessSupervisor(log_dir=str(tmp_path))
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0
        mock_proc.returncode = 0
        sv._processes["done"] = mock_proc
        assert sv.status("done") == "exited(0)"

    def test_status_exited_nonzero(self, tmp_path: Path) -> None:
        """status() reports non-zero exit codes."""
        sv = ProcessSupervisor(log_dir=str(tmp_path))
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 1
        mock_proc.returncode = 1
        sv._processes["failed"] = mock_proc
        assert sv.status("failed") == "exited(1)"

    def test_status_stopped(self, tmp_path: Path) -> None:
        """status() returns 'stopped' for untracked process."""
        sv = ProcessSupervisor(log_dir=str(tmp_path))
        assert sv.status("unknown") == "stopped"

    def test_is_running_true(self, tmp_path: Path) -> None:
        """is_running returns True for a running process."""
        sv = ProcessSupervisor(log_dir=str(tmp_path))
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        sv._processes["live"] = mock_proc
        assert sv.is_running("live") is True

    def test_is_running_false(self, tmp_path: Path) -> None:
        """is_running returns False for a stopped process."""
        sv = ProcessSupervisor(log_dir=str(tmp_path))
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0
        sv._processes["done"] = mock_proc
        assert sv.is_running("done") is False

    def test_is_running_false_for_untracked(self, tmp_path: Path) -> None:
        """is_running returns False for an untracked process."""
        sv = ProcessSupervisor(log_dir=str(tmp_path))
        assert sv.is_running("ghost") is False


class TestProcessSupervisorEdgeCases:
    """Edge-case behaviour for ProcessSupervisor."""

    def test_start_replaces_finished_process(self, tmp_path: Path) -> None:
        """A finished process is replaced when start() is called again."""
        sv = ProcessSupervisor(log_dir=str(tmp_path))
        old_proc = MagicMock()
        old_proc.poll.return_value = 0
        sv._processes["worker"] = old_proc

        new_proc = MagicMock()
        new_proc.pid = 99
        new_proc.poll.return_value = None

        with patch(
            "anvil.supervisor.supervisor.subprocess.Popen", return_value=new_proc
        ):
            sv.start("worker", ["sleep", "30"])

        assert sv._processes["worker"] is new_proc

    def test_stop_missing_from_dict(self, tmp_path: Path) -> None:
        """stop() handles a process that was never added (safety)."""
        sv = ProcessSupervisor(log_dir=str(tmp_path))
        sv.stop("missing")

    def test_status_empty_processes(self, tmp_path: Path) -> None:
        """status() handles empty state gracefully."""
        sv = ProcessSupervisor(log_dir=str(tmp_path))
        assert sv.status("anything") == "stopped"
