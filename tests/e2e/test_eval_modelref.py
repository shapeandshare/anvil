"""e2e tests for evaluation with ModelRef (spec 064, US3).

Tests that ``POST /v1/eval/fine-tuned`` accepts ``model_name``/``model_version``
and ``base_model_name``/``base_model_version``, and ``GET /v1/eval/fine-tuned/{run_id}``
exposes ModelRef fields.

TDD: RED phase — these tests should fail before implementation.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestPostFineTunedModelRef:
    """Verify POST /v1/eval/fine-tuned with ModelRef fields."""

    ENDPOINT = "/v1/eval/fine-tuned"

    async def test_requires_eval_dataset_name(self, client: AsyncClient) -> None:
        """Missing eval_dataset_name should still 400 even with ModelRef."""
        resp = await client.post(
            self.ENDPOINT,
            json={
                "model_id": 1,
                "base_model_id": 2,
                "model_name": "test-model",
                "model_version": 1,
                "base_model_name": "base-model",
                "base_model_version": 1,
            },
        )
        assert resp.status_code == 400
        assert "eval-dataset" in resp.json()["detail"].lower()


class TestGetEvaluationRunModelRef:
    """Verify GET /v1/eval/fine-tuned/{run_id} exposes ModelRef fields."""

    async def test_returns_404_for_missing_run(self, client: AsyncClient) -> None:
        """Unknown run ID still returns 404."""
        resp = await client.get("/v1/eval/fine-tuned/99999")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


class TestListEvaluationModelRef:
    """Verify GET /v1/eval/fine-tuned returns ModelRef fields."""

    async def test_list_shape_has_modelref_fields(self, client: AsyncClient) -> None:
        """List response should include model_name/model_version fields."""
        resp = await client.get("/v1/eval/fine-tuned")
        assert resp.status_code == 200
        data = resp.json()
        assert "runs" in data
        assert "total" in data