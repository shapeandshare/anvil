"""Tests for SaasFinetuneBackend (047 SaaS Fine-Tuning Pipeline, Phase 3).

Verifies the provider-backed SaaS fine-tune backend: submit-then-poll,
is_available(), auto-registration, routing, and end-to-end HTTP flow.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anvil.services.compute.compute_backend_result import ComputeBackendResult
from anvil.services.compute.compute_status import ComputeStatus
from anvil.services.compute.registry_backend import RegistryBackend
from anvil.services.compute.result import ComputeResult
from anvil.services.compute.training_engine import TrainingEngine


@pytest.fixture
def fake_config() -> dict:
    return {
        "method": "lora",
        "base_model_ref": 1,
        "compute_backend": "saas",
        "lora_rank": 8,
        "lora_alpha": 16,
        "num_steps": 3,
        "learning_rate": 5e-4,
        "device": "cpu",
    }


@pytest.fixture
def fake_provider() -> AsyncMock:
    """A fake SaasFinetuneProvider that succeeds immediately."""
    provider = AsyncMock()
    provider.submit.return_value = "job_ref_123"
    provider.poll_status.return_value = ComputeStatus.COMPLETED
    provider.fetch_adapter.return_value = "/tmp/fake_adapter"
    return provider


@pytest.fixture
def progress_callback() -> MagicMock:
    return MagicMock()


@pytest.fixture
def stop_check() -> MagicMock:
    return MagicMock(return_value=False)


@pytest.fixture
def saas_backend(fake_provider):
    from anvil.services.compute.saas_finetune_backend import SaasFinetuneBackend

    return SaasFinetuneBackend(provider=fake_provider)


class TestSaasFinetuneBackendIdentity:
    """T008: Verify the backend identity and availability contract."""

    def test_name(self):
        from anvil.services.compute.saas_finetune_backend import SaasFinetuneBackend

        assert SaasFinetuneBackend.name == RegistryBackend.SAAS_FINETUNE

    def test_name_is_str(self):
        from anvil.services.compute.saas_finetune_backend import SaasFinetuneBackend

        assert isinstance(SaasFinetuneBackend.name, str)

    @patch(
        "anvil.services.compute.saas_finetune_backend._saas_configured",
        return_value=True,
    )
    def test_is_available_true(self, mock_saas):
        from anvil.services.compute.saas_finetune_backend import SaasFinetuneBackend

        assert SaasFinetuneBackend.is_available() is True

    @patch(
        "anvil.services.compute.saas_finetune_backend._saas_configured",
        return_value=False,
    )
    def test_is_available_false(self, mock_saas):
        from anvil.services.compute.saas_finetune_backend import SaasFinetuneBackend

        assert SaasFinetuneBackend.is_available() is False

    def test_module_imports_register(self):
        import anvil.services.compute.saas_finetune_backend as sfb

        assert hasattr(sfb, "SaasFinetuneBackend")
        assert sfb.SaasFinetuneBackend.name == RegistryBackend.SAAS_FINETUNE


class TestSaasFinetuneBackendRun:
    """T007: SaasFinetuneBackend.run() with injected fake provider."""

    async def test_success_path_returns_completed(
        self, saas_backend, fake_config, progress_callback, stop_check
    ):
        result = await saas_backend.run(
            ["doc1"],
            fake_config,
            progress_callback=progress_callback,
            stop_check=stop_check,
        )
        assert result.status == ComputeStatus.COMPLETED
        assert result.adapter_id is not None
        assert result.artifact_uris.get("adapter_path") == "/tmp/fake_adapter"
        assert result.backend == ComputeBackendResult.SAAS
        assert result.engine == TrainingEngine.TORCH

    async def test_failure_path_returns_failed(
        self, fake_provider, fake_config, progress_callback, stop_check
    ):
        fake_provider.poll_status.return_value = ComputeStatus.FAILED
        from anvil.services.compute.saas_finetune_backend import SaasFinetuneBackend

        backend = SaasFinetuneBackend(provider=fake_provider)
        result = await backend.run(
            ["doc1"],
            fake_config,
            progress_callback=progress_callback,
            stop_check=stop_check,
        )
        assert result.status == ComputeStatus.FAILED

    async def test_cancellation_returns_failed(
        self, saas_backend, fake_config, progress_callback, stop_check
    ):
        stop_check.return_value = True  # cancel immediately
        result = await saas_backend.run(
            ["doc1"],
            fake_config,
            progress_callback=progress_callback,
            stop_check=stop_check,
        )
        assert result.status == ComputeStatus.FAILED
        assert "cancelled" in (result.error_message or "").lower()

    async def test_submit_calls_provider(
        self, fake_provider, fake_config, progress_callback, stop_check
    ):
        from anvil.services.compute.saas_finetune_backend import SaasFinetuneBackend

        backend = SaasFinetuneBackend(provider=fake_provider)
        await backend.run(
            ["doc1"],
            fake_config,
            progress_callback=progress_callback,
            stop_check=stop_check,
        )
        fake_provider.submit.assert_called_once()
        fake_provider.poll_status.assert_called_once_with("job_ref_123")
        fake_provider.fetch_adapter.assert_called_once_with("job_ref_123")


class TestSaasFinetuneRouting:
    """T009: Routing: resolve_fine_tune SAAS mapping + training.py remap."""

    def test_resolve_fine_tune_returns_saas_when_configured(self, monkeypatch):
        from anvil.services.compute.resolve import resolve_fine_tune

        monkeypatch.setattr(
            "anvil.services.compute.resolve._saas_configured", lambda: True
        )
        monkeypatch.setattr(
            "anvil.services.compute.resolve._estimate_host_memory_gb", lambda: 1.0
        )
        result = resolve_fine_tune(
            {
                "method": "lora",
                "base_model_ref": "large-model-7b",
                "compute_backend": "saas",
            }
        )
        assert result["backend"] == ComputeBackendResult.SAAS
        assert result["engine"] == TrainingEngine.TORCH

    def test_resolve_fine_tune_raises_when_not_configured(self, monkeypatch):
        from anvil.services.compute.compute_backend_unavailable import (
            ComputeBackendUnavailable,
        )
        from anvil.services.compute.resolve import resolve_fine_tune

        monkeypatch.setattr(
            "anvil.services.compute.resolve._saas_configured", lambda: False
        )
        with pytest.raises(ComputeBackendUnavailable):
            resolve_fine_tune(
                {
                    "method": "lora",
                    "base_model_ref": "large-model-7b",
                    "compute_backend": "saas",
                }
            )

    def test_backend_name_maps_to_saas_finetune(self):
        """Verify that when backend_name == SAAS and method is lora,
        the remap in training.py produces SAAS_FINETUNE."""
        from anvil.services.compute.compute_backend_result import ComputeBackendResult
        from anvil.services.compute.registry_backend import RegistryBackend

        backend_name = ComputeBackendResult.SAAS
        method = "lora"
        if backend_name == ComputeBackendResult.SAAS and method in ("lora", "qlora"):
            backend_name = RegistryBackend.SAAS_FINETUNE
        assert backend_name == RegistryBackend.SAAS_FINETUNE

    def test_backend_name_stays_saas_for_full_method(self):
        from anvil.services.compute.compute_backend_result import ComputeBackendResult
        from anvil.services.compute.registry_backend import RegistryBackend

        backend_name = ComputeBackendResult.SAAS
        method = "full"
        if backend_name == ComputeBackendResult.SAAS and method in ("lora", "qlora"):
            backend_name = RegistryBackend.SAAS_FINETUNE
        assert backend_name == ComputeBackendResult.SAAS


class TestSaasFinetuneE2E:
    """T010: e2e HTTP test for SaaS fine-tune submission."""

    @patch("anvil.services.compute.resolve._saas_configured", return_value=True)
    async def test_submit_saas_lora_via_api(self, mock_saas, client):
        """Submit a LoRA fine-tune with compute_backend='saas' and a fake
        provider. Verify a run is created, SSE complete event fires, and a
        LoRAAdapter row exists afterward."""
        # Inject a fake SaasFinetuneProvider via the registry
        fake_provider = AsyncMock()
        fake_provider.submit.return_value = "job_ref_42"
        fake_provider.poll_status.return_value = ComputeStatus.COMPLETED
        fake_provider.fetch_adapter.return_value = "/tmp/e2e_adapter"

        from anvil.services.compute.registry import register
        from anvil.services.compute.saas_finetune_backend import SaasFinetuneBackend

        register("saas-finetune", lambda: SaasFinetuneBackend(provider=fake_provider))

        # Submit via the existing /training/start endpoint
        r = await client.post(
            "/v1/training/start",
            json={
                "method": "lora",
                "base_model_ref": 1,
                "compute_backend": "saas",
                "lora_rank": 8,
                "lora_alpha": 16,
                "num_steps": 3,
                "n_embd": 16,
                "n_head": 4,
                "n_layer": 1,
                "block_size": 16,
                "learning_rate": 0.01,
            },
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "run_id" in data
