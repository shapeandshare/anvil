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

import re
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

    When ``config["method"]`` is ``"lora"`` or ``"qlora"`` resolution is
    delegated to ``resolve_fine_tune()``, which applies size-based
    local-vs-SaaS routing under the D4 rules. No routing logic is
    duplicated here (Constitution §11.4).

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

    # LoRA/QLoRA fine-tuning: delegate to resolve_fine_tune().
    # Behavior-preserving for the local-only case (SaaS not configured
    # → local), while adding size-based SaaS routing when configured.
    method = config.get("method", "full")
    if method in ("lora", "qlora"):
        return resolve_fine_tune(config)

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


########################################################################
# Fine-tune compute routing
########################################################################


def _saas_configured() -> bool:
    """Check whether the SaaS compute backend is available.

    Returns ``False`` initially.  Spec 047 will implement the real
    availability check (e.g., configured endpoint, credentials).

    Returns
    -------
    bool
        ``True`` if a SaaS compute backend is configured and available.
    """
    return False


def _estimate_host_memory_gb() -> float:
    """Estimate available host memory for fine-tune ResourceSpec checks.

    Returns a best-effort estimate of readable memory in gigabytes.
    For CUDA devices the GPU VRAM is queried when torch is available.
    For other devices a conservative heuristic is used.

    Returns
    -------
    float
        Estimated available memory in GB.
    """
    device = _detect_device()
    if device == DeviceType.CUDA:
        try:
            import torch

            props = torch.cuda.get_device_properties(0)
            return round(props.total_memory / (1024**3), 1)
        except Exception:
            return 16.0
    if device == DeviceType.MPS:
        return 8.0
    return 4.0


#: Per-method memory multipliers used by the ResourceSpec VRAM estimate.
#: The QLoRA value already folds 4-bit quantization into the multiplier
#: (FR-022a): full-weight training needs optimizer + gradient copies
#: (~2x params), LoRA trains small adapters over frozen full-precision
#: weights (~1.2x), and QLoRA freezes 4-bit-quantized weights (~0.6x).
_METHOD_MEMORY_MULTIPLIER: dict[str, float] = {
    "full": 2.0,
    "lora": 1.2,
    "qlora": 0.6,
}

#: Fixed memory overhead (GB) for intermediate buffers during fine-tuning.
_FINE_TUNE_OVERHEAD_GB: float = 0.5


def resolve_fine_tune(config: dict[str, Any]) -> dict[str, Any]:
    """Resolve a fine-tune job to a compute backend by ResourceSpec.

    Estimates the memory required for the fine-tune
    (``base_params * method_multiplier + overhead``, FR-022a) and selects
    the backend under the D4 degraded-mode rules (ADR-015):

    - ``auto``: local if it fits the host envelope; SaaS if it does not
      fit and SaaS is configured; otherwise silently falls back to local
      (auto never raises, preserving the pre-046 local-only behavior when
      SaaS is unavailable).
    - ``local-cpu`` / ``local-gpu``: always local. Local backends degrade
      gracefully at runtime, so routing never raises here (NMRG — matches
      the pre-046 unconditional-local behavior).
    - ``saas``: SaaS if configured; otherwise raises
      ``ComputeBackendUnavailable`` (explicit-unavailable raises, D4).

    The QLoRA method multiplier already accounts for 4-bit quantization
    (see ``_METHOD_MEMORY_MULTIPLIER``); there is no separate quantization
    factor input.

    Parameters
    ----------
    config : dict[str, Any]
        Configuration with ``method`` (``"full"``, ``"lora"``,
        ``"qlora"``), ``base_model_ref`` (model identifier), and
        ``compute_backend`` (defaults to ``"auto"``).

    Returns
    -------
    dict[str, Any]
        Resolved config with ``"engine"``, ``"device"``, and ``"backend"``
        keys. ``"backend"`` is always a ``ComputeBackendResult`` value.

    Raises
    ------
    ComputeBackendUnavailable
        If ``compute_backend`` is ``"saas"`` but SaaS is not configured,
        or the value is not a recognised fine-tune backend identifier.
    """
    method: str = config.get("method", "lora")
    base_model_ref: str = config.get("base_model_ref", "default")
    compute_backend: str = config.get("compute_backend", ComputeBackend.AUTO)

    model_params_b: float = _parse_model_params(base_model_ref)
    method_mult: float = _METHOD_MEMORY_MULTIPLIER.get(method, 1.2)
    required_gb: float = model_params_b * method_mult + _FINE_TUNE_OVERHEAD_GB

    fits_local: bool = required_gb <= _estimate_host_memory_gb()
    device: DeviceType = _detect_device()
    saas_avail: bool = _saas_configured()

    local_result: dict[str, Any] = {
        "engine": TrainingEngine.TORCH,
        "device": device,
        "backend": ComputeBackendResult.LOCAL,
    }
    saas_result: dict[str, Any] = {
        "engine": TrainingEngine.TORCH,
        "device": device,
        "backend": ComputeBackendResult.SAAS,
    }

    if compute_backend == ComputeBackend.AUTO:
        if fits_local:
            return local_result
        if saas_avail:
            return saas_result
        return local_result

    if compute_backend in (ComputeBackend.LOCAL_CPU, ComputeBackend.LOCAL_GPU):
        return local_result

    if compute_backend == ComputeBackend.SAAS:
        if not saas_avail:
            raise ComputeBackendUnavailable(
                "SaaS compute backend selected but not configured. "
                "Configure the SaaS provider, or use a local compute_backend."
            )
        return saas_result

    raise ComputeBackendUnavailable(
        f"Unknown compute_backend for fine-tune: {compute_backend!r}"
    )


def _parse_model_params(base_model_ref: str) -> float:
    """Estimate a base model's parameter count in billions from its reference.

    Matches a parameter-count token of the form ``<number>b`` (case
    insensitive) that is preceded by a hyphen or start-of-string and
    followed by a hyphen or end-of-string, so ``"llama-2-13b-chat"``
    yields ``13.0`` (not ``2.0``) and ``"tinyllama-1.1b"`` yields ``1.1``.
    Falls back to ``7.0`` when no size token is present.

    Parameters
    ----------
    base_model_ref : str
        Model identifier string (e.g. ``"tinyllama-1.1b"``).

    Returns
    -------
    float
        Estimated parameter count in billions.
    """
    match = re.search(r"(?:^|[-_/])(\d+(?:\.\d+)?)b(?:$|[-_/])", base_model_ref.lower())
    if match:
        return float(match.group(1))
    return 7.0
