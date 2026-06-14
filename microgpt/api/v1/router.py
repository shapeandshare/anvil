"""Versioned API v1 router."""

import os
import random
import signal
import subprocess
import time
from pathlib import Path

import psutil
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from microgpt.api.v1.corpora import router as corpora_router
from microgpt.api.v1.datasets import router as datasets_router
from microgpt.api.v1.eval import router as eval_router
from microgpt.api.v1.eval_datasets import router as eval_datasets_router
from microgpt.api.v1.experiments import router as experiments_router
from microgpt.api.v1.inference import router as inference_router
from microgpt.api.v1.registry import router as registry_router
from microgpt.api.v1.training import router as training_router
from microgpt.core.engine import GPT, softmax
from microgpt.gpu import detect_gpu

router = APIRouter()
router.include_router(training_router)
router.include_router(experiments_router)
router.include_router(datasets_router)
router.include_router(corpora_router)
router.include_router(registry_router)
router.include_router(eval_router)
router.include_router(eval_datasets_router)
router.include_router(inference_router)

MODELS_DIR = Path("data/models")


_start_time: float = time.time()


@router.get("/health")
async def health():
    cpu_percent = psutil.cpu_percent(interval=0)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    gpu = detect_gpu()
    return {
        "status": "healthy",
        "version": "0.1.0",
        "uptime_seconds": int(time.time() - _start_time),
        "system": {
            "cpu_percent": cpu_percent,
            "memory_percent": mem.percent,
            "memory_used_gb": round(mem.used / (1024**3), 1),
            "memory_total_gb": round(mem.total / (1024**3), 1),
            "disk_percent": disk.percent,
            "disk_used_gb": round(disk.used / (1024**3), 1),
            "disk_total_gb": round(disk.total / (1024**3), 1),
        },
        "gpu": {
            "available": gpu.available,
            "backend": gpu.backend,
            "device_name": gpu.device_name,
            "memory_total_gb": gpu.memory_total_gb,
            "memory_available_gb": gpu.memory_available_gb,
            "compute_capability": gpu.compute_capability,
            "torch_version": gpu.torch_version,
            "cuda_version": gpu.cuda_version,
            "errors": gpu.errors,
        },
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
        raise HTTPException(
            status_code=400, detail="web server cannot be managed via API"
        )
    if name == "mlflow":
        mlflow = getattr(request.app.state, "mlflow", None)
        if mlflow is None:
            raise HTTPException(
                status_code=500, detail="MLflow service not initialized"
            )
        if mlflow.is_running:
            return {"status": "already_running"}
        mlflow.start()
        return {"status": "started"}
    raise HTTPException(status_code=404, detail=f"Unknown service: {name}")


@router.post("/services/{name}/stop")
async def stop_service(name: str, request: Request):
    if name == "web":
        raise HTTPException(
            status_code=400, detail="web server cannot be managed via API"
        )
    if name == "mlflow":
        mlflow = getattr(request.app.state, "mlflow", None)
        if mlflow is None:
            raise HTTPException(
                status_code=500, detail="MLflow service not initialized"
            )
        if not mlflow.is_running:
            return {"status": "already_stopped"}
        mlflow.stop()
        return {"status": "stopped"}
    raise HTTPException(status_code=404, detail=f"Unknown service: {name}")


@router.post("/services/{name}/restart")
async def restart_service(name: str, request: Request):
    if name == "web":
        raise HTTPException(
            status_code=400, detail="web server cannot be managed via API"
        )
    if name == "mlflow":
        mlflow = getattr(request.app.state, "mlflow", None)
        if mlflow is None:
            raise HTTPException(
                status_code=500, detail="MLflow service not initialized"
            )
        if mlflow.is_running:
            mlflow.stop()
        mlflow.start()
        return {"status": "restarted"}
    raise HTTPException(status_code=404, detail=f"Unknown service: {name}")


def _poll_port(port: int, timeout: float = 2.0) -> list[int]:
    """Repeatedly check if a port is free; return remaining PIDs after timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if not result.stdout.strip():
            return []
        time.sleep(0.3)
    return [int(pid) for pid in result.stdout.strip().split()]


@router.post("/services/{name}/kill-port")
async def kill_service_port(name: str, request: Request):
    SERVICE_PORTS = {"mlflow": 5000}
    port = SERVICE_PORTS.get(name)
    if port is None:
        raise HTTPException(
            status_code=404, detail=f"Unknown service or no port configured: {name}"
        )
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if not result.stdout.strip():
            return {"status": "port_free", "port": port, "killed": 0}
        pids = [int(pid) for pid in result.stdout.strip().split()]
        killed = 0
        for pid in pids:
            try:
                os.kill(pid, signal.SIGTERM)
                killed += 1
            except ProcessLookupError:
                pass
        survivors = _poll_port(port)
        for pid in survivors:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        return {"status": "killed", "port": port, "killed": killed}
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Timeout while scanning port")
    except FileNotFoundError:
        raise HTTPException(
            status_code=500, detail="lsof not found — cannot scan ports"
        )


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return request.app.state.templates.TemplateResponse(
        request,
        "archetypes/training.html",
    )


@router.get("/training-page", response_class=HTMLResponse)
async def training_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        request,
        "archetypes/training.html",
    )


@router.get("/experiments-page", response_class=HTMLResponse)
async def experiments_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        request,
        "archetypes/experiment.html",
    )


@router.get("/learn/graph", response_class=HTMLResponse)
async def graph_concept_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        request,
        "archetypes/graph.html",
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
        "archetypes/playground.html",
    )


LEARNING_ARC = [
    {
        "key": "tokenization",
        "title": "Tokenization",
        "path": "/v1/learn/tokenization",
        "desc": "How the model chops text into character tokens and maps them to IDs.",
    },
    {
        "key": "embeddings",
        "title": "Embeddings",
        "path": "/v1/learn/embeddings",
        "desc": "How each token ID becomes a dense vector the model can compute with.",
    },
    {
        "key": "attention",
        "title": "Attention",
        "path": "/v1/learn/attention",
        "desc": "How each token looks at its predecessors to build context-aware representations.",
    },
    {
        "key": "sampling",
        "title": "Sampling",
        "path": "/v1/learn/sampling",
        "desc": "How the model picks the next character from its probability distribution.",
    },
    {
        "key": "training-loop",
        "title": "Training Loop",
        "path": "/v1/learn/training-loop",
        "desc": "How the model learns by minimizing prediction error step by step.",
    },
]


def _arc_context(current_key: str) -> dict:
    """Build prev/next navigation context from LEARNING_ARC."""
    idx = next(
        (i for i, item in enumerate(LEARNING_ARC) if item["key"] == current_key), -1
    )
    return {
        "arc": LEARNING_ARC,
        "current_key": current_key,
        "current_index": idx,
        "prev": LEARNING_ARC[idx - 1] if idx > 0 else None,
        "next": LEARNING_ARC[idx + 1] if 0 <= idx < len(LEARNING_ARC) - 1 else None,
    }


TOKENIZATION_STEPS = [
    {
        "key": "what-is-a-token",
        "title": "What is a Token?",
        "body": (
            "This model works with individual characters as tokens. "
            "Not words, not subwords, just single characters. "
            "Type some text into the widget on the right and watch each character get highlighted. "
            "Every letter, space, and punctuation mark is one token."
        ),
        "widget": "tokenization",
    },
    {
        "key": "the-vocabulary",
        "title": "The Vocabulary",
        "body": (
            "The model builds its vocabulary from the sorted unique characters in the training data. "
            "If the data contains a, b, c, and space, those are all the character types it knows. "
            "The widget shows you the full vocabulary count (vocab_size). "
            "Notice there is one extra slot reserved for a special marker called BOS."
        ),
        "widget": "tokenization",
    },
    {
        "key": "token-ids",
        "title": "Token IDs",
        "body": (
            "Every character in the vocabulary gets a numeric ID: its index in the sorted list. "
            "The widget shows each character's ID next to it. "
            "The BOS marker always gets the highest ID (vocab_size - 1). "
            "The model never sees characters, only these integer IDs."
        ),
        "widget": "tokenization",
    },
    {
        "key": "bos-wrapping",
        "title": "BOS Wrapping",
        "body": (
            "Every sequence the model processes begins and ends with the BOS marker "
            "(Begin Of Sequence). The widget shows a highlighted BOS at both ends. "
            "BOS gives the model a fixed starting point so it knows when a sequence "
            "starts and when it ends. Try typing different text and watch the BOS bookends."
        ),
        "widget": "tokenization",
    },
    {
        "key": "from-text-to-numbers",
        "title": "From Text to Numbers",
        "body": (
            "Putting it all together: your text becomes a list of integers. "
            "The model receives [BOS, id_of_a, id_of_b, ..., BOS]. "
            "Each position in this sequence will get its own embedding in the next lesson. "
            "Type longer or shorter text and see how the token count changes."
        ),
        "widget": "tokenization",
    },
]

EMBEDDING_STEPS = [
    {
        "key": "what-is-an-embedding",
        "title": "What is an Embedding?",
        "body": (
            "A token ID is just an integer. The model needs a dense vector to compute with. "
            "It looks up each token ID in the WTE (Weight Token Embedding) matrix. "
            "This matrix has one row per token, each row is a 16-dimensional vector (n_embd = 16). "
            "Type some text and watch each character get mapped to its embedding vector."
        ),
        "widget": "embedding",
    },
    {
        "key": "position-matters",
        "title": "Position Matters",
        "body": (
            "The same character at different positions needs different representations. "
            "The letter 'e' at position 0 and position 5 mean different things. "
            "The model adds a position embedding (WPE) to each token embedding. "
            "WPE has one row per position up to block_size (16). "
            "The widget shows the final combined embedding after both are summed."
        ),
        "widget": "embedding",
    },
    {
        "key": "the-embedding-space",
        "title": "The Embedding Space",
        "body": (
            "Sixteen dimensions is hard to visualize. The widget projects these vectors "
            "down to 2D using PCA (Principal Component Analysis). "
            "Each dot is one character from your input, colored by its position. "
            "The spatial arrangement comes from the model's actual learned weights."
        ),
        "widget": "embedding",
    },
    {
        "key": "similarity-in-space",
        "title": "Similarity in Space",
        "body": (
            "Dots that are close together in the 2D projection have similar "
            "combined embeddings. Dots far apart are different. "
            "Characters that often appear in similar contexts may cluster together. "
            "This is the model's geometric view of your text."
        ),
        "widget": "embedding",
    },
    {
        "key": "type-and-explore",
        "title": "Type and Explore",
        "body": (
            "Try typing different words and phrases. "
            "Notice how the cloud of points shifts as each character gets its own "
            "token embedding plus a position offset. "
            "These combined embeddings are what flow into the attention mechanism next."
        ),
        "widget": "embedding",
    },
]

ATTENTION_STEPS = [
    {
        "key": "what-is-attention",
        "title": "What is Attention?",
        "body": (
            "Attention helps each token build a representation by looking at itself "
            "and every token that came before it. Type some text, then use the left and right "
            "arrow keys to pick a token. The heatmap will show how strongly that token "
            "focuses on each earlier token. Brighter means stronger attention."
        ),
        "widget": "attention",
    },
    {
        "key": "how-attention-is-computed",
        "title": "How Attention is Computed",
        "body": (
            "At each position, the model computes three vectors: Query (what am I looking for), "
            "Key (what do I contain), and Value (what info do I carry). "
            "It takes the dot product of the current token's Query with every earlier token's Key. "
            "Those scores go through softmax to become attention weights (0 to 1, summing to 1)."
        ),
        "widget": "attention",
    },
    {
        "key": "lower-triangular-pattern",
        "title": "Lower-Triangular Pattern",
        "body": (
            "Notice the heatmap is lower-triangular: each token only attends to itself "
            "and tokens before it. The model never looks at future tokens that would leak "
            "information it should predict. Navigate between tokens with arrow keys and watch "
            "how each row only covers positions <= its own index."
        ),
        "widget": "attention",
    },
    {
        "key": "multi-head-attention",
        "title": "Multi-Head Attention",
        "body": (
            "This model has 4 attention heads running in parallel (n_head = 4). "
            "Each head learns a different relationship pattern. "
            "One head might focus on the previous character, another on the start of a word. "
            "Use the head selector to switch between heads and compare patterns."
        ),
        "widget": "attention",
    },
    {
        "key": "explore-different-input",
        "title": "Explore Different Input",
        "body": (
            "Type completely different text and watch the attention patterns change. "
            "The weights reflect what the model has learned from its training data. "
            "Experiment with short words, repeated characters, and punctuation. "
            "Each input produces a unique attention signature."
        ),
        "widget": "attention",
    },
]

SAMPLING_STEPS = [
    {
        "key": "from-logits-to-probabilities",
        "title": "From Logits to Probabilities",
        "body": (
            "After processing all tokens, the model outputs logits: raw scores for every "
            "character in the vocabulary. Higher logit = the model thinks that character "
            "is more likely next. The widget shows these as a bar chart. "
            "Softmax converts logits into probabilities that sum to 1."
        ),
        "widget": "sampling",
    },
    {
        "key": "temperature",
        "title": "Temperature",
        "body": (
            "Temperature scales the logits before softmax. Low temperature (near 0) "
            "makes the distribution peaky: the most likely character dominates. "
            "High temperature (1.0+) flattens the distribution: all characters become "
            "more equally likely. Move the temperature slider and watch the bars reshape."
        ),
        "widget": "sampling",
    },
    {
        "key": "top-k-sampling",
        "title": "Top-K Sampling",
        "body": (
            "Top-K restricts sampling to the K most probable characters. "
            "The probability mass is redistributed only among those K. "
            "K = 1 is greedy decoding (always pick the most likely). "
            "K = vocab_size uses the full distribution. "
            "Adjust the top-K slider and see which characters get cut off."
        ),
        "widget": "sampling",
    },
    {
        "key": "reading-the-distribution",
        "title": "Reading the Distribution",
        "body": (
            "Each bar is one character from the vocabulary. "
            "Tall bar = the model is confident that character comes next. "
            "Short or missing bar = the model considers that unlikely. "
            "The widget labels each bar with the character and its probability. "
            "Notice how only a handful of characters get meaningful probability."
        ),
        "widget": "sampling",
    },
    {
        "key": "sampling-in-practice",
        "title": "Sampling in Practice",
        "body": (
            "Temperature and top-K work together. Try temperature 0.5 with top-K 5 "
            "for moderately focused sampling. Then try temperature 1.5 with top-K 20 "
            "for more diverse outputs. The bars update in real time as you adjust. "
            "This is the same sampling used when generating text in the Playground."
        ),
        "widget": "sampling",
    },
]

TRAINING_LOOP_STEPS = [
    {
        "key": "what-is-training",
        "title": "What is Training?",
        "body": (
            "Training adjusts all model parameters to make better predictions. "
            "At each step: the model reads a sequence, predicts tokens one by one, "
            "measures how wrong it was (loss), and nudges every parameter to reduce that error. "
            "The widget shows a loss curve from a real training run. "
            "Scrub through it to watch the model improve."
        ),
        "widget": "trainingLoop",
    },
    {
        "key": "the-loss-curve",
        "title": "The Loss Curve",
        "body": (
            "Loss quantifies prediction error: how surprised the model is by the actual next "
            "character. A decreasing curve means the model is learning patterns in the data. "
            "Early steps have high loss (the model is guessing blindly). "
            "Later steps have lower loss as the model picks up character-level patterns. "
            "Drag the scrubber to see loss at any point in training."
        ),
        "widget": "trainingLoop",
    },
    {
        "key": "what-loss-tells-you",
        "title": "What Loss Tells You",
        "body": (
            "The shape of the curve reveals training quality. A smooth downward slope "
            "means stable learning. Plateaus suggest the model needs more capacity or "
            "different hyperparameters. Spikes or oscillations may mean the learning rate "
            "is too high. Compare curves from different experiments to build intuition."
        ),
        "widget": "trainingLoop",
    },
    {
        "key": "gradient-descent",
        "title": "Gradient Descent",
        "body": (
            "The optimizer (Adam) computes gradients for every parameter and updates them "
            "in the direction that reduces loss. The learning rate controls step size: "
            "too small = painfully slow progress, too big = overshooting and divergence. "
            "This model uses linear learning rate decay: lr_t = lr * (1 - step/num_steps)."
        ),
        "widget": "trainingLoop",
    },
    {
        "key": "training-to-generation",
        "title": "Training to Generation",
        "body": (
            "A trained model generates new text character by character: "
            "it predicts the next char, samples it (using the sampling lesson's techniques), "
            "feeds it back as input, and repeats. Better loss = more coherent output. "
            "If no training run exists yet, the widget will prompt you to go Train a model. "
            "When you do, return here to see your own loss curve."
        ),
        "widget": "trainingLoop",
    },
]


@router.get("/learn", response_class=HTMLResponse)
async def learn_index(request: Request):
    return request.app.state.templates.TemplateResponse(
        request,
        "archetypes/learn-index.html",
        {"arc": LEARNING_ARC},
    )


@router.get("/learn/attention", response_class=HTMLResponse)
async def attention_concept_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        request,
        "archetypes/concept.html",
        {"steps": ATTENTION_STEPS, **_arc_context("attention")},
    )


@router.get("/learn/tokenization", response_class=HTMLResponse)
async def tokenization_concept_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        request,
        "archetypes/concept.html",
        {"steps": TOKENIZATION_STEPS, **_arc_context("tokenization")},
    )


@router.get("/learn/embeddings", response_class=HTMLResponse)
async def embeddings_concept_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        request,
        "archetypes/concept.html",
        {"steps": EMBEDDING_STEPS, **_arc_context("embeddings")},
    )


@router.get("/learn/sampling", response_class=HTMLResponse)
async def sampling_concept_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        request,
        "archetypes/concept.html",
        {"steps": SAMPLING_STEPS, **_arc_context("sampling")},
    )


@router.get("/learn/training-loop", response_class=HTMLResponse)
async def training_loop_concept_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        request,
        "archetypes/concept.html",
        {"steps": TRAINING_LOOP_STEPS, **_arc_context("training-loop")},
    )


@router.get("/models-page", response_class=HTMLResponse)
async def models_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        request,
        "archetypes/models.html",
    )


@router.get("/model-detail/{model_id}", response_class=HTMLResponse)
async def model_detail_page(request: Request, model_id: int):
    return request.app.state.templates.TemplateResponse(
        request,
        "archetypes/model_detail.html",
        {"model_id": model_id},
    )


@router.get("/inference/models")
async def list_inference_models():
    from microgpt.db.repositories.models import ModelRepository
    from microgpt.db.session import AsyncSessionLocal
    from microgpt.services.models import ModelRegistryService

    async with AsyncSessionLocal() as session:
        repo = ModelRepository(session)
        svc = ModelRegistryService(repo)
        models = await svc.get_inference_models()
        if not models:
            return {
                "models": [],
                "message": "No models registered. Train an experiment and register it first.",
            }
        return {"models": models}


@router.post("/inference/sample")
async def inference_sample(body: dict):
    from microgpt.core.autograd import Value

    model_id = body.get("model_id")
    version = body.get("version")
    temperature = body.get("temperature", 0.5)
    num_samples = body.get("num_samples", 10)
    prompt = body.get("prompt", "")
    top_k = body.get("top_k")
    top_p = body.get("top_p")

    if model_id is None or version is None:
        raise HTTPException(status_code=400, detail="model_id and version required")

    if top_k is not None:
        if not isinstance(top_k, int) or top_k <= 0:
            raise HTTPException(
                status_code=400, detail="top_k must be a positive integer"
            )

    if top_p is not None:
        if not isinstance(top_p, (int, float)) or top_p <= 0.0 or top_p > 1.0:
            raise HTTPException(
                status_code=400,
                detail="top_p must be a float in the range (0.0, 1.0]",
            )

    from microgpt.db.repositories.models import ModelRepository
    from microgpt.db.session import AsyncSessionLocal
    from microgpt.services.models import ModelRegistryService

    async with AsyncSessionLocal() as session:
        repo = ModelRepository(session)
        svc = ModelRegistryService(repo)
        v = await svc.get_version(model_id, version)

    if v is None:
        raise HTTPException(
            status_code=404, detail="Model version not found in registry"
        )

    model_path = Path(v["artifact_path"])
    if not model_path.exists():
        raise HTTPException(status_code=404, detail="Model artifact not found")

    model = GPT.load(str(model_path))
    chars = model.chars
    if not chars:
        raise HTTPException(status_code=400, detail="Model has no character mapping")

    BOS = len(chars)
    prompt_ids = []
    if prompt and isinstance(prompt, str) and len(prompt) > 0:
        try:
            prompt_ids = [BOS] + [chars.index(ch) for ch in prompt]
        except ValueError as err:
            bad_char = next(ch for ch in prompt if ch not in chars)
            raise HTTPException(
                status_code=400,
                detail=f"Character {bad_char!r} not in model vocabulary",
            ) from err
        prompt_ids = prompt_ids[: model.block_size]

    def apply_top_k(scaled, top_k_val, vocab_size):
        if top_k_val <= 0 or top_k_val >= vocab_size:
            return scaled
        sorted_vals = sorted(scaled, key=lambda v: v.data, reverse=True)
        threshold = sorted_vals[top_k_val - 1].data
        return [v if v.data >= threshold else Value(-1e10) for v in scaled]

    def apply_top_p(scaled, top_p_val):
        if top_p_val <= 0.0 or top_p_val >= 1.0:
            return scaled
        sorted_vals = sorted(scaled, key=lambda v: v.data, reverse=True)
        sorted_probs = softmax(sorted_vals)
        cumsum = 0.0
        cutoff_idx = 0
        for i, p in enumerate(sorted_probs):
            cumsum += p.data
            if cumsum >= top_p_val:
                cutoff_idx = i
                break
        else:
            cutoff_idx = len(sorted_vals) - 1
        threshold = sorted_vals[cutoff_idx].data
        return [v if v.data >= threshold else Value(-1e10) for v in scaled]

    samples = []
    for _ in range(num_samples):
        keys = [[] for _ in range(model.n_layer)]
        values = [[] for _ in range(model.n_layer)]

        if prompt_ids:
            logits = model.forward(prompt_ids[0], 0, keys, values)
            for pos_id in range(1, len(prompt_ids)):
                logits = model.forward(prompt_ids[pos_id], pos_id, keys, values)
            sample = [chars[idx] for idx in prompt_ids[1:]]
            for pos_id in range(len(prompt_ids), model.block_size):
                scaled = [logit / temperature for logit in logits]
                if top_k is not None:
                    scaled = apply_top_k(scaled, top_k, model.vocab_size)
                if top_p is not None:
                    scaled = apply_top_p(scaled, top_p)
                probs = softmax(scaled)
                token_id = random.choices(
                    range(model.vocab_size), weights=[p.data for p in probs]
                )[0]
                if token_id == BOS:
                    break
                sample.append(chars[token_id])
                if pos_id < model.block_size - 1:
                    logits = model.forward(token_id, pos_id, keys, values)
        else:
            token_id = BOS
            sample = []
            for pos_id in range(model.block_size):
                logits = model.forward(token_id, pos_id, keys, values)
                scaled = [logit / temperature for logit in logits]
                if top_k is not None:
                    scaled = apply_top_k(scaled, top_k, model.vocab_size)
                if top_p is not None:
                    scaled = apply_top_p(scaled, top_p)
                probs = softmax(scaled)
                token_id = random.choices(
                    range(model.vocab_size), weights=[p.data for p in probs]
                )[0]
                if token_id == BOS:
                    break
                sample.append(chars[token_id])

        samples.append("".join(sample))

    return {"samples": samples}
