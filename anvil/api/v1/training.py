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
import os
import tempfile
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from starlette.responses import StreamingResponse

from ...db.models.training_config import TrainingConfig
from ...db.repositories.content_versions import ContentVersionRepository
from ...db.repositories.corpora import CorpusRepository
from ...db.repositories.datasets import DatasetRepository
from ...db.session import AsyncSessionLocal
from ...gpu import GpuInfo, detect_gpu
from ...services.compute.compute_backend_unavailable import ComputeBackendUnavailable
from ...services.compute.resolve import resolve_backend
from ...services.compute.result import ComputeResult
from ...services.compute.training_engine import TrainingEngine
from ...services.content.lineage_service import LineageService
from ...services.inference.inference import InferenceService
from ...services.tracking.mps_metrics_collector import MPSMetricsCollector
from ...services.tracking.mps_sampler_thread import MPSSamplerThread
from ...services.tracking.tracking import TrackingService
from ...services.training.export import SafetensorsExportService
from ...services.training.memory_estimator import (
    MemoryEstimate,
    estimate_training_memory,
)
from ...services.training.training import TrainingService

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


def _validate_hparams(
    n_embd: int,
    n_head: int,
    _block_size: int,
) -> None:
    """Validate hyperparameter constraints for training.

    Checks that ``n_head <= n_embd``, ``n_embd`` is divisible by
    ``n_head``, and ``head_dim`` is even (required by RoPE).

    Parameters
    ----------
    n_embd : int
        Embedding dimension.
    n_head : int
        Number of attention heads.
    block_size : int
        Context window size (validated by Pydantic at the boundary).

    Raises
    ------
    HTTPException
        With status 422 if any constraint is violated.
    """
    if n_head > n_embd:
        raise HTTPException(
            status_code=422,
            detail=(
                f"n_head ({n_head}) exceeds n_embd ({n_embd}) — head_dim would"
                f" be 0. n_head must be <= n_embd."
            ),
        )
    if n_embd % n_head != 0:
        raise HTTPException(
            status_code=422,
            detail=(
                f"n_embd ({n_embd}) is not divisible by n_head ({n_head}). "
                f"The embedding dimension must be evenly divisible by the number"
                f" of attention heads. "
                f"Try n_head="
                f"{max(h for h in range(1, min(n_head, 64) + 1) if n_embd % h == 0)}."
            ),
        )
    head_dim = n_embd // n_head
    if head_dim % 2 != 0:
        raise HTTPException(
            status_code=422,
            detail=(
                f"head_dim={head_dim} is odd — RoPE (Rotary Position Embedding)"
                f" requires an even head dimension. "
                f"Try adjusting n_embd or n_head so that n_embd / n_head is even."
            ),
        )


def _resolve_training_backend(
    compute_backend: str | None,
) -> tuple[TrainingEngine, str]:
    """Resolve compute backend and device for training.

    Parameters
    ----------
    compute_backend : str | None
        Compute backend identifier (e.g. ``"auto"``, ``"local-torch"``).

    Returns
    -------
    tuple[TrainingEngine, str]
        ``(engine_backend, device)`` tuple.

    Raises
    ------
    HTTPException
        With status 422 if the requested backend is unavailable.
    """
    try:
        resolved = resolve_backend({"compute_backend": compute_backend})
    except ComputeBackendUnavailable as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return resolved["engine"], resolved["device"]


