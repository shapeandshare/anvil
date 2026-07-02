"""Unit tests for Evaluator."""

from __future__ import annotations

import math
from unittest.mock import MagicMock, patch

import pytest

from anvil.services.evaluation.evaluator import Evaluator, EvaluatorResult


@pytest.fixture
def mock_inference():
    svc = MagicMock()
    svc.generate.return_value = "generated output"
    svc.loss_breakdown.return_value = {
        "average_loss": 1.5,
        "perplexity": 4.48,
        "model": {},
        "tokens": [{"char": "a", "id": 0}],
        "losses": [1.5],
        "random_baseline": 2.3,
        "vocab_size": 64,
    }
    return svc


@pytest.fixture
def mock_loaded_model():
    return MagicMock()


@pytest.fixture
def evaluator(mock_inference):
    return Evaluator(mock_inference)


class TestEvaluator:
    """Verify Evaluator.evaluate_prompt combines generate + loss_breakdown."""

    def test_returns_evaluator_result(self, evaluator, mock_loaded_model):
        result = evaluator.evaluate_prompt("hello", loaded_model=mock_loaded_model)
        assert isinstance(result, EvaluatorResult)
        assert result.generated_text == "generated output"
        assert math.isclose(result.avg_loss, 1.5, rel_tol=1e-9)
        assert math.isclose(result.perplexity, 4.48, rel_tol=1e-9)

    def test_calls_generate_with_correct_args(
        self, evaluator, mock_inference, mock_loaded_model
    ):
        evaluator.evaluate_prompt(
            "hello", loaded_model=mock_loaded_model, temperature=0.5, max_tokens=50
        )
        mock_inference.generate.assert_called_once_with(
            mock_loaded_model, prompt="hello", temperature=0.5, max_tokens=50
        )

    def test_calls_loss_breakdown_with_prompt(
        self, evaluator, mock_inference, mock_loaded_model
    ):
        evaluator.evaluate_prompt("test prompt", loaded_model=mock_loaded_model)
        mock_inference.loss_breakdown.assert_called_once_with(
            "test prompt", mock_loaded_model
        )

    def test_computes_perplexity_when_missing(
        self, evaluator, mock_inference, mock_loaded_model
    ):
        mock_inference.loss_breakdown.return_value = {
            "average_loss": 2.0,
            "model": {},
            "tokens": [],
            "losses": [2.0],
            "random_baseline": 2.3,
            "vocab_size": 64,
        }
        result = evaluator.evaluate_prompt("hello", loaded_model=mock_loaded_model)
        assert math.isclose(result.avg_loss, 2.0, rel_tol=1e-9)
        assert result.perplexity > 0

        assert math.isclose(result.perplexity, math.exp(2.0), rel_tol=1e-2)


class TestTrackOnlyRefusal:
    """Verify Evaluator refuses track-only models per FR-003."""

    def test_no_track_only_gate_in_evaluator(
        self, evaluator, mock_inference, mock_loaded_model
    ):
        """Evaluator itself does not gate on TRACK_ONLY — that is the service layer's job.
        The Evaluator is a pure function: given a loaded model, it runs generate + loss.
        The track-only gate lives in EvaluationService._load_model_for_eval and the API endpoint.
        """
        result = evaluator.evaluate_prompt("hello", loaded_model=mock_loaded_model)
        assert result is not None
