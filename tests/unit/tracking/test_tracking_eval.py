"""Unit tests for TrackingService eval-specific methods."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anvil.services._shared.evaluation_status import EvaluationRunStatus
from anvil.services.tracking.tracking import TrackingService


@pytest.fixture
def tracking():
    svc = TrackingService()
    svc._state = MagicMock(status="active")
    svc._lock = AsyncMock()
    svc._experiment_id = "0"
    svc._client = MagicMock()
    svc._lazy_init = MagicMock()
    svc.start_run = AsyncMock(return_value="mlflow_run_abc")
    svc.set_tag = AsyncMock()
    svc.log_metric = AsyncMock()
    svc.finish_run = AsyncMock()
    svc.fail_run = AsyncMock()
    return svc


class TestStartEvalRun:
    """Verify start_eval_run creates an MLflow run with correct eval tags."""

    async def test_calls_start_run(self, tracking):
        run_id = await tracking.start_eval_run(
            model_id=42,
            base_model_id=40,
            tokenizer_family="char",
        )
        assert run_id == "mlflow_run_abc"
        tracking.start_run.assert_awaited_once()

    async def test_sets_eval_tags(self, tracking):
        await tracking.start_eval_run(
            model_id=42,
            base_model_id=40,
            tokenizer_family="subword",
        )
        tag_calls = [c.args for c in tracking.set_tag.await_args_list]
        assert ("mlflow_run_abc", "anvil.origin", "evaluation") in tag_calls
        assert ("mlflow_run_abc", "anvil.entity_type", "evaluation") in tag_calls
        assert ("mlflow_run_abc", "anvil.base_model_ref", "40") in tag_calls
        assert ("mlflow_run_abc", "anvil.fine_tuned_model_id", "42") in tag_calls
        assert ("mlflow_run_abc", "anvil.tokenizer_family", "subword") in tag_calls
        assert (
            "mlflow_run_abc",
            "anvil.eval_status",
            EvaluationRunStatus.RUNNING,
        ) in tag_calls

    async def test_sets_adapter_tag_when_provided(self, tracking):
        await tracking.start_eval_run(
            model_id=42,
            base_model_id=40,
            adapter_id="run_99",
            tokenizer_family="char",
        )
        tracking.set_tag.assert_any_call("mlflow_run_abc", "anvil.adapter_id", "run_99")

    async def test_returns_empty_when_start_run_degraded(self, tracking):
        tracking.start_run = AsyncMock(return_value="")
        run_id = await tracking.start_eval_run(
            model_id=42,
            base_model_id=40,
            tokenizer_family="char",
        )
        assert run_id == ""
        tracking.set_tag.assert_not_awaited()


class TestFinishEvalRun:
    """Verify finish_eval_run sets completed status."""

    async def test_sets_completed_tag_and_finishes(self, tracking):
        await tracking.finish_eval_run("mlflow_run_abc")
        tracking.set_tag.assert_any_call(
            "mlflow_run_abc", "anvil.eval_status", EvaluationRunStatus.COMPLETED
        )
        tracking.finish_run.assert_awaited_once_with("mlflow_run_abc")

    async def test_skips_when_run_id_empty(self, tracking):
        await tracking.finish_eval_run("")
        tracking.finish_run.assert_not_awaited()


class TestFailEvalRun:
    """Verify fail_eval_run sets failed status with reason."""

    async def test_sets_failed_tag_and_fails(self, tracking):
        await tracking.fail_eval_run("mlflow_run_abc", reason="model error")
        tracking.set_tag.assert_any_call(
            "mlflow_run_abc", "anvil.eval_status", EvaluationRunStatus.FAILED
        )
        tracking.set_tag.assert_any_call(
            "mlflow_run_abc", "anvil.eval_error", "model error"
        )
        tracking.fail_run.assert_awaited_once_with(
            "mlflow_run_abc", _reason="model error"
        )

    async def test_skips_when_run_id_empty(self, tracking):
        await tracking.fail_eval_run("")
        tracking.fail_run.assert_not_awaited()
