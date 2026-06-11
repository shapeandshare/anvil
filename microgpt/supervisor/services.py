import os
import signal
import subprocess
from pathlib import Path

from microgpt.config import get_config


class MLflowService:
    def __init__(self):
        cfg = get_config()
        self.mlruns_dir = Path("mlruns")
        self.mlruns_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = Path(cfg["log_dir"]) / "mlflow.log"
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.process: subprocess.Popen | None = None
        self.port = 5000

    def start(self) -> None:
        if self.process is not None and self.process.poll() is None:
            return
        self.process = subprocess.Popen(
            [
                "mlflow",
                "server",
                "--backend-store-uri",
                f"sqlite:///{self.mlruns_dir / 'mlflow.db'}",
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

    def stop(self) -> None:
        if self.process is None or self.process.poll() is not None:
            return
        try:
            os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            self.process.wait(timeout=10)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
        self.process = None

    @property
    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    @property
    def tracking_uri(self) -> str:
        return f"sqlite:///{self.mlruns_dir / 'mlflow.db'}"
