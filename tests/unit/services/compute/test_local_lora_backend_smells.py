"""Unit tests for S1192/S3776 smell fixes in local_lora_backend.

Tests the extracted module-level constant ``_CANCELLED_MSG`` and the
helper functions extracted from ``_run_real_lora`` to reduce cognitive
complexity.
"""

import sys
from unittest.mock import MagicMock, patch, sentinel

import pytest

from anvil.services.compute.local_lora_backend import (
    _CANCELLED_MSG,
    _generate_sample,
    _resolve_device_config,
    _resolve_quantization_config,
    _run_training_loop,
)
from anvil.services.training.stop_requested import StopRequested


class TestCancelledMsg:
    """S1192: The duplicate string literal is now a single constant."""

    def test_constant_exists(self):
        """_CANCELLED_MSG is defined and has the expected value."""
        assert _CANCELLED_MSG == "Training cancelled by user"

    def test_constant_is_str(self):
        assert isinstance(_CANCELLED_MSG, str)


class TestResolveDeviceConfig:
    """_resolve_device_config returns correct (dtype, device) tuples."""

    def test_cpu_default(self):
        """When device='cpu', always returns (float32, 'cpu')."""
        mock_torch = MagicMock()
        dtype, device = _resolve_device_config("cpu", mock_torch)
        assert device == "cpu"
        assert dtype is mock_torch.float32

    def test_cuda_available(self):
        """When device='cuda' and CUDA is available, returns (bfloat16, 'cuda')."""
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True
        dtype, device = _resolve_device_config("cuda", mock_torch)
        assert device == "cuda"
        assert dtype is mock_torch.bfloat16

    def test_cuda_unavailable_falls_to_cpu(self):
        """When device='cuda' but CUDA is unavailable, falls to (float32, 'cpu')."""
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        dtype, device = _resolve_device_config("cuda", mock_torch)
        assert device == "cpu"
        assert dtype is mock_torch.float32

    def test_mps_available(self):
        """When device='mps' and MPS is available, returns (float32, 'mps')."""
        mock_torch = MagicMock()
        mock_torch.backends.mps.is_available.return_value = True
        dtype, device = _resolve_device_config("mps", mock_torch)
        assert device == "mps"
        assert dtype is mock_torch.float32

    def test_mps_unavailable_falls_to_cpu(self):
        """When device='mps' but MPS is unavailable, falls to (float32, 'cpu')."""
        mock_torch = MagicMock()
        mock_torch.backends.mps.is_available.return_value = False
        dtype, device = _resolve_device_config("mps", mock_torch)
        assert device == "cpu"
        assert dtype is mock_torch.float32


class TestResolveQuantizationConfig:
    """_resolve_quantization_config returns config or None."""

    def test_lora_returns_none(self):
        """When method='lora', returns None (no quantization)."""
        assert _resolve_quantization_config("lora") is None

    def test_qlora_no_bitsandbytes_returns_none(self):
        """When method='qlora' but bitsandbytes unavailable, returns None."""
        with patch(
            "anvil.services.compute.local_lora_backend._bitsandbytes_available",
            return_value=False,
        ):
            result = _resolve_quantization_config("qlora")
        assert result is None

    @patch("anvil.services.compute.local_lora_backend._bitsandbytes_available")
    def test_qlora_with_bitsandbytes_returns_config(
        self,
        mock_bnb,
    ):
        """When method='qlora' and bitsandbytes available, returns config."""
        mock_bnb.return_value = True
        mock_bnb_config_instance = MagicMock()
        mock_bnb_config_cls = MagicMock(return_value=mock_bnb_config_instance)
        mock_transformers = MagicMock()
        mock_transformers.BitsAndBytesConfig = mock_bnb_config_cls
        with patch.dict("sys.modules", {"transformers": mock_transformers}):
            result = _resolve_quantization_config("qlora")
        assert result is mock_bnb_config_instance


class TestRunTrainingLoop:
    """_run_training_loop executes steps and respects stop_check."""

    def test_runs_all_steps(self):
        """Training loop runs all steps and returns the final loss."""
        mock_model = MagicMock()
        mock_model.outputs.loss.item.return_value = 0.5
        mock_model.side_effect = lambda **kw: mock_model.outputs
        progress = MagicMock()
        stop = MagicMock(return_value=False)

        result = _run_training_loop(
            peft_model=mock_model,
            input_ids=sentinel.input_ids,
            attention_mask=sentinel.attention_mask,
            optimizer=MagicMock(),
            num_steps=3,
            progress_callback=progress,
            stop_check=stop,
        )

        assert result == 0.5
        assert progress.call_count == 3
        assert stop.call_count == 3

    def test_stop_check_raises_stop_requested(self):
        """When stop_check returns True, StopRequested is raised."""
        mock_model = MagicMock()
        progress = MagicMock()
        stop = MagicMock()
        stop.side_effect = [False, True]  # pass first check, fail second

        with pytest.raises(StopRequested, match=_CANCELLED_MSG):
            _run_training_loop(
                peft_model=mock_model,
                input_ids=sentinel.input_ids,
                attention_mask=sentinel.attention_mask,
                optimizer=MagicMock(),
                num_steps=5,
                progress_callback=progress,
                stop_check=stop,
            )

        # Should have stopped before completing all 5 steps
        assert progress.call_count == 1


class TestGenerateSample:
    """_generate_sample returns a list with one decoded string."""

    def test_returns_list_with_one_sample(self):
        """Generate sample returns a single-element list."""
        mock_torch = MagicMock()
        mock_torch.no_grad.return_value.__enter__.return_value = None

        mock_peft = MagicMock()
        mock_peft.generate.return_value = [[101, 102, 103]]

        mock_tokenizer = MagicMock()
        mock_tokenizer.decode.return_value = "generated text"

        input_ids = MagicMock()
        result = _generate_sample(
            peft_model=mock_peft,
            tokenizer=mock_tokenizer,
            input_ids=input_ids,
            torch=mock_torch,
        )

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0] == "generated text"
        mock_peft.eval.assert_called_once()
