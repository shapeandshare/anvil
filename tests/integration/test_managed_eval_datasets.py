"""Integration tests for managed evaluation datasets (MLflow genai)."""

from unittest.mock import MagicMock, patch

import pytest

from anvil.services.capability_unavailable import CapabilityUnavailable
from anvil.services.tracking import TrackingService


@pytest.mark.asyncio
async def test_create_eval_dataset_when_available():
    """create_eval_dataset succeeds when genai is available."""
    mock_dataset = MagicMock()
    mock_dataset.name = "my_eval"

    with patch("mlflow.genai.datasets.create_dataset", return_value=mock_dataset):
        svc = TrackingService(tracking_uri="http://127.0.0.1:5000")
        result = await svc.create_eval_dataset(name="my_eval")
        assert result is not None


@pytest.mark.asyncio
async def test_create_eval_dataset_raises_when_unavailable():
    """create_eval_dataset raises CapabilityUnavailable when genai not supported."""
    svc = TrackingService(tracking_uri="file:///tmp/mlruns")
    with pytest.raises(CapabilityUnavailable):
        await svc.create_eval_dataset(name="my_eval")


@pytest.mark.asyncio
async def test_capability_unavailable_never_fails_training_run():
    """SC-007: CapabilityUnavailable from eval-dataset API path never fails a run."""
    svc = TrackingService(tracking_uri="file:///tmp/mlruns")
    with pytest.raises(CapabilityUnavailable):
        await svc.create_eval_dataset(name="test")
    assert not svc.is_degraded
