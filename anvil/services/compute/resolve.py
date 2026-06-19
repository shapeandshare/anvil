"""Compute backend resolution logic.

Maps user-facing ``compute_backend`` configuration strings to concrete
engine and device combinations.  Implements the D4 degraded-mode
convention:

- ``auto`` / ``local-cpu`` / ``local-gpu`` silently fall back to CPU
  if the preferred engine or accelerator is missing.
- ``modal`` explicitly raises ``ComputeBackendUnavailable`` if Modal is
  not installed -- it must never silently fall back to local.

Device detection utilities (``_detect_device``, ``_torch_available``,
``_modal_available``) are internal helpers used by the resolution
function.
"""

from typing import Any

from .compute_backend_unavailable import ComputeBackendUnavailable

#: Cache for resolution results keyed by input config fingerprint.
#: Used to avoid redundant device probing during repeated resolution
#: calls within the same request lifecycle.
_RESOLUTION_CACHE: dict[str, dict[str, Any]] = {}


def _detect_device() -> str:
    """Detect the best available compute device on the current host.

    Checks for CUDA GPUs first, then Apple Silicon MPS, and falls back
    to CPU.  Silently returns ``"cpu"`` if PyTorch is not installed.

    Returns
    -------
    str
        Device identifier: ``"cuda"``, ``"mps"``, or ``"cpu"``.
    """
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
    """Check whether the Modal cloud compute package is installed.

    Returns
    -------
    bool
        ``True`` if the ``modal`` package can be imported.
    """
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
    - ``modal`` **must not** silently fall back to local -- raises
      ``ComputeBackendUnavailable`` if not available.

    Parameters
    ----------
    config : dict[str, Any]
        Configuration dictionary containing a ``"compute_backend"`` key.
        Defaults to ``"auto"`` if the key is absent.

    Returns
    -------
    dict[str, Any]
        Resolved configuration with ``"engine"``, ``"device"``, and
        ``"backend"`` keys set.

    Raises
    ------
    ComputeBackendUnavailable
        If ``compute_backend`` is ``"modal"`` but the ``modal`` package
        is not installed, or if the value is not a recognised backend
        identifier.
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

    # auto -- prefer GPU if available
    if backend == "auto":
        device = _detect_device()
        if device != "cpu" and _torch_available():
            return {"engine": "torch", "device": device, "backend": "local"}
        return {"engine": "stdlib", "device": "cpu", "backend": "local"}

    raise ComputeBackendUnavailable(f"Unknown compute_backend: {backend!r}")


def _torch_available() -> bool:
    """Check whether the PyTorch package is installed.

    Returns
    -------
    bool
        ``True`` if ``torch`` can be imported.
    """
    try:
        import torch  # noqa: F401

        return True
    except ImportError:
        return False
