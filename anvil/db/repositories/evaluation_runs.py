"""Repository for ``EvaluationRun``, ``MetricDelta``, and ``EvalSample`` CRUD operations."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.evaluation_run import EvalSample, EvaluationRun, MetricDelta


class EvaluationRunRepository:
    """Async CRUD repository for evaluation run entities.

    Parameters
    ----------
    session : AsyncSession
        SQLAlchemy async session bound to the application database.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- EvaluationRun ---

    async def create(self, run: EvaluationRun) -> EvaluationRun:
        """Persist a new ``EvaluationRun``.

        Parameters
        ----------
        run : EvaluationRun
            Unsaved evaluation run instance.

        Returns
        -------
        EvaluationRun
            The saved instance with ``id`` populated.
        """
        self._session.add(run)
        await self._session.flush()
        return run

    async def get_by_id(self, run_id: int) -> EvaluationRun | None:
        """Look up an evaluation run by its primary key.

        Parameters
        ----------
        run_id : int
            The evaluation run ID.

        Returns
        -------
        EvaluationRun | None
            The matching run, or ``None`` if not found.
        """
        stmt = select(EvaluationRun).where(EvaluationRun.id == run_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_status(
        self,
        run_id: int,
        status: str,
        error_message: str | None = None,
    ) -> None:
        """Update the status of an evaluation run.

        Parameters
        ----------
        run_id : int
            The evaluation run ID.
        status : str
            New status value (``EvaluationRunStatus``).
        error_message : str | None, optional
            Error detail if transitioning to ``"failed"``. Defaults to ``None``.
        """
        values: dict[str, Any] = {"status": status}
        if error_message is not None:
            values["error_message"] = error_message
        if status == "running":
            values["started_at"] = func.now()
        elif status in ("completed", "failed"):
            values["finished_at"] = func.now()

        stmt = update(EvaluationRun).where(EvaluationRun.id == run_id).values(**values)
        await self._session.execute(stmt)

    async def list_by_model(
        self,
        model_id: int,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[Sequence[EvaluationRun], int]:
        """List evaluation runs for a specific model, newest first.

        Parameters
        ----------
        model_id : int
            FK to ``ExternalModel.id``.
        limit : int, optional
            Maximum results. Defaults to 20.
        offset : int, optional
            Result offset for pagination. Defaults to 0.

        Returns
        -------
        tuple[Sequence[EvaluationRun], int]
            (Runs, total count) for the given model.
        """
        count_q = (
            select(func.count())
            .select_from(EvaluationRun)
            .where(EvaluationRun.external_model_id == model_id)
        )
        total = await self._session.scalar(count_q)

        stmt = (
            select(EvaluationRun)
            .where(EvaluationRun.external_model_id == model_id)
            .order_by(EvaluationRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all(), total or 0

    async def list_by_status(
        self,
        status: str,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[Sequence[EvaluationRun], int]:
        """List evaluation runs by status, newest first.

        Parameters
        ----------
        status : str
            Status to filter by (e.g. ``"pending"``, ``"completed"``).
        limit : int, optional
            Maximum results. Defaults to 20.
        offset : int, optional
            Result offset for pagination. Defaults to 0.

        Returns
        -------
        tuple[Sequence[EvaluationRun], int]
            (Runs, total count) for the given status.
        """
        count_q = (
            select(func.count())
            .select_from(EvaluationRun)
            .where(EvaluationRun.status == status)
        )
        total = await self._session.scalar(count_q)

        stmt = (
            select(EvaluationRun)
            .where(EvaluationRun.status == status)
            .order_by(EvaluationRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all(), total or 0

    # --- MetricDelta ---

    async def add_metric_delta(self, delta: MetricDelta) -> MetricDelta:
        """Persist a metric delta for an evaluation run.

        Parameters
        ----------
        delta : MetricDelta
            Unsaved metric delta instance.

        Returns
        -------
        MetricDelta
            The saved instance with ``id`` populated.
        """
        self._session.add(delta)
        await self._session.flush()
        return delta

    async def get_metrics(self, run_id: int) -> Sequence[MetricDelta]:
        """Return all metric deltas for an evaluation run.

        Parameters
        ----------
        run_id : int
            The evaluation run ID.

        Returns
        -------
        Sequence[MetricDelta]
            Metric delta rows for the run.
        """
        stmt = (
            select(MetricDelta)
            .where(MetricDelta.evaluation_run_id == run_id)
            .order_by(MetricDelta.metric_name)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    # --- EvalSample ---

    async def add_sample(self, sample: EvalSample) -> EvalSample:
        """Persist a per-prompt sample for an evaluation run.

        Parameters
        ----------
        sample : EvalSample
            Unsaved eval sample instance.

        Returns
        -------
        EvalSample
            The saved instance with ``id`` populated.
        """
        self._session.add(sample)
        await self._session.flush()
        return sample

    async def get_samples(self, run_id: int) -> Sequence[EvalSample]:
        """Return all per-prompt samples for an evaluation run.

        Parameters
        ----------
        run_id : int
            The evaluation run ID.

        Returns
        -------
        Sequence[EvalSample]
            Eval sample rows for the run, ordered by prompt index.
        """
        stmt = (
            select(EvalSample)
            .where(EvalSample.evaluation_run_id == run_id)
            .order_by(EvalSample.prompt_index)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
