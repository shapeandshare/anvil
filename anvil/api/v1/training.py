import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from starlette.responses import StreamingResponse

from anvil.gpu import detect_gpu
from anvil.services.compute.errors import ComputeBackendUnavailable
from anvil.services.compute.resolve import resolve_backend
from anvil.services.memory_estimator import estimate_training_memory
from anvil.services.metrics_collectors import MPSMetricsCollector, MPSSamplerThread
from anvil.services.tracking import TrackingService
from anvil.services.training import TrainingService

logger = logging.getLogger(__name__)

router = APIRouter()
svc = TrainingService()
tracking_svc = TrackingService()
_tasks: dict[int, asyncio.Task] = {}
MODELS_DIR = Path("data/models")
MODELS_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/training/start")
async def start_training(config: dict):
    n_embd = config.get("n_embd", 16)
    n_head = config.get("n_head", 4)
    block_size = config.get("block_size", 16)

    if n_head > n_embd:
        raise HTTPException(
            status_code=422,
            detail=f"n_head ({n_head}) exceeds n_embd ({n_embd}) — head_dim would be 0. n_head must be <= n_embd."
        )
    if n_embd % n_head != 0:
        raise HTTPException(
            status_code=422,
            detail=f"n_embd ({n_embd}) is not divisible by n_head ({n_head}). "
                   f"The embedding dimension must be evenly divisible by the number of attention heads. "
                   f"Try n_head={max(h for h in range(1, n_head + 1) if n_embd % h == 0)}."
        )
    head_dim = n_embd // n_head
    if head_dim % 2 != 0:
        raise HTTPException(
            status_code=422,
            detail=f"head_dim={head_dim} is odd — RoPE (Rotary Position Embedding) requires an even head dimension. "
                   f"Try adjusting n_embd or n_head so that n_embd / n_head is even."
        )

    use_gpu = config.get("use_gpu", False)
    compute_backend = config.get("compute_backend", "auto")
    dataset_id = config.get("dataset_id")
    corpus_id = config.get("corpus_id")

    # Backward compat: if legacy use_gpu is set without compute_backend, map it
    if "compute_backend" not in config and use_gpu:
        compute_backend = "local-gpu"
    elif "compute_backend" not in config and not use_gpu:
        compute_backend = "auto"

    try:
        resolved = resolve_backend({"compute_backend": compute_backend})
    except ComputeBackendUnavailable as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    engine_backend = resolved["engine"]
    device = resolved["device"]

    gpu_info = detect_gpu()

    memory_est = None
    if engine_backend == "torch":
        memory_est = estimate_training_memory(
            vocab_size=200,
            n_embd=n_embd,
            n_head=n_head,
            n_layer=config.get("n_layer", 1),
            block_size=block_size,
            use_gpu=True,
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

    run_id = svc.reserve_run()

    if memory_est is not None and memory_est.warnings:
        logger.warning(
            "Memory estimate for run %d: %s",
            run_id,
            "; ".join(memory_est.warnings),
        )

    hyperparams = {
        "n_layer": config.get("n_layer", 1),
        "n_embd": n_embd,
        "n_head": n_head,
        "block_size": block_size,
        "num_steps": config.get("num_steps", 1000),
        "learning_rate": config.get("learning_rate", 0.01),
        "beta1": config.get("beta1", 0.85),
        "beta2": config.get("beta2", 0.99),
        "temperature": config.get("temperature", 0.5),
        "use_gpu": use_gpu,
        "compute_backend": compute_backend,
        "corpus_id": corpus_id,
        "dataset_id": dataset_id,
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

    # Generate a numeric experiment_id from the run_id_seq table.
    # This is used as the anvil.experiment_id tag for MLflow lookup.
    experiment_id = await svc.allocate_experiment_id()

    # Store experiment identity as MLflow tags
    if mlflow_run_id:
        await tracking_svc.set_tag(mlflow_run_id, "anvil.experiment_id", str(experiment_id))
        await tracking_svc.set_tag(mlflow_run_id, "anvil.status", "running")

    from anvil.db.session import AsyncSessionLocal

    input_digest = None
    input_role = None
    if mlflow_run_id and dataset_id:
        async with AsyncSessionLocal() as sess:
            try:
                input_digest = await tracking_svc.log_dataset_input(
                    mlflow_run_id, dataset_id=dataset_id, role="training", session=sess
                )
                input_role = "training"
            except Exception:
                pass
    elif mlflow_run_id and corpus_id:
        async with AsyncSessionLocal() as sess:
            try:
                input_digest = await tracking_svc.log_corpus_input(
                    mlflow_run_id, corpus_id=corpus_id, session=sess
                )
                input_role = "corpus"
            except Exception:
                pass

    # Store input metadata as MLflow tags (not in DB)
    if mlflow_run_id and input_digest:
        await tracking_svc.set_tag(mlflow_run_id, "anvil.input_digest", input_digest)
        await tracking_svc.set_tag(mlflow_run_id, "anvil.input_role", input_role or "training")

    # Phase 1C: push dataset/corpus metadata as MLflow tags
    if mlflow_run_id and dataset_id:
        async with AsyncSessionLocal() as sess:
            try:
                from anvil.db.repositories.datasets import DatasetRepository
                ds_repo = DatasetRepository(sess)
                ds = await ds_repo.get(dataset_id)
                if ds:
                    await tracking_svc.set_tag(mlflow_run_id, "anvil.dataset.name", ds.name)
                    await tracking_svc.set_tag(mlflow_run_id, "anvil.dataset.vocab_size", str(ds.vocabulary_size or ""))
                    await tracking_svc.set_tag(mlflow_run_id, "anvil.dataset.sample_count", str(ds.sample_count or 0))
                    await tracking_svc.set_tag(mlflow_run_id, "anvil.dataset.document_count", str(ds.document_count or 0))
                    await tracking_svc.set_tag(mlflow_run_id, "anvil.dataset.curation_version", str(ds.curation_version or 0))
            except Exception:
                pass
    elif mlflow_run_id and corpus_id:
        async with AsyncSessionLocal() as sess:
            try:
                from anvil.db.repositories.corpora import CorpusRepository
                corp_repo = CorpusRepository(sess)
                corpus = await corp_repo.get(corpus_id)
                if corpus:
                    await tracking_svc.set_tag(mlflow_run_id, "anvil.dataset.name", corpus.name)
                    await tracking_svc.set_tag(mlflow_run_id, "anvil.corpus.file_count", str(corpus.file_count or 0))
                    await tracking_svc.set_tag(mlflow_run_id, "anvil.corpus.document_count", str(corpus.document_count or 0))
                    if corpus.language_map:
                        await tracking_svc.set_tag(mlflow_run_id, "anvil.corpus.language_map", corpus.language_map)
            except Exception:
                pass

    mps_thread = None
    if mlflow_run_id and MPSMetricsCollector.is_available():
        mps_thread = MPSSamplerThread(tracking_svc, mlflow_run_id, interval=5.0)
        mps_thread.start()

    event_loop = asyncio.get_event_loop()

    def mlflow_progress_callback(step: int, loss: float) -> None:
        asyncio.run_coroutine_threadsafe(
            tracking_svc.log_metric(mlflow_run_id, "loss", loss, step=step),
            event_loop,
        )

    async def on_complete(result, config: dict):
        model = result.model
        final_loss = result.final_loss or 0.0
        samples = result.samples
        uchars = result.uchars

        await tracking_svc.finish_run(mlflow_run_id)
        await tracking_svc.log_final_metric(mlflow_run_id, "final_loss", final_loss)

        await tracking_svc.set_tag(mlflow_run_id, "architectures", "LlamaForCausalLM")

        # Local path: log artifacts, run safetensors export
        # Remote path: artifacts were logged inside the cloud job — skip
        if model is not None:
            with tempfile.TemporaryDirectory() as tmpdir:
                samples_path = os.path.join(tmpdir, "samples.txt")
                with open(samples_path, "w") as f:
                    f.write("\n".join(samples))
                if mlflow_run_id:
                    try:
                        client = tracking_svc._client
                        if client:
                            loop = asyncio.get_event_loop()
                            await loop.run_in_executor(
                                None,
                                lambda: client.log_artifact(mlflow_run_id, samples_path),
                            )
                    except Exception:
                        pass

                model_path = os.path.join(tmpdir, "model.json")
                model.save(model_path, uchars)
                if mlflow_run_id:
                    try:
                        client = tracking_svc._client
                        if client:
                            loop = asyncio.get_event_loop()
                            await loop.run_in_executor(
                                None, lambda: client.log_artifact(mlflow_run_id, model_path)
                            )
                    except Exception:
                        pass

                # Auto-export safetensors after every successful local training
                from anvil.services.export import SafetensorsExportService

                export_svc = SafetensorsExportService()
                export_result = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: export_svc.export(model, tmpdir, uchars)
                )

                if export_result["error"]:
                    # FR-016: training is still successful, failure is flagged
                    logger.warning(
                        "Safetensors export failed: %s", export_result["error"]
                    )
                    # Emit error event for SSE stream
                    queue = svc.get_queue(run_id)
                    if queue:
                        await queue.put({
                            "event": "export_error",
                            "data": json.dumps({"error": export_result["error"]}),
                        })
                else:
                    if mlflow_run_id and export_result["safetensors_path"]:
                        try:
                            client = tracking_svc._client
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
                        except Exception:
                            logger.exception(
                                "Failed to log safetensors artifacts to MLflow"
                            )

        from anvil.db.session import AsyncSessionLocal

        # Store final status as MLflow tags (no DB experiment row)
        if mlflow_run_id:
            await tracking_svc.set_tag(mlflow_run_id, "anvil.status", "finished")
            await tracking_svc.set_tag(mlflow_run_id, "anvil.final_loss", str(final_loss))

        if model is not None:
            experiment_model_path = MODELS_DIR / f"experiment_{experiment_id}.json"
            model.save(str(experiment_model_path), uchars)

        if mps_thread is not None:
            mps_thread.stop()

        # Register model with MLflow after DB commit so experiment
        # is visible even if model registration hangs
        if mlflow_run_id:
            registry_name = None
            if dataset_id is not None:
                from anvil.db.repositories.datasets import DatasetRepository

                async with AsyncSessionLocal() as sess:
                    ds_repo = DatasetRepository(sess)
                    ds = await ds_repo.get(dataset_id)
                    if ds:
                        registry_name = ds.name
            elif corpus_id is not None:
                from anvil.db.repositories.corpora import CorpusRepository

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
            except Exception:
                logger.exception(
                    "Failed to register model for experiment %s",
                    experiment_id,
                )

    async def _run_training():
        try:
            await svc.start_training(
                config,
                run_id,
                on_complete=on_complete,
                progress_callback_override=mlflow_progress_callback,
            )
        except Exception as exc:
            await tracking_svc.fail_run(mlflow_run_id, reason=str(exc))
            if mlflow_run_id:
                await tracking_svc.set_tag(mlflow_run_id, "anvil.status", "failed")
                await tracking_svc.set_tag(mlflow_run_id, "anvil.error", str(exc))
            if mps_thread is not None:
                mps_thread.stop()

    task = asyncio.create_task(_run_training())
    _tasks[run_id] = task

    def _cleanup(t: asyncio.Task) -> None:
        _tasks.pop(run_id, None)

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
async def training_run_status(run_id: int):
    """Check whether a training run is still active on the server."""
    queue = svc.get_queue(run_id)
    if queue is None:
        raise HTTPException(status_code=404, detail="Run not found or already completed")
    return {"run_id": run_id, "status": "active"}


@router.get("/training/stream/{run_id}")
async def stream_training(run_id: int):
    queue = svc.get_queue(run_id)
    if queue is None:
        async def _run_gone():
            yield "event: error\ndata: " + json.dumps({"message": "Training run has already completed or was never started"}) + "\n\n"
        return StreamingResponse(
            _run_gone(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    async def event_stream():
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=30)
                yield f"event: {msg['event']}\ndata: {msg['data']}\n\n"
                if msg["event"] in ("complete", "error"):
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
async def list_configs():
    from sqlalchemy import select

    from anvil.db.models.training_config import TrainingConfig
    from anvil.db.session import AsyncSessionLocal

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
                    "use_gpu": c.use_gpu,
                    "created_at": str(c.created_at),
                }
                for c in configs
            ]
        }


@router.post("/training/{run_id}/stop")
async def stop_training(run_id: int):
    svc.stop_run(run_id)
    queue = svc.get_queue(run_id)
    if queue is not None:
        await queue.put({
            "event": "error",
            "data": json.dumps({"message": "Training stopped by user"}),
        })
    return {"status": "stopped"}


@router.get("/forward-pass/graph")
async def forward_pass_graph():
    from anvil.services.inference import InferenceService

    svc = InferenceService()
    try:
        loaded = await svc.load_model()
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return svc.forward_graph(loaded)
