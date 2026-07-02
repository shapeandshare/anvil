"""Unit tests for EvaluationRunRepository using a real in-memory SQLite session."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from anvil.db.base import Base
from anvil.db.models.evaluation_run import EvalSample, EvaluationRun, MetricDelta
from anvil.db.models.external_model import ExternalModel
from anvil.db.repositories.evaluation_runs import EvaluationRunRepository


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as sess:
        yield sess
    await engine.dispose()


@pytest.fixture
async def base_models(session: AsyncSession) -> tuple[int, int]:
    base = ExternalModel(
        display_name="Base",
        source_type="huggingface",
        source_identifier="base/model",
        architecture_family="Llama",
        parameter_count=1000,
        license="mit",
        tokenizer_family="char",
        revision_sha="abc",
        runnable_status="runnable",
        asset_availability="assets_available",
    )
    ft = ExternalModel(
        display_name="Fine-Tuned",
        source_type="huggingface",
        source_identifier="ft/model",
        architecture_family="Llama",
        parameter_count=1000,
        license="mit",
        tokenizer_family="char",
        revision_sha="def",
        runnable_status="runnable",
        asset_availability="assets_available",
    )
    session.add(base)
    session.add(ft)
    await session.flush()
    return base.id, ft.id


def _make_run(base_id: int, ft_id: int, status: str = "pending") -> EvaluationRun:
    return EvaluationRun(
        external_model_id=ft_id,
        base_external_model_id=base_id,
        tokenizer_family="char",
        base_tokenizer_family="char",
        status=status,
        prompt_count=0,
    )


class TestCreate:
    """Verify creating an evaluation run persists the entity."""

    async def test_creates_and_assigns_id(
        self, session: AsyncSession, base_models
    ) -> None:
        base_id, ft_id = base_models
        repo = EvaluationRunRepository(session)
        run = await repo.create(_make_run(base_id, ft_id))
        assert run.id is not None


class TestGetById:
    """Verify lookup by primary key."""

    async def test_returns_none_when_not_found(self, session: AsyncSession) -> None:
        repo = EvaluationRunRepository(session)
        assert await repo.get_by_id(999) is None

    async def test_returns_run_when_found(
        self, session: AsyncSession, base_models
    ) -> None:
        base_id, ft_id = base_models
        repo = EvaluationRunRepository(session)
        run = await repo.create(_make_run(base_id, ft_id))
        fetched = await repo.get_by_id(run.id)
        assert fetched is not None
        assert fetched.id == run.id


class TestUpdateStatus:
    """Verify status update sets appropriate fields."""

    async def test_sets_running_and_started_at(
        self, session: AsyncSession, base_models
    ) -> None:
        base_id, ft_id = base_models
        repo = EvaluationRunRepository(session)
        run = await repo.create(_make_run(base_id, ft_id))
        await repo.update_status(run.id, "running")
        await session.refresh(run)
        assert run.status == "running"
        assert run.started_at is not None

    async def test_sets_failed_with_error(
        self, session: AsyncSession, base_models
    ) -> None:
        base_id, ft_id = base_models
        repo = EvaluationRunRepository(session)
        run = await repo.create(_make_run(base_id, ft_id))
        await repo.update_status(run.id, "failed", error_message="Model not found")
        await session.refresh(run)
        assert run.status == "failed"
        assert run.error_message == "Model not found"
        assert run.finished_at is not None


class TestListByModel:
    """Verify listing runs for a model with pagination."""

    async def test_returns_empty_when_no_runs(self, session: AsyncSession) -> None:
        repo = EvaluationRunRepository(session)
        runs, total = await repo.list_by_model(1)
        assert list(runs) == []
        assert total == 0

    async def test_respects_limit_and_offset(
        self, session: AsyncSession, base_models
    ) -> None:
        base_id, ft_id = base_models
        repo = EvaluationRunRepository(session)
        for _ in range(5):
            await repo.create(_make_run(base_id, ft_id))
        runs, total = await repo.list_by_model(ft_id, limit=2, offset=0)
        assert len(list(runs)) == 2
        assert total == 5


class TestListByStatus:
    """Verify listing runs by status."""

    async def test_filters_by_status(self, session: AsyncSession, base_models) -> None:
        base_id, ft_id = base_models
        repo = EvaluationRunRepository(session)
        await repo.create(_make_run(base_id, ft_id, status="completed"))
        await repo.create(_make_run(base_id, ft_id, status="pending"))
        runs, total = await repo.list_by_status("completed")
        assert total == 1
        assert list(runs)[0].status == "completed"


class TestMetricsAndSamples:
    """Verify metric delta and sample persistence + retrieval."""

    async def test_add_and_get_metrics(
        self, session: AsyncSession, base_models
    ) -> None:
        base_id, ft_id = base_models
        repo = EvaluationRunRepository(session)
        run = await repo.create(_make_run(base_id, ft_id))
        await repo.add_metric_delta(
            MetricDelta(
                evaluation_run_id=run.id,
                metric_name="eval_loss",
                fine_tuned_value=1.5,
                base_value=2.0,
                delta=-0.5,
                comparable=True,
            )
        )
        metrics = await repo.get_metrics(run.id)
        assert len(list(metrics)) == 1
        assert list(metrics)[0].metric_name == "eval_loss"

    async def test_add_and_get_samples(
        self, session: AsyncSession, base_models
    ) -> None:
        base_id, ft_id = base_models
        repo = EvaluationRunRepository(session)
        run = await repo.create(_make_run(base_id, ft_id))
        await repo.add_sample(
            EvalSample(
                evaluation_run_id=run.id,
                prompt_index=0,
                input="hello",
                base_output="world",
                fine_tuned_output="there",
                base_loss=2.0,
                fine_tuned_loss=1.5,
            )
        )
        samples = await repo.get_samples(run.id)
        assert len(list(samples)) == 1
        assert list(samples)[0].input == "hello"

    async def test_get_metrics_empty(self, session: AsyncSession, base_models) -> None:
        base_id, ft_id = base_models
        repo = EvaluationRunRepository(session)
        run = await repo.create(_make_run(base_id, ft_id))
        assert list(await repo.get_metrics(run.id)) == []

    async def test_get_samples_empty(self, session: AsyncSession, base_models) -> None:
        base_id, ft_id = base_models
        repo = EvaluationRunRepository(session)
        run = await repo.create(_make_run(base_id, ft_id))
        assert list(await repo.get_samples(run.id)) == []
