# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

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

from .._shared.device_type import DeviceType
from .compute_backend import ComputeBackend
from .compute_backend_result import ComputeBackendResult
from .compute_backend_unavailable import ComputeBackendUnavailable
from .training_engine import TrainingEngine

#: Cache for resolution results keyed by input config fingerprint.
#: Used to avoid redundant device probing during repeated resolution
#: calls within the same request lifecycle.
_RESOLUTION_CACHE: dict[str, dict[str, Any]] = {}


def _detect_device() -> DeviceType:
    """Detect the best available compute device on the current host.

    Checks for CUDA GPUs first, then Apple Silicon MPS, and falls back
    to CPU.  Silently returns ``DeviceType.CPU`` if PyTorch is not
    installed.

    Returns
    -------
    DeviceType
        Device identifier: ``DeviceType.CUDA``, ``DeviceType.MPS``, or
        ``DeviceType.CPU``.
    """
    try:
        import torch

        if torch.cuda.is_available():
            return DeviceType.CUDA
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return DeviceType.MPS
    except ImportError:
        pass
    return DeviceType.CPU


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
    - AUTO: auto-detect
    - LOCAL_CPU: stdlib, CPU
    - LOCAL_GPU: torch, detected device (or falls back to CPU + stdlib)
    - MODAL: Modal cloud

    When ``config["method"]`` is ``"lora"`` or ``"qlora"`` the routing
    is forced to the ``local-lora`` backend with torch engine and
    auto-detected device, regardless of ``compute_backend``.

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
    compute_backend_default: str = ComputeBackend.AUTO
    backend = config.get("compute_backend", compute_backend_default)

    # LoRA/QLoRA fine-tuning: always route to local-lora torch backend.
    method = config.get("method", "full")
    if method in ("lora", "qlora"):
        device = _detect_device()
        return {
            "engine": TrainingEngine.TORCH,
            "device": device,
            "backend": ComputeBackendResult.LOCAL,
        }

    if backend == ComputeBackend.MODAL:
        if not _modal_available():
            raise ComputeBackendUnavailable(
                "Modal selected but not available. "
                "Install via: pip install anvil[compute] "
                "and authenticate via: modal token new"
            )
        return {
            "engine": TrainingEngine.TORCH,
            "device": DeviceType.CUDA,
            "backend": ComputeBackendResult.MODAL,
        }

    if backend == ComputeBackend.LOCAL_GPU:
        device = _detect_device()
        if device != DeviceType.CPU and _torch_available():
            return {
                "engine": TrainingEngine.TORCH,
                "device": device,
                "backend": ComputeBackendResult.LOCAL,
            }
        return {
            "engine": TrainingEngine.STDLIB,
            "device": DeviceType.CPU,
            "backend": ComputeBackendResult.LOCAL,
        }

    if backend == ComputeBackend.LOCAL_CPU:
        return {
            "engine": TrainingEngine.STDLIB,
            "device": DeviceType.CPU,
            "backend": ComputeBackendResult.LOCAL,
        }

    # auto -- prefer GPU if available
    if backend == ComputeBackend.AUTO:
        device = _detect_device()
        if device != DeviceType.CPU and _torch_available():
            return {
                "engine": TrainingEngine.TORCH,
                "device": device,
                "backend": ComputeBackendResult.LOCAL,
            }
        return {
            "engine": TrainingEngine.STDLIB,
            "device": DeviceType.CPU,
            "backend": ComputeBackendResult.LOCAL,
        }

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
