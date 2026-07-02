"""Orchestration for fine-tuned model evaluation (spec 054).

Combines per-prompt generation + loss comparison, async SSE streaming,
and persisting results to the database and MLflow.

The evaluation runtime (SSE queues + background tasks) is process-shared
module-level state, mirroring the training runtime, so the POST submit
request and the separate SSE GET request observe the same queue.
Background workers open their own ``AsyncSessionLocal`` session — the
request-scoped session is never used after the request returns.
"""

from __future__ import annotations

import asyncio
import json
import math
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ...db.models.evaluation_run import EvalSample, EvaluationRun, MetricDelta
from ...db.repositories.evaluation_runs import EvaluationRunRepository
from ...db.repositories.external_models import ExternalModelRepository
from ...db.session import AsyncSessionLocal
from ...services._shared.evaluation_status import EvaluationRunStatus
from ...services._shared.runnable_status import RunnableStatus
from ...services.inference.inference import InferenceService
from ...services.inference.loaded_model import LoadedModel
from ...services.tracking.tracking import TrackingService
from .evaluator import Evaluator

_QUEUES: dict[int, asyncio.Queue[dict[str, object] | None]] = {}
_TASKS: dict[int, asyncio.Task[Any]] = {}


class EvaluationService:
    """Orchestrates fine-tuned model evaluations as async SSE-streamed jobs.

    Parameters
    ----------
    session : AsyncSession
        Request-scoped DB session, used ONLY for synchronous validation and
        read queries (create, get, list). Background workers open their own
        session and never touch this one.
    inference : InferenceService
        Inference service for loading models, generating, and loss.
    tracking : TrackingService
        MLflow tracking service for eval metric recording.
    """

    def __init__(
        self,
        session: AsyncSession,
        inference: InferenceService,
        tracking: TrackingService,
    ) -> None:
        self._session = session
        self._repo = EvaluationRunRepository(session)
        self._models_repo = ExternalModelRepository(session)
        self._inference = inference
        self._tracking = tracking

    async def start_evaluation(
        self,
        *,
        model_id: int,
        base_model_id: int,
        adapter_id: str | None = None,
        eval_dataset_name: str | None = None,
        prompts: list[str] | None = None,
        tokenizer_family: str = "char",
        base_tokenizer_family: str | None = None,
    ) -> EvaluationRun:
        """Create an ``EvaluationRun`` and dispatch the async worker.

        The run row is created and committed via the request-scoped session
        BEFORE the background task is scheduled, so the worker (which uses its
        own session) never races an uncommitted row.

        Parameters
        ----------
        model_id : int
            ``ExternalModel.id`` of the fine-tuned model.
        base_model_id : int
            ``ExternalModel.id`` of the base model.
        adapter_id : str | None, optional
            Adapter ID for adapter model evaluations.
        eval_dataset_name : str | None, optional
            Name of an MLflow eval-dataset.
        prompts : list[str] | None, optional
            Prompts to evaluate.
        tokenizer_family : str, optional
            Tokenizer family. Defaults to ``"char"``.
        base_tokenizer_family : str | None, optional
            Base tokenizer family. Defaults to ``None``.

        Returns
        -------
        EvaluationRun
            The created run (status ``PENDING``).

        Raises
        ------
        ValueError
            If the model is not found or is ``TRACK_ONLY``.
        """
        model = await self._models_repo.get(model_id)
        if model is None:
            raise ValueError(f"Model {model_id} not found")
        if model.runnable_status == RunnableStatus.TRACK_ONLY:
            raise ValueError(model.runnable_reason or "Model is track-only")

        evaluation_run = EvaluationRun(
            external_model_id=model_id,
            base_external_model_id=base_model_id,
            adapter_id=adapter_id,
            tokenizer_family=tokenizer_family,
            base_tokenizer_family=base_tokenizer_family,
            eval_dataset_name=eval_dataset_name,
            status=EvaluationRunStatus.PENDING,
            prompt_count=0,
        )
        evaluation_run = await self._repo.create(evaluation_run)
        await self._session.commit()

        run_id = evaluation_run.id
        _QUEUES[run_id] = asyncio.Queue()

        task = asyncio.create_task(
            _run_eval_worker(
                run_id=run_id,
                model_id=model_id,
                base_model_id=base_model_id,
                adapter_id=adapter_id,
                tokenizer_family=tokenizer_family,
                base_tokenizer_family=base_tokenizer_family,
                prompts=list(prompts or []),
            )
        )
        _TASKS[run_id] = task
        task.add_done_callback(lambda _t: _TASKS.pop(run_id, None))
        return evaluation_run

    async def get_event_stream(self, run_id: int) -> AsyncGenerator[str, None]:
        """Stream SSE events for an evaluation run.

        Parameters
        ----------
        run_id : int
            The evaluation run ID.

        Yields
        ------
        str
            SSE-formatted event strings.
        """
        queue = _QUEUES.get(run_id)
        if queue is None:
            yield 'event: error\ndata: {"message": "No active evaluation for this run_id"}\n\n'
            return

        yield 'event: status\ndata: {"status": "running"}\n\n'

        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=30)
            except TimeoutError:
                yield "event: keepalive\ndata: {}\n\n"
                continue
            if msg is None:
                break
            yield f"event: {msg['event']}\ndata: {msg['data']}\n\n"
            if msg["event"] in ("complete", "error"):
                break
        _QUEUES.pop(run_id, None)

    async def get_run(self, run_id: int) -> EvaluationRun | None:
        """Fetch a persisted evaluation run.

        Parameters
        ----------
        run_id : int
            The evaluation run ID.

        Returns
        -------
        EvaluationRun | None
            The run, or ``None`` if not found.
        """
        return await self._repo.get_by_id(run_id)

    async def get_metrics(self, run_id: int) -> list[MetricDelta]:
        """Fetch metric deltas for an evaluation run.

        Parameters
        ----------
        run_id : int
            The evaluation run ID.

        Returns
        -------
        list[MetricDelta]
            Metric delta rows.
        """
        return list(await self._repo.get_metrics(run_id))

    async def get_samples(self, run_id: int) -> list[EvalSample]:
        """Fetch per-prompt samples for an evaluation run.

        Parameters
        ----------
        run_id : int
            The evaluation run ID.

        Returns
        -------
        list[EvalSample]
            Per-prompt sample rows.
        """
        return list(await self._repo.get_samples(run_id))

    async def list_runs(
        self,
        *,
        model_id: int | None = None,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[EvaluationRun], int]:
        """List evaluation runs with optional filters.

        Parameters
        ----------
        model_id : int, optional
            Filter by fine-tuned model ID. Defaults to ``None``.
        status : str, optional
            Filter by status. Defaults to ``None``.
        limit : int, optional
            Max results. Defaults to 20.
        offset : int, optional
            Result offset. Defaults to 0.

        Returns
        -------
        tuple[list[EvaluationRun], int]
            (Runs, total count).
        """
        if model_id is not None:
            runs, total = await self._repo.list_by_model(
                model_id, limit=limit, offset=offset
            )
            return list(runs), total
        if status is not None:
            runs, total = await self._repo.list_by_status(
                status, limit=limit, offset=offset
            )
            return list(runs), total
        runs, total = await self._repo.list_by_model(0, limit=limit, offset=offset)
        return list(runs), total


