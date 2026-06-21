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
import tempfile
from pathlib import Path

import pytest

from anvil.supervisor.supervisor import (
    ProcessSupervisor,
    kill_pid_file,
    read_pid,
    write_pid,
)

# --
# PID file helpers
# --


class TestWriteReadPid:
    """Round-trip write_pid → read_pid."""

    def test_write_and_read(self):
        """write_pid creates a file that read_pid can parse."""
        with tempfile.TemporaryDirectory() as tmp:
            path = write_pid("test-proc", pid_dir=tmp)
            assert path.exists()
            pid = read_pid("test-proc", pid_dir=tmp)
            assert pid == os.getpid()

    def test_read_nonexistent(self):
        """read_pid returns None for a non-existent PID file."""
        with tempfile.TemporaryDirectory() as tmp:
            pid = read_pid("ghost", pid_dir=tmp)
            assert pid is None

    def test_write_creates_dir(self):
        """write_pid creates the pid_dir if it does not exist."""
        with tempfile.TemporaryDirectory() as tmp:
            nested = Path(tmp) / "sub" / "pids"
            write_pid("nested", pid_dir=str(nested))
            assert nested.exists()
            assert (nested / "nested.pid").exists()


class TestKillPidFile:
    """kill_pid_file behaviour for existing and missing processes."""

    def test_kill_nonexistent_returns_false(self):
        """kill_pid_file returns False when the PID file does not exist."""
        with tempfile.TemporaryDirectory() as tmp:
            result = kill_pid_file("ghost", pid_dir=tmp)
            assert result is False

    def test_kill_nonexistent_process_cleans_up(self):
        """kill_pid_file cleans up the PID file even if the process
        is already gone."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gone.pid"
            path.write_text("999999")
            result = kill_pid_file("gone", pid_dir=tmp)
            # 999999 does not exist (or we can't signal it).
            # The method should return False and clean up the file.
            assert result is False
            assert not path.exists()


# --
# ProcessSupervisor
# --


class TestProcessSupervisor:
    """ProcessSupervisor lifecycle tests using short-lived subprocesses."""

    def test_status_stopped_initially(self):
        """A supervisor with no started processes reports 'stopped'."""
        sv = ProcessSupervisor()
        assert sv.status("nonexistent") == "stopped"
        assert sv.is_running("nonexistent") is False

    def test_start_and_stop(self):
        """start launches a process and stop terminates it."""
        with tempfile.TemporaryDirectory() as tmp:
            sv = ProcessSupervisor(log_dir=tmp)
            sv.start("sleeper", ["sleep", "0.1"])
            assert sv.is_running("sleeper") is True
            assert sv.status("sleeper") == "running"

            sv.stop("sleeper")
            assert sv.is_running("sleeper") is False

    def test_duplicate_start_is_noop(self):
        """Starting a process that is already running should be a
        no-op."""
        with tempfile.TemporaryDirectory() as tmp:
            sv = ProcessSupervisor(log_dir=tmp)
            sv.start("dup", ["sleep", "0.2"])
            sv.start("dup", ["sleep", "0.2"])
            assert sv.is_running("dup") is True
            sv.stop_all()

    def test_stop_nonexistent_is_noop(self):
        """Stopping a process that was never started should not
        raise."""
        sv = ProcessSupervisor()
        sv.stop("never-started")  # should not raise

    def test_stop_all(self):
        """stop_all stops all tracked processes."""
        with tempfile.TemporaryDirectory() as tmp:
            sv = ProcessSupervisor(log_dir=tmp)
            sv.start("p1", ["sleep", "0.1"])
            sv.start("p2", ["sleep", "0.1"])
            sv.stop_all()
            assert sv.is_running("p1") is False
            assert sv.is_running("p2") is False

    def test_status_exited(self):
        """A process that has exited should report its returncode."""
        with tempfile.TemporaryDirectory() as tmp:
            sv = ProcessSupervisor(log_dir=tmp)
            sv.start("quick", ["true"])
            # Wait for process to finish, then poll.
            proc = sv._processes["quick"]
            proc.wait(timeout=5)
            status = sv.status("quick")
            assert status.startswith("exited(")

    def test_start_creates_log_file(self):
        """start should create a log file for the process output."""
        import sys

        with tempfile.TemporaryDirectory() as tmp:
            sv = ProcessSupervisor(log_dir=tmp)
            sv.start(
                "logger",
                [
                    sys.executable,
                    "-c",
                    "import sys; print('hello', flush=True); sys.stdout.flush()",
                ],
            )
            # Wait for the quick process to finish and flush output.
            proc = sv._processes.get("logger")
            if proc is not None:
                proc.wait(timeout=5)
            sv.stop("logger")
            log = Path(tmp) / "logger.log"
            assert log.exists()
            assert log.stat().st_size > 0
