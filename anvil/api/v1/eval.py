"""Eval endpoints for v1 API.

Includes perplexity computation (existing) and fine-tuned model evaluation
(spec 054) — side-by-side comparison of a fine-tuned model against its
base with SSE streaming.
"""

import math
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from starlette.responses import StreamingResponse

from ...core.engine import softmax
from ...services.inference.inference import InferenceService
from ...workbench import AnvilWorkbench
from ..deps import get_workbench
from .schemas_eval import (
    EvalFineTunedBody,
    EvalPerplexityBody,
    EvalSampleResponse,
    EvaluationRunListResponse,
    EvaluationRunResponse,
    MetricDeltaResponse,
)

router = APIRouter()


# ------------------------------------------------------------------
# Perplexity (existing)
# ------------------------------------------------------------------


@router.post("/eval/perplexity")
async def eval_perplexity(body: EvalPerplexityBody) -> dict[str, Any]:
    """Compute perplexity of a model on a given text string.

    Loads the specified model version, tokenizes the input text, and computes
    the average cross-entropy loss over the first ``block_size`` tokens.
    Perplexity is ``exp(avg_loss)``.

    Parameters
    ----------
    body : EvalPerplexityBody
        Request body with ``model_id``, ``version``, and ``text``.

    Returns
    -------
    dict
        Perplexity, average loss, number of positions evaluated, vocabulary
        size, and model configuration.

    Raises
    ------
    HTTPException
        If ``model_id`` or ``version`` is missing (400), ``text`` is empty
        (400), the model is not found (404), or a character is not in the
        vocabulary (400).
    """
    model_id = body.model_id
    version = body.version
    text = body.text

    inf_svc = InferenceService()
    try:
        loaded = await inf_svc.load_model(model_id, version)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    model = loaded.model
    chars = loaded.chars

    BOS = len(chars)
    try:
        tokens = [BOS] + [chars.index(ch) for ch in text]
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Character '{e.args[0]}' not in model vocabulary",
        ) from e

    n = min(model.block_size, len(tokens) - 1)
    keys: list[list[list[Any]]] = [[] for _ in range(model.n_layer)]
    values: list[list[list[Any]]] = [[] for _ in range(model.n_layer)]
    losses = []
    for pos_id in range(n):
        token_id, target_id = tokens[pos_id], tokens[pos_id + 1]
        logits = model.forward(token_id, pos_id, keys, values)
        probs = softmax(logits)
        loss_t = -probs[target_id].log()
        losses.append(loss_t.data)

    avg_loss = sum(losses) / len(losses)
    perplexity = math.exp(avg_loss)

    return {
        "perplexity": perplexity,
        "avg_loss": avg_loss,
        "num_positions": n,
        "vocab_size": model.vocab_size,
        "model_config": {
            "n_layer": model.n_layer,
            "n_embd": model.n_embd,
            "n_head": model.n_head,
            "block_size": model.block_size,
        },
    }


# ------------------------------------------------------------------
# Fine-tuned model evaluation (spec 054)
# ------------------------------------------------------------------


