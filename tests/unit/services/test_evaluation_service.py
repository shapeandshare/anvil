"""Tests for EvaluationService — orchestration, SSE streaming, helpers."""

from __future__ import annotations

import math
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anvil.services.evaluation.evaluation_service import (
    EvaluationService,
    _compute_metric_deltas,
    _perplexity,
)


class TestPerplexity:
    """_perplexity helper function."""

    def test_normal_loss(self):
        assert _perplexity(0.0) == math.exp(0.0)
        assert _perplexity(1.0) == math.exp(1.0)
        assert _perplexity(5.0) == math.exp(5.0)

    def test_overflow_returns_infinity(self):
        assert _perplexity(700) == float("inf")
        assert _perplexity(1000) == float("inf")


class TestComputeMetricDeltas:
    """_compute_metric_deltas helper function."""

    def test_empty_losses(self):
        deltas = _compute_metric_deltas(
            run_id=1, base_losses=[], ft_losses=[], comparable=True
        )
        assert len(deltas) == 2
        eval_loss = deltas[0]
        assert eval_loss.metric_name == "eval_loss"
        assert eval_loss.fine_tuned_value == 0.0
        assert eval_loss.base_value == 0.0
        assert eval_loss.comparable is True

    def typical_case(self):
        deltas = _compute_metric_deltas(
            run_id=2,
            base_losses=[2.0, 3.0],
            ft_losses=[1.5, 2.5],
            comparable=False,
        )
        assert len(deltas) == 2
        assert deltas[0].metric_name == "eval_loss"
        assert deltas[0].delta == -0.5  # (1.5+2.5)/2 - (2.0+3.0)/2
        assert deltas[0].comparable is False
        assert deltas[1].metric_name == "perplexity"


