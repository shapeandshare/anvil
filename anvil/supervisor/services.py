# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""MLflow service lifecycle management.

Provides the :class:`MLflowService` class for starting, stopping, and
monitoring an MLflow tracking server as a managed subprocess. Includes
zombie-port cleanup logic to gracefully handle orphaned processes on
restart.
"""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from ..config import get_config
from ..workspace.workspace_paths import WorkspacePaths


class MLflowService:
    """Manages the lifecycle of an MLflow tracking server subprocess.

    Wraps the ``mlflow server`` command in a :class:`subprocess.Popen`
    managed instance. On start, any zombie process occupying the target
    port is killed before launching. PID tracking via a ``mlflow.pid``
    file under the configured log directory enables external monitoring.

    Parameters
    ----------
    cfg : dict
        Application configuration dictionary (retrieved via
        :func:`~anvil.config.get_config`). Uses keys ``log_dir``,
        ``mlflow_port``, ``mlflow_uri``, and ``mlflow_backend_store_uri``.
    workspace_paths : WorkspacePaths or None, optional
        If provided, the MLflow runs directory (``mlruns_dir``) is
        derived from this value object instead of defaulting to
        ``./mlruns`` relative to CWD.
    """

    def __init__(
        self,
        workspace_paths: WorkspacePaths | None = None,
    ) -> None:
        cfg = get_config()
        if workspace_paths is not None:
            self.mlruns_dir = workspace_paths.mlruns_dir
        else:
            self.mlruns_dir = Path("mlruns")
        self.mlruns_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir = Path(cfg["log_dir"])
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "mlflow.log"
        self.process: subprocess.Popen[bytes] | None = None
        self.port = cfg["mlflow_port"]
        self._tracking_uri: str = cfg["mlflow_uri"]
        self._backend_store_uri = cfg["mlflow_backend_store_uri"]

    def _free_port(self) -> None:
        """Kill any zombie process occupying the configured MLflow port.

        Scans processes listening on ``self.port`` and sends ``SIGTERM``
        (followed by ``SIGKILL`` after a 1-second grace period) to any
        matching Python, MLflow, or uvicorn processes. Only targets
        processes whose command name contains ``python``, ``mlflow``, or
        ``uvicorn`` to avoid killing unrelated system services.

        Uses ``lsof`` and ``ps`` (macOS / Linux) and silently exits on
        ``FileNotFoundError`` when these utilities are unavailable (e.g.
        minimal containers).
        """
        try:
            result = subprocess.run(
                ["lsof", "-ti", f":{self.port}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if not result.stdout.strip():
                return
            pids = []
            for pid_str in result.stdout.strip().split():
                try:
                    comm = subprocess.run(
                        ["ps", "-p", pid_str, "-o", "comm="],
                        capture_output=True,
                        text=True,
                        timeout=3,
                    )
                    cmd = comm.stdout.strip().lower()
                    if any(kw in cmd for kw in ("python", "mlflow", "uvicorn")):
                        pids.append(int(pid_str))
                except (subprocess.TimeoutExpired, ValueError):
                    pass
            if not pids:
                return
            for pid in pids:
                try:
                    os.kill(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline:
                time.sleep(0.3)
                remaining = []
                for pid in pids:
                    try:
                        os.kill(pid, 0)
                        remaining.append(pid)
                    except ProcessLookupError:
                        pass
                if not remaining:
                    return
                for pid in remaining:
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    def start(self) -> None:
        """Start the MLflow tracking server as a subprocess.

        If the server is already running (based on process poll status),
        this is a no-op. Before launching, the target port is freed via
        :meth:`_free_port`. The server process is started with ``preexec_fn
        = os.setsid`` so that the entire process group can be signalled
        during shutdown.

        The process PID is recorded to ``{log_dir}/mlflow.pid``.
        """
        if self.process is not None and self.process.poll() is None:
            return
        self._free_port()
        mlflow_bin = str(Path(sys.executable).parent / "mlflow")
        self.process = subprocess.Popen(
            [
                mlflow_bin,
                "server",
                "--backend-store-uri",
                self._backend_store_uri,
                "--host",
                "0.0.0.0",
                "--port",
                str(self.port),
                "--workers",
                "1",
                "--allowed-hosts",
                "*",
            ],
            stdout=open(self.log_file, "w"),
            stderr=subprocess.STDOUT,
            preexec_fn=os.setsid,
        )
        (self.log_dir / "mlflow.pid").write_text(str(self.process.pid))

    def stop(self) -> None:
        """Stop the MLflow tracking server subprocess.

        Sends ``SIGTERM`` to the entire process group and waits up to
        10 seconds for graceful shutdown. If the process does not exit
        in time, ``SIGKILL`` is sent. The process reference is cleared
        and the PID file is removed.
        """
        pid_file = self.log_dir / "mlflow.pid"
        if self.process is None or self.process.poll() is not None:
            pid_file.unlink(missing_ok=True)
            return
        try:
            os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            self.process.wait(timeout=10)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
        finally:
            self.process = None
            pid_file.unlink(missing_ok=True)

    async def async_stop(self) -> None:
        """Async variant of :meth:`stop` — wraps the blocking wait in a thread.

        Use this from async context (e.g. FastAPI route handlers) to avoid
        blocking the event loop for up to 10 seconds during MLflow shutdown.
        """
        pid_file = self.log_dir / "mlflow.pid"
        if self.process is None or self.process.poll() is not None:
            pid_file.unlink(missing_ok=True)
            return
        try:
            os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            await asyncio.to_thread(self.process.wait, timeout=10)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
        finally:
            self.process = None
            pid_file.unlink(missing_ok=True)

    @property
    def is_running(self) -> bool:
        """Check whether the MLflow server subprocess is currently running.

        Returns
        -------
        bool
            ``True`` if the process has been started and has not exited.
        """
        return self.process is not None and self.process.poll() is None

    @property
    def tracking_uri(self) -> str:
        """Return the MLflow tracking server URI.

        Returns
        -------
        str
            The URI clients should use to reach the MLflow tracking
            server (e.g. ``http://127.0.0.1:5001``).
        """
        return self._tracking_uri
