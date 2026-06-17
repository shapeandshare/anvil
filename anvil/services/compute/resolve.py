from __future__ import annotations

from typing import Any

from anvil.services.compute.errors import ComputeBackendUnavailable

_RESOLUTION_CACHE: dict[str, dict[str, Any]] = {}


def _detect_device() -> str:
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
    except ImportError:
        pass
    return "cpu"


def _modal_available() -> bool:
    try:
        import modal  # noqa: F401
    except ImportError:
        return False
    return True


def resolve_backend(config: dict[str, Any]) -> dict[str, Any]:
    """Map ``compute_backend`` string to a resolved engine + device.

    D4 rule:
    - ``auto`` / ``local-cpu`` / ``local-gpu`` silently fall back to CPU
      if the preferred engine/accelerator is missing.
    - ``modal`` **must not** silently fall back to local — raises
      ``ComputeBackendUnavailable`` if not available.
    """
    backend = config.get("compute_backend", "auto")

    if backend == "modal":
        if not _modal_available():
            raise ComputeBackendUnavailable(
                "Modal selected but not available. "
                "Install via: pip install anvil[compute] "
                "and authenticate via: modal token new"
            )
        return {"engine": "torch", "device": "cuda", "backend": "modal"}

    if backend == "local-gpu":
        device = _detect_device()
        if device != "cpu" and _torch_available():
            return {"engine": "torch", "device": device, "backend": "local"}
        return {"engine": "stdlib", "device": "cpu", "backend": "local"}

    if backend == "local-cpu":
        return {"engine": "stdlib", "device": "cpu", "backend": "local"}

    # auto — prefer GPU if available
    if backend == "auto":
        device = _detect_device()
        if device != "cpu" and _torch_available():
            return {"engine": "torch", "device": device, "backend": "local"}
        return {"engine": "stdlib", "device": "cpu", "backend": "local"}

    raise ComputeBackendUnavailable(f"Unknown compute_backend: {backend!r}")


def _torch_available() -> bool:
    try:
        import torch  # noqa: F401
        return True
    except ImportError:
        return False