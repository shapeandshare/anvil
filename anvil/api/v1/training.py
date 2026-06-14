import asyncio
import json
import logging
import os
import tempfile
from datetime import UTC
from pathlib import Path

from fastapi import APIRouter, HTTPException
from starlette.responses import StreamingResponse

from anvil.gpu import detect_gpu, resolve_device
from anvil.services.metrics_collectors import MPSMetricsCollector, MPSSamplerThread
from anvil.services.tracking import TrackingService
from anvil.services.training import StopRequested, TrainingService

logger = logging.getLogger(__name__)

router = APIRouter()
svc = TrainingService()
tracking_svc = TrackingService()
_tasks: dict[int, asyncio.Task] = {}
MODELS_DIR = Path("data/models")
MODELS_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/training/start")
async def start_training(config: dict):
    run_id = svc.reserve_run()

    use_gpu = config.get("use_gpu", False)
    dataset_id = config.get("dataset_id")
    corpus_id = config.get("corpus_id")
    hyperparams = {
        "n_layer": config.get("n_layer", 1),
        "n_embd": config.get("n_embd", 16),
        "n_head": config.get("n_head", 4),
        "block_size": config.get("block_size", 16),
        "num_steps": config.get("num_steps", 1000),
        "learning_rate": config.get("learning_rate", 0.01),
        "beta1": config.get("beta1", 0.85),
        "beta2": config.get("beta2", 0.99),
        "temperature": config.get("temperature", 0.5),
        "use_gpu": use_gpu,
        "corpus_id": corpus_id,
        "dataset_id": dataset_id,
    }

    gpu_info = detect_gpu()
    engine_backend = "torch" if use_gpu else "stdlib"
    device = resolve_device(use_gpu=use_gpu)

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

    from anvil.db.repositories.experiments import ExperimentRepository
    from anvil.db.session import AsyncSessionLocal

    experiment_id = None
    async with AsyncSessionLocal() as session:
        repo = ExperimentRepository(session)
        exp = await repo.create_running(
            config_id=None,
            run_name=f"run-{run_id}" if not tracking_svc.is_degraded else None,
            mlflow_run_id=mlflow_run_id or None,
            dataset_id=dataset_id,
            corpus_id=corpus_id,
            engine_backend=engine_backend,
            device=device,
        )
        experiment_id = exp.id
        await session.commit()

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

    if input_digest:
        async with AsyncSessionLocal() as sess:
            repo = ExperimentRepository(sess)
            exp_obj = await repo.get(experiment_id)
            if exp_obj:
                exp_obj.input_digest = input_digest
                exp_obj.input_role = input_role
                await repo.update(exp_obj)
                await sess.commit()

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

    async def on_complete(
        model, config: dict, final_loss: float, samples: list[str], uchars: list[str]
    ):
        await tracking_svc.finish_run(mlflow_run_id)
        await tracking_svc.log_final_metric(mlflow_run_id, "final_loss", final_loss)

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

        from anvil.db.repositories.experiments import ExperimentRepository
        from anvil.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            repo = ExperimentRepository(session)
            from datetime import datetime

            await repo.mark_finished(
                experiment_id=experiment_id,
                final_loss=final_loss,
                generated_samples=json.dumps(samples),
                completed_at=datetime.now(UTC),
            )

            experiment_model_path = MODELS_DIR / f"experiment_{experiment_id}.json"
            model.save(str(experiment_model_path), uchars)

            if mps_thread is not None:
                mps_thread.stop()

            await session.commit()

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
            if mps_thread is not None:
                mps_thread.stop()
            async with AsyncSessionLocal() as sess:
                from datetime import datetime

                from anvil.db.repositories.experiments import ExperimentRepository

                repo = ExperimentRepository(sess)
                await repo.mark_failed(
                    experiment_id=experiment_id,
                    error_message=str(exc),
                    completed_at=datetime.now(UTC),
                )
                await sess.commit()

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


@router.get("/training/stream/{run_id}")
async def stream_training(run_id: int):
    queue = svc.get_queue(run_id)
    if queue is None:
        raise HTTPException(status_code=404, detail="Run not found")

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
