"""GPU detection and device selection for anvil."""

from pydantic import BaseModel, Field

from .services._shared.device_type import DeviceType


class GpuInfo(BaseModel):
    """Detected GPU capabilities of the host system."""

    available: bool = False
    backend: DeviceType | None = None
    device_name: str | None = None
    memory_total_gb: float | None = None
    memory_available_gb: float | None = None
    compute_capability: str | None = None
    torch_version: str | None = None
    cuda_version: str | None = None
    errors: list[str] = Field(default_factory=list)


def detect_gpu() -> GpuInfo:
    """Detect available GPU backends (CUDA / MPS) using torch if installed.

    Returns a GpuInfo instance — always safe to call, never raises.
    """
    info = GpuInfo()

    try:
        import torch

        info.torch_version = torch.__version__

        if torch.backends.mps.is_available():
            info.available = True
            info.backend = DeviceType.MPS
            info.device_name = _get_mps_device_name()
            try:
                info.memory_total_gb = _get_mps_memory()
            except Exception:
                pass
            return info

        if torch.cuda.is_available():
            info.available = True
            info.backend = DeviceType.CUDA
            info.device_name = torch.cuda.get_device_name(0)
            info.memory_total_gb = torch.cuda.get_device_properties(0).total_mem / (
                1024**3
            )
            try:
                free, _ = torch.cuda.mem_get_info(0)
                info.memory_available_gb = free / (1024**3)
            except Exception:
                pass
            cap = torch.cuda.get_device_capability(0)
            info.compute_capability = f"{cap[0]}.{cap[1]}"
            info.cuda_version = torch.version.cuda
            return info

    except ImportError:
        info.errors.append("torch not installed — install with: pip install torch")
    except Exception as exc:
        info.errors.append(f"GPU detection error: {exc}")

    return info


def _get_mps_device_name() -> str:
    """Return a human-readable name for the MPS device."""
    import platform

    machine = platform.machine()
    if machine == "arm64":
        import subprocess

        try:
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            return result.stdout.strip() or "Apple Silicon"
        except Exception:
            return "Apple Silicon"
    return f"MPS ({machine})"


def _get_mps_memory() -> float | None:
    """Return total system memory in GB as a proxy for MPS-usable memory."""
    import psutil

    return psutil.virtual_memory().total / (1024**3)


def resolve_device(preferred: str | None = None) -> str:
    """Resolve the best available device string for PyTorch.

    If *preferred* is provided it is returned immediately. Otherwise
    the function auto-detects the available GPU backend and returns
    ``"cuda:0"`` (CUDA), ``"mps"`` (Apple Silicon), or ``"cpu"``.

    Parameters
    ----------
    preferred : str, optional
        Explicit device override such as ``"cuda:0"``, ``"mps"``, or
        ``"cpu"``. Defaults to ``None``.

    Returns
    -------
    str
        A torch-compatible device string: ``"cuda:0"``, ``"mps"``, or
        ``"cpu"``.
    """
    if preferred is not None:
        return preferred

    info = detect_gpu()
    if info.available and info.backend:
        return {"cuda": "cuda:0", "mps": "mps"}.get(info.backend, "cpu")

    return "cpu"
