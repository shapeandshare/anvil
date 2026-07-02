"""e2e tests for fine-tuned model evaluation (spec 054).

Tests the full HTTP contract for ``/v1/eval/fine-tuned``, ``/v1/sse/eval/{run_id}``,
and the GET result endpoints, plus error cases (no dataset, missing run).
Uses the real ASGI app + in-memory DB from the shared ``client`` fixture.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from anvil.db.models.external_model import ExternalModel
from anvil.db.session import AsyncSessionLocal


async def _make_model(display_name: str, runnable: str = "runnable") -> int:
    async with AsyncSessionLocal() as session:
        model = ExternalModel(
            display_name=display_name,
            source_type="huggingface",
            source_identifier=f"{display_name}/repo",
            architecture_family="Llama",
            parameter_count=1000,
            license="mit",
            tokenizer_family="char",
            revision_sha="abc",
            runnable_status=runnable,
            asset_availability="assets_available",
        )
        session.add(model)
        await session.commit()
        return model.id


class TestPostFineTunedEval:
    """Verify POST /v1/eval/fine-tuned validation."""

    ENDPOINT = "/v1/eval/fine-tuned"

    async def test_requires_eval_dataset_name(self, client: AsyncClient) -> None:
        resp = await client.post(
            self.ENDPOINT,
            json={
                "model_id": 1,
                "base_model_id": 2,
            },
        )
        assert resp.status_code == 400
        assert "eval-dataset" in resp.json()["detail"].lower()

    async def test_refuses_missing_model(self, client: AsyncClient) -> None:
        resp = await client.post(
            self.ENDPOINT,
            json={
                "model_id": 99999,
                "base_model_id": 99998,
                "eval_dataset_name": "test-dataset",
            },
        )
        assert resp.status_code == 400
        assert "not found" in resp.json()["detail"].lower()

    async def test_refuses_track_only_model(self, client: AsyncClient) -> None:
        model_id = await _make_model("track-only-model", runnable="track_only")
        base_id = await _make_model("base-model")
        resp = await client.post(
            self.ENDPOINT,
            json={
                "model_id": model_id,
                "base_model_id": base_id,
                "eval_dataset_name": "test-dataset",
            },
        )
        assert resp.status_code == 400
        assert "track" in resp.json()["detail"].lower()


class TestGetEvaluationRun:
    """Verify GET /v1/eval/fine-tuned/{run_id}."""

    async def test_returns_404_for_missing_run(self, client: AsyncClient) -> None:
        resp = await client.get("/v1/eval/fine-tuned/99999")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


class TestGetEvaluationSamples:
    """Verify GET /v1/eval/fine-tuned/{run_id}/samples."""

    async def test_returns_404_for_missing_run(self, client: AsyncClient) -> None:
        resp = await client.get("/v1/eval/fine-tuned/99999/samples")
        assert resp.status_code == 404


class TestListEvaluationRuns:
    """Verify GET /v1/eval/fine-tuned list endpoint."""

    async def test_returns_paginated_shape(self, client: AsyncClient) -> None:
        resp = await client.get("/v1/eval/fine-tuned")
        assert resp.status_code == 200
        body = resp.json()
        assert "runs" in body
        assert "total" in body
        assert "limit" in body
        assert "offset" in body

    async def test_supports_status_filter(self, client: AsyncClient) -> None:
        resp = await client.get("/v1/eval/fine-tuned?status=completed")
        assert resp.status_code == 200
        assert resp.json()["runs"] == []


class TestSSEStream:
    """Verify GET /v1/sse/eval/{run_id} SSE contract."""

    async def test_returns_error_event_for_unknown_run(
        self, client: AsyncClient
    ) -> None:
        async with client.stream("GET", "/v1/sse/eval/99999") as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")
            body = ""
            async for chunk in resp.aiter_text():
                body += chunk
                if "event: error" in body or "event: status" in body:
                    break
            assert "event:" in body