def _estimate_memory(
    engine_backend: TrainingEngine,
    config: TrainConfig,
    gpu_info: GpuInfo,
) -> MemoryEstimate | None:
    """Estimate GPU memory for torch backend and raise if OOM.

    Parameters
    ----------
    engine_backend : TrainingEngine
        The resolved training engine backend.
    config : TrainConfig
        Training configuration with hyperparameters.
    gpu_info : GpuInfo
        GPU information from ``detect_gpu()``.

    Returns
    -------
    MemoryEstimate | None
        Memory estimate if ``engine_backend`` is ``TORCH``, else ``None``.

    Raises
    ------
    HTTPException
        With status 422 if the model config would OOM the GPU.
    """
    if engine_backend != TrainingEngine.TORCH:
        return None
    memory_est = estimate_training_memory(
        vocab_size=200,
        n_embd=config.n_embd,
        n_head=config.n_head,
        n_layer=config.n_layer,
        block_size=config.block_size,
        gpu_info=gpu_info,
    )
    if memory_est.would_oom:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Model config would likely OOM your GPU. "
                f"Estimated peak memory: {memory_est.peak_gb:.1f} GB, "
                f"available: {memory_est.available_gb:.1f} GB "
                f"({memory_est.device_backend}, {memory_est.device_name}). "
                f"Try reducing n_embd, n_layer, n_head, or block_size. "
                f"Breakdown: {memory_est.param_count:,} params, "
                f"{memory_est.weights_bytes / (1024**2):.0f} MB weights, "
                f"{memory_est.gradients_bytes / (1024**2):.0f} MB gradients, "
                f"{memory_est.optimizer_bytes / (1024**2):.0f} MB optimizer, "
                f"{memory_est.kv_cache_bytes / (1024**2):.0f} MB KV cache."
            ),
        )
    return memory_est


async def _setup_mlflow_run(
    config: TrainConfig,
    _run_id: int,
    engine_backend: TrainingEngine,
    device: str,
    tracking_svc: TrackingService,  # pylint: disable=redefined-outer-name
    gpu_info: GpuInfo,
) -> tuple[str | None, int]:
    """Build hyperparams dict, start MLflow run, and allocate experiment ID.

    Parameters
    ----------
    config : TrainConfig
        Training configuration.
    run_id : int
        Reserved training run ID.
    engine_backend : TrainingEngine
        Resolved compute engine backend.
    device : str
        Resolved device string.
    tracking_svc : TrackingService
        MLflow tracking service instance.
    gpu_info : GpuInfo
        GPU information for enrichment tags.

    Returns
    -------
    tuple[str | None, int]
        ``(mlflow_run_id, experiment_id)`` tuple.
    """
    hyperparams: dict[str, str | int | float | None] = {
        "n_layer": config.n_layer,
        "n_embd": config.n_embd,
        "n_head": config.n_head,
        "block_size": config.block_size,
        "num_steps": config.num_steps,
        "learning_rate": config.learning_rate,
        "beta1": config.beta1,
        "beta2": config.beta2,
        "temperature": config.temperature,
        "compute_backend": config.compute_backend,
        "corpus_id": config.corpus_id,
        "dataset_id": config.dataset_id,
        "content_version_id": config.content_version_id,
    }

    hyperparams["gpu_available"] = str(gpu_info.available)
    hyperparams["gpu_backend"] = str(gpu_info.backend or "cpu")
    if gpu_info.device_name:
        hyperparams["gpu_device_name"] = gpu_info.device_name
    if gpu_info.torch_version:
        hyperparams["torch_version"] = gpu_info.torch_version

    mlflow_run_id = await tracking_svc.start_run(
        run_name=None,
        params=hyperparams,
        engine_backend=engine_backend,
        device=device,
    )

    experiment_id = await svc.allocate_experiment_id()

    if mlflow_run_id:
        await tracking_svc.set_tag(
            mlflow_run_id,
            "anvil.experiment_id",
            str(experiment_id),
        )
        await tracking_svc.set_tag(mlflow_run_id, "anvil.status", "running")

    return mlflow_run_id, experiment_id


