# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for eval API endpoints.

Covers perplexity computation via /v1/eval/perplexity.
"""

from __future__ import annotations

from datetime import UTC, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from anvil.api.app import app
from anvil.api.deps import get_workbench
from anvil.services.inference.inference import InferenceService


class TestEvalPerplexity:
    """Tests for POST /v1/eval/perplexity."""

    @pytest.fixture
    def mock_model(self):
        """Create a mock loaded model for testing perplexity."""
        model = MagicMock()
        model.vocab_size = 10
        model.n_embd = 16
        model.n_head = 4
        model.n_layer = 1
        model.block_size = 16
        return model

    @pytest.fixture
    def mock_loaded(self, mock_model):
        """Create a mock loaded model result with chars."""
        loaded = MagicMock()
        loaded.model = mock_model
        # chars = list of unique chars for vocabulary
        loaded.chars = list("abcdefghij")  # 10 chars matching vocab_size
        return loaded

    async def test_perplexity_computed_successfully(self, client, mock_loaded):
        """Happy path: perplexity computed for a valid model and text."""

        class FakeValue:
            data = 0.5

            def log(self):
                return FakeValue()

            def __neg__(self):
                return FakeValue()

        fake_value = FakeValue()

        with (
            patch.object(
                InferenceService,
                "load_model",
                return_value=mock_loaded,
            ),
            patch("anvil.api.v1.eval.softmax", return_value=[fake_value] * 10),
        ):
            resp = await client.post(
                "/v1/eval/perplexity",
                json={
                    "model_id": 1,
                    "version": 1,
                    "text": "abc",
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "perplexity" in data
        assert data["perplexity"] > 0
        assert "avg_loss" in data
        assert data["avg_loss"] > 0
        assert data["num_positions"] > 0
        assert data["vocab_size"] == 10
        assert "model_config" in data
        assert data["model_config"]["n_layer"] == 1
        assert data["model_config"]["n_embd"] == 16
        assert data["model_config"]["n_head"] == 4
        assert data["model_config"]["block_size"] == 16

    async def test_returns_404_when_model_not_found(self, client):
        """Returns 404 when the model is not found."""
        with patch.object(
            InferenceService,
            "load_model",
            side_effect=ValueError("Model not found"),
        ):
            resp = await client.post(
                "/v1/eval/perplexity",
                json={
                    "model_id": 999,
                    "version": 1,
                    "text": "abc",
                },
            )
        assert resp.status_code == 404
        assert "Model not found" in resp.json()["detail"]

    async def test_returns_404_on_file_not_found(self, client):
        """Returns 404 when the model file is not found."""
        with patch.object(
            InferenceService,
            "load_model",
            side_effect=FileNotFoundError("model file missing"),
        ):
            resp = await client.post(
                "/v1/eval/perplexity",
                json={
                    "model_id": 1,
                    "version": 1,
                    "text": "abc",
                },
            )
        assert resp.status_code == 404
        assert "model file missing" in resp.json()["detail"]

    async def test_returns_400_for_char_out_of_vocab(self, client, mock_loaded):
        """Returns 400 when text contains a character not in vocabulary."""
        with patch.object(
            InferenceService,
            "load_model",
            return_value=mock_loaded,
        ):
            resp = await client.post(
                "/v1/eval/perplexity",
                json={
                    "model_id": 1,
                    "version": 1,
                    "text": "xyz!",
                },
            )
        assert resp.status_code == 400
        assert "not in model vocabulary" in resp.json()["detail"]

    async def test_validates_required_fields(self, client):
        """Pydantic validation: missing fields return 422."""
        resp = await client.post(
            "/v1/eval/perplexity",
            json={"text": "abc"},
        )
        assert resp.status_code == 422

    async def test_validates_empty_text(self, client):
        """Pydantic validation: empty text returns 422."""
        resp = await client.post(
            "/v1/eval/perplexity",
            json={"model_id": 1, "version": 1, "text": ""},
        )
        assert resp.status_code == 422

    async def test_validates_extra_fields_forbidden(self, client):
        """Pydantic validation: extra fields are forbidden."""
        resp = await client.post(
            "/v1/eval/perplexity",
            json={
                "model_id": 1,
                "version": 1,
                "text": "abc",
                "extra": "field",
            },
        )
        assert resp.status_code == 422


########################################################################
# Fine-tuned model evaluation (spec 054)
########################################################################


class TestStartFineTunedEval:
    """Tests for POST /v1/eval/fine-tuned."""

    @pytest.fixture
    def mock_eval_wb(self):
        wb = MagicMock()
        wb.evaluate_fine_tuned = AsyncMock(
            return_value=MagicMock(id=42, status="queued"),
        )
        app.dependency_overrides[get_workbench] = lambda: wb
        yield wb
        app.dependency_overrides.clear()

    async def test_start_success(self, client, mock_eval_wb):
        """Returns 201 with run_id and sse_url."""
        resp = await client.post(
            "/v1/eval/fine-tuned",
            json={
                "model_id": 1,
                "base_model_id": 1,
                "eval_dataset_name": "test-ds",
            },
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["run_id"] == 42
        assert data["status"] == "queued"
        assert "sse_url" in data

    async def test_start_missing_eval_dataset(self, client):
        """Returns 400 when eval_dataset_name is not provided."""
        resp = await client.post(
            "/v1/eval/fine-tuned",
            json={"model_id": 1, "base_model_id": 1},
        )

        assert resp.status_code == 400
        assert "eval-dataset name is required" in resp.json()["detail"]

    async def test_start_value_error(self, client):
        """Returns 400 when evaluate_fine_tuned raises ValueError."""
        wb = MagicMock()
        wb.evaluate_fine_tuned = AsyncMock(
            side_effect=ValueError("Invalid model"),
        )
        app.dependency_overrides[get_workbench] = lambda: wb
        try:
            resp = await client.post(
                "/v1/eval/fine-tuned",
                json={
                    "model_id": 1,
                    "base_model_id": 999,
                    "eval_dataset_name": "test-ds",
                },
            )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 400


class TestGetEvaluationRun:
    """Tests for GET /v1/eval/fine-tuned/{run_id}."""

    def _make_mock_run(self):
        r = MagicMock()
        r.id = 1
        r.external_model_id = 10
        r.base_external_model_id = 5
        r.adapter_id = None
        r.tokenizer_family = "bpe"
        r.base_tokenizer_family = "bpe"
        r.status = "completed"
        r.prompt_count = 5
        r.created_at = datetime.now(UTC)
        r.started_at = datetime.now(UTC)
        r.finished_at = datetime.now(UTC)
        r.mlflow_run_id = "mlflow_run_1"
        return r

    async def test_get_found(self, client):
        """Returns evaluation run details."""
        mock_run = self._make_mock_run()
        mock_metrics = [
            MagicMock(
                metric_name="perplexity",
                fine_tuned_value=5.0,
                base_value=10.0,
                delta=-5.0,
                comparable=True,
            ),
        ]

        mock_wb = MagicMock()
        mock_wb.get_evaluation_run = AsyncMock(return_value=mock_run)
        mock_wb.evaluation = MagicMock()
        mock_wb.evaluation.get_metrics = AsyncMock(return_value=mock_metrics)
        mock_wb.external_model_repo = MagicMock()
        mock_wb.external_model_repo.get = AsyncMock(return_value=None)
        app.dependency_overrides[get_workbench] = lambda: mock_wb
        try:
            resp = await client.get("/v1/eval/fine-tuned/1")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == 1
        assert data["status"] == "completed"
        assert len(data["metrics"]) == 1
        assert data["metrics"][0]["metric_name"] == "perplexity"

    async def test_get_not_found(self, client):
        """Returns 404 when evaluation run not found."""
        mock_wb = MagicMock()
        mock_wb.get_evaluation_run = AsyncMock(return_value=None)
        app.dependency_overrides[get_workbench] = lambda: mock_wb
        try:
            resp = await client.get("/v1/eval/fine-tuned/999")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 404

    async def test_get_with_model_names(self, client):
        """Returns model name from repository."""
        mock_run = self._make_mock_run()
        mock_model = MagicMock()
        mock_model.display_name = "fine-tuned-model"
        mock_base = MagicMock()
        mock_base.display_name = "base-model"

        mock_wb = MagicMock()
        mock_wb.get_evaluation_run = AsyncMock(return_value=mock_run)
        mock_wb.evaluation = MagicMock()
        mock_wb.evaluation.get_metrics = AsyncMock(return_value=[])
        mock_wb.external_model_repo = MagicMock()

        async def _fake_get(mid):
            if mid == 10:
                return mock_model
            if mid == 5:
                return mock_base
            return None

        mock_wb.external_model_repo.get = AsyncMock(side_effect=_fake_get)
        app.dependency_overrides[get_workbench] = lambda: mock_wb
        try:
            resp = await client.get("/v1/eval/fine-tuned/1")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["model_name"] == "fine-tuned-model"
        assert data["base_model_name"] == "base-model"


class TestGetEvalSamples:
    """Tests for GET /v1/eval/fine-tuned/{run_id}/samples."""

    async def test_returns_samples(self, client):
        """Returns per-prompt sample outputs."""
        mock_sample = MagicMock()
        mock_sample.prompt_index = 0
        mock_sample.input = "hello"
        mock_sample.base_output = "world"
        mock_sample.fine_tuned_output = "there"
        mock_sample.base_loss = 0.5
        mock_sample.fine_tuned_loss = 0.3

        mock_wb = MagicMock()
        mock_wb.get_evaluation_run = AsyncMock(return_value=MagicMock(id=1))
        mock_wb.get_evaluation_samples = AsyncMock(return_value=[mock_sample])
        app.dependency_overrides[get_workbench] = lambda: mock_wb
        try:
            resp = await client.get("/v1/eval/fine-tuned/1/samples")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["prompt_index"] == 0
        assert data[0]["input"] == "hello"

    async def test_returns_404_when_not_found(self, client):
        """Returns 404 when evaluation run not found."""
        mock_wb = MagicMock()
        mock_wb.get_evaluation_run = AsyncMock(return_value=None)
        app.dependency_overrides[get_workbench] = lambda: mock_wb
        try:
            resp = await client.get("/v1/eval/fine-tuned/999/samples")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 404


class TestListEvaluationRuns:
    """Tests for GET /v1/eval/fine-tuned."""

    async def test_list_with_filters(self, client):
        """Returns paginated evaluation run list."""
        mock_run = MagicMock()
        mock_run.id = 1
        mock_run.external_model_id = 10
        mock_run.base_external_model_id = None
        mock_run.adapter_id = None
        mock_run.tokenizer_family = "bpe"
        mock_run.base_tokenizer_family = None
        mock_run.status = "completed"
        mock_run.prompt_count = 5
        mock_run.created_at = datetime.now(UTC)
        mock_run.started_at = None
        mock_run.finished_at = None
        mock_run.mlflow_run_id = None

        mock_wb = MagicMock()
        mock_wb.list_evaluation_runs = AsyncMock(
            return_value=([mock_run], 1),
        )
        app.dependency_overrides[get_workbench] = lambda: mock_wb
        try:
            resp = await client.get(
                "/v1/eval/fine-tuned?model_id=10&status=completed&limit=5&offset=0",
            )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["runs"]) == 1
        assert data["runs"][0]["run_id"] == 1
        assert data["runs"][0]["status"] == "completed"

    async def test_list_empty(self, client):
        """Returns empty list when no runs match."""
        mock_wb = MagicMock()
        mock_wb.list_evaluation_runs = AsyncMock(return_value=([], 0))

        app.dependency_overrides[get_workbench] = lambda: mock_wb
        try:
            resp = await client.get("/v1/eval/fine-tuned")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["runs"] == []


class TestStreamEval:
    """Tests for GET /v1/sse/eval/{run_id}."""

    async def test_stream_returns_event_stream(self, client):
        """Returns SSE streaming response."""
        mock_wb = MagicMock()
        mock_wb.evaluation = MagicMock()
        mock_wb.evaluation.get_event_stream = MagicMock(return_value=[])
        app.dependency_overrides[get_workbench] = lambda: mock_wb
        try:
            resp = await client.get("/v1/sse/eval/1")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.headers.get("content-type") == "text/event-stream; charset=utf-8"
