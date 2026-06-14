from __future__ import annotations

import asyncio
import platform
import re
import subprocess
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from microgpt.services.tracking import TrackingService


class MPSMetricsCollector:

    IOREG_CMD: tuple[str, ...] = ("ioreg", "-r", "-c", "AGXAccelerator", "-d", "2")

    @staticmethod
    def is_available() -> bool:
        return platform.system() == "Darwin" and platform.processor() == "arm"

    @staticmethod
    def _parse_ioreg(output: str) -> dict[str, float | None]:
        result: dict[str, float | None] = {"utilization_pct": None, "memory_gb": None}
        util_match = re.search(r'"Device Utilization %"\s*=\s*(\d+)', output)
        if util_match:
            result["utilization_pct"] = float(util_match.group(1))
        mem_match = re.search(r'"In use system memory"\s*=\s*(\d+)', output)
        if mem_match:
            result["memory_gb"] = int(mem_match.group(1)) / (1024**3)
        return result

    @classmethod
    def get_utilization(cls) -> float | None:
        if not cls.is_available():
            return None
        try:
            result = subprocess.run(
                cls.IOREG_CMD, capture_output=True, text=True, timeout=2
            )
            parsed = cls._parse_ioreg(result.stdout)
            return parsed["utilization_pct"]
        except Exception:
            return None

    @classmethod
    def get_memory_gb(cls) -> float | None:
        if not cls.is_available():
            return None
        try:
            result = subprocess.run(
                cls.IOREG_CMD, capture_output=True, text=True, timeout=2
            )
            parsed = cls._parse_ioreg(result.stdout)
            return parsed["memory_gb"]
        except Exception:
            return None


class MPSSamplerThread(threading.Thread):

    def __init__(
        self,
        tracking_svc: TrackingService,
        run_id: str,
        interval: float = 5.0,
    ):
        super().__init__(daemon=True, name="mps-metrics-sampler")
        self._tracking_svc = tracking_svc
        self._run_id = run_id
        self._interval = interval
        self._stop_event = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None

    def run(self) -> None:
        import asyncio

        try:
            self._loop = asyncio.new_event_loop()
            step = 0
            while not self._stop_event.wait(self._interval):
                util = MPSMetricsCollector.get_utilization()
                mem = MPSMetricsCollector.get_memory_gb()
                if util is not None:
                    self._loop.run_until_complete(
                        self._tracking_svc.log_metric(
                            self._run_id, "system/gpu_util_pct", util, step=step
                        )
                    )
                if mem is not None:
                    self._loop.run_until_complete(
                        self._tracking_svc.log_metric(
                            self._run_id, "system/gpu_memory_gb", mem, step=step
                        )
                    )
                step += 1
        except Exception:
            pass
        finally:
            if self._loop:
                self._loop.close()

    def stop(self) -> None:
        self._stop_event.set()
