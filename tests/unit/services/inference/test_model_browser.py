# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for the model browser eligibility function.

``ModelBrowserService.check_eligibility`` is a static method that
determines whether a ``ResourceEnvelope`` is satisfied by the host
system's RAM and GPU capabilities.
"""

from __future__ import annotations

import pytest

from anvil.services.inference.model_browser import ModelBrowserService
from anvil.services.inference.model_browser_types import ResourceEnvelope


class _FakeGpuInfo:
    """Test double for ``anvil.gpu.GpuInfo``.

    Parameters
    ----------
    available : bool
        Whether a GPU is available. Defaults to ``False``.
    backend : str | None
        The GPU backend identifier (``"cuda"``, ``"mps"``, or
        ``None``). Defaults to ``None``.
    memory_total_gb : float | None
        Total GPU memory in GB. Defaults to ``None``.
    """

    def __init__(
        self,
        *,
        available: bool = False,
        backend: str | None = None,
        memory_total_gb: float | None = None,
    ) -> None:
        """Initialize the test double with the given attributes."""
        self.available = available
        self.backend = backend
        self.memory_total_gb = memory_total_gb


####################################################################
# Red-phase tests (all skipped — implementation comes next)
####################################################################


def test_ram_too_low() -> None:
    """Return False when system RAM is below ``min_ram_gb``.

    Exercises the RAM guard: if the host has less RAM than the model
    requires, eligibility must be rejected regardless of GPU state.
    """
    envelope = ResourceEnvelope(
        min_ram_gb=16,
        min_vram_per_backend={"cpu": 0},
        supported_methods=["lora"],
    )
    gpu = _FakeGpuInfo()
    result = ModelBrowserService.check_eligibility(envelope, gpu, ram_total_gb=8)
    assert result is False


def test_ram_sufficient_no_gpu() -> None:
    """Return True when RAM is adequate and no GPU is present.

    CPU-only systems should pass eligibility when they meet the RAM
    requirement — no VRAM check is needed for the CPU path.
    """
    envelope = ResourceEnvelope(
        min_ram_gb=8,
        min_vram_per_backend={"cpu": 0},
        supported_methods=["lora"],
    )
    gpu = _FakeGpuInfo()
    result = ModelBrowserService.check_eligibility(envelope, gpu, ram_total_gb=16)
    assert result is True


def test_vram_sufficient_cuda() -> None:
    """Return True when CUDA GPU meets the per-backend VRAM requirement.

    A CUDA GPU with 8 GB VRAM satisfies a ``"cuda"`` requirement
    of 4 GB; RAM is also sufficient.
    """
    envelope = ResourceEnvelope(
        min_ram_gb=4,
        min_vram_per_backend={"cpu": 0, "cuda": 4},
        supported_methods=["lora"],
    )
    gpu = _FakeGpuInfo(available=True, backend="cuda", memory_total_gb=8.0)
    result = ModelBrowserService.check_eligibility(envelope, gpu, ram_total_gb=16)
    assert result is True


def test_vram_insufficient_cuda() -> None:
    """Return False when CUDA GPU has insufficient VRAM.

    A CUDA GPU with only 2 GB VRAM cannot satisfy a ``"cuda"``
    requirement of 4 GB, even though RAM is adequate.
    """
    envelope = ResourceEnvelope(
        min_ram_gb=4,
        min_vram_per_backend={"cpu": 0, "cuda": 4},
        supported_methods=["lora"],
    )
    gpu = _FakeGpuInfo(available=True, backend="cuda", memory_total_gb=2.0)
    result = ModelBrowserService.check_eligibility(envelope, gpu, ram_total_gb=16)
    assert result is False


def test_mps_best_effort() -> None:
    """Return True when MPS (unified memory) meets VRAM requirement.

    MPS GPUs share system memory, so the check compares against
    ``memory_total_gb``. 16 GB system RAM satisfies a ``"mps"``
    requirement of 12 GB.
    """
    envelope = ResourceEnvelope(
        min_ram_gb=8,
        min_vram_per_backend={"cpu": 0, "mps": 12},
        supported_methods=["qlora"],
    )
    gpu = _FakeGpuInfo(available=True, backend="mps", memory_total_gb=16.0)
    result = ModelBrowserService.check_eligibility(envelope, gpu, ram_total_gb=16)
    assert result is True


def test_hf_available_returns_bool() -> None:
    """``hf_available`` reports importability without importing the module.

    The result must be a plain ``bool`` and must agree with whether
    ``importlib.util.find_spec`` can locate ``huggingface_hub``.
    """
    import importlib.util

    result = ModelBrowserService.hf_available()
    expected = importlib.util.find_spec("huggingface_hub") is not None
    assert isinstance(result, bool)
    assert result is expected
