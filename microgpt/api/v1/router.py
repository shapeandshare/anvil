"""Versioned API v1 router."""

import json
import random
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from microgpt.api.v1.corpora import router as corpora_router
from microgpt.api.v1.datasets import router as datasets_router
from microgpt.core.engine import GPT, softmax
from microgpt.api.v1.experiments import router as experiments_router
from microgpt.api.v1.training import router as training_router

router = APIRouter()
router.include_router(training_router)
router.include_router(experiments_router)
router.include_router(datasets_router)
router.include_router(corpora_router)

MODELS_DIR = Path("data/models")


_start_time: float = time.time()


@router.get("/health")
async def health():
    return {
        "status": "healthy",
        "version": "0.1.0",
        "uptime_seconds": int(time.time() - _start_time),
    }


@router.get("/services")
async def list_services(request: Request):
    mlflow = getattr(request.app.state, "mlflow", None)
    mlflow_status = "running" if mlflow and mlflow.is_running else "stopped"
    return {
        "services": [
            {"name": "web", "status": "running"},
            {"name": "mlflow", "status": mlflow_status, "port": 5000},
        ]
    }


@router.get("/services/logs/{name}")
async def get_service_logs(name: str, lines: int = 50):
    log_file = Path("logs") / f"{name}.log"
    if not log_file.exists():
        return {"logs": []}
    content = log_file.read_text().splitlines()
    return {"logs": content[-lines:]}


@router.post("/services/restart-all")
async def restart_all_services(request: Request):
    results = {}
    mlflow = getattr(request.app.state, "mlflow", None)
    if mlflow is not None:
        if mlflow.is_running:
            mlflow.stop()
        mlflow.start()
        results["mlflow"] = "restarted"
    else:
        results["mlflow"] = "not_initialized"
    results["web"] = "cannot_manage"
    return {"status": "ok", "results": results}


@router.post("/services/logs/{name}/clear")
async def clear_service_logs(name: str):
    log_file = Path("logs") / f"{name}.log"
    if log_file.exists():
        log_file.write_text("")
        return {"status": "cleared"}
    return {"status": "no_logs"}


@router.post("/services/{name}/start")
async def start_service(name: str, request: Request):
    if name == "web":
        raise HTTPException(status_code=400, detail="web server cannot be managed via API")
    if name == "mlflow":
        mlflow = getattr(request.app.state, "mlflow", None)
        if mlflow is None:
            raise HTTPException(status_code=500, detail="MLflow service not initialized")
        if mlflow.is_running:
            return {"status": "already_running"}
        mlflow.start()
        return {"status": "started"}
    raise HTTPException(status_code=404, detail=f"Unknown service: {name}")


@router.post("/services/{name}/stop")
async def stop_service(name: str, request: Request):
    if name == "web":
        raise HTTPException(status_code=400, detail="web server cannot be managed via API")
    if name == "mlflow":
        mlflow = getattr(request.app.state, "mlflow", None)
        if mlflow is None:
            raise HTTPException(status_code=500, detail="MLflow service not initialized")
        if not mlflow.is_running:
            return {"status": "already_stopped"}
        mlflow.stop()
        return {"status": "stopped"}
    raise HTTPException(status_code=404, detail=f"Unknown service: {name}")


@router.post("/services/{name}/restart")
async def restart_service(name: str, request: Request):
    if name == "web":
        raise HTTPException(status_code=400, detail="web server cannot be managed via API")
    if name == "mlflow":
        mlflow = getattr(request.app.state, "mlflow", None)
        if mlflow is None:
            raise HTTPException(status_code=500, detail="MLflow service not initialized")
        if mlflow.is_running:
            mlflow.stop()
        mlflow.start()
        return {"status": "restarted"}
    raise HTTPException(status_code=404, detail=f"Unknown service: {name}")


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return request.app.state.templates.TemplateResponse(
        request,
        "training.html",
    )


@router.get("/training-page", response_class=HTMLResponse)
async def training_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        request,
        "training.html",
    )


@router.get("/experiments-page", response_class=HTMLResponse)
async def experiments_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        request,
        "experiments.html",
    )


@router.get("/datasets-page", response_class=HTMLResponse)
async def datasets_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        request,
        "datasets.html",
    )


@router.get("/operations-page", response_class=HTMLResponse)
async def operations_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        request,
        "operations.html",
    )


@router.get("/inference-page", response_class=HTMLResponse)
async def inference_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        request,
        "inference.html",
    )


@router.get("/inference/models")
async def list_inference_models():
    from microgpt.db.session import AsyncSessionLocal
    from microgpt.db.models.training_config import Experiment
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Experiment).where(Experiment.status == "completed").order_by(Experiment.created_at.desc())
        )
        experiments = result.scalars().all()
        return {
            "models": [
                {
                    "id": e.id,
                    "final_loss": e.final_loss,
                    "created_at": str(e.created_at),
                }
                for e in experiments
            ]
        }


@router.post("/inference/sample")
async def inference_sample(body: dict):
    import random
    from microgpt.core.engine import GPT, softmax

    experiment_id = body.get("experiment_id")
    temperature = body.get("temperature", 0.5)
    num_samples = body.get("num_samples", 10)

    if experiment_id is None:
        raise HTTPException(status_code=400, detail="experiment_id required")

    model_path = MODELS_DIR / f"experiment_{experiment_id}.json"
    if not model_path.exists():
        raise HTTPException(status_code=404, detail="Model not found")

    with open(model_path) as f:
        data = json.load(f)

    chars = data.get("chars")
    if not chars:
        raise HTTPException(status_code=400, detail="Model has no character mapping")

    model = GPT(
        vocab_size=data["vocab_size"],
        n_embd=data["n_embd"],
        n_head=data["n_head"],
        n_layer=data["n_layer"],
        block_size=data["block_size"],
    )
    for k, mat_data in data["state_dict"].items():
        for i, row in enumerate(mat_data):
            for j, val in enumerate(row):
                model.state_dict[k][i][j].data = val

    BOS = len(chars)
    samples = []
    for _ in range(num_samples):
        keys = [[] for _ in range(model.n_layer)]
        values = [[] for _ in range(model.n_layer)]
        token_id = BOS
        sample = []
        for pos_id in range(model.block_size):
            logits = model.forward(token_id, pos_id, keys, values)
            scaled = [logit / temperature for logit in logits]
            probs = softmax(scaled)
            token_id = random.choices(
                range(model.vocab_size), weights=[p.data for p in probs]
            )[0]
            if token_id == BOS:
                break
            sample.append(chars[token_id])
        samples.append("".join(sample))

    return {"samples": samples}
