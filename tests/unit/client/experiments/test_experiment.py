# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for the Experiment DTO — construction, defaults, and serialization."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from anvil.client.experiments.experiment import Experiment


class TestExperimentConstruction:
    """Experiment construction with various parameter combinations."""

    def test_minimal_construction(self) -> None:
        exp = Experiment(id="exp-1", name="my-experiment")
        assert exp.id == "exp-1"
        assert exp.name == "my-experiment"
        assert exp.run_count == 0
        assert exp.best_loss is None
        assert exp.duration is None
        assert exp.mlflow_url is None

    def test_full_construction(self) -> None:
        exp = Experiment(
            id="exp-42",
            name="full-experiment",
            run_count=10,
            best_loss=0.05,
            duration=123.4,
            mlflow_url="http://mlflow:5001/#/experiments/42",
        )
        assert exp.id == "exp-42"
        assert exp.name == "full-experiment"
        assert exp.run_count == 10
        assert exp.best_loss == 0.05
        assert exp.duration == 123.4
        assert exp.mlflow_url == "http://mlflow:5001/#/experiments/42"


class TestExperimentDefaults:
    """Default values for optional fields."""

    def test_run_count_defaults_to_zero(self) -> None:
        assert Experiment(id="x", name="x").run_count == 0

    def test_best_loss_defaults_to_none(self) -> None:
        assert Experiment(id="x", name="x").best_loss is None

    def test_duration_defaults_to_none(self) -> None:
        assert Experiment(id="x", name="x").duration is None

    def test_mlflow_url_defaults_to_none(self) -> None:
        assert Experiment(id="x", name="x").mlflow_url is None


class TestExperimentValidation:
    """Pydantic validation constraints."""

    def test_id_required(self) -> None:
        with pytest.raises(ValidationError):
            Experiment(name="x")  # type: ignore[call-arg]

    def test_name_required(self) -> None:
        with pytest.raises(ValidationError):
            Experiment(id="x")  # type: ignore[call-arg]


class TestExperimentSerialization:
    """Round-trip JSON serialization / deserialization."""

    def test_serialize_to_dict(self) -> None:
        exp = Experiment(id="e1", name="test", run_count=5, best_loss=0.1)
        data = exp.model_dump()
        assert data["id"] == "e1"
        assert data["name"] == "test"
        assert data["run_count"] == 5
        assert data["best_loss"] == 0.1
        assert data["duration"] is None
        assert data["mlflow_url"] is None

    def test_round_trip_json(self) -> None:
        exp = Experiment(id="e99", name="roundtrip", run_count=42, best_loss=0.01)
        json_str = exp.model_dump_json()
        restored = Experiment.model_validate_json(json_str)
        assert restored.id == "e99"
        assert restored.name == "roundtrip"
        assert restored.run_count == 42
        assert restored.best_loss == 0.01

    def test_deserialize_from_dict(self) -> None:
        raw = {"id": "e7", "name": "from-dict", "run_count": 10}
        exp = Experiment.model_validate(raw)
        assert exp.id == "e7"
        assert exp.name == "from-dict"
        assert exp.run_count == 10
