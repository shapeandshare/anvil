import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

from anvil.config import get_config, set_resolved_mlflow_uri


class MLflowService:
    def __init__(self):
        cfg = get_config()
        self.mlruns_dir = Path("mlruns")
        self.mlruns_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir = Path(cfg["log_dir"])
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "mlflow.log"
        self.process: subprocess.Popen | None = None
        self.port = cfg["mlflow_port"]
        self._tracking_uri = cfg["mlflow_uri"]
        self._backend_store_uri = cfg["mlflow_backend_store_uri"]

    @staticmethod
    def _detect_lan_ip() -> str | None:
        """Discover the primary LAN IP address of this host.

        Connects to a public resolver to determine which interface
        carries the default route, then returns that interface's IP.
        Returns None if detection fails.
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(1.0)
                s.connect(("1.1.1.1", 80))
                ip = s.getsockname()[0]
                if ip and not ip.startswith("127."):
                    return ip
            return None
        except (OSError, socket.error):
            return None

    def _free_port(self) -> None:
        """Kill any Python/MLflow zombie occupying our target port before starting.

        Only targets processes with 'python' or 'mlflow' in their command name
        to avoid killing system processes (e.g., macOS ControlCenter on 5000).
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

        # Auto-detect LAN IP so browser-facing MLflow links resolve from
        # other machines. Only override if the user hasn't explicitly
        # configured ANVIL_MLFLOW_URI (i.e. still points at 127.0.0.1).
        cfg = get_config()
        if cfg["mlflow_uri"] == f"http://127.0.0.1:{self.port}":
            lan_ip = self._detect_lan_ip()
            if lan_ip:
                self._tracking_uri = f"http://{lan_ip}:{self.port}"
                set_resolved_mlflow_uri(self._tracking_uri)

    def stop(self) -> None:
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

    @property
    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    @property
    def tracking_uri(self) -> str:
        return self._tracking_uri