@router.post("/eval/fine-tuned", status_code=201)
async def start_fine_tuned_eval(
    body: EvalFineTunedBody,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, object]:
    """Trigger an async fine-tuned model evaluation.

    Creates an ``EvaluationRun``, validates the model is not ``track-only``,
    and starts evaluation as an async background task.  Returns a ``run_id``
    and the SSE stream URL.

    Parameters
    ----------
    body : EvalFineTunedBody
        Request body with model identifiers.
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        JSON response with ``run_id``, ``status``, and ``sse_url``.

    Raises
    ------
    HTTPException
        If the model is not found or is ``track-only`` (400), or an
        eval-dataset name is not provided (400).
    """
    if not body.eval_dataset_name:
        raise HTTPException(
            status_code=400,
            detail="An eval-dataset name is required. Held-out split auto-derivation is not yet"
            " supported. Create an eval-dataset first via POST /v1/eval-datasets.",
        )
    try:
        run = await workbench.evaluate_fine_tuned(
            model_id=body.model_id,
            base_model_id=body.base_model_id,
            adapter_id=body.adapter_id,
            eval_dataset_name=body.eval_dataset_name,
            prompts=[],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {
        "run_id": run.id,
        "status": run.status,
        "sse_url": f"/v1/sse/eval/{run.id}",
    }


@router.get("/sse/eval/{run_id}")
async def stream_eval(
    run_id: int,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> StreamingResponse:
    """SSE stream for evaluation progress.

    Parameters
    ----------
    run_id : int
        The evaluation run ID.
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    StreamingResponse
        SSE stream with ``text/event-stream`` content type.
    """
    return StreamingResponse(
        workbench.evaluation.get_event_stream(run_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/eval/fine-tuned/{run_id}")
async def get_evaluation_run(
    run_id: int,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> EvaluationRunResponse:
    """Fetch persisted evaluation run details.

    Parameters
    ----------
    run_id : int
        The evaluation run ID.
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    EvaluationRunResponse
        The run with metrics and metadata.

    Raises
    ------
    HTTPException
        If the run is not found (404).
    """
    run = await workbench.get_evaluation_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"EvaluationRun {run_id} not found")

    metrics = await workbench.evaluation.get_metrics(run_id)
    model = await workbench.external_model_repo.get(run.external_model_id)
    base_model = (
        await workbench.external_model_repo.get(run.base_external_model_id)
        if run.base_external_model_id
        else None
    )

    return EvaluationRunResponse(
        run_id=run.id,
        model_id=run.external_model_id,
        model_name=model.display_name if model else f"model-{run.external_model_id}",
        base_model_id=run.base_external_model_id or run.external_model_id,
        base_model_name=base_model.display_name if base_model else "base",
        adapter_id=run.adapter_id,
        tokenizer_family=run.tokenizer_family,
        base_tokenizer_family=run.base_tokenizer_family,
        status=run.status,
        prompt_count=run.prompt_count,
        metrics=[
            MetricDeltaResponse(
                metric_name=m.metric_name,
                fine_tuned_value=m.fine_tuned_value,
                base_value=m.base_value,
                delta=m.delta,
                comparable=m.comparable,
            )
            for m in metrics
        ],
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        mlflow_run_id=run.mlflow_run_id,
    )


@router.get("/eval/fine-tuned/{run_id}/samples")
async def get_evaluation_samples(
    run_id: int,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> list[EvalSampleResponse]:
    """Fetch per-prompt sample outputs for an evaluation run.

    Parameters
    ----------
    run_id : int
        The evaluation run ID.
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    list[EvalSampleResponse]
        Per-prompt side-by-side outputs.

    Raises
    ------
    HTTPException
        If the run is not found (404).
    """
    run = await workbench.get_evaluation_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"EvaluationRun {run_id} not found")

    samples = await workbench.get_evaluation_samples(run_id)
    return [
        EvalSampleResponse(
            prompt_index=s.prompt_index,
            input=s.input,
            base_output=s.base_output,
            fine_tuned_output=s.fine_tuned_output,
            base_loss=s.base_loss,
            fine_tuned_loss=s.fine_tuned_loss,
        )
        for s in samples
    ]


@router.get("/eval/fine-tuned")
async def list_evaluation_runs(
    model_id: int | None = None,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> EvaluationRunListResponse:
    """List evaluation runs with optional filters.

    Parameters
    ----------
    model_id : int, optional
        Filter by fine-tuned model ID.
    status : str, optional
        Filter by run status.
    limit : int, optional
        Max results per page. Defaults to 20.
    offset : int, optional
        Result offset. Defaults to 0.
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    EvaluationRunListResponse
        Paginated list of evaluation runs.
    """
    runs, total = await workbench.list_evaluation_runs(
        model_id=model_id, status=status, limit=limit, offset=offset
    )

    responses = []
    for run in runs:
        responses.append(
            EvaluationRunResponse(
                run_id=run.id,
                model_id=run.external_model_id,
                model_name=f"model-{run.external_model_id}",
                base_model_id=run.base_external_model_id or run.external_model_id,
                base_model_name="base",
                adapter_id=run.adapter_id,
                tokenizer_family=run.tokenizer_family,
                base_tokenizer_family=run.base_tokenizer_family,
                status=run.status,
                prompt_count=run.prompt_count,
                created_at=run.created_at,
                started_at=run.started_at,
                finished_at=run.finished_at,
                mlflow_run_id=run.mlflow_run_id,
            )
        )

    return EvaluationRunListResponse(
        runs=responses,
        total=total,
        limit=limit,
        offset=offset,
    )
