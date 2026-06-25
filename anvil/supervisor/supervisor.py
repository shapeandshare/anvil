# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Process supervisor for background service lifecycle.

Provides the :class:`ProcessSupervisor` class for managing subprocess
lifecycles (start, stop, status) and standalone helper functions
(:func:`write_pid`, :func:`read_pid`, :func:`kill_pid_file`) for
PID-file-based process tracking.

Module-level constant ``_PID_DIR`` controls the default directory
where PID files are stored.
"""

import os
import signal
import subprocess
from pathlib import Path

# Default directory for PID files created by write_pid / kill_pid_file.
_PID_DIR = "logs"


def write_pid(name: str, pid_dir: str = _PID_DIR) -> Path:
    """Write the current process PID to a named PID file.

    Creates the PID directory if it does not exist and writes the
    current process ID to ``{pid_dir}/{name}.pid``.

    Parameters
    ----------
    name : str
        Logical name for the process (used as the PID file stem).
    pid_dir : str, optional
        Directory in which to create the PID file. Defaults to
        the module-level ``_PID_DIR`` (``"logs"``).

    Returns
    -------
    Path
        Path to the created PID file.
    """
    path = Path(pid_dir) / f"{name}.pid"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(os.getpid()))
    return path


def read_pid(name: str, pid_dir: str = _PID_DIR) -> int | None:
    """Read a PID from a named PID file.

    Parameters
    ----------
    name : str
        Logical name of the process (PID file stem).
    pid_dir : str, optional
        Directory containing the PID file. Defaults to ``_PID_DIR``
        (``"logs"``).

    Returns
    -------
    int | None
        The PID as an integer, or ``None`` if the PID file does not
        exist.
    """
    path = Path(pid_dir) / f"{name}.pid"
    if not path.exists():
        return None
    return int(path.read_text().strip())


def kill_pid_file(
    name: str, sig: int = signal.SIGTERM, pid_dir: str = _PID_DIR
) -> bool:
    """Kill a process identified by a named PID file.

    Reads the PID from ``{pid_dir}/{name}.pid``, sends the specified
    signal, and removes the PID file. If the process is already gone
    (``ProcessLookupError``), the file is still cleaned up.

    Parameters
    ----------
    name : str
        Logical name of the process (PID file stem).
    sig : int, optional
        Signal to send (e.g. ``signal.SIGTERM``, ``signal.SIGKILL``).
        Defaults to ``signal.SIGTERM``.
    pid_dir : str, optional
        Directory containing the PID file. Defaults to ``_PID_DIR``
        (``"logs"``).

    Returns
    -------
    bool
        ``True`` if the signal was successfully sent, ``False`` if
        the PID file did not exist or the process could not be found.
    """
    pid = read_pid(name, pid_dir=pid_dir)
    if pid is None:
        return False
    path = Path(pid_dir) / f"{name}.pid"
    try:
        os.kill(pid, sig)
        path.unlink(missing_ok=True)
        return True
    except (ProcessLookupError, FileNotFoundError):
        path.unlink(missing_ok=True)
        return False


class ProcessSupervisor:
    """Manages background subprocess lifecycles via named entries.

    Provides methods to start, stop, and query the status of named
    subprocesses. Processes are started with ``preexec_fn=os.setsid``
    so that the entire process group can be signalled during shutdown.
    Log output is redirected to ``{log_dir}/{name}.log``.

    Parameters
    ----------
    log_dir : str, optional
        Directory for log and PID files. Created automatically if it
        does not exist. Defaults to ``"logs"``.
    """

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._processes: dict[str, subprocess.Popen[bytes]] = {}

    def start(self, name: str, cmd: list[str]) -> None:
        """Start a named background subprocess.

        If a process with the same name is already running, this is
        a no-op. The subprocess is started in a new process group via
        ``preexec_fn=os.setsid``. Standard output and standard error
        are redirected to ``{log_dir}/{name}.log``.

        Parameters
        ----------
        name : str
            Logical name for the process (used for tracking and log
            file naming).
        cmd : list[str]
            Command and arguments to execute (as passed to
            :class:`subprocess.Popen`).
        """
        if name in self._processes and self._processes[name].poll() is None:
            return
        log_file = self.log_dir / f"{name}.log"
        proc = subprocess.Popen(
            cmd,
            stdout=open(log_file, "w"),
            stderr=subprocess.STDOUT,
            preexec_fn=os.setsid,
        )
        self._processes[name] = proc

    def stop(self, name: str) -> None:
        """Stop a named background subprocess.

        Sends ``SIGTERM`` to the entire process group and waits up to
        10 seconds for graceful shutdown. If the process does not exit
        in time, ``SIGKILL`` is sent. The process entry is removed from
        the tracking dictionary.

        Parameters
        ----------
        name : str
            Logical name of the process to stop. No-op if the process
            does not exist or has already exited.
        """
        proc = self._processes.get(name)
        if proc is None or proc.poll() is not None:
            return
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            proc.wait(timeout=10)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        finally:
            self._processes.pop(name, None)

    def stop_all(self) -> None:
        """Stop all tracked background subprocesses.

        Iterates over a snapshot of the tracked process names and
        calls :meth:`stop` on each.
        """
        for name in list(self._processes.keys()):
            self.stop(name)

    def status(self, name: str) -> str:
        """Return the current status of a named process.

        Parameters
        ----------
        name : str
            Logical name of the process.

        Returns
        -------
        str
            One of ``"running"``, ``"stopped"``, or
            ``"exited(returncode)"``.
        """
        proc = self._processes.get(name)
        if proc is None:
            return "stopped"
        if proc.poll() is None:
            return "running"
        return f"exited({proc.returncode})"

    def is_running(self, name: str) -> bool:
        """Check whether a named process is currently running.

        Parameters
        ----------
        name : str
            Logical name of the process.

        Returns
        -------
        bool
            ``True`` if the process is tracked and has not exited.
        """
        return self.status(name) == "running"
