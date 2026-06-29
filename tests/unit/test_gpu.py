# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for GPU detection and device resolution.

Uses monkeypatch to simulate torch availability, MPS, CUDA, and
no-GPU scenarios.  Also tests resolve_device helper.
"""

from __future__ import annotations

import sys
from typing import Any

import pytest

from anvil.gpu import GpuInfo, detect_gpu, resolve_device
from anvil.services._shared.device_type import DeviceType


class _MockModule:
    def __init__(self, **attrs: Any) -> None:
        for k, v in attrs.items():
            setattr(self, k, v)


# ── GpuInfo model ─────────────────────────────────────────────────────────


def test_gpu_info_defaults() -> None:
    info = GpuInfo()
    assert info.available is False
    assert info.backend is None
    assert info.device_name is None


def test_gpu_info_with_values() -> None:
    info = GpuInfo(
        available=True,
        backend=DeviceType.CUDA,
        device_name="NVIDIA Test GPU",
        memory_total_gb=8.0,
        memory_available_gb=4.0,
        compute_capability="8.0",
        torch_version="2.0.0",
        cuda_version="12.0",
        errors=["test error"],
    )
    assert info.available is True
    assert info.backend == DeviceType.CUDA
    assert info.device_name == "NVIDIA Test GPU"


# ── detect_gpu ────────────────────────────────────────────────────────────


def test_detect_gpu_no_torch(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "torch", None)
    info = detect_gpu()
    assert info.available is False
    assert "torch not installed" in info.errors[0]


def test_detect_gpu_mps_available(monkeypatch) -> None:
    mps_b = _MockModule(is_available=lambda: True)
    cuda_b = _MockModule(is_available=lambda: False)
    mock_torch = _MockModule(
        __version__="2.1.0", backends=_MockModule(mps=mps_b), cuda=cuda_b
    )
    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setattr("anvil.gpu._get_mps_device_name", lambda: "Apple M2")
    monkeypatch.setattr("anvil.gpu._get_mps_memory", lambda: 16.0)

    info = detect_gpu()
    assert info.available is True
    assert info.backend == DeviceType.MPS
    assert info.device_name == "Apple M2"
    assert info.torch_version == "2.1.0"


def test_detect_gpu_mps_memory_fails_gracefully(monkeypatch) -> None:
    mps_b = _MockModule(is_available=lambda: True)
    cuda_b = _MockModule(is_available=lambda: False)
    mock_torch = _MockModule(
        __version__="2.1.0", backends=_MockModule(mps=mps_b), cuda=cuda_b
    )
    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setattr("anvil.gpu._get_mps_device_name", lambda: "Apple M2")

    def _raise_oserror() -> float:
        raise OSError("fail")

    monkeypatch.setattr("anvil.gpu._get_mps_memory", _raise_oserror)

    info = detect_gpu()
    assert info.available is True
    assert info.backend == DeviceType.MPS
    assert info.memory_total_gb is None


def test_detect_gpu_cuda_available(monkeypatch) -> None:
    cuda_b = _MockModule(
        is_available=lambda: True,
        get_device_name=lambda i: "NVIDIA RTX 4090",
        get_device_properties=lambda i: _MockModule(total_memory=24 * 1024**3),
        mem_get_info=lambda i: (12 * 1024**3, 24 * 1024**3),
        get_device_capability=lambda i: (8, 9),
    )
    mock_torch = _MockModule(
        __version__="2.0.0",
        backends=_MockModule(mps=_MockModule(is_available=lambda: False)),
        cuda=cuda_b,
        version=_MockModule(cuda="12.1"),
    )
    monkeypatch.setitem(sys.modules, "torch", mock_torch)

    info = detect_gpu()
    assert info.available is True
    assert info.backend == DeviceType.CUDA
    assert info.device_name == "NVIDIA RTX 4090"
    assert info.memory_total_gb == pytest.approx(24.0, rel=0.1)
    assert info.memory_available_gb == pytest.approx(12.0, rel=0.1)
    assert info.compute_capability == "8.9"
    assert info.cuda_version == "12.1"


def test_detect_gpu_cuda_mem_get_info_fails(monkeypatch) -> None:
    def _raise(*a, **kw):
        raise RuntimeError("cuda error")

    cuda_b = _MockModule(
        is_available=lambda: True,
        get_device_name=lambda i: "NVIDIA RTX 3060",
        get_device_properties=lambda i: _MockModule(total_memory=12 * 1024**3),
        mem_get_info=_raise,
        get_device_capability=lambda i: (7, 5),
    )
    mock_torch = _MockModule(
        __version__="2.0.1",
        backends=_MockModule(mps=_MockModule(is_available=lambda: False)),
        cuda=cuda_b,
        version=_MockModule(cuda="11.8"),
    )
    monkeypatch.setitem(sys.modules, "torch", mock_torch)

    info = detect_gpu()
    assert info.available is True
    assert info.backend == DeviceType.CUDA
    assert info.memory_available_gb is None


def test_detect_gpu_torch_no_gpu(monkeypatch) -> None:
    mock_torch = _MockModule(
        __version__="2.1.0",
        backends=_MockModule(mps=_MockModule(is_available=lambda: False)),
        cuda=_MockModule(is_available=lambda: False),
    )
    monkeypatch.setitem(sys.modules, "torch", mock_torch)

    info = detect_gpu()
    assert info.available is False
    assert info.backend is None
    assert info.torch_version == "2.1.0"


def test_detect_gpu_runtime_error(monkeypatch) -> None:
    mock_torch = _MockModule(
        __version__="2.0.0",
        backends=_MockModule(mps=_MockModule(is_available=lambda: True)),
        cuda=_MockModule(),
    )
    monkeypatch.setitem(sys.modules, "torch", mock_torch)

    def _raise_runtime() -> str:
        raise RuntimeError("err")

    monkeypatch.setattr("anvil.gpu._get_mps_device_name", _raise_runtime)

    info = detect_gpu()
    # available was set to True before the RuntimeError; device_name is None
    assert info.available is True
    assert info.backend == DeviceType.MPS
    assert info.device_name is None
    assert len(info.errors) > 0


# ── _get_mps_device_name ──────────────────────────────────────────────────


def test_get_mps_device_name_arm64(monkeypatch) -> None:
    monkeypatch.setattr("platform.machine", lambda: "arm64")
    monkeypatch.setattr(
        "subprocess.run",
        lambda *a, **kw: _MockModule(stdout="Apple M2 Pro\n", stderr="", returncode=0),
    )
    from anvil.gpu import _get_mps_device_name

    assert _get_mps_device_name() == "Apple M2 Pro"


def test_get_mps_device_name_arm64_sysctl_fails(monkeypatch) -> None:
    monkeypatch.setattr("platform.machine", lambda: "arm64")

    def _raise_notfound(*a, **kw):
        raise FileNotFoundError("no sysctl")

    monkeypatch.setattr("subprocess.run", _raise_notfound)
    from anvil.gpu import _get_mps_device_name

    assert _get_mps_device_name() == "Apple Silicon"


def test_get_mps_device_name_non_arm64(monkeypatch) -> None:
    monkeypatch.setattr("platform.machine", lambda: "x86_64")
    from anvil.gpu import _get_mps_device_name

    assert _get_mps_device_name() == "MPS (x86_64)"


# ── _get_mps_memory ───────────────────────────────────────────────────────


def test_get_mps_memory_with_psutil(monkeypatch) -> None:
    monkeypatch.setattr(
        "psutil.virtual_memory", lambda: _MockModule(total=16 * 1024**3)
    )
    from anvil.gpu import _get_mps_memory

    assert _get_mps_memory() == pytest.approx(16.0, rel=0.1)


def test_get_mps_memory_without_psutil(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "psutil", None)
    from anvil.gpu import _get_mps_memory

    assert _get_mps_memory() is None


# ── resolve_device ────────────────────────────────────────────────────────


def test_resolve_device_preferred_returned() -> None:
    assert resolve_device("cpu") == "cpu"
    assert resolve_device("cuda:0") == "cuda:0"
    assert resolve_device("mps") == "mps"


def test_resolve_device_falls_back_to_cpu(monkeypatch) -> None:
    monkeypatch.setattr("anvil.gpu.detect_gpu", lambda: GpuInfo())
    assert resolve_device() == "cpu"


def test_resolve_device_detects_cuda(monkeypatch) -> None:
    monkeypatch.setattr(
        "anvil.gpu.detect_gpu", lambda: GpuInfo(available=True, backend=DeviceType.CUDA)
    )
    assert resolve_device() == "cuda:0"


def test_resolve_device_detects_mps(monkeypatch) -> None:
    monkeypatch.setattr(
        "anvil.gpu.detect_gpu", lambda: GpuInfo(available=True, backend=DeviceType.MPS)
    )
    assert resolve_device() == "mps"


def test_resolve_device_cpu_backend(monkeypatch) -> None:
    info = GpuInfo(available=True, backend=DeviceType.CPU)
    monkeypatch.setattr("anvil.gpu.detect_gpu", lambda: info)
    assert resolve_device() == "cpu"
