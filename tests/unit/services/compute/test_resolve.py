# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for backend resolution (D4 fallback logic)."""


import pytest

from anvil.services.compute.compute_backend_unavailable import ComputeBackendUnavailable

# We test resolve_backend by patching its internal helpers


def test_auto_with_torch_available(monkeypatch):
    from anvil.services.compute.resolve import resolve_backend

    monkeypatch.setattr(
        "anvil.services.compute.resolve._detect_device",
        lambda: "cuda",
    )
    monkeypatch.setattr(
        "anvil.services.compute.resolve._torch_available",
        lambda: True,
    )
    result = resolve_backend({"compute_backend": "auto"})
    assert result["engine"] == "torch"
    assert result["device"] == "cuda"
    assert result["backend"] == "local"


def test_auto_without_torch(monkeypatch):
    from anvil.services.compute.resolve import resolve_backend

    monkeypatch.setattr(
        "anvil.services.compute.resolve._detect_device",
        lambda: "cpu",
    )
    result = resolve_backend({"compute_backend": "auto"})
    assert result["engine"] == "stdlib"
    assert result["device"] == "cpu"
    assert result["backend"] == "local"


def test_local_cpu_always_stdlib(monkeypatch):
    from anvil.services.compute.resolve import resolve_backend

    monkeypatch.setattr(
        "anvil.services.compute.resolve._detect_device",
        lambda: "cuda",  # GPU exists but local-cpu ignores it
    )
    result = resolve_backend({"compute_backend": "local-cpu"})
    assert result["engine"] == "stdlib"
    assert result["device"] == "cpu"


def test_local_gpu_falls_back_to_cpu_when_torch_missing(monkeypatch):
    """D4: implicit capability downgrade — silent fallback."""
    from anvil.services.compute.resolve import resolve_backend

    monkeypatch.setattr(
        "anvil.services.compute.resolve._detect_device",
        lambda: "cpu",
    )
    result = resolve_backend({"compute_backend": "local-gpu"})
    assert result["engine"] == "stdlib"
    assert result["device"] == "cpu"


def test_local_gpu_uses_cuda_when_available(monkeypatch):
    from anvil.services.compute.resolve import resolve_backend

    monkeypatch.setattr(
        "anvil.services.compute.resolve._detect_device",
        lambda: "cuda",
    )
    monkeypatch.setattr(
        "anvil.services.compute.resolve._torch_available",
        lambda: True,
    )
    result = resolve_backend({"compute_backend": "local-gpu"})
    assert result["engine"] == "torch"
    assert result["device"] == "cuda"


def test_modal_raises_when_not_available(monkeypatch):
    """D4: explicit remote selection must NOT silently fall back."""
    from anvil.services.compute.resolve import resolve_backend

    monkeypatch.setattr(
        "anvil.services.compute.resolve._modal_available",
        lambda: False,
    )
    with pytest.raises(ComputeBackendUnavailable) as exc:
        resolve_backend({"compute_backend": "modal"})
    assert "pip install anvil[compute]" in str(exc.value)


def test_modal_succeeds_when_available(monkeypatch):
    from anvil.services.compute.resolve import resolve_backend

    monkeypatch.setattr(
        "anvil.services.compute.resolve._modal_available",
        lambda: True,
    )
    result = resolve_backend({"compute_backend": "modal"})
    assert result["backend"] == "modal"
    assert result["engine"] == "torch"


def test_default_is_auto(monkeypatch):
    from anvil.services.compute.resolve import resolve_backend

    monkeypatch.setattr(
        "anvil.services.compute.resolve._detect_device",
        lambda: "cpu",
    )
    result = resolve_backend({})  # no compute_backend key
    assert result["backend"] == "local"


def test_unknown_backend_raises():
    from anvil.services.compute.resolve import resolve_backend

    with pytest.raises(ComputeBackendUnavailable):
        resolve_backend({"compute_backend": "nonexistent"})
