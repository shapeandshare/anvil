# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for :mod:`anvil.gpu` — GPU detection and device selection.

All tests use ``monkeypatch`` to avoid any real PyTorch or CUDA/MPS
dependency.  A mock torch module is injected into ``sys.modules`` so
that the lazy ``import torch`` inside ``detect_gpu()`` resolves to the
mock instead of the real package.
"""

import platform
import subprocess
import sys
import types

import pytest

import anvil.gpu as gpu_module
from anvil.services._shared.device_type import DeviceType

######################################################################
# Mock torch factory
######################################################################


def _mock_torch(
    *,
    mps_available: bool = False,
    cuda_available: bool = False,
    raise_on_mps: bool = False,
    raise_on_cuda: bool = False,
    device_name: str = "Mock GPU",
    total_memory_gb: int = 8,
    free_memory_gb: int = 4,
    compute_capability: tuple[int, int] = (8, 0),
    cuda_version: str = "12.1",
) -> types.SimpleNamespace:
    """Build a duck-typed mock torch module for GPU-detection tests.

    Parameters
    ----------
    mps_available : bool
        Whether ``torch.backends.mps.is_available()`` returns ``True``.
    cuda_available : bool
        Whether ``torch.cuda.is_available()`` returns ``True``.
    raise_on_mps : bool
        If ``True``, ``torch.backends.mps.is_available()`` raises
        ``RuntimeError``.
    raise_on_cuda : bool
        If ``True``, ``torch.cuda.is_available()`` raises ``RuntimeError``.
    device_name : str
        Value returned by ``torch.cuda.get_device_name(0)``.
    total_memory_gb : int
        Total GPU memory in GB (used for device properties).
    free_memory_gb : int
        Free GPU memory in GB (used for ``mem_get_info``).
    compute_capability : tuple of (int, int)
        CUDA compute capability returned by
        ``torch.cuda.get_device_capability(0)``.
    cuda_version : str
        Value of ``torch.version.cuda``.

    Returns
    -------
    types.SimpleNamespace
        A namespace object that quacks like the ``torch`` module for the
        purposes of ``detect_gpu()``.
    """

    # ── backends.mps ──────────────────────────────────────────────────
    def _mps_is_available() -> bool:
        if raise_on_mps:
            msg = "MPS is not available"
            raise RuntimeError(msg)
        return mps_available

    mock_mps = types.SimpleNamespace(is_available=_mps_is_available)

    # ── backends ──────────────────────────────────────────────────────
    mock_backends = types.SimpleNamespace(mps=mock_mps)

    # ── cuda ──────────────────────────────────────────────────────────
    def _cuda_is_available() -> bool:
        if raise_on_cuda:
            msg = "CUDA driver error"
            raise RuntimeError(msg)
        return cuda_available

    def _get_device_name(dev: int) -> str:
        return device_name

    def _get_device_properties(dev: int) -> types.SimpleNamespace:
        return types.SimpleNamespace(total_memory=total_memory_gb * 1024**3)

    def _mem_get_info(dev: int) -> tuple[int, int]:
        return (free_memory_gb * 1024**3, total_memory_gb * 1024**3)

    def _get_device_capability(dev: int) -> tuple[int, int]:
        return compute_capability

    mock_cuda = types.SimpleNamespace(
        is_available=_cuda_is_available,
        get_device_name=_get_device_name,
        get_device_properties=_get_device_properties,
        mem_get_info=_mem_get_info,
        get_device_capability=_get_device_capability,
    )

    # ── version ───────────────────────────────────────────────────────
    mock_version = types.SimpleNamespace(cuda=cuda_version)

    return types.SimpleNamespace(
        __version__="2.1.0",
        backends=mock_backends,
        cuda=mock_cuda,
        version=mock_version,
    )


def _patch_torch(
    monkeypatch: pytest.MonkeyPatch, **kwargs: object
) -> types.SimpleNamespace:
    """Inject a mock ``torch`` into ``sys.modules`` and ``gpu_module``.

    ``detect_gpu()`` does a lazy ``import torch`` inside the function
    body, which Python resolves via ``sys.modules["torch"]``.  This
    helper also sets ``gpu_module.torch`` so that any attribute-level
    access (e.g. from ``TYPE_CHECKING`` blocks) also sees the mock.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Pytest monkeypatch fixture.
    **kwargs
        Forwarded to :func:`_mock_torch`.

    Returns
    -------
    types.SimpleNamespace
        The mock torch instance.
    """
    mock = _mock_torch(**kwargs)
    # ``detect_gpu()`` does ``import torch`` inside the function body;
    # Python resolves lazy imports via ``sys.modules``, not module-level
    # attributes.  ``gpu_module`` has no ``torch`` attribute to patch.
    monkeypatch.setitem(sys.modules, "torch", mock)
    return mock


######################################################################
# Tests — GpuInfo model defaults
######################################################################


class TestGpuInfoModel:
    """GpuInfo Pydantic model defaults."""

    def test_defaults(self) -> None:
        """GpuInfo() has predictable default field values."""
        info = gpu_module.GpuInfo()

        assert info.available is False
        assert info.backend is None
        assert info.device_name is None
        assert info.memory_total_gb is None
        assert info.memory_available_gb is None
        assert info.compute_capability is None
        assert info.torch_version is None
        assert info.cuda_version is None
        assert info.errors == []


######################################################################
# Tests — detect_gpu()
######################################################################


class TestDetectGpu:
    """detect_gpu() behaviour under various torch configurations."""

    def test_mps_branch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """MPS backend is detected when ``backends.mps.is_available()``
        returns ``True``.

        The helper functions ``_get_mps_device_name`` and
        ``_get_mps_memory`` are also mocked so that the test is fully
        deterministic.
        """
        _patch_torch(monkeypatch, mps_available=True)
        monkeypatch.setattr(gpu_module, "_get_mps_device_name", lambda: "Apple M3 Pro")
        monkeypatch.setattr(gpu_module, "_get_mps_memory", lambda: 32.0)

        info = gpu_module.detect_gpu()

        assert info.available is True
        assert info.backend == DeviceType.MPS
        assert info.device_name == "Apple M3 Pro"
        assert info.memory_total_gb == 32.0
        assert info.memory_available_gb is None  # not set in MPS branch
        assert info.compute_capability is None  # not set in MPS branch
        assert info.cuda_version is None

    def test_cuda_branch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """CUDA backend is detected when MPS is unavailable and CUDA is
        available.

        All CUDA fields (device_name, memory_total_gb,
        memory_available_gb, compute_capability, cuda_version) are
        populated.
        """
        _patch_torch(
            monkeypatch,
            mps_available=False,
            cuda_available=True,
            device_name="NVIDIA RTX 4090",
            total_memory_gb=24,
            free_memory_gb=16,
            compute_capability=(8, 9),
            cuda_version="12.1",
        )

        info = gpu_module.detect_gpu()

        assert info.available is True
        assert info.backend == DeviceType.CUDA
        assert info.device_name == "NVIDIA RTX 4090"
        assert info.memory_total_gb == 24.0
        assert info.memory_available_gb == 16.0
        assert info.compute_capability == "8.9"
        assert info.cuda_version == "12.1"
        assert info.torch_version == "2.1.0"

    def test_no_torch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When ``import torch`` raises ``ImportError`` the function
        returns ``available=False`` with an appropriate error message.

        ``sys.modules["torch"]`` is set to ``None`` so that CPython's
        import machinery raises ``ImportError`` before it ever reaches
        the filesystem.
        """
        monkeypatch.setitem(sys.modules, "torch", None)

        info = gpu_module.detect_gpu()

        assert info.available is False
        assert info.backend is None
        assert len(info.errors) == 1
        assert "torch not installed" in info.errors[0]

    def test_runtime_error_on_mps_check(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A ``RuntimeError`` from ``backends.mps.is_available()`` is
        caught gracefully and stored in ``info.errors``.
        """
        _patch_torch(monkeypatch, raise_on_mps=True)

        info = gpu_module.detect_gpu()

        assert info.available is False
        assert len(info.errors) == 1
        assert "GPU detection error" in info.errors[0]
        assert "MPS is not available" in info.errors[0]

    def test_runtime_error_on_cuda_check(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A ``RuntimeError`` from ``torch.cuda.is_available()`` is
        caught gracefully (MPS returns ``False``, so the CUDA branch is
        attempted).
        """
        _patch_torch(monkeypatch, mps_available=False, raise_on_cuda=True)

        info = gpu_module.detect_gpu()

        assert info.available is False
        assert len(info.errors) == 1
        assert "GPU detection error" in info.errors[0]
        assert "CUDA driver error" in info.errors[0]

    def test_mps_memory_error_caught(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An ``OSError`` from ``_get_mps_memory()`` in the MPS branch
        is caught gracefully — ``memory_total_gb`` stays ``None``.
        """
        _patch_torch(monkeypatch, mps_available=True)
        monkeypatch.setattr(gpu_module, "_get_mps_device_name", lambda: "Apple M3")
        monkeypatch.setattr(
            gpu_module,
            "_get_mps_memory",
            lambda: (_ for _ in ()).throw(OSError("no mem")),
        )

        info = gpu_module.detect_gpu()

        assert info.available is True
        assert info.backend == DeviceType.MPS
        assert info.memory_total_gb is None

    def test_cuda_mem_get_info_error_caught(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A ``RuntimeError`` from ``torch.cuda.mem_get_info()`` is
        caught gracefully — ``memory_available_gb`` stays ``None`` but
        other CUDA fields are still populated.
        """
        mock = _mock_torch(
            mps_available=False,
            cuda_available=True,
            device_name="NVIDIA RTX 4090",
            total_memory_gb=24,
            free_memory_gb=16,
            compute_capability=(8, 9),
            cuda_version="12.1",
        )

        # Make mem_get_info raise RuntimeError
        def _mem_get_info_raise(*args: object) -> None:
            raise RuntimeError("CUDA out of memory")

        mock.cuda.mem_get_info = _mem_get_info_raise
        monkeypatch.setitem(sys.modules, "torch", mock)

        info = gpu_module.detect_gpu()

        assert info.available is True
        assert info.backend == DeviceType.CUDA
        assert info.device_name == "NVIDIA RTX 4090"
        assert info.memory_total_gb == 24.0
        assert info.memory_available_gb is None  # exception path
        assert info.compute_capability == "8.9"


######################################################################
# Tests — _get_mps_device_name()
######################################################################


class TestGetMpsDeviceName:
    """_get_mps_device_name() under various platform and subprocess
    conditions.
    """

    def test_arm64_sysctl_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """On ``arm64`` a successful ``sysctl`` call returns the chip
        brand string.
        """
        monkeypatch.setattr(platform, "machine", lambda: "arm64")
        mock_result = types.SimpleNamespace(stdout="Apple M3 Max\n", stderr="")
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: mock_result)

        assert gpu_module._get_mps_device_name() == "Apple M3 Max"

    def test_arm64_sysctl_empty_stdout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """On ``arm64`` an empty ``sysctl`` stdout falls back to
        ``"Apple Silicon"``.
        """
        monkeypatch.setattr(platform, "machine", lambda: "arm64")
        mock_result = types.SimpleNamespace(stdout="", stderr="")
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: mock_result)

        assert gpu_module._get_mps_device_name() == "Apple Silicon"

    def test_arm64_sysctl_whitespace_stdout(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """On ``arm64`` a whitespace-only ``sysctl`` stdout falls back
        to ``"Apple Silicon"``.
        """
        monkeypatch.setattr(platform, "machine", lambda: "arm64")
        mock_result = types.SimpleNamespace(stdout="   \n", stderr="")
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: mock_result)

        assert gpu_module._get_mps_device_name() == "Apple Silicon"

    def test_arm64_timeout_expired(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """On ``arm64`` a ``subprocess.TimeoutExpired`` falls back to
        ``"Apple Silicon"``.
        """
        monkeypatch.setattr(platform, "machine", lambda: "arm64")

        def _raise_timeout(*args: object, **kwargs: object) -> None:
            raise subprocess.TimeoutExpired(
                cmd=["sysctl", "-n", "machdep.cpu.brand_string"], timeout=2
            )

        monkeypatch.setattr(subprocess, "run", _raise_timeout)

        assert gpu_module._get_mps_device_name() == "Apple Silicon"

    def test_arm64_file_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """On ``arm64`` a ``FileNotFoundError`` falls back to
        ``"Apple Silicon"``.
        """
        monkeypatch.setattr(platform, "machine", lambda: "arm64")

        def _raise_fnf(*args: object, **kwargs: object) -> None:
            raise FileNotFoundError("sysctl not found")

        monkeypatch.setattr(subprocess, "run", _raise_fnf)

        assert gpu_module._get_mps_device_name() == "Apple Silicon"

    def test_arm64_os_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """On ``arm64`` an ``OSError`` falls back to
        ``"Apple Silicon"``.
        """
        monkeypatch.setattr(platform, "machine", lambda: "arm64")

        def _raise_oserr(*args: object, **kwargs: object) -> None:
            raise OSError("permission denied")

        monkeypatch.setattr(subprocess, "run", _raise_oserr)

        assert gpu_module._get_mps_device_name() == "Apple Silicon"

    def test_non_arm64(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """On non-``arm64`` architectures the function returns
        ``"MPS (<arch>)"``.
        """
        monkeypatch.setattr(platform, "machine", lambda: "x86_64")

        assert gpu_module._get_mps_device_name() == "MPS (x86_64)"


######################################################################
# Tests — _get_mps_memory()
######################################################################


class TestGetMpsMemory:
    """_get_mps_memory() with and without psutil."""

    def test_psutil_available(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When psutil is installed the function returns total system
        memory in GB as a ``float``.
        """
        mock_vmem = types.SimpleNamespace(total=16 * 1024**3)
        mock_psutil = types.SimpleNamespace(virtual_memory=lambda: mock_vmem)
        # ``_get_mps_memory()`` does ``import psutil`` inside the function
        # body, so the mock must live in ``sys.modules``.
        monkeypatch.setitem(sys.modules, "psutil", mock_psutil)

        result = gpu_module._get_mps_memory()

        assert result is not None
        assert isinstance(result, float)
        assert result == pytest.approx(16.0)

    def test_psutil_not_installed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When psutil cannot be imported the function returns
        ``None``.
        """
        monkeypatch.setitem(sys.modules, "psutil", None)

        result = gpu_module._get_mps_memory()

        assert result is None


######################################################################
# Tests — resolve_device()
######################################################################


class TestResolveDevice:
    """resolve_device() with and without a preferred device."""

    def test_preferred_override(self) -> None:
        """When a preferred device string is given it is returned
        unchanged, regardless of the actual GPU state.
        """
        result = gpu_module.resolve_device(preferred="cpu")
        assert result == "cpu"

        result = gpu_module.resolve_device(preferred="cuda:0")
        assert result == "cuda:0"

        result = gpu_module.resolve_device(preferred="mps")
        assert result == "mps"

    def test_cuda_auto_detect(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When no preferred device is given and CUDA is available the
        function returns ``"cuda:0"``.
        """
        mock_info = gpu_module.GpuInfo(available=True, backend=DeviceType.CUDA)
        monkeypatch.setattr(gpu_module, "detect_gpu", lambda: mock_info)

        assert gpu_module.resolve_device() == "cuda:0"

    def test_mps_auto_detect(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When no preferred device is given and MPS is available the
        function returns ``"mps"``.
        """
        mock_info = gpu_module.GpuInfo(available=True, backend=DeviceType.MPS)
        monkeypatch.setattr(gpu_module, "detect_gpu", lambda: mock_info)

        assert gpu_module.resolve_device() == "mps"

    def test_no_gpu_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When no preferred device is given and no GPU is detected the
        function returns ``"cpu"``.
        """
        mock_info = gpu_module.GpuInfo(available=False, backend=None)
        monkeypatch.setattr(gpu_module, "detect_gpu", lambda: mock_info)

        assert gpu_module.resolve_device() == "cpu"
