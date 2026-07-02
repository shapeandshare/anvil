"""Unit tests for evaluation ORM models and repository."""

from __future__ import annotations

import pytest

from anvil.db.models.evaluation_run import EvalSample, EvaluationRun, MetricDelta
from anvil.services._shared.evaluation_status import EvaluationRunStatus


class TestEvaluationRunStatus:
    """Verify enum members, string values, and valid transitions."""

    def test_members(self) -> None:
        assert EvaluationRunStatus.PENDING == "pending"
        assert EvaluationRunStatus.RUNNING == "running"
        assert EvaluationRunStatus.COMPLETED == "completed"
        assert EvaluationRunStatus.FAILED == "failed"

    def test_valid_values(self) -> None:
        values = {m.value for m in EvaluationRunStatus}
        assert values == {"pending", "running", "completed", "failed"}

    def test_str_conversion(self) -> None:
        assert str(EvaluationRunStatus.PENDING) == "pending"
        assert str(EvaluationRunStatus.RUNNING) == "running"

    def test_from_string(self) -> None:
        assert EvaluationRunStatus("pending") is EvaluationRunStatus.PENDING
        assert EvaluationRunStatus("running") is EvaluationRunStatus.RUNNING
        assert EvaluationRunStatus("completed") is EvaluationRunStatus.COMPLETED
        assert EvaluationRunStatus("failed") is EvaluationRunStatus.FAILED


class TestEvaluationRunOrm:
    """Verify ORM model column types, nullable constraints, and defaults."""

    def test_column_types(self) -> None:
        cols = {c.name: c for c in EvaluationRun.__table__.columns}
        assert cols["id"].primary_key
        assert cols["external_model_id"].nullable is False
        assert cols["base_external_model_id"].nullable is True
        assert cols["adapter_id"].nullable is True
        assert cols["tokenizer_family"].nullable is False
        assert cols["eval_dataset_name"].nullable is True
        assert cols["status"].nullable is False
        assert cols["mlflow_run_id"].nullable is True
        assert cols["prompt_count"].nullable is False
        assert cols["error_message"].nullable is True
        assert "created_at" in cols
        assert "updated_at" in cols

    def test_indexes(self) -> None:
        indexes = {idx.name for idx in EvaluationRun.__table__.indexes}
        assert "ix_evaluation_runs_external_model_id" in indexes
        assert "ix_evaluation_runs_base_external_model_id" in indexes
        assert "ix_evaluation_runs_status" in indexes
        assert "ix_evaluation_runs_created_at" in indexes

    def test_default_status(self) -> None:
        assert EvaluationRun.__table__.columns["status"].default is not None


class TestMetricDeltaOrm:
    """Verify FK cascade, uniqueness constraint, and comparable flag."""

    def test_columns(self) -> None:
        cols = {c.name: c for c in MetricDelta.__table__.columns}
        assert cols["evaluation_run_id"].nullable is False
        assert cols["metric_name"].nullable is False
        assert cols["fine_tuned_value"].nullable is False
        assert cols["base_value"].nullable is False
        assert cols["delta"].nullable is False
        assert cols["comparable"].nullable is False

    def test_unique_constraint(self) -> None:
        constraints = MetricDelta.__table__.constraints
        names = {c.name for c in constraints}
        assert "uq_metric_delta_per_run" in names

    def test_cascade_delete(self) -> None:
        fk = next(iter(MetricDelta.__table__.foreign_keys))
        assert fk.ondelete == "CASCADE"


class TestEvalSampleOrm:
    """Verify FK cascade, composite uniqueness, and nullable side-by-side fields."""

    def test_columns(self) -> None:
        cols = {c.name: c for c in EvalSample.__table__.columns}
        assert cols["evaluation_run_id"].nullable is False
        assert cols["prompt_index"].nullable is False
        assert cols["input"].nullable is False
        assert cols["base_output"].nullable is True
        assert cols["fine_tuned_output"].nullable is True
        assert cols["base_loss"].nullable is True
        assert cols["fine_tuned_loss"].nullable is True

    def test_unique_constraint(self) -> None:
        constraints = EvalSample.__table__.constraints
        names = {c.name for c in constraints}
        assert "uq_sample_per_run" in names

    def test_cascade_delete(self) -> None:
        fk = next(iter(EvalSample.__table__.foreign_keys))
        assert fk.ondelete == "CASCADE"
