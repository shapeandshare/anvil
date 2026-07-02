"""Tests for adapter persistence (047 SaaS Fine-Tuning Pipeline, Phase 2).

Verifies that both local and SaaS LoRA completions produce a ``LoRAAdapter``
DB row and populate ``ComputeResult.adapter_id`` (currently never set).
"""

from __future__ import annotations

import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anvil.services.compute.compute_backend_result import ComputeBackendResult
from anvil.services.compute.compute_status import ComputeStatus
from anvil.services.compute.local_lora_backend import LocalLoraBackend
from anvil.services.compute.registry_backend import RegistryBackend
from anvil.services.compute.result import ComputeResult
from anvil.services.compute.training_engine import TrainingEngine


@pytest.fixture
def lora_config() -> dict:
    return {
        "method": "lora",
        "base_model_ref": "test-model",
        "lora_rank": 8,
        "lora_alpha": 16,
        "lora_target_modules": ["q_proj", "v_proj"],
        "lora_dropout": 0.05,
        "num_steps": 3,
        "learning_rate": 5e-4,
        "device": "cpu",
    }


@pytest.fixture
def progress_callback() -> MagicMock:
    return MagicMock()


@pytest.fixture
def stop_check() -> MagicMock:
    return MagicMock(return_value=False)


class TestAdapterPersistence:
    """Tests for the adapter-persistence gap fix (047 Phase 2)."""

    # ── T003: LocalLoraBackend.run() returns non-null adapter_id ────────

    @patch("anvil.services.compute.local_lora_backend._peft_available")
    async def test_local_lora_run_returns_adapter_id(
        self,
        mock_available: MagicMock,
        lora_config: dict,
        progress_callback: MagicMock,
        stop_check: MagicMock,
    ) -> None:
        """T003: LocalLoraBackend.run() returns a ComputeResult with non-null adapter_id.

        Currently always None — this test will FAIL until T004 is implemented.
        """
        mock_available.return_value = False  # synthetic path
        backend = LocalLoraBackend()
        result = await backend.run(
            ["doc1", "doc2"],
            lora_config,
            progress_callback=progress_callback,
            stop_check=stop_check,
        )
        assert result.status == ComputeStatus.COMPLETED
        assert (
            result.adapter_id is not None
        ), "adapter_id must be non-null after a completed LoRA run"
        assert isinstance(result.adapter_id, str)
        assert len(result.adapter_id) > 0

    # ── T002: LoRAAdapter DB row is created ─────────────────────────────

    async def test_adapter_row_created_on_complete(
        self,
    ) -> None:
        adapter_path = f"{tempfile.mkdtemp()}/test_adapter"
        # Arrange: create a minimal ComputeResult with adapter_id
        result = ComputeResult(
            status=ComputeStatus.COMPLETED,
            model=None,
            final_loss=0.5,
            samples=["hello"],
            engine=TrainingEngine.TORCH,
            backend=ComputeBackendResult.LOCAL,
            artifact_uris={"adapter_path": adapter_path},
            adapter_id="test-run_42",
        )

        # Use a mock repo to verify add() is called
        mock_repo = MagicMock()
        mock_repo.add = AsyncMock()

        # Call the persistence service
        from anvil.services.training.adapter_persistence import (
            AdapterPersistenceService,
        )

        service = AdapterPersistenceService(lora_adapter_repo=mock_repo)
        await service.persist(result, {"base_model_ref": 1})

        # Assert: add() was called once with correct fields
        mock_repo.add.assert_called_once()
        saved_adapter = mock_repo.add.call_args[0][0]
        assert saved_adapter.adapter_id == "test-run_42"
        assert saved_adapter.storage_path == adapter_path
