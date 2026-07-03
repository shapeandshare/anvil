"""Training run lifecycle service — owns the full training lifecycle.

Extracts training orchestration from the route handler into a
reusable service-layer class so BOTH the existing ``POST /training/start``
route and the teaching flow can produce loadable models.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from ...gpu import GpuInfo, detect_gpu
from ..compute.resolve import resolve_backend
from ..compute.result import ComputeResult
from ..compute.training_engine import TrainingEngine
from ..inference.inference import InferenceService
from ..tracking.mps_metrics_collector import MPSMetricsCollector
from ..tracking.mps_sampler_thread import MPSSamplerThread
from ..tracking.tracking import TrackingService
from ..training.export import SafetensorsExportService
from ..training.memory_estimator import MemoryEstimate, estimate_training_memory
from ..training.training import TrainingService
from .training_run_config import TrainingRunConfig

logger = logging.getLogger(__name__)


class TrainingRunService:
    """Owns the full training lifecycle — validation through model persistence.

    Encapsulates hyperparameter validation, compute-backend resolution,
    MLflow setup, background task creation, model artifact persistence,
    and MLflow model registration.  Designed for use from both the
    ``POST /training/start`` route and the teaching loop.

    Parameters
    ----------
    svc : TrainingService
        Low-level training orchestrator (run reservation, doc loading,
        SSE queues).
    tracking : TrackingService
        MLflow experiment tracking service.
    models_dir : Path
        Directory where trained model artifacts (``experiment_{id}.json``)
        are persisted.
    """

    def __init__(
        self,
        svc: TrainingService,
        tracking: TrackingService,
        models_dir: Path,
        tasks: dict[int, asyncio.Task[Any]] | None = None,
    ) -> None:
        self._svc = svc
        self._tracking = tracking
        self._models_dir = models_dir
        self._models_dir.mkdir(parents=True, exist_ok=True)
        # Accept an optional shared tasks dict (e.g. the module-level dict
        # in the route file so SSE handlers can inspect it).
        self._tasks = tasks if tasks is not None else {}

    ########################################################################
    # Public API
    ########################################################################

    def is_run_active(self, run_id: int) -> bool:
        """Return whether a training task is still active for *run_id*.

        Parameters
        ----------
        run_id : int
            The local training run ID.

        Returns
        -------
        bool
            ``True`` if the task is registered and not yet done.
        """
        return run_id in self._tasks

    @property
    def tasks(self) -> dict[int, asyncio.Task[Any]]:
        """Expose the tasks dict for route-level SSE handlers."""
        return self._tasks

    async def start_training_run(
        self,
        config: TrainingRunConfig,
        on_progress: Callable[[int, float], None] | None = None,
        on_complete_extra: (
            Callable[[ComputeResult, dict[str, Any]], Awaitable[None]] | None
        ) = None,
    ) -> dict[str, Any]:
        """Validate, set up, and launch a training run in the background.

        This is the full lifecycle method.  It validates the
        configuration, resolves the compute backend, reserves a run,
        sets up the MLflow run, logs dataset metadata, creates an
        ``asyncio.Task`` for the actual training, and returns
        immediately with run metadata.

        Parameters
        ----------
        config : TrainingRunConfig
            Validated training configuration with all hyperparameters.
        on_progress : callable, optional
            Optional sync ``(step, loss)`` callback for external
            progress tracking (e.g. the teaching loop).
        on_complete_extra : callable, optional
            Optional async ``(ComputeResult, config_dict)`` callback
            invoked after the standard completion handler.  Used by
            the teaching loop to update session state.

        Returns
        -------
        dict[str, Any]
            Keys ``run_id``, ``mlflow_run_id``, ``experiment_id``,
            ``status``, and ``tracking``.

        Raises
        ------
        HTTPException
            Via internal helpers for invalid hyperparameters,
            unavailable backends, or OOM estimates.
        """
        # ── Validation ────────────────────────────────────────────────
        self._validate_hparams(config.n_embd, config.n_head, config.block_size)
        self._validate_method(config)
        await self._validate_warm_start(config)

        engine_backend, device = self._resolve_training_backend(
            config.compute_backend, method=config.method
        )

        gpu_info = detect_gpu()
        memory_est = self._estimate_memory(engine_backend, config, gpu_info)

        run_id = self._svc.reserve_run()
        if memory_est is not None and memory_est.warnings:
            logger.warning(
                "Memory estimate for run %d: %s",
                run_id,
                "; ".join(memory_est.warnings),
            )

        mlflow_run_id, experiment_id = await self._setup_mlflow_run(
            config,
            run_id,
            engine_backend,
            device,
            gpu_info,
        )

        await self._log_dataset_metadata(
            mlflow_run_id,
            config.dataset_id,
            config.corpus_id,
            config.content_version_id,
        )

        # ── Background task setup ─────────────────────────────────────
        mps_thread: MPSSamplerThread | None = None
        if mlflow_run_id and MPSMetricsCollector.is_available():
            mps_thread = MPSSamplerThread(self._tracking, mlflow_run_id, interval=5.0)
            mps_thread.start()

        event_loop = asyncio.get_event_loop()

        def _mlflow_progress_callback(step: int, loss: float) -> None:
            """Log per-step metrics to MLflow from worker thread."""
            if mlflow_run_id is None:
                return
            asyncio.run_coroutine_threadsafe(
                self._tracking.log_metric(mlflow_run_id, "loss", loss, step=step),
                event_loop,
            )

        def _combined_progress(step: int, loss: float) -> None:
            _mlflow_progress_callback(step, loss)
            if on_progress:
                on_progress(step, loss)

        async def _run_training() -> None:
            """Coroutine wrapper that runs training and handles exceptions."""
            try:

                async def _completion_wrapper(
                    result: ComputeResult,
                    config_dict: dict[str, Any],
                ) -> None:
                    await self._on_complete(
                        result=result,
                        config_dict=config_dict,
                        mlflow_run_id=mlflow_run_id,
                        experiment_id=experiment_id,
                        dataset_id=config.dataset_id,
                        corpus_id=config.corpus_id,
                        mps_thread=mps_thread,
                        run_id=run_id,
                    )
                    if on_complete_extra is not None:
                        await on_complete_extra(result, config_dict)

                await self._svc.start_training(
                    config.model_dump(),
                    run_id,
                    on_complete=_completion_wrapper,
                    progress_callback_override=_combined_progress,
                )
            except Exception as exc:  # pylint: disable=broad-exception-caught
                q = self._svc.get_queue(run_id)
                if q is not None:
                    await q.put(
                        {
                            "event": "error",
                            "data": json.dumps({"message": str(exc)}),
                        }
                    )
                if mlflow_run_id:
                    await self._tracking.fail_run(mlflow_run_id, _reason=str(exc))
                    await self._tracking.set_tag(
                        mlflow_run_id, "anvil.status", "failed"
                    )
                    await self._tracking.set_tag(mlflow_run_id, "anvil.error", str(exc))
                if mps_thread is not None:
                    mps_thread.stop()

        task = asyncio.create_task(_run_training())
        self._tasks[run_id] = task

        async def _orphan_queue_release() -> None:
            await asyncio.sleep(120)
            self._svc.release_queue(run_id)

        def _cleanup(_t: asyncio.Task[Any]) -> None:
            self._tasks.pop(run_id, None)
            orphan = asyncio.create_task(_orphan_queue_release())
            orphan.add_done_callback(lambda _t: None)

        task.add_done_callback(_cleanup)

        self._svc.store_run_metadata(
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
        if self._tracking.is_degraded:
            response["tracking"] = "degraded"
        else:
            response["tracking"] = "active"
        return response

    ########################################################################
    # Validation helpers
    ########################################################################

    @staticmethod
    def _validate_hparams(
        n_embd: int,
        n_head: int,
        block_size: int,
    ) -> None:
        """Validate architectural hyperparameter constraints.

        Parameters
        ----------
        n_embd : int
            Embedding dimension.
        n_head : int
            Number of attention heads.
        block_size : int
            Context window size.

        Raises
        ------
        ValueError
            If any constraint is violated.
        """
        if n_head > n_embd:
            raise ValueError(
                f"n_head ({n_head}) exceeds n_embd ({n_embd}) — head_dim"
                f" would be 0. n_head must be <= n_embd."
            )
        if n_embd % n_head != 0:
            raise ValueError(
                f"n_embd ({n_embd}) is not divisible by n_head ({n_head}). "
                f"The embedding dimension must be evenly divisible by the"
                f" number of attention heads."
            )
        head_dim = n_embd // n_head
        if head_dim % 2 != 0:
            raise ValueError(
                f"head_dim={head_dim} is odd — RoPE requires an even head"
                f" dimension. Try adjusting n_embd or n_head."
            )

    @staticmethod
    def _validate_method(config: TrainingRunConfig) -> None:
        """Validate LoRA/QLoRA method constraints.

        Parameters
        ----------
        config : TrainingRunConfig
            Training configuration to validate.

        Raises
        ------
        ValueError
            If method constraints are violated.
        """
        method = config.method or "full"

        if method in ("lora", "qlora"):
            if config.base_model_ref is None:
                raise ValueError(
                    "base_model_ref is required when method is "
                    f"{method!r}. Select an imported HuggingFace model"
                    " to fine-tune."
                )
            if config.lora_rank is None:
                raise ValueError("lora_rank is required when method is {method!r}.")
        elif method == "full":
            if any(
                v is not None
                for v in (
                    config.lora_rank,
                    config.lora_alpha,
                    config.lora_target_modules,
                    config.lora_dropout,
                    config.lora_bias,
                )
            ):
                raise ValueError(
                    "lora_* fields are not allowed when method is 'full'."
                    " Set method to 'lora' or 'qlora' for LoRA"
                    " fine-tuning."
                )
        else:
            raise ValueError(
                f"Unknown method: {method!r}. Must be 'full', 'lora', or" " 'qlora'."
            )

    async def _validate_warm_start(self, config: TrainingRunConfig) -> None:
        """Validate warm-start architecture consistency.

        When ``base_model_ref`` is set with ``method='full'``, loads the
        base model and checks that architecture dimensions match.

        Parameters
        ----------
        config : TrainingRunConfig
            Training configuration to validate.

        Raises
        ------
        ValueError
            If architecture dimensions conflict with the base model.
        """
        if config.base_model_ref is None or config.method != "full":
            return
        inference = InferenceService()
        try:
            base_model = await inference.load_model(model_id=config.base_model_ref)
        except ValueError as e:
            raise ValueError(str(e)) from None

        if config.n_embd != base_model.model.n_embd:
            raise ValueError(
                f"n_embd={config.n_embd} conflicts with base model's"
                f" n_embd={base_model.model.n_embd}. Architecture"
                " dimensions are inherited from the base checkpoint"
                " during warm-start."
            )
        if config.n_head != base_model.model.n_head:
            raise ValueError(
                f"n_head={config.n_head} conflicts with base model's"
                f" n_head={base_model.model.n_head}. Architecture"
                " dimensions are inherited from the base checkpoint"
                " during warm-start."
            )
        if config.n_layer != base_model.model.n_layer:
            raise ValueError(
                f"n_layer={config.n_layer} conflicts with base model's"
                f" n_layer={base_model.model.n_layer}. Architecture"
                " dimensions are inherited from the base checkpoint"
                " during warm-start."
            )
        if config.block_size != base_model.model.block_size:
            raise ValueError(
                f"block_size={config.block_size} conflicts with base"
                f" model's block_size={base_model.model.block_size}."
                " Architecture dimensions are inherited from the base"
                " checkpoint during warm-start."
            )

    ########################################################################
    # Backend resolution and memory estimation
    ########################################################################

    @staticmethod
    def _resolve_training_backend(
        compute_backend: str | None,
        method: str = "full",
    ) -> tuple[TrainingEngine, str]:
        """Resolve compute backend and device for training.

        Parameters
        ----------
        compute_backend : str | None
            Compute backend identifier (e.g. ``"auto"``, ``"local-torch"``).
        method : str, optional
            Training method (``"full"``, ``"lora"``, ``"qlora"``).

        Returns
        -------
        tuple[TrainingEngine, str]
            ``(engine_backend, device)`` tuple.

        Raises
        ------
        ComputeBackendUnavailable
            If the requested backend is unavailable.
        """
        resolved = resolve_backend(
            {"compute_backend": compute_backend, "method": method}
        )
        return resolved["engine"], resolved["device"]

    @staticmethod
    def _estimate_memory(
        engine_backend: TrainingEngine,
        config: TrainingRunConfig,
        gpu_info: GpuInfo,
    ) -> MemoryEstimate | None:
        """Estimate GPU memory and raise if OOM.

        Parameters
        ----------
        engine_backend : TrainingEngine
            The resolved training engine backend.
        config : TrainingRunConfig
            Training configuration.
        gpu_info : GpuInfo
            GPU information from ``detect_gpu()``.

        Returns
        -------
        MemoryEstimate | None
            Memory estimate if ``engine_backend`` is TORCH, else None.

        Raises
        ------
        ValueError
            If the model config would OOM the GPU.
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
            raise ValueError(
                f"Model config would likely OOM your GPU."
                f" Estimated peak memory: {memory_est.peak_gb:.1f} GB,"
                f" available: {memory_est.available_gb:.1f} GB"
                f" ({memory_est.device_backend},"
                f" {memory_est.device_name}). Try reducing n_embd,"
                f" n_layer, n_head, or block_size. Breakdown:"
                f" {memory_est.param_count:,} params,"
                f" {memory_est.weights_bytes / (1024**2):.0f} MB"
                f" weights,"
                f" {memory_est.gradients_bytes / (1024**2):.0f} MB"
                f" gradients,"
                f" {memory_est.optimizer_bytes / (1024**2):.0f} MB"
                f" optimizer,"
                f" {memory_est.kv_cache_bytes / (1024**2):.0f} MB"
                f" KV cache."
            )
        return memory_est

    ########################################################################
    # MLflow setup
    ########################################################################

    async def _setup_mlflow_run(
        self,
        config: TrainingRunConfig,
        run_id: int,
        engine_backend: TrainingEngine,
        device: str,
        gpu_info: GpuInfo,
    ) -> tuple[str | None, int]:
        """Build hyperparams dict, start MLflow run, allocate experiment ID.

        Parameters
        ----------
        config : TrainingRunConfig
            Training configuration.
        run_id : int
            Reserved training run ID.
        engine_backend : TrainingEngine
            Resolved compute engine backend.
        device : str
            Resolved device string.
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

        mlflow_run_id = await self._tracking.start_run(
            run_name=None,
            params=hyperparams,
            engine_backend=engine_backend,
            device=device,
        )

        experiment_id = await self._svc.allocate_experiment_id()

        if mlflow_run_id:
            await self._tracking.set_tag(
                mlflow_run_id,
                "anvil.experiment_id",
                str(experiment_id),
            )
            await self._tracking.set_tag(mlflow_run_id, "anvil.status", "running")

        return mlflow_run_id, experiment_id

    ########################################################################
    # Dataset metadata logging
    ########################################################################

    async def _log_dataset_metadata(
        self,
        mlflow_run_id: str | None,
        dataset_id: int | None,
        corpus_id: int | None,
        content_version_id: int | None,
    ) -> None:
        """Log dataset metadata as MLflow tags.

        Parameters
        ----------
        mlflow_run_id : str | None
            MLflow run ID (may be None if MLflow is degraded).
        dataset_id : int | None
            Optional dataset ID.
        corpus_id : int | None
            Optional corpus ID.
        content_version_id : int | None
            Optional content version ID.
        """
        from ...db.repositories.content_versions import (  # import-placement:allow — inherited route pattern
            ContentVersionRepository,
        )
        from ...db.repositories.corpora import (  # import-placement:allow — inherited route pattern
            CorpusRepository,
        )
        from ...db.repositories.datasets import (  # import-placement:allow — inherited route pattern
            DatasetRepository,
        )
        from ...db.session import (  # import-placement:allow — inherited route pattern
            AsyncSessionLocal,
        )
        from ...services.content.lineage_service import (  # import-placement:allow — inherited route pattern
            LineageService,
        )

        input_digest: str | None = None
        input_role: str | None = None
        if mlflow_run_id and dataset_id:
            async with AsyncSessionLocal() as sess:
                try:
                    input_digest = await self._tracking.log_dataset_input(
                        mlflow_run_id,
                        dataset_id=dataset_id,
                        role="training",
                        session=sess,
                    )
                    input_role = "training"
                except Exception:  # pylint: disable=broad-exception-caught
                    logger.warning(
                        "Failed to log dataset input to MLflow run %s",
                        mlflow_run_id,
                        exc_info=True,
                    )
                    pass
        elif mlflow_run_id and corpus_id:
            async with AsyncSessionLocal() as sess:
                try:
                    input_digest = await self._tracking.log_corpus_input(
                        mlflow_run_id,
                        corpus_id=corpus_id,
                        session=sess,
                    )
                    input_role = "corpus"
                except Exception:  # pylint: disable=broad-exception-caught
                    logger.warning(
                        "Failed to log corpus input to MLflow run %s",
                        mlflow_run_id,
                        exc_info=True,
                    )
                    pass

        if mlflow_run_id and input_digest:
            await self._tracking.set_tag(
                mlflow_run_id,
                "anvil.input_digest",
                input_digest,
            )
            await self._tracking.set_tag(
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
                        await self._tracking.set_tag(
                            mlflow_run_id,
                            "anvil.dataset.name",
                            ds.name,
                        )
                        await self._tracking.set_tag(
                            mlflow_run_id,
                            "anvil.dataset.vocab_size",
                            str(ds.vocabulary_size or ""),
                        )
                        await self._tracking.set_tag(
                            mlflow_run_id,
                            "anvil.dataset.sample_count",
                            str(ds.sample_count or 0),
                        )
                        await self._tracking.set_tag(
                            mlflow_run_id,
                            "anvil.dataset.document_count",
                            str(ds.document_count or 0),
                        )
                        await self._tracking.set_tag(
                            mlflow_run_id,
                            "anvil.dataset.curation_version",
                            str(ds.curation_version or 0),
                        )
                except Exception:  # pylint: disable=broad-exception-caught
                    logger.warning(
                        "Failed to set dataset tags on MLflow run %s",
                        mlflow_run_id,
                        exc_info=True,
                    )
                    pass
        elif mlflow_run_id and corpus_id:
            async with AsyncSessionLocal() as sess:
                try:
                    corp_repo = CorpusRepository(sess)
                    corpus = await corp_repo.get(corpus_id)
                    if corpus:
                        await self._tracking.set_tag(
                            mlflow_run_id,
                            "anvil.dataset.name",
                            corpus.name,
                        )
                        await self._tracking.set_tag(
                            mlflow_run_id,
                            "anvil.corpus.file_count",
                            str(corpus.file_count or 0),
                        )
                        await self._tracking.set_tag(
                            mlflow_run_id,
                            "anvil.corpus.document_count",
                            str(corpus.document_count or 0),
                        )
                        if corpus.language_map:
                            await self._tracking.set_tag(
                                mlflow_run_id,
                                "anvil.corpus.language_map",
                                corpus.language_map,
                            )
                except Exception:  # pylint: disable=broad-exception-caught
                    logger.warning(
                        "Failed to set corpus tags on MLflow run %s",
                        mlflow_run_id,
                        exc_info=True,
                    )
                    pass

        if mlflow_run_id and content_version_id is not None:
            async with AsyncSessionLocal() as sess:
                try:
                    ver_repo = ContentVersionRepository(sess)
                    version = await ver_repo.get(int(content_version_id))
                    if version:
                        await self._tracking.set_tag(
                            mlflow_run_id,
                            "anvil.content_version_id",
                            str(content_version_id),
                        )
                        await self._tracking.set_tag(
                            mlflow_run_id,
                            "anvil.content_manifest_digest",
                            version.manifest_digest,
                        )

                        client = self._tracking._client
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
                                            "version_number": (version.version_number),
                                            "manifest_digest": (
                                                version.manifest_digest
                                            ),
                                            "label": version.label,
                                            "entry_count": (version.entry_count),
                                            "total_bytes": (version.total_bytes),
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

                        lineage = LineageService(ver_repo)
                        await lineage.record_run_ref(
                            version_id=version.id,
                            mlflow_run_id=mlflow_run_id,
                            corpus_ref=f"corpus:{version.corpus_id}",
                        )
                        await sess.commit()
                except Exception:  # pylint: disable=broad-exception-caught
                    logger.error(
                        "Failed to record lineage for run %s",
                        mlflow_run_id,
                        exc_info=True,
                    )
                    pass

    ########################################################################
    # Training completion handler
    ########################################################################

    async def _on_complete(
        self,
        *,
        result: ComputeResult,
        config_dict: dict[str, Any],
        mlflow_run_id: str | None,
        experiment_id: int,
        dataset_id: int | None,
        corpus_id: int | None,
        mps_thread: MPSSamplerThread | None,
        run_id: int,
    ) -> None:
        """Handle training completion: persist artifacts, export safetensors,
        register model.

        Parameters
        ----------
        result : ComputeResult
            Result with ``model``, ``final_loss``, ``samples``, etc.
        config_dict : dict
            Training configuration dict.
        mlflow_run_id : str or None
            MLflow run ID if tracking is active.
        experiment_id : int
            Numeric experiment ID.
        dataset_id : int or None
            Dataset ID used for training.
        corpus_id : int or None
            Corpus ID used for training.
        mps_thread : MPSSamplerThread or None
            MPS metrics thread to stop.
        run_id : int
            Local run ID (for queue access).
        """
        from ...db.repositories.corpora import (  # import-placement:allow — inherited route pattern
            CorpusRepository,
        )
        from ...db.repositories.datasets import (  # import-placement:allow — inherited route pattern
            DatasetRepository,
        )
        from ...db.session import (  # import-placement:allow — inherited route pattern
            AsyncSessionLocal,
        )

        final_loss = result.final_loss or 0.0
        samples = result.samples
        uchars = result.uchars
        model = result.model

        if mlflow_run_id:
            await self._tracking.finish_run(mlflow_run_id)
            await self._tracking.log_final_metric(
                mlflow_run_id, "final_loss", final_loss
            )
            await self._tracking.set_tag(
                mlflow_run_id, "architectures", "LlamaForCausalLM"
            )

            if config_dict.get("base_model_ref") is not None:
                await self._tracking.set_tag(mlflow_run_id, "anvil.warm_start", "true")
                await self._tracking.set_tag(
                    mlflow_run_id,
                    "anvil.base_model_ref",
                    str(config_dict["base_model_ref"]),
                )
                specialization_corpus = "unknown"
                if dataset_id is not None:
                    async with AsyncSessionLocal() as sess:
                        ds_repo = DatasetRepository(sess)
                        ds = await ds_repo.get(dataset_id)
                        if ds:
                            specialization_corpus = ds.name
                elif corpus_id is not None:
                    async with AsyncSessionLocal() as sess:
                        corp_repo = CorpusRepository(sess)
                        corpus = await corp_repo.get(corpus_id)
                        if corpus:
                            specialization_corpus = corpus.name
                await self._tracking.set_tag(
                    mlflow_run_id,
                    "anvil.specialization_corpus",
                    specialization_corpus,
                )

        if model is not None:
            with tempfile.TemporaryDirectory() as tmpdir:
                samples_path = os.path.join(tmpdir, "samples.txt")
                with open(  # noqa: ASYNC230 — inherited route pattern; model.save() is synchronous
                    samples_path, "w", encoding="utf-8"
                ) as f:
                    f.write("\n".join(samples))
                if mlflow_run_id:
                    try:
                        c = self._tracking._client
                        if c:
                            loop = asyncio.get_event_loop()
                            await loop.run_in_executor(
                                None,
                                lambda c=c: c.log_artifact(  # type: ignore[misc]
                                    mlflow_run_id, samples_path
                                ),
                            )
                    except Exception:  # pylint: disable=broad-exception-caught
                        logger.warning(
                            "Failed to log samples artifact to MLflow run" " %s",
                            mlflow_run_id,
                            exc_info=True,
                        )
                        pass

                model_path = os.path.join(tmpdir, "model.json")
                model.save(model_path, uchars)  # type: ignore[attr-defined]
                if mlflow_run_id:
                    try:
                        c = self._tracking._client
                        if c:
                            loop = asyncio.get_event_loop()
                            await loop.run_in_executor(
                                None,
                                lambda c=c: c.log_artifact(  # type: ignore[misc]
                                    mlflow_run_id, model_path
                                ),
                            )
                    except Exception:  # pylint: disable=broad-exception-caught
                        logger.warning(
                            "Failed to log model artifact to MLflow run %s",
                            mlflow_run_id,
                            exc_info=True,
                        )
                        pass

                export_svc = SafetensorsExportService()
                export_result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: export_svc.export(model, tmpdir, uchars),  # type: ignore[arg-type]
                )

                if export_result["error"]:
                    logger.warning(
                        "Safetensors export failed: %s",
                        export_result["error"],
                    )
                    queue = self._svc.get_queue(run_id)
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
                            client = self._tracking._client
                            if client:
                                loop = asyncio.get_event_loop()
                                await loop.run_in_executor(
                                    None,
                                    lambda: client.log_artifact(
                                        mlflow_run_id,
                                        export_result["safetensors_path"],
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
                                "Failed to log safetensors artifacts to" " MLflow"
                            )

        if mlflow_run_id:
            await self._tracking.set_tag(mlflow_run_id, "anvil.status", "finished")
            await self._tracking.set_tag(
                mlflow_run_id,
                "anvil.final_loss",
                str(final_loss),
            )

        if model is not None:
            experiment_model_path = (
                self._models_dir / f"experiment_{experiment_id}.json"
            )
            model.save(str(experiment_model_path), uchars)  # type: ignore[attr-defined]

        if mps_thread is not None:
            mps_thread.stop()

        # ── Adapter persistence (047) ────────────────────────────────
        if result.adapter_id is not None:
            from ...db.repositories.lora_adapter_repository import (  # import-placement:allow — cycle with adapter_persistence
                LoRAAdapterRepository,
            )
            from ..training.adapter_persistence import (  # import-placement:allow — cycle with lora_repo
                AdapterPersistenceService,
            )

            async with AsyncSessionLocal() as sess:
                repo = LoRAAdapterRepository(sess)
                persistence = AdapterPersistenceService(repo)
                await persistence.persist(result, config_dict, run_id=run_id)

        # ── MLflow model registration ────────────────────────────────
        if mlflow_run_id:
            registry_name: str | None = None
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
                await self._tracking.register_source_model(
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

    ########################################################################
    # Teaching-loop callback factory
    ########################################################################

    def build_teaching_on_complete(
        self,
        mlflow_run_id: str | None,
        experiment_id: int,
        teaching_session_id: int,
        teaching_round_index: int,
        run_id: int,
    ) -> Callable[[ComputeResult, dict[str, Any]], Awaitable[None]]:
        """Build an ``on_complete`` callback that sets teaching MLflow tags.

        Parameters
        ----------
        mlflow_run_id : str or None
            MLflow run ID.
        experiment_id : int
            Numeric experiment ID.
        teaching_session_id : int
            Teaching session ID for lineage tags.
        teaching_round_index : int
            Round index for lineage tags.
        run_id : int
            Local run ID for queue/artifact operations.

        Returns
        -------
        callable
            An async ``on_complete`` callback suitable for
            ``TrainingService.start_training``.
        """
        dataset_id: int | None = None
        corpus_id: int | None = None

        async def _teaching_on_complete(
            result: ComputeResult,
            config_dict: dict[str, Any],
        ) -> None:
            nonlocal dataset_id, corpus_id
            dataset_id = config_dict.get("dataset_id")
            corpus_id = config_dict.get("corpus_id")

            await self._on_complete(
                result=result,
                config_dict=config_dict,
                mlflow_run_id=mlflow_run_id,
                experiment_id=experiment_id,
                dataset_id=dataset_id,
                corpus_id=corpus_id,
                mps_thread=None,
                run_id=run_id,
            )

            # Set teaching lineage tags
            if mlflow_run_id and not self._tracking.is_degraded:
                await self._tracking.set_tag(
                    mlflow_run_id,
                    "teaching_session_id",
                    str(teaching_session_id),
                )
                await self._tracking.set_tag(
                    mlflow_run_id,
                    "teaching_round_index",
                    str(teaching_round_index),
                )
                await self._tracking.set_tag(
                    mlflow_run_id,
                    "anvil.origin",
                    "teaching",
                )
                if experiment_id:
                    await self._tracking.set_tag(
                        mlflow_run_id,
                        "teaching_parent_experiment_id",
                        str(experiment_id),
                    )

        return _teaching_on_complete