class TestEvaluationServiceCore:
    """Core EvaluationService methods with mocked dependencies."""

    @pytest.fixture
    def svc(self):
        session = MagicMock()
        inference = MagicMock()
        tracking = MagicMock()
        return EvaluationService(session, inference, tracking)

    @pytest.mark.asyncio
    async def test_get_run_delegates(self, svc):
        svc._repo.get_by_id = AsyncMock(return_value="fake_run")
        result = await svc.get_run(42)
        svc._repo.get_by_id.assert_awaited_once_with(42)
        assert result == "fake_run"

    @pytest.mark.asyncio
    async def test_get_run_returns_none(self, svc):
        svc._repo.get_by_id = AsyncMock(return_value=None)
        result = await svc.get_run(999)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_metrics_delegates(self, svc):
        svc._repo.get_metrics = AsyncMock(return_value=["m1", "m2"])
        result = await svc.get_metrics(1)
        svc._repo.get_metrics.assert_awaited_once_with(1)
        assert result == ["m1", "m2"]

    @pytest.mark.asyncio
    async def test_get_metrics_empty(self, svc):
        svc._repo.get_metrics = AsyncMock(return_value=[])
        result = await svc.get_metrics(1)
        assert result == []

    @pytest.mark.asyncio
    async def test_get_samples_delegates(self, svc):
        svc._repo.get_samples = AsyncMock(return_value=["s1"])
        result = await svc.get_samples(1)
        svc._repo.get_samples.assert_awaited_once_with(1)
        assert result == ["s1"]

    @pytest.mark.asyncio
    async def test_list_runs_no_filters(self, svc):
        svc._repo.list_by_model = AsyncMock(return_value=(["r1", "r2"], 2))
        runs, total = await svc.list_runs()
        assert runs == ["r1", "r2"]
        assert total == 2

    @pytest.mark.asyncio
    async def test_list_runs_by_model(self, svc):
        svc._repo.list_by_model = AsyncMock(return_value=(["r1"], 1))
        runs, total = await svc.list_runs(model_id=5)
        svc._repo.list_by_model.assert_awaited_once_with(5, limit=20, offset=0)
        assert total == 1

    @pytest.mark.asyncio
    async def test_list_runs_by_status(self, svc):
        svc._repo.list_by_status = AsyncMock(return_value=(["r1"], 1))
        runs, total = await svc.list_runs(status="completed")
        svc._repo.list_by_status.assert_awaited_once_with(
            "completed", limit=20, offset=0
        )
        assert total == 1

    @pytest.mark.asyncio
    async def test_list_runs_with_limit_offset(self, svc):
        svc._repo.list_by_model = AsyncMock(return_value=(["r1"], 50))
        runs, total = await svc.list_runs(limit=5, offset=10)
        svc._repo.list_by_model.assert_awaited_once_with(0, limit=5, offset=10)
        assert total == 50

    @pytest.mark.asyncio
    async def test_start_evaluation_model_not_found(self, svc):
        svc._models_repo.get = AsyncMock(return_value=None)
        with pytest.raises(ValueError, match="not found"):
            await svc.start_evaluation(model_id=1, base_model_id=2)

    @pytest.mark.asyncio
    async def test_start_evaluation_track_only(self, svc):
        mock_model = MagicMock()
        mock_model.runnable_status = "track_only"
        mock_model.runnable_reason = "Model is track only"
        svc._models_repo.get = AsyncMock(return_value=mock_model)
        with pytest.raises(ValueError, match="track"):
            await svc.start_evaluation(model_id=1, base_model_id=2)

    @pytest.mark.asyncio
    async def test_start_evaluation_creates_run(self, svc):
        mock_model = MagicMock()
        mock_model.runnable_status = "runnable"
        svc._models_repo.get = AsyncMock(return_value=mock_model)

        mock_run = MagicMock()
        mock_run.id = 100
        svc._repo.create = AsyncMock(return_value=mock_run)
        svc._session.commit = AsyncMock()

        with (
            patch(
                "anvil.services.evaluation.evaluation_service._run_eval_worker"
            ) as mock_worker,
            patch(
                "anvil.services.evaluation.evaluation_service.asyncio.create_task"
            ) as mock_create_task,
        ):
            mock_task = MagicMock()
            mock_create_task.return_value = mock_task
            result = await svc.start_evaluation(
                model_id=1, base_model_id=2, prompts=["hello"]
            )
            assert result.id == 100
            svc._repo.create.assert_awaited_once()
            svc._session.commit.assert_awaited_once()
            mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_event_stream_no_queue(self, svc):
        generator = svc.get_event_stream(999)
        events = []
        async for event in generator:
            events.append(event)
        assert len(events) == 1
        assert "No active evaluation" in events[0]

    @pytest.mark.asyncio
    async def test_get_event_stream_with_timeout(self, svc):
        import asyncio

        queue: asyncio.Queue[dict[str, object] | None] = asyncio.Queue()
        from anvil.services.evaluation import evaluation_service

        evaluation_service._QUEUES[50] = queue

        generator = svc.get_event_stream(50)
        it = generator.__aiter__()

        event1 = await it.__anext__()
        assert "running" in event1

        await queue.put(
            {
                "event": "progress",
                "data": '{"prompt_index": 0, "total": 1}',
            }
        )
        event2 = await it.__anext__()
        assert "progress" in event2

        await queue.put(None)
        with pytest.raises(StopAsyncIteration):
            await it.__anext__()

        evaluation_service._QUEUES.pop(50, None)

    @pytest.mark.asyncio
    async def test_get_event_stream_complete_breaks(self, svc):
        import asyncio

        queue: asyncio.Queue[dict[str, object] | None] = asyncio.Queue()
        from anvil.services.evaluation import evaluation_service

        evaluation_service._QUEUES[51] = queue
        generator = svc.get_event_stream(51)
        it = generator.__aiter__()

        await it.__anext__()  # running event

        await queue.put({"event": "complete", "data": "{}"})
        event = await it.__anext__()
        assert "complete" in event

        # After complete, the queue should be consumed and generator ends.
        await queue.put(None)  # cleanup sentinel (put by _run_eval_worker)
        with pytest.raises(StopAsyncIteration):
            await it.__anext__()

        evaluation_service._QUEUES.pop(51, None)

    @pytest.mark.asyncio
    async def test_get_event_stream_error_breaks(self, svc):
        import asyncio

        queue: asyncio.Queue[dict[str, object] | None] = asyncio.Queue()
        from anvil.services.evaluation import evaluation_service

        evaluation_service._QUEUES[52] = queue
        generator = svc.get_event_stream(52)
        it = generator.__aiter__()

        await it.__anext__()  # running event

        await queue.put({"event": "error", "data": '{"message":"fail"}'})
        event = await it.__anext__()
        assert "error" in event

        await queue.put(None)
        with pytest.raises(StopAsyncIteration):
            await it.__anext__()

        evaluation_service._QUEUES.pop(52, None)