async def _log_dataset_metadata(
    mlflow_run_id: str | None,
    dataset_id: int | None,
    corpus_id: int | None,
    content_version_id: int | None,
    tracking_svc: TrackingService,  # pylint: disable=redefined-outer-name
) -> None:
    """Log dataset, corpus, and content-version metadata as MLflow tags.

    Parameters
    ----------
    mlflow_run_id : str | None
        MLflow run ID (may be ``None`` if MLflow is degraded).
    dataset_id : int | None
        Optional dataset ID.
    corpus_id : int | None
        Optional corpus ID.
    content_version_id : int | None
        Optional content version ID for reproducibility.
    tracking_svc : TrackingService
        MLflow tracking service instance.
    """
    input_digest: str | None = None
    input_role: str | None = None
    if mlflow_run_id and dataset_id:
        async with AsyncSessionLocal() as sess:
            try:
                input_digest = await tracking_svc.log_dataset_input(
                    mlflow_run_id,
                    dataset_id=dataset_id,
                    role="training",
                    session=sess,
                )
                input_role = "training"
            except Exception:  # pylint: disable=broad-exception-caught
                pass
    elif mlflow_run_id and corpus_id:
        async with AsyncSessionLocal() as sess:
            try:
                input_digest = await tracking_svc.log_corpus_input(
                    mlflow_run_id,
                    corpus_id=corpus_id,
                    session=sess,
                )
                input_role = "corpus"
            except Exception:  # pylint: disable=broad-exception-caught
                pass

    if mlflow_run_id and input_digest:
        await tracking_svc.set_tag(
            mlflow_run_id,
            "anvil.input_digest",
            input_digest,
        )
        await tracking_svc.set_tag(
            mlflow_run_id,
            "anvil.input_role",
            input_role or "training",
        )

    if mlflow_run_id and dataset_id:
        async with AsyncSessionLocal() as sess:
            try:
                ds_repo = DatasetRepository(sess)
                ds = await ds_repo.get(dataset_id)
                if ds:
                    await tracking_svc.set_tag(
                        mlflow_run_id,
                        "anvil.dataset.name",
                        ds.name,
                    )
                    await tracking_svc.set_tag(
                        mlflow_run_id,
                        "anvil.dataset.vocab_size",
                        str(ds.vocabulary_size or ""),
                    )
                    await tracking_svc.set_tag(
                        mlflow_run_id,
                        "anvil.dataset.sample_count",
                        str(ds.sample_count or 0),
                    )
                    await tracking_svc.set_tag(
                        mlflow_run_id,
                        "anvil.dataset.document_count",
                        str(ds.document_count or 0),
                    )
                    await tracking_svc.set_tag(
                        mlflow_run_id,
                        "anvil.dataset.curation_version",
                        str(ds.curation_version or 0),
                    )
            except Exception:  # pylint: disable=broad-exception-caught
                pass
    elif mlflow_run_id and corpus_id:
        async with AsyncSessionLocal() as sess:
            try:

                corp_repo = CorpusRepository(sess)
                corpus = await corp_repo.get(corpus_id)
                if corpus:
                    await tracking_svc.set_tag(
                        mlflow_run_id,
                        "anvil.dataset.name",
                        corpus.name,
                    )
                    await tracking_svc.set_tag(
                        mlflow_run_id,
                        "anvil.corpus.file_count",
                        str(corpus.file_count or 0),
                    )
                    await tracking_svc.set_tag(
                        mlflow_run_id,
                        "anvil.corpus.document_count",
                        str(corpus.document_count or 0),
                    )
                    if corpus.language_map:
                        await tracking_svc.set_tag(
                            mlflow_run_id,
                            "anvil.corpus.language_map",
                            corpus.language_map,
                        )
            except Exception:  # pylint: disable=broad-exception-caught
                pass

    if mlflow_run_id and content_version_id is not None:
        async with AsyncSessionLocal() as sess:
            try:

                ver_repo = ContentVersionRepository(sess)
                lineage = LineageService(ver_repo)
                version = await ver_repo.get(int(content_version_id))
                if version:
                    await tracking_svc.set_tag(
                        mlflow_run_id,
                        "anvil.content_version_id",
                        str(content_version_id),
                    )
                    await tracking_svc.set_tag(
                        mlflow_run_id,
                        "anvil.content_manifest_digest",
                        version.manifest_digest,
                    )

                    client = tracking_svc._client  # pylint: disable=protected-access
                    if client:

                        def _log_manifest() -> None:
                            with tempfile.NamedTemporaryFile(
                                mode="w",
                                suffix=".json",
                                delete=False,
                            ) as f:
                                json.dump(
                                    {
                                        "version_id": version.id,
                                        "version_number": version.version_number,
                                        "manifest_digest": version.manifest_digest,
                                        "label": version.label,
                                        "entry_count": version.entry_count,
                                        "total_bytes": version.total_bytes,
                                    },
                                    f,
                                )
                                fpath = f.name
                            client.log_artifact(mlflow_run_id, fpath)
                            os.unlink(fpath)

                        await asyncio.get_event_loop().run_in_executor(
                            None,
                            _log_manifest,
                        )

                    await lineage.record_run_ref(
                        version_id=version.id,
                        mlflow_run_id=mlflow_run_id,
                        corpus_ref=f"corpus:{version.corpus_id}",
                    )
                    await sess.commit()
            except Exception:  # pylint: disable=broad-exception-caught
                pass


