"""Process supervisor for background service lifecycle."""

import os
import signal
import subprocess
from pathlib import Path


class ProcessSupervisor:
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._processes: dict[str, subprocess.Popen] = {}

    def start(self, name: str, cmd: list[str]) -> None:
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
        for name in list(self._processes.keys()):
            self.stop(name)

    def status(self, name: str) -> str:
        proc = self._processes.get(name)
        if proc is None:
            return "stopped"
        if proc.poll() is None:
            return "running"
        return f"exited({proc.returncode})"

    def is_running(self, name: str) -> bool:
        return self.status(name) == "running"
