# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Training control endpoints for v1 API.

Provides routes for starting, stopping, and streaming training runs, as well
as managing training configs and the forward pass computation graph. Training
runs execute asynchronously in the background with real-time SSE streaming.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from starlette.responses import StreamingResponse

from ...db.models.training_config import TrainingConfig
from ...db.session import AsyncSessionLocal
from ...services.compute.compute_backend_unavailable import ComputeBackendUnavailable
from ...services.inference.inference import InferenceService
from ...services.tracking.tracking import TrackingService
from ...services.training.training import TrainingService
from ...services.training.training_run_config import TrainingRunConfig
from ...services.training.training_run_service import TrainingRunService

logger = logging.getLogger(__name__)


class TrainConfig(BaseModel):
    """Pydantic model for training configuration.

    Validates hyperparameters at the API boundary. Business-logic
    constraints (n_head <= n_embd, divisibility, even head_dim) are
    enforced separately in the endpoint handler.

    Attributes
    ----------
    n_embd : int
        Embedding dimension. Default ``16``. Range ``[4, 4096]``.
    n_layer : int
        Number of transformer layers. Default ``1``. Range ``[1, 128]``.
    n_head : int
        Number of attention heads. Default ``4``. Range ``[1, 64]``.
    block_size : int
        Context window size. Default ``16``. Range ``[8, 4096]``.
    num_steps : int
        Training iterations. Default ``1000``. Range ``[1, 1000000]``.
    learning_rate : float
        Adam learning rate. Default ``0.01``. Range ``(0, 1.0]``.
    beta1 : float
        Adam beta1. Default ``0.85``.
    beta2 : float
        Adam beta2. Default ``0.99``.
    temperature : float
        Sampling temperature. Default ``0.5``. Range ``[0, 2.0]``.
    compute_backend : str | None
        Compute backend identifier. Default ``"auto"``.
    dataset_id : int | None
        Optional dataset ID for training data.
    corpus_id : int | None
        Optional corpus ID for training data.
    content_version_id : int | None
        Optional content version ID for reproducibility.
    device : str | None
        Optional device override (e.g. ``"cpu"``, ``"cuda:0"``, ``"mps"``).
    base_model_ref : int | None
        Optional experiment ID of a previously trained model to use as
        a warm-start checkpoint. When set, architecture dimensions
        (``n_embd``, ``n_head``, ``n_layer``, ``block_size``) are
        inherited from the base model and explicit overrides are
        rejected with HTTP 422.
    method : str
        Training method. ``"full"`` (default, from-scratch pretraining),
        ``"lora"``, or ``"qlora"``. When ``"full"``, existing behavior is
        unchanged and ``lora_*`` fields must be absent.
    lora_rank : int | None
        LoRA rank ``r``. Required when ``method`` is ``"lora"`` or ``"qlora"``.
    lora_alpha : float | None
        LoRA scaling alpha. Required when method is LoRA/QLoRA.
    lora_target_modules : list[str] | None
        Target module names (e.g. ``["q_proj", "v_proj"]``). Defaults to
        per-architecture values from the curated catalog if omitted.
    lora_dropout : float | None
        LoRA dropout rate. Range ``[0, 1]``.
    lora_bias : str | None
        LoRA bias setting: ``"none"``, ``"all"``, or ``"lora_only"``.
    """

    model_config = ConfigDict(extra="forbid")

    n_embd: int = Field(default=16, ge=4, le=4096)
    n_layer: int = Field(default=1, ge=1, le=128)
    n_head: int = Field(default=4, ge=1, le=64)
    block_size: int = Field(default=16, ge=8, le=4096)
    num_steps: int = Field(default=1000, ge=1, le=1_000_000)
    learning_rate: float = Field(default=0.01, gt=0, le=1.0)
    beta1: float = Field(default=0.85)
    beta2: float = Field(default=0.99)
    temperature: float = Field(default=0.5, ge=0, le=2.0)
    compute_backend: str | None = Field(default="auto")
    dataset_id: int | None = None
    corpus_id: int | None = None
    content_version_id: int | None = None
    device: str | None = None
    base_model_ref: int | None = None

    method: str = Field(default="full")
    lora_rank: int | None = Field(default=None, ge=1, le=1024)
    lora_alpha: float | None = Field(default=None, gt=0)
    lora_target_modules: list[str] | None = None
    lora_dropout: float | None = Field(default=None, ge=0, le=1)
    lora_bias: str | None = None


router = APIRouter()
svc = TrainingService()
tracking_svc = TrackingService()
_tasks: dict[int, asyncio.Task[Any]] = {}
"""dict[int, asyncio.Task]: In-memory registry of active training tasks keyed by
run ID."""
MODELS_DIR = Path("data/models")
"""Path: Default directory where trained model artifacts are saved."""
MODELS_DIR.mkdir(parents=True, exist_ok=True)

_models_dir_override: Path | None = None
"""Path | None: Optional runtime override for MODELS_DIR, set via
:func:`set_models_dir` when a :class:`~anvil.workspace.workspace_paths.WorkspacePaths`
instance is available at call time."""


def set_models_dir(path: Path | None) -> None:
    """Override the effective models directory at runtime.

    Intended to be called with ``workspace_paths.models_dir`` during
    application initialisation when a ``WorkspacePaths`` instance is
    available.  Resets to the module-level default when ``None``.

    Parameters
    ----------
    path : Path | None
        The models directory to use, or ``None`` to fall back to
        ``MODELS_DIR``.
    """
    global _models_dir_override  # pylint: disable=global-statement
    _models_dir_override = path