@router.post("/training/start")
async def start_training(config: TrainConfig) -> dict[str, Any]:
    """Start a new training run asynchronously.

    Validates hyperparameters (``n_embd``, ``n_head``, ``block_size``),
    resolves the compute backend, estimates GPU memory for torch backend,
    creates an MLflow run, and launches the training as an ``asyncio.Task``.

    Parameters
    ----------
    config : TrainConfig
        Pydantic-validated training configuration with all hyperparameter
        fields. See ``TrainConfig`` for field details and defaults.

    Returns
    -------
    dict
        ``run_id``, ``mlflow_run_id``, ``experiment_id``, ``status``, and
        ``tracking`` status.

    Raises
    ------
    HTTPException
        If ``n_head > n_embd`` (422), ``n_embd`` not divisible by ``n_head``
        (422), ``head_dim`` is odd (422), compute backend unavailable (422),
        or model would OOM GPU (422).
    """
    _validate_hparams(config.n_embd, config.n_head, config.block_size)

    engine_backend, device = _resolve_training_backend(config.compute_backend)

    gpu_info = detect_gpu()
    memory_est = _estimate_memory(engine_backend, config, gpu_info)

    run_id = svc.reserve_run()
    if memory_est is not None and memory_est.warnings:
        logger.warning(
            "Memory estimate for run %d: %s",
            run_id,
            "; ".join(memory_est.warnings),
        )

    mlflow_run_id, experiment_id = await _setup_mlflow_run(
        config,
        run_id,
        engine_backend,
        device,
        tracking_svc,
        gpu_info,
    )

    await _log_dataset_metadata(
        mlflow_run_id,
        config.dataset_id,
        config.corpus_id,
        config.content_version_id,
        tracking_svc,
    )

    dataset_id = config.dataset_id
    corpus_id = config.corpus_id

    mps_thread = None
    if mlflow_run_id and MPSMetricsCollector.is_available():
        mps_thread = MPSSamplerThread(tracking_svc, mlflow_run_id, interval=5.0)
        mps_thread.start()

    event_loop = asyncio.get_event_loop()

    def mlflow_progress_callback(step: int, loss: float) -> None:
        """Callback invoked by the training engine each step to log metrics to MLflow.

        Parameters
        ----------
        step : int
            Current training step number.
        loss : float
            Loss value at this step.
        """
        if mlflow_run_id is None:
            return
        asyncio.run_coroutine_threadsafe(
            tracking_svc.log_metric(mlflow_run_id, "loss", loss, step=step),
            event_loop,
        )

    async def on_complete(result: ComputeResult, _config: dict[str, Any]) -> None:
        """Handle training completion: persist artifacts, export safetensors, register model.

        Parameters
        ----------
        result : TrainingResult
            Result object with ``model``, ``final_loss``, ``samples``, ``uchars``.
        config : dict
            Training configuration used for this run.
        """
        final_loss = result.final_loss or 0.0
        samples = result.samples
        uchars = result.uchars
        model = result.model

        if mlflow_run_id:
            await tracking_svc.finish_run(mlflow_run_id)
            await tracking_svc.log_final_metric(mlflow_run_id, "final_loss", final_loss)
            await tracking_svc.set_tag(
                mlflow_run_id, "architectures", "LlamaForCausalLM"
            )

        # Local path: log artifacts, run safetensors export
        # Remote path: artifacts were logged inside the cloud job — skip
        if model is not None:
            with tempfile.TemporaryDirectory() as tmpdir:
                samples_path = os.path.join(tmpdir, "samples.txt")
                with open(samples_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(samples))
                if mlflow_run_id:
                    try:
                        client = (
                            tracking_svc._client
                        )  # pylint: disable=protected-access
                        if client:
                            loop = asyncio.get_event_loop()
                            await loop.run_in_executor(
                                None,
                                lambda: client.log_artifact(  # type: ignore[union-attr]
                                    mlflow_run_id, samples_path
                                ),
                            )
                    except Exception:  # pylint: disable=broad-exception-caught
                        pass

                model_path = os.path.join(tmpdir, "model.json")
                model.save(model_path, uchars)  # type: ignore[attr-defined]
                if mlflow_run_id:
                    try:
                        client = (
                            tracking_svc._client
                        )  # pylint: disable=protected-access
                        if client:
                            loop = asyncio.get_event_loop()
                            await loop.run_in_executor(
                                None,
                                lambda: client.log_artifact(  # type: ignore[union-attr]
                                    mlflow_run_id, model_path
                                ),
                            )
                    except Exception:  # pylint: disable=broad-exception-caught
                        pass

                # Auto-export safetensors after every successful local training

                export_svc = SafetensorsExportService()
                export_result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: export_svc.export(model, tmpdir, uchars),  # type: ignore[arg-type]
                )

                if export_result["error"]:
                    # FR-016: training is still successful, failure is flagged
                    logger.warning(
                        "Safetensors export failed: %s", export_result["error"]
                    )
                    # Emit error event for SSE stream
                    queue = svc.get_queue(run_id)
                    if queue:
                        await queue.put(
                            {
                                "event": "export_error",
                                "data": json.dumps({"error": export_result["error"]}),
                            }
                        )
                else:
                    if mlflow_run_id and export_result["safetensors_path"]:
                        try:
                            client = (
                                tracking_svc._client
                            )  # pylint: disable=protected-access
                            if client:
                                loop = asyncio.get_event_loop()
                                await loop.run_in_executor(
                                    None,
                                    lambda: client.log_artifact(
                                        mlflow_run_id, export_result["safetensors_path"]
                                    ),
                                )
                                if export_result["config_path"]:
                                    await loop.run_in_executor(
                                        None,
                                        lambda: client.log_artifact(
                                            mlflow_run_id,
                                            export_result["config_path"],
                                        ),
                                    )
                                if export_result["tokenizer_path"]:
                                    await loop.run_in_executor(
                                        None,
                                        lambda: client.log_artifact(
                                            mlflow_run_id,
                                            export_result["tokenizer_path"],
                                        ),
                                    )
                                if export_result.get("mlmodel_path"):
                                    await loop.run_in_executor(
                                        None,
                                        lambda: client.log_artifact(
                                            mlflow_run_id,
                                            export_result["mlmodel_path"],
                                        ),
                                    )
                                if export_result.get("conda_path"):
                                    await loop.run_in_executor(
                                        None,
                                        lambda: client.log_artifact(
                                            mlflow_run_id,
                                            export_result["conda_path"],
                                        ),
                                    )
                        except Exception:  # pylint: disable=broad-exception-caught
                            logger.exception(
                                "Failed to log safetensors artifacts to MLflow"
                            )

        # Store final status as MLflow tags (no DB experiment row)
        if mlflow_run_id:
            await tracking_svc.set_tag(mlflow_run_id, "anvil.status", "finished")
            await tracking_svc.set_tag(
                mlflow_run_id, "anvil.final_loss", str(final_loss)
            )

        if model is not None:
            experiment_model_path = (
                _get_models_dir() / f"experiment_{experiment_id}.json"
            )
            model.save(str(experiment_model_path), uchars)  # type: ignore[attr-defined]

        if mps_thread is not None:
            mps_thread.stop()

        # Register model with MLflow after DB commit so experiment
        # is visible even if model registration hangs
        if mlflow_run_id:
            registry_name = None
            if dataset_id is not None:

                async with AsyncSessionLocal() as sess:
                    ds_repo = DatasetRepository(sess)
                    ds = await ds_repo.get(dataset_id)
                    if ds:
                        registry_name = ds.name
            elif corpus_id is not None:

                async with AsyncSessionLocal() as sess:
                    corp_repo = CorpusRepository(sess)
                    corpus = await corp_repo.get(corpus_id)
                    if corpus:
                        registry_name = corpus.name

            try:
                await tracking_svc.register_source_model(
                    run_id=mlflow_run_id,
                    name=registry_name,
                    dataset_id=dataset_id,
                    corpus_id=corpus_id,
                )
            except Exception:  # pylint: disable=broad-exception-caught
                logger.exception(
                    "Failed to register model for experiment %s",
                    experiment_id,
                )

    async def _run_training() -> None:
        """Coroutine wrapper that runs training and handles exceptions."""
        try:
            await svc.start_training(
                config.model_dump(),
                run_id,
                on_complete=on_complete,
                progress_callback_override=mlflow_progress_callback,
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            # Notify the SSE client about the failure before cleaning up,
            # so the stream doesn't hang with heartbeats forever.
            q = svc.get_queue(run_id)
            if q is not None:
                await q.put(
                    {
                        "event": "error",
                        "data": json.dumps({"message": str(exc)}),
                    }
                )
            if mlflow_run_id:
                await tracking_svc.fail_run(mlflow_run_id, _reason=str(exc))
            if mlflow_run_id:
                await tracking_svc.set_tag(mlflow_run_id, "anvil.status", "failed")
                await tracking_svc.set_tag(mlflow_run_id, "anvil.error", str(exc))
            if mps_thread is not None:
                mps_thread.stop()

    task = asyncio.create_task(_run_training())
    _tasks[run_id] = task

    async def _orphan_queue_release() -> None:
        """Release queue 120s after training task completes (SSE may never connect)."""
        await asyncio.sleep(120)
        svc.release_queue(run_id)

    def _cleanup(_t: asyncio.Task[Any]) -> None:
        """Remove the task from ``_tasks`` dict on completion."""
        _tasks.pop(run_id, None)
        orphan_task = asyncio.create_task(_orphan_queue_release())
        orphan_task.add_done_callback(lambda _t: None)

    task.add_done_callback(_cleanup)

    svc.store_run_metadata(
        run_id,
        mlflow_run_id=mlflow_run_id or None,
        experiment_id=experiment_id,
    )

    response = {
        "run_id": run_id,
        "mlflow_run_id": mlflow_run_id or None,
        "experiment_id": experiment_id,
        "status": "running",
    }
    if tracking_svc.is_degraded:
        response["tracking"] = "degraded"
    else:
        response["tracking"] = "active"
    return response


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

        Cleans up the queue object once the stream ends (terminal event
        consumed, heartbeat timeout, or client disconnect), but only if
        the training task has already completed.  If the training is still
        actively running, the queue is preserved so that a reconnecting
        client can find it and resume streaming.
        """
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"event: {msg['event']}\ndata: {msg['data']}\n\n"
                    if msg["event"] in ("complete", "error", "divergence"):
                        break
                except TimeoutError:
                    yield "event: heartbeat\ndata: {}\n\n"
        finally:
            # Only release the queue if training has completed.  When the
            # client disconnects (page refresh, navigation) while training
            # is still running, the queue must remain in _queues so that
            # the new page can reconnect and resume the SSE stream.  The
            # orphan-queue cleanup task (120s after the training task
            # finishes) will eventually release it.
            if run_id not in _tasks:
                svc.release_queue(run_id)

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
