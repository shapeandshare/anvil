"""MPS metrics collector — Apple Silicon GPU utilisation and memory sampling.

Provides the ``MPSMetricsCollector`` class for querying Apple Silicon GPU
stats via the ``ioreg`` command-line tool.
"""

import platform
import re
import subprocess


class MPSMetricsCollector:
    """Collects GPU utilization and memory metrics on Apple Silicon.

    Uses the ``ioreg`` command-line tool to query the AGXAccelerator
    for device utilisation percentage and in-use system memory.
    """

    # The ``ioreg`` command to query the Apple GPU accelerator.
    IOREG_CMD: tuple[str, ...] = ("ioreg", "-r", "-c", "AGXAccelerator", "-d", "2")

    @staticmethod
    def is_available() -> bool:
        """Check whether MPS metrics collection is supported on this platform.

        Returns
        -------
        bool
            ``True`` on Apple Silicon macOS (arm64/Darwin).
        """
        return platform.system() == "Darwin" and platform.processor() == "arm"

    @staticmethod
    def _parse_ioreg(output: str) -> dict[str, float | None]:
        """Parse ``ioreg`` output for utilisation and memory values.

        Parameters
        ----------
        output : str
            Raw stdout from the ``ioreg`` command.

        Returns
        -------
        dict[str, float | None]
            Dict with keys ``"utilization_pct"`` and ``"memory_gb"``.
            Values are ``None`` if the corresponding field was not found.
        """
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
        """Query current GPU utilisation percentage.

        Returns
        -------
        float or None
            Utilisation percentage (0-100) or ``None`` if unavailable.
        """
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
        """Query current GPU in-use system memory in GB.

        Returns
        -------
        float or None
            Memory in gigabytes or ``None`` if unavailable.
        """
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
