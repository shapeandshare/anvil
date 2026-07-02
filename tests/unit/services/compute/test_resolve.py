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


def test_auto_falls_back_to_cpu_when_gpu_detected_but_torch_unavailable(monkeypatch):
    """D4: GPU detected but torch missing → silent fallback to stdlib+cpu."""
    from anvil.services.compute.resolve import resolve_backend

    monkeypatch.setattr(
        "anvil.services.compute.resolve._detect_device",
        lambda: "cuda",
    )
    monkeypatch.setattr(
        "anvil.services.compute.resolve._torch_available",
        lambda: False,
    )
    result = resolve_backend({"compute_backend": "auto"})
    assert result["engine"] == "stdlib"
    assert result["device"] == "cpu"
    assert result["backend"] == "local"


def test_local_gpu_falls_back_when_gpu_detected_but_torch_unavailable(monkeypatch):
    """D4: GPU exists but torch is not installed → silent fallback."""
    from anvil.services.compute.resolve import resolve_backend

    monkeypatch.setattr(
        "anvil.services.compute.resolve._detect_device",
        lambda: "cuda",
    )
    monkeypatch.setattr(
        "anvil.services.compute.resolve._torch_available",
        lambda: False,
    )
    result = resolve_backend({"compute_backend": "local-gpu"})
    assert result["engine"] == "stdlib"
    assert result["device"] == "cpu"
    assert result["backend"] == "local"


def test_auto_uses_mps_when_available(monkeypatch):
    """Apple Silicon MPS detection works with torch available."""
    from anvil.services.compute.resolve import resolve_backend

    monkeypatch.setattr(
        "anvil.services.compute.resolve._detect_device",
        lambda: "mps",
    )
    monkeypatch.setattr(
        "anvil.services.compute.resolve._torch_available",
        lambda: True,
    )
    result = resolve_backend({"compute_backend": "auto"})
    assert result["engine"] == "torch"
    assert result["device"] == "mps"
    assert result["backend"] == "local"


def test_local_gpu_uses_mps_when_available(monkeypatch):
    """local-gpu resolves to torch+mps on Apple Silicon."""
    from anvil.services.compute.resolve import resolve_backend

    monkeypatch.setattr(
        "anvil.services.compute.resolve._detect_device",
        lambda: "mps",
    )
    monkeypatch.setattr(
        "anvil.services.compute.resolve._torch_available",
        lambda: True,
    )
    result = resolve_backend({"compute_backend": "local-gpu"})
    assert result["engine"] == "torch"
    assert result["device"] == "mps"
    assert result["backend"] == "local"


def test_modal_full_return_dict(monkeypatch):
    """Modal backend returns all expected keys."""
    from anvil.services.compute.resolve import resolve_backend

    monkeypatch.setattr(
        "anvil.services.compute.resolve._modal_available",
        lambda: True,
    )
    result = resolve_backend({"compute_backend": "modal"})
    assert result == {
        "engine": "torch",
        "device": "cuda",
        "backend": "modal",
    }


def test_resolve_cache_not_exposed():
    """_RESOLUTION_CACHE exists as module-level dict."""
    from anvil.services.compute import resolve as resolve_mod

    assert hasattr(resolve_mod, "_RESOLUTION_CACHE")
    assert isinstance(resolve_mod._RESOLUTION_CACHE, dict)


########################################################################
# resolve_fine_tune tests
########################################################################


def test_resolve_finetune_fits_local_auto(monkeypatch):
    """Small fine-tune with auto resolves to local backend."""
    from anvil.services.compute.resolve import resolve_fine_tune

    monkeypatch.setattr(
        "anvil.services.compute.resolve._detect_device",
        lambda: "cuda",
    )
    monkeypatch.setattr(
        "anvil.services.compute.resolve._torch_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "anvil.services.compute.resolve._estimate_host_memory_gb",
        lambda: 16.0,
    )

    result = resolve_fine_tune(
        {
            "method": "lora",
            "base_model_ref": "tinyllama-1.1b",
            "compute_backend": "auto",
        }
    )
    assert result["backend"] == "local"
    assert result["engine"] == "torch"