def _get_models_dir() -> Path:
    """Return the effective models directory.

    Returns the runtime override if set, otherwise the module-level
    ``MODELS_DIR`` default.  Used at call time (e.g. inside route
    handlers that cannot import ``WorkspacePaths`` directly because
    the module is loaded at import time).

    Returns
    -------
    Path
        The models directory to use.
    """
    return _models_dir_override if _models_dir_override is not None else MODELS_DIR


@router.post(
    "/training/start",
    responses={
        422: {
            "description": (
                "Validation failure: n_head > n_embd, n_embd not divisible by "
                "n_head, odd head_dim, compute backend unavailable, OOM "
                "estimate, or architecture conflict during warm-start."
            ),
        },
    },
)
async def start_training(config: TrainConfig) -> dict[str, Any]:
    """Start a new training run asynchronously.

    Delegates to ``TrainingRunService`` for the full lifecycle.
    The route handles request parsing (``TrainConfig`` → service
    config) and converts service-layer exceptions to HTTP responses.

    Parameters
    ----------
    config : TrainConfig
        Pydantic-validated training configuration.

    Returns
    -------
    dict
        ``run_id``, ``mlflow_run_id``, ``experiment_id``, ``status``,
        and ``tracking`` status.

    Raises
    ------
    HTTPException
        With status 422 for any validation failure.
    """
    run_svc = TrainingRunService(
        svc=svc,
        tracking=tracking_svc,
        models_dir=_get_models_dir(),
        tasks=_tasks,
    )
    svc_config = TrainingRunConfig(**config.model_dump())
    try:
        return await run_svc.start_training_run(svc_config)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except ComputeBackendUnavailable as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.get("/training/{run_id}/status")
async def training_run_status(run_id: int) -> dict[str, Any]:
    """Check whether a training run is still active on the server.

    Parameters
    ----------
    run_id : int
        The training run ID.

    Returns
    -------
    dict
        ``run_id`` and ``status`` (``"active"`` if found).

    Raises
    ------
    HTTPException
        If the run is not found or already completed (404).
    """
    queue = svc.get_queue(run_id)
    if queue is None:
        raise HTTPException(
            status_code=404, detail="Run not found or already completed"
        )
    return {"run_id": run_id, "status": "active"}


@router.get("/training/stream/{run_id}")
async def stream_training(run_id: int) -> StreamingResponse:
    """SSE event stream for a training run.

    Returns a ``StreamingResponse`` that emits Server-Sent Events as the
    training progresses. Events include ``metrics``, ``complete``, ``error``,
    ``export_error``, and periodic ``heartbeat`` keep-alive messages.

    Parameters
    ----------
    run_id : int
        The training run ID.

    Returns
    -------
    StreamingResponse
        SSE stream with ``text/event-stream`` content type.
    """
    queue = svc.get_queue(run_id)
    if queue is None:

        async def _run_gone() -> AsyncGenerator[str, None]:
            yield (
                "event: error\ndata: "
                + json.dumps(
                    {
                        "message": "Training run has already completed or was never started"
                    }
                )
                + "\n\n"
            )

        return StreamingResponse(
            _run_gone(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    async def event_stream() -> AsyncGenerator[str, None]:
        """Generator that yields SSE-formatted events from the training queue.

        Queue cleanup is handled by the ``_orphan_queue_release`` timeout
        (120s) in ``TrainingRunService._cleanup``.  We must NOT release the
        queue here — doing so races with ``_tasks.pop(run_id)`` in the
        ``_cleanup`` callback: when a page refresh happens moments after
        training completes, ``_tasks[run_id]`` is already gone, so a
        ``release_queue`` here fires *immediately* instead of waiting the
        full 120-second reconnect window.
        """
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=30)
                yield f"event: {msg['event']}\ndata: {msg['data']}\n\n"
                if msg["event"] in ("complete", "error", "divergence"):
                    break
            except TimeoutError:
                yield "event: heartbeat\ndata: {}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/training/configs")
async def list_configs() -> dict[str, Any]:
    """List all saved training configurations.

    Returns
    -------
    dict
        List of config dicts with ``id``, ``name``, hyperparameter values,
        and ``created_at``, ordered by most recent first.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(TrainingConfig).order_by(TrainingConfig.created_at.desc())
        )
        configs = result.scalars().all()
        return {
            "configs": [
                {
                    "id": c.id,
                    "name": c.name,
                    "n_layer": c.n_layer,
                    "n_embd": c.n_embd,
                    "n_head": c.n_head,
                    "block_size": c.block_size,
                    "num_steps": c.num_steps,
                    "learning_rate": c.learning_rate,
                    "temperature": c.temperature,
                    "created_at": str(c.created_at),
                }
                for c in configs
            ]
        }


@router.post("/training/{run_id}/stop")
async def stop_training(run_id: int) -> dict[str, Any]:
    """Stop an active training run.

    Signals the run to stop and pushes an error event to the SSE queue
    so the client receives a notification.

    Parameters
    ----------
    run_id : int
        The training run ID to stop.

    Returns
    -------
    dict
        ``status`` set to ``"stopped"``.
    """
    svc.stop_run(run_id)
    queue = svc.get_queue(run_id)
    if queue is not None:
        await queue.put(
            {
                "event": "error",
                "data": json.dumps({"message": "Training stopped by user"}),
            }
        )
    return {"status": "stopped"}


@router.get("/forward-pass/graph")
async def forward_pass_graph() -> dict[str, Any]:
    """Get the forward pass computation graph for the demo model.

    Loads the demo model and returns its computation graph structure
    for visualization in the learning widgets.

    Returns
    -------
    dict
        Forward pass graph with node and edge descriptions.

    Raises
    ------
    HTTPException
        If the demo model is not found (404).
    """
    inf_svc = InferenceService()
    try:
        loaded = await inf_svc.load_model()
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return inf_svc.forward_graph(loaded)
