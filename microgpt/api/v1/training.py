import asyncio
import json
import os
import tempfile
from pathlib import Path

import mlflow.entities
from fastapi import APIRouter, HTTPException
from mlflow.tracking import MlflowClient
from starlette.responses import StreamingResponse

from microgpt.services.training import TrainingService

router = APIRouter()
svc = TrainingService()
_tasks: set[asyncio.Task] = set()
MODELS_DIR = Path("data/models")
MODELS_DIR.mkdir(parents=True, exist_ok=True)

MLFLOW_TRACKING_URI = "sqlite:///./mlruns/mlflow.db"
MLFLOW_EXPERIMENT_NAME = "microgpt-workbench"


def _get_mlflow_client() -> MlflowClient:
    return MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)


def _get_or_create_experiment() -> str:
    client = _get_mlflow_client()
    exp = client.get_experiment_by_name(MLFLOW_EXPERIMENT_NAME)
    if exp:
        return exp.experiment_id
    return client.create_experiment(MLFLOW_EXPERIMENT_NAME)


@router.post("/training/start")
async def start_training(config: dict):
    run_id = svc.reserve_run()
    exp_id = _get_or_create_experiment()
    mlflow_run = _get_mlflow_client().create_run(exp_id)
    mlflow_run_id = mlflow_run.info.run_id

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
        "corpus_id": corpus_id,
        "dataset_id": dataset_id,
    }
    _get_mlflow_client().log_batch(
        run_id=mlflow_run_id,
        params=[mlflow.entities.Param(k, str(v)) for k, v in hyperparams.items()],
    )

    def mlflow_progress_callback(step: int, loss: float) -> None:
        try:
            _get_mlflow_client().log_metric(mlflow_run_id, "loss", loss, step=step)
        except Exception:
            pass

    async def on_complete(model, config: dict, final_loss: float, samples: list[str], uchars: list[str]):
        client = _get_mlflow_client()
        client.log_metric(mlflow_run_id, "final_loss", final_loss)

        with tempfile.TemporaryDirectory() as tmpdir:
            samples_path = os.path.join(tmpdir, "samples.txt")
            with open(samples_path, "w") as f:
                f.write("\n".join(samples))
            client.log_artifact(mlflow_run_id, samples_path)

            model_path = os.path.join(tmpdir, "model.json")
            model.save(model_path, uchars)
            client.log_artifact(mlflow_run_id, model_path)

        client.set_terminated(mlflow_run_id)

        from microgpt.db.session import AsyncSessionLocal
        from microgpt.db.models.training_config import Experiment, TrainingConfig

        async with AsyncSessionLocal() as session:
            training_config = TrainingConfig(**{k: v for k, v in hyperparams.items() if v is not None or k not in ("corpus_id", "dataset_id")})
            session.add(training_config)
            await session.flush()
            await session.refresh(training_config)

            exp = Experiment(
                status="completed",
                config_id=training_config.id,
                final_loss=final_loss,
                generated_samples=json.dumps(samples),
                mlflow_run_id=mlflow_run_id,
            )
            session.add(exp)
            await session.flush()
            await session.refresh(exp)

            # Persist model artifact for registry access
            experiment_model_path = MODELS_DIR / f"experiment_{exp.id}.json"
            model.save(str(experiment_model_path), uchars)

            await session.commit()

    task = asyncio.create_task(
        svc.start_training(config, run_id, on_complete=on_complete, progress_callback_override=mlflow_progress_callback)
    )
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return {"run_id": run_id, "mlflow_run_id": mlflow_run_id, "status": "started"}


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
    from microgpt.db.session import AsyncSessionLocal
    from microgpt.db.models.training_config import TrainingConfig
    from sqlalchemy import select

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
    return {"status": "stopped"}