def test_resolve_finetune_over_local_auto_saas(monkeypatch):
    """Over-local fine-tune with auto + SaaS configured routes to SaaS."""
    from anvil.services.compute.resolve import resolve_fine_tune

    monkeypatch.setattr(
        "anvil.services.compute.resolve._detect_device",
        lambda: "cuda",
    )
    monkeypatch.setattr(
        "anvil.services.compute.resolve._torch_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "anvil.services.compute.resolve._estimate_host_memory_gb",
        lambda: 2.0,
    )
    monkeypatch.setattr(
        "anvil.services.compute.resolve._saas_configured",
        lambda: True,
    )

    result = resolve_fine_tune(
        {
            "method": "full",
            "base_model_ref": "large-model-7b",
            "compute_backend": "auto",
        }
    )
    assert result["backend"] == "saas"
    assert result["engine"] == "torch"


def test_resolve_finetune_over_local_auto_no_saas(monkeypatch):
    """Over-local auto + SaaS unavailable silently falls back to local (D4)."""
    from anvil.services.compute.resolve import resolve_fine_tune

    monkeypatch.setattr(
        "anvil.services.compute.resolve._detect_device",
        lambda: "cuda",
    )
    monkeypatch.setattr(
        "anvil.services.compute.resolve._estimate_host_memory_gb",
        lambda: 2.0,
    )
    monkeypatch.setattr(
        "anvil.services.compute.resolve._saas_configured",
        lambda: False,
    )

    result = resolve_fine_tune(
        {
            "method": "full",
            "base_model_ref": "large-model-7b",
            "compute_backend": "auto",
        }
    )
    assert result["backend"] == "local"
    assert result["engine"] == "torch"


def test_resolve_finetune_explicit_local_over_limit_still_local(monkeypatch):
    """Explicit local-cpu/local-gpu always resolves local (NMRG, never raises)."""
    from anvil.services.compute.resolve import resolve_fine_tune

    monkeypatch.setattr(
        "anvil.services.compute.resolve._detect_device",
        lambda: "cuda",
    )
    monkeypatch.setattr(
        "anvil.services.compute.resolve._estimate_host_memory_gb",
        lambda: 2.0,
    )

    for backend in ("local-cpu", "local-gpu"):
        result = resolve_fine_tune(
            {
                "method": "full",
                "base_model_ref": "large-model-7b",
                "compute_backend": backend,
            }
        )
        assert result["backend"] == "local"
        assert result["engine"] == "torch"


def test_resolve_finetune_explicit_saas_not_configured(monkeypatch):
    """Explicit saas with SaaS not configured raises (D4 explicit-unavailable)."""
    from anvil.services.compute.compute_backend_unavailable import (
        ComputeBackendUnavailable,
    )
    from anvil.services.compute.resolve import resolve_fine_tune

    monkeypatch.setattr(
        "anvil.services.compute.resolve._saas_configured",
        lambda: False,
    )

    with pytest.raises(ComputeBackendUnavailable):
        resolve_fine_tune(
            {
                "method": "full",
                "base_model_ref": "large-model-7b",
                "compute_backend": "saas",
            }
        )


def test_resolve_finetune_method_sizing(monkeypatch):
    """Method multipliers move the local/SaaS boundary at a fixed budget."""
    from anvil.services.compute.resolve import resolve_fine_tune

    monkeypatch.setattr(
        "anvil.services.compute.resolve._detect_device",
        lambda: "cuda",
    )
    monkeypatch.setattr(
        "anvil.services.compute.resolve._saas_configured",
        lambda: True,
    )
    # 3b model: full=3*2.0+0.5=6.5, lora=3*1.2+0.5=4.1, qlora=3*0.6+0.5=2.3.
    # A 5 GB budget makes full over-local (→saas) but lora and qlora fit.
    monkeypatch.setattr(
        "anvil.services.compute.resolve._estimate_host_memory_gb",
        lambda: 5.0,
    )

    full_result = resolve_fine_tune(
        {"method": "full", "base_model_ref": "mid-model-3b", "compute_backend": "auto"}
    )
    lora_result = resolve_fine_tune(
        {"method": "lora", "base_model_ref": "mid-model-3b", "compute_backend": "auto"}
    )
    qlora_result = resolve_fine_tune(
        {"method": "qlora", "base_model_ref": "mid-model-3b", "compute_backend": "auto"}
    )

    assert full_result["backend"] == "saas"
    assert lora_result["backend"] == "local"
    assert qlora_result["backend"] == "local"


