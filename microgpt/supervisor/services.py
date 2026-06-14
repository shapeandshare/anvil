import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from microgpt.config import get_config


class MLflowService:
    def __init__(self):
        cfg = get_config()
        self.mlruns_dir = Path("mlruns")
        self.mlruns_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir = Path(cfg["log_dir"])
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "mlflow.log"
        self.process: subprocess.Popen | None = None
        self.port = 5000
        self._tracking_uri = cfg["mlflow_uri"]
        self._backend_store_uri = cfg["mlflow_backend_store_uri"]

    def _free_port(self) -> None:
        """Kill any zombie process occupying our target port before starting."""
        try:
            result = subprocess.run(
                ["lsof", "-ti", f":{self.port}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if not result.stdout.strip():
                return
            for pid_str in result.stdout.strip().split():
                try:
                    os.kill(int(pid_str), signal.SIGTERM)
                except (ProcessLookupError, ValueError):
                    pass
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline:
                time.sleep(0.3)
                check = subprocess.run(
                    ["lsof", "-ti", f":{self.port}"],
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                if not check.stdout.strip():
                    return
                for pid_str in check.stdout.strip().split():
                    try:
                        os.kill(int(pid_str), signal.SIGKILL)
                    except (ProcessLookupError, ValueError):
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
                "127.0.0.1",
                "--port",
                str(self.port),
                "--workers",
                "1",
            ],
            stdout=open(self.log_file, "w"),
            stderr=subprocess.STDOUT,
            preexec_fn=os.setsid,
        )
        (self.log_dir / "mlflow.pid").write_text(str(self.process.pid))

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