def _perplexity(avg_loss: float) -> float:
    """Compute perplexity from average loss, guarding against overflow."""
    return math.exp(avg_loss) if avg_loss < 700 else float("inf")


async def _evaluate_all_prompts(
    *,
    run_id: int,
    queue: asyncio.Queue[dict[str, object] | None] | None,
    prompts: list[str],
    evaluator: Evaluator,
    base_loaded: LoadedModel,
    ft_loaded: LoadedModel,
    repo: EvaluationRunRepository,
    session: AsyncSession,
) -> tuple[list[float], list[float]]:
    """Evaluate every prompt against base and fine-tuned models.

    Persists each ``EvalSample`` and streams progress events over the SSE
    queue.  ``None``-safe on the queue — callers that have no queue simply
    skip the SSE pushes.

    Parameters
    ----------
    run_id : int
        Evaluation run ID (for sample association).
    queue : asyncio.Queue[dict[str, object] | None] | None
        SSE event queue, or ``None`` to skip streaming.
    prompts : list[str]
        Prompts to evaluate.
    evaluator : Evaluator
        Per-prompt loss evaluator.
    base_loaded : object
        Loaded base model reference.
    ft_loaded : object
        Loaded fine-tuned model reference.
    repo : EvaluationRunRepository
        Repository for persisting samples.
    session : AsyncSession
        DB session for per-sample commits.

    Returns
    -------
    tuple[list[float], list[float]]
        ``(base_losses, ft_losses)`` — one entry per prompt.
    """
    base_losses: list[float] = []
    ft_losses: list[float] = []

    for idx, prompt in enumerate(prompts):
        base_result = evaluator.evaluate_prompt(prompt, loaded_model=base_loaded)
        ft_result = evaluator.evaluate_prompt(prompt, loaded_model=ft_loaded)
        base_losses.append(base_result.avg_loss)
        ft_losses.append(ft_result.avg_loss)

        await repo.add_sample(
            EvalSample(
                evaluation_run_id=run_id,
                prompt_index=idx,
                input=prompt,
                base_output=base_result.generated_text,
                fine_tuned_output=ft_result.generated_text,
                base_loss=base_result.avg_loss,
                fine_tuned_loss=ft_result.avg_loss,
            )
        )
        await session.commit()

        if queue is not None:
            await queue.put(
                {
                    "event": "progress",
                    "data": json.dumps(
                        {
                            "prompt_index": idx,
                            "total": len(prompts),
                            "base_loss": base_result.avg_loss,
                            "fine_tuned_loss": ft_result.avg_loss,
                        }
                    ),
                }
            )

    return base_losses, ft_losses