def test_resolve_finetune_always_returns_valid_backend_enum(monkeypatch):
    """resolve_fine_tune never returns a False/None backend sentinel."""
    from anvil.services.compute.compute_backend_result import ComputeBackendResult
    from anvil.services.compute.resolve import resolve_fine_tune

    monkeypatch.setattr(
        "anvil.services.compute.resolve._detect_device",
        lambda: "cuda",
    )
    monkeypatch.setattr(
        "anvil.services.compute.resolve._estimate_host_memory_gb",
        lambda: 2.0,
    )
    monkeypatch.setattr(
        "anvil.services.compute.resolve._saas_configured",
        lambda: False,
    )

    for backend in ("auto", "local-cpu", "local-gpu"):
        result = resolve_fine_tune(
            {
                "method": "full",
                "base_model_ref": "large-model-7b",
                "compute_backend": backend,
            }
        )
        assert result["backend"] in tuple(ComputeBackendResult)


def test_parse_model_params_edge_cases():
    """Model-ref parsing handles ambiguous refs and unknown fallbacks."""
    from anvil.services.compute.resolve import _parse_model_params

    assert _parse_model_params("tinyllama-1.1b") == 1.1
    assert _parse_model_params("large-model-7b") == 7.0
    assert _parse_model_params("model-70b") == 70.0
    assert _parse_model_params("llama-2-13b-chat") == 13.0
    assert _parse_model_params("v2-model-7b") == 7.0
    assert _parse_model_params("bert-base") == 7.0
    assert _parse_model_params("gpt2-medium") == 7.0


########################################################################
# NMRG: resolve_backend() lora/qlora delegation
########################################################################


def test_resolve_backend_lora_delegates_local(monkeypatch):
    """resolve_backend with method=lora delegates and stays local (NMRG)."""
    from anvil.services.compute.resolve import resolve_backend

    monkeypatch.setattr(
        "anvil.services.compute.resolve._detect_device",
        lambda: "cuda",
    )
    monkeypatch.setattr(
        "anvil.services.compute.resolve._estimate_host_memory_gb",
        lambda: 16.0,
    )
    result = resolve_backend(
        {
            "method": "lora",
            "compute_backend": "local-gpu",
            "base_model_ref": "tinyllama-1.1b",
        }
    )
    assert result["backend"] == "local"
    assert result["engine"] == "torch"


def test_resolve_backend_qlora_over_local_no_saas_stays_local(monkeypatch):
    """resolve_backend qlora over-local auto without SaaS stays local (NMRG)."""
    from anvil.services.compute.resolve import resolve_backend

    monkeypatch.setattr(
        "anvil.services.compute.resolve._detect_device",
        lambda: "cuda",
    )
    monkeypatch.setattr(
        "anvil.services.compute.resolve._estimate_host_memory_gb",
        lambda: 1.0,
    )
    monkeypatch.setattr(
        "anvil.services.compute.resolve._saas_configured",
        lambda: False,
    )
    result = resolve_backend(
        {
            "method": "qlora",
            "compute_backend": "auto",
            "base_model_ref": "large-model-7b",
        }
    )
    assert result["backend"] == "local"


def test_resolve_finetune_nmrg(monkeypatch):
    """Existing resolve_backend() non-fine-tune paths unchanged."""
    from anvil.services.compute.resolve import resolve_backend

    monkeypatch.setattr(
        "anvil.services.compute.resolve._detect_device",
        lambda: "cpu",
    )
    result = resolve_backend({"compute_backend": "auto"})
    assert result["engine"] == "stdlib"
    assert result["device"] == "cpu"
    assert result["backend"] == "local"
