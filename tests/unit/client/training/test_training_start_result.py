# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for the TrainingStartResult DTO — construction, defaults, and
serialization.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from anvil.client.training.training_start_result import TrainingStartResult


class TestTrainingStartResultConstruction:
    """TrainingStartResult construction with various parameter combinations."""

    def test_full_construction(self) -> None:
        result = TrainingStartResult(
            run_id="run-123",
            mlflow_run_id="mlflow-456",
            experiment_id="exp-789",
        )
        assert result.run_id == "run-123"
        assert result.mlflow_run_id == "mlflow-456"
        assert result.experiment_id == "exp-789"


class TestTrainingStartResultValidation:
    """Pydantic validation constraints. All fields are required."""

    def test_run_id_required(self) -> None:
        with pytest.raises(ValidationError):
            TrainingStartResult(mlflow_run_id="x", experiment_id="x")  # type: ignore[call-arg]

    def test_mlflow_run_id_required(self) -> None:
        with pytest.raises(ValidationError):
            TrainingStartResult(run_id="x", experiment_id="x")  # type: ignore[call-arg]

    def test_experiment_id_required(self) -> None:
        with pytest.raises(ValidationError):
            TrainingStartResult(run_id="x", mlflow_run_id="x")  # type: ignore[call-arg]

    def test_all_fields_required(self) -> None:
        with pytest.raises(ValidationError):
            TrainingStartResult()  # type: ignore[call-arg]


class TestTrainingStartResultSerialization:
    """Round-trip JSON serialization / deserialization."""

    def test_serialize_to_dict(self) -> None:
        result = TrainingStartResult(
            run_id="run-1",
            mlflow_run_id="mlflow-1",
            experiment_id="exp-1",
        )
        data = result.model_dump()
        assert data["run_id"] == "run-1"
        assert data["mlflow_run_id"] == "mlflow-1"
        assert data["experiment_id"] == "exp-1"

    def test_round_trip_json(self) -> None:
        result = TrainingStartResult(
            run_id="run-99",
            mlflow_run_id="mlflow-99",
            experiment_id="exp-99",
        )
        json_str = result.model_dump_json()
        restored = TrainingStartResult.model_validate_json(json_str)
        assert restored.run_id == "run-99"
        assert restored.mlflow_run_id == "mlflow-99"
        assert restored.experiment_id == "exp-99"

    def test_deserialize_from_dict(self) -> None:
        raw = {
            "run_id": "run-7",
            "mlflow_run_id": "mlflow-7",
            "experiment_id": "exp-7",
        }
        result = TrainingStartResult.model_validate(raw)
        assert result.run_id == "run-7"
        assert result.mlflow_run_id == "mlflow-7"
        assert result.experiment_id == "exp-7"