def _compute_metric_deltas(
    *,
    run_id: int,
    base_losses: list[float],
    ft_losses: list[float],
    comparable: bool,
) -> list[MetricDelta]:
    """Compute ``eval_loss`` and ``perplexity`` deltas from per-prompt losses.

    Parameters
    ----------
    run_id : int
        Evaluation run ID for the metric rows.
    base_losses : list[float]
        Per-prompt base-model losses.
    ft_losses : list[float]
        Per-prompt fine-tuned model losses.
    comparable : bool
        Whether the losses are comparable (same tokenizer family).

    Returns
    -------
    list[MetricDelta]
        Two metric-delta rows (eval_loss, perplexity).
    """
    avg_base = sum(base_losses) / len(base_losses) if base_losses else 0.0
    avg_ft = sum(ft_losses) / len(ft_losses) if ft_losses else 0.0

    return [
        MetricDelta(
            evaluation_run_id=run_id,
            metric_name="eval_loss",
            fine_tuned_value=avg_ft,
            base_value=avg_base,
            delta=avg_ft - avg_base,
            comparable=comparable,
        ),
        MetricDelta(
            evaluation_run_id=run_id,
            metric_name="perplexity",
            fine_tuned_value=_perplexity(avg_ft),
            base_value=_perplexity(avg_base),
            delta=_perplexity(avg_ft) - _perplexity(avg_base),
            comparable=comparable,
        ),
    ]


async def _persist_eval_results(
    *,
    run_id: int,
    deltas: list[MetricDelta],
    total: int,
    mlflow_run_id: str,
    repo: EvaluationRunRepository,
    tracking: TrackingService,
    session: AsyncSession,
) -> None:
    """Persist metric deltas, update run metadata, and log to MLflow.

    Parameters
    ----------
    run_id : int
        Evaluation run ID.
    deltas : list[MetricDelta]
        Computed metric deltas.
    total : int
        Total prompt count.
    mlflow_run_id : str
        MLflow run ID for metric logging.
    repo : EvaluationRunRepository
        Repository for DB writes.
    tracking : TrackingService
        MLflow tracking service.
    session : AsyncSession
        DB session for commits.
    """
    for delta in deltas:
        await repo.add_metric_delta(delta)
        await tracking.log_eval_metric(mlflow_run_id, delta.metric_name, delta.delta)

    run = await repo.get_by_id(run_id)
    if run is not None:
        run.prompt_count = total
        run.mlflow_run_id = mlflow_run_id or None

    await repo.update_status(run_id, EvaluationRunStatus.COMPLETED)
    await session.commit()


