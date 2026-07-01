"""Tests for LocalLoraBackend (spec 044 LoRA fine-tuning backend)."""

from unittest.mock import MagicMock, patch

import pytest

from anvil.services.compute.compute_status import ComputeStatus
from anvil.services.compute.local_lora_backend import LocalLoraBackend
from anvil.services.compute.registry_backend import RegistryBackend
from anvil.services.compute.result import ComputeResult


@pytest.fixture
def lora_config():
    return {
        "method": "lora",
        "base_model_ref": 1,
        "lora_rank": 8,
        "lora_alpha": 16,
        "lora_target_modules": ["q_proj", "v_proj"],
        "lora_dropout": 0.05,
        "num_steps": 3,
        "learning_rate": 5e-4,
        "device": "cpu",
    }


@pytest.fixture
def qlora_config(lora_config):
    cfg = dict(lora_config)
    cfg["method"] = "qlora"
    return cfg


@pytest.fixture
def lora_backend():
    return LocalLoraBackend()


@pytest.fixture
def progress_callback():
    return MagicMock()


@pytest.fixture
def stop_check():
    return MagicMock(return_value=False)


class TestLocalLoraBackendIdentity:
    """Verify the backend identity and availability contract."""

    def test_name(self):
        assert LocalLoraBackend.name == RegistryBackend.LOCAL_LORA

    def test_name_is_str(self):
        assert isinstance(LocalLoraBackend.name, str)

    @patch("anvil.services.compute.local_lora_backend._peft_available")
    def test_is_available_true(self, mock_available):
        mock_available.return_value = True
        assert LocalLoraBackend.is_available() is True

    @patch("anvil.services.compute.local_lora_backend._peft_available")
    def test_is_available_false(self, mock_available):
        mock_available.return_value = False
        assert LocalLoraBackend.is_available() is False


class TestLocalLoraBackendSyntheticRun:
    """When peft/torch are not available, the backend runs a synthetic loop."""

    @patch("anvil.services.compute.local_lora_backend._peft_available")
    async def test_synthetic_run_returns_completed(
        self,
        mock_available,
        lora_backend,
        lora_config,
        progress_callback,
        stop_check,
    ):
        mock_available.return_value = False
        result = await lora_backend.run(
            ["doc1", "doc2"],
            lora_config,
            progress_callback=progress_callback,
            stop_check=stop_check,
        )
        assert result.status == ComputeStatus.COMPLETED
        assert result.engine == "torch"

    @patch("anvil.services.compute.local_lora_backend._peft_available")
    async def test_synthetic_run_calls_progress(
        self,
        mock_available,
        lora_backend,
        lora_config,
        progress_callback,
        stop_check,
    ):
        mock_available.return_value = False
        await lora_backend.run(
            ["doc1"],
            lora_config,
            progress_callback=progress_callback,
            stop_check=stop_check,
        )
        assert progress_callback.call_count == 3  # num_steps=3

    @patch("anvil.services.compute.local_lora_backend._peft_available")
    async def test_synthetic_run_honours_stop(
        self,
        mock_available,
        lora_backend,
        lora_config,
        progress_callback,
        stop_check,
    ):
        mock_available.return_value = False
        stop_check.return_value = True  # cancel immediately
        result = await lora_backend.run(
            ["doc1"],
            lora_config,
            progress_callback=progress_callback,
            stop_check=stop_check,
        )
        assert result.status == ComputeStatus.FAILED


class TestQLoRADegrade:
    """When bitsandbytes is unavailable, QLoRA falls back to LoRA."""

    @patch("anvil.services.compute.local_lora_backend._peft_available")
    @patch("anvil.services.compute.local_lora_backend._bitsandbytes_available")
    async def test_qlora_degrade_to_lora(
        self,
        mock_bnb,
        mock_peft,
        lora_backend,
        qlora_config,
        progress_callback,
        stop_check,
    ):
        mock_peft.return_value = False  # falls back to synthetic
        mock_bnb.return_value = False
        result = await lora_backend.run(
            ["doc1"],
            qlora_config,
            progress_callback=progress_callback,
            stop_check=stop_check,
        )
        # Even with method=qlora, should complete via synthetic fallback
        assert result.status == ComputeStatus.COMPLETED


class TestLocalLoraBackendRegistration:
    """Verify the backend can be auto-registered."""

    def test_module_imports_register(self):
        # Verify the module can be imported without error and
        # carries the expected factory callable at module level.
        import anvil.services.compute.local_lora_backend as llb

        assert hasattr(llb, "LocalLoraBackend")
        assert llb.LocalLoraBackend.name == RegistryBackend.LOCAL_LORA