async def _report_eval_complete(
    *,
    queue: asyncio.Queue[dict[str, object] | None],
    deltas: list[MetricDelta],
    run_id: int,
) -> None:
    """Send metric-delta and completion events over the SSE queue.

    Parameters
    ----------
    queue : asyncio.Queue[dict[str, object] | None]
        SSE event queue.
    deltas : list[MetricDelta]
        Metric deltas to emit.
    run_id : int
        Evaluation run ID.
    """
    for delta in deltas:
        await queue.put(
            {
                "event": "metric",
                "data": json.dumps(
                    {
                        "metric_name": delta.metric_name,
                        "fine_tuned_value": delta.fine_tuned_value,
                        "base_value": delta.base_value,
                        "delta": delta.delta,
                        "comparable": delta.comparable,
                    }
                ),
            }
        )
    await queue.put(
        {
            "event": "complete",
            "data": json.dumps(
                {"run_id": run_id, "status": EvaluationRunStatus.COMPLETED}
            ),
        }
    )


async def _run_eval_worker(
    *,
    run_id: int,
    model_id: int,
    base_model_id: int,
    adapter_id: str | None,
    tokenizer_family: str,
    base_tokenizer_family: str | None,
    prompts: list[str],
) -> None:
    """Background worker: evaluate prompts, persist, and stream SSE events.

    Opens its OWN ``AsyncSessionLocal`` session (independent of any request
    session) and commits explicitly. Receives only primitives — never a
    detached ORM object. Delegates to focused helpers for the per-prompt
    evaluation loop, metric computation, persistence, and SSE reporting.

    Parameters
    ----------
    run_id : int
        The evaluation run ID (already committed).
    model_id : int
        Fine-tuned model ``ExternalModel.id``.
    base_model_id : int
        Base model ``ExternalModel.id``.
    adapter_id : str | None
        Adapter ID for adapter models.
    tokenizer_family : str
        Fine-tuned tokenizer family.
    base_tokenizer_family : str | None
        Base tokenizer family (for cross-tokenizer comparability).
    prompts : list[str]
        Prompts to evaluate.
    """
    queue = _QUEUES.get(run_id)
    inference = InferenceService()
    tracking = TrackingService()
    evaluator = Evaluator(inference)
    total = len(prompts)
    comparable = (
        tokenizer_family == base_tokenizer_family if base_tokenizer_family else True
    )
    mlflow_run_id = ""

    async with AsyncSessionLocal() as session:
        repo = EvaluationRunRepository(session)
        try:
            await repo.update_status(run_id, EvaluationRunStatus.RUNNING)
            await session.commit()

            mlflow_run_id = await tracking.start_eval_run(
                model_id=model_id,
                base_model_id=base_model_id,
                adapter_id=adapter_id,
                tokenizer_family=tokenizer_family,
            )

            base_loaded = await inference.load_model(model_id=base_model_id)
            ft_loaded = await inference.load_model(
                model_id=model_id, adapter_id=adapter_id
            )

            base_losses, ft_losses = await _evaluate_all_prompts(
                run_id=run_id,
                queue=queue,
                prompts=prompts,
                evaluator=evaluator,
                base_loaded=base_loaded,
                ft_loaded=ft_loaded,
                repo=repo,
                session=session,
            )

            deltas = _compute_metric_deltas(
                run_id=run_id,
                base_losses=base_losses,
                ft_losses=ft_losses,
                comparable=comparable,
            )

            await _persist_eval_results(
                run_id=run_id,
                deltas=deltas,
                total=total,
                mlflow_run_id=mlflow_run_id,
                repo=repo,
                tracking=tracking,
                session=session,
            )
            await tracking.finish_eval_run(mlflow_run_id)

            if queue is not None:
                await _report_eval_complete(queue=queue, deltas=deltas, run_id=run_id)

        except Exception as exc:  # pylint: disable=broad-exception-caught
            await repo.update_status(run_id, EvaluationRunStatus.FAILED, str(exc))
            await session.commit()
            if mlflow_run_id:
                await tracking.fail_eval_run(mlflow_run_id, reason=str(exc))
            if queue is not None:
                await queue.put(
                    {
                        "event": "error",
                        "data": json.dumps({"message": str(exc)}),
                    }
                )
        finally:
            if queue is not None:
                queue.put_nowait(None)
