"""Versioned API v1 router.

Aggregates all sub-routers (training, experiments, datasets, corpora, registry,
eval, eval_datasets, inference, compute) under a single ``APIRouter`` instance.
Also provides service management endpoints, HTML page rendering routes, and
learning-content data structures (``LEARNING_ARC``, step constants).
"""

import os
import random
import signal
import subprocess
import time
from pathlib import Path

import psutil
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from anvil import __version__ as anvil_version
from anvil.api.v1.compute import router as compute_router
from anvil.api.v1.corpora import router as corpora_router
from anvil.api.v1.datasets import router as datasets_router
from anvil.api.v1.eval import router as eval_router
from anvil.api.v1.eval_datasets import router as eval_datasets_router
from anvil.api.v1.experiments import router as experiments_router
from anvil.api.v1.inference import router as inference_router
from anvil.api.v1.registry import router as registry_router
from anvil.api.v1.training import router as training_router
from anvil.config import get_config, get_mlflow_browser_uri
from anvil.core.engine import softmax
from anvil.gpu import detect_gpu

router = APIRouter()
router.include_router(training_router)
router.include_router(experiments_router)
router.include_router(datasets_router)
router.include_router(corpora_router)
router.include_router(registry_router)
router.include_router(eval_router)
router.include_router(eval_datasets_router)
router.include_router(inference_router)
router.include_router(compute_router)

MODELS_DIR = Path("data/models")
"""Path: Directory where trained model artifacts are stored on disk."""


_start_time: float = time.time()
"""float: Unix timestamp (epoch seconds) when the server process started."""


@router.get("/health")
async def health():
    """Return system health status including CPU, memory, disk, and GPU.

    Returns
    -------
    dict
        ``status``, ``version``, ``uptime_seconds``, ``system`` metrics and
        ``gpu`` details.
    """
    cpu_percent = psutil.cpu_percent(interval=0)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    gpu = detect_gpu()
    return {
        "status": "healthy",
        "version": anvil_version,
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
    """List available services and their status.

    Parameters
    ----------
    request : Request
        The incoming HTTP request.

    Returns
    -------
    dict
        List of service dicts with ``name``, ``status``, ``port``, and
        ``mlflow_url`` where applicable.
    """
    mlflow = getattr(request.app.state, "mlflow", None)
    if mlflow is None:
        mlflow_status = (
            "external" if get_config()["mlflow_disable_local"] else "stopped"
        )
    else:
        mlflow_status = "running" if mlflow.is_running else "stopped"
    return {
        "services": [
            {"name": "web", "status": "running"},
            {
                "name": "mlflow",
                "status": mlflow_status,
                "port": get_config()["mlflow_port"],
                "mlflow_url": get_mlflow_browser_uri(request),
            },
        ]
    }


@router.get("/services/logs/{name}")
async def get_service_logs(name: str, lines: int = 50):
    """Retrieve the last N lines of a service log file.

    Parameters
    ----------
    name : str
        Service name (e.g. ``"web"``, ``"mlflow"``).
    lines : int, optional
        Number of log lines to return. Defaults to ``50``.

    Returns
    -------
    dict
        ``logs`` list of log line strings.
    """
    log_file = Path("logs") / f"{name}.log"
    if not log_file.exists():
        return {"logs": []}
    content = log_file.read_text().splitlines()
    return {"logs": content[-lines:]}


@router.post("/services/restart-all")
async def restart_all_services(request: Request):
    """Restart all managed services (MLflow).

    Parameters
    ----------
    request : Request
        The incoming HTTP request.

    Returns
    -------
    dict
        Status and per-service restart results.
    """
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
    """Clear a service's log file by truncating it.

    Parameters
    ----------
    name : str
        Service name.

    Returns
    -------
    dict
        ``status`` set to ``"cleared"`` or ``"no_logs"``.
    """
    log_file = Path("logs") / f"{name}.log"
    if log_file.exists():
        log_file.write_text("")
        return {"status": "cleared"}
    return {"status": "no_logs"}


@router.post("/services/{name}/start")
async def start_service(name: str, request: Request):
    """Start a managed service by name.

    Parameters
    ----------
    name : str
        Service name (``"mlflow"`` supported).
    request : Request
        The incoming HTTP request.

    Returns
    -------
    dict
        Status indicating the result of the start operation.

    Raises
    ------
    HTTPException
        If the service is the web server (400), not initialized (500),
        or unknown (404).
    """
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
    """Stop a managed service by name.

    Parameters
    ----------
    name : str
        Service name (``"mlflow"`` supported).
    request : Request
        The incoming HTTP request.

    Returns
    -------
    dict
        Status indicating the result of the stop operation.

    Raises
    ------
    HTTPException
        If the service is the web server (400), not initialized (500),
        or unknown (404).
    """
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
    """Restart a managed service by name.

    Parameters
    ----------
    name : str
        Service name (``"mlflow"`` supported).
    request : Request
        The incoming HTTP request.

    Returns
    -------
    dict
        Status indicating the result of the restart operation.

    Raises
    ------
    HTTPException
        If the service is the web server (400), not initialized (500),
        or unknown (404).
    """
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
    """Repeatedly check if a port is free; return remaining PIDs after timeout.

    Parameters
    ----------
    port : int
        The port number to check.
    timeout : float, optional
        Maximum time in seconds to wait for the port to become free.
        Defaults to ``2.0``.

    Returns
    -------
    list[int]
        List of remaining PID(s) still listening on the port, or empty
        list if the port became free.
    """
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
    """Kill all processes listening on a service's port.

    Uses ``lsof`` to find processes, sends ``SIGTERM``, polls for cleanup,
    then sends ``SIGKILL`` to any survivors.

    Parameters
    ----------
    name : str
        Service name (``"mlflow"`` supported).
    request : Request
        The incoming HTTP request.

    Returns
    -------
    dict
        ``status``, ``port``, and ``killed`` count.

    Raises
    ------
    HTTPException
        If the service has no configured port (404), ``lsof`` not found
        (500), or port scanning times out (500).
    """
    SERVICE_PORTS = {"mlflow": get_config()["mlflow_port"]}
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
    """Render the root training dashboard page.

    Parameters
    ----------
    request : Request
        The incoming HTTP request.

    Returns
    -------
    HTMLResponse
        Rendered ``archetypes/training.html`` template.
    """
    return request.app.state.templates.TemplateResponse(
        request,
        "archetypes/training.html",
    )


@router.get("/training-page", response_class=HTMLResponse)
async def training_page(request: Request):
    """Render the training configuration and control page.

    Parameters
    ----------
    request : Request
        The incoming HTTP request.

    Returns
    -------
    HTMLResponse
        Rendered ``archetypes/training.html`` template.
    """
    return request.app.state.templates.TemplateResponse(
        request,
        "archetypes/training.html",
    )


@router.get("/experiments-page", response_class=HTMLResponse)
async def experiments_page(request: Request):
    """Render the experiment history and comparison page.

    Parameters
    ----------
    request : Request
        The incoming HTTP request.

    Returns
    -------
    HTMLResponse
        Rendered ``archetypes/experiment.html`` template.
    """
    return request.app.state.templates.TemplateResponse(
        request,
        "archetypes/experiment.html",
    )


@router.get("/learn/graph", response_class=HTMLResponse)
async def graph_concept_page(request: Request):
    """Render the interactive forward pass computation graph page.

    Parameters
    ----------
    request : Request
        The incoming HTTP request.

    Returns
    -------
    HTMLResponse
        Rendered ``archetypes/graph.html`` template with arc context.
    """
    return request.app.state.templates.TemplateResponse(
        request,
        "archetypes/graph.html",
        _arc_context("graph"),
    )


@router.get("/datasets-page", response_class=HTMLResponse)
async def datasets_page(request: Request):
    """Render the dataset management page.

    Parameters
    ----------
    request : Request
        The incoming HTTP request.

    Returns
    -------
    HTMLResponse
        Rendered ``datasets.html`` template.
    """
    return request.app.state.templates.TemplateResponse(
        request,
        "datasets.html",
    )


@router.get("/operations-page", response_class=HTMLResponse)
async def operations_page(request: Request):
    """Render the service operations and management page.

    Parameters
    ----------
    request : Request
        The incoming HTTP request.

    Returns
    -------
    HTMLResponse
        Rendered ``operations.html`` template.
    """
    return request.app.state.templates.TemplateResponse(
        request,
        "operations.html",
    )


@router.get("/inference-page", response_class=HTMLResponse)
async def inference_page(request: Request):
    """Render the model inference/sampling playground page.

    Parameters
    ----------
    request : Request
        The incoming HTTP request.

    Returns
    -------
    HTMLResponse
        Rendered ``archetypes/playground.html`` template.
    """
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
        "key": "parameters",
        "title": "Parameters",
        "path": "/v1/learn/parameters",
        "desc": "Where the model's ~4K parameters live and what each matrix does.",
    },
    {
        "key": "autograd",
        "title": "Autograd",
        "path": "/v1/learn/autograd",
        "desc": "How gradients flow backward through the computation graph to train the model.",
    },
    {
        "key": "attention",
        "title": "Attention",
        "path": "/v1/learn/attention",
        "desc": "How each token looks at its predecessors to build context-aware representations.",
    },
    {
        "key": "loss",
        "title": "Cross-Entropy Loss",
        "path": "/v1/learn/loss",
        "desc": "How prediction error is measured and what the loss number means.",
    },
    {
        "key": "sampling",
        "title": "Sampling",
        "path": "/v1/learn/sampling",
        "desc": "How the model picks the next character from its probability distribution.",
    },
    {
        "key": "adam",
        "title": "Adam Optimizer",
        "path": "/v1/learn/adam",
        "desc": "How momentum and adaptive learning rates make training converge faster.",
    },
    {
        "key": "training-loop",
        "title": "Training Loop",
        "path": "/v1/learn/training-loop",
        "desc": "How the model learns by minimizing prediction error step by step.",
    },
    {
        "key": "architecture",
        "title": "Architecture",
        "path": "/v1/learn/architecture",
        "desc": "The full Llama decoder stack — RoPE, RMSNorm, SwiGLU — visualized end to end.",
    },
    {
        "key": "graph",
        "title": "Forward Pass",
        "path": "/v1/learn/graph",
        "desc": "Scrub through the Llama forward pass step by step on an interactive computation graph.",
    },
    {
        "key": "data-flow",
        "title": "Data Flow",
        "path": "/v1/learn/data-flow",
        "desc": "How a training request travels from browser to engine and back via SSE.",
    },
    {
        "key": "export",
        "title": "Model Export",
        "path": "/v1/learn/export",
        "desc": "How trained models are exported to safetensors for HuggingFace compatibility.",
    },
    {
        "key": "faq",
        "title": "FAQ",
        "path": "/v1/learn/faq",
        "desc": "Frequently asked questions about how anvil works and what it can do.",
    },
    {
        "key": "cloud-compute",
        "title": "Training in the Cloud",
        "path": "/v1/learn/cloud-compute",
        "desc": "Run training on external compute with Modal, Modal GPUs, MLflow artifact sync, and the submitted/poll/complete lifecycle.",
    },
]


def _arc_context(current_key: str) -> dict:
    """Build prev/next navigation context from ``LEARNING_ARC``.

    Parameters
    ----------
    current_key : str
        The key of the current learning module (e.g. ``"tokenization"``).

    Returns
    -------
    dict
        ``arc`` (full list), ``current_key``, ``current_index``,
        ``prev`` (previous module dict or None), and ``next`` (next
        module dict or None).
    """
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
    {
        "key": "tokenizer-vocabulary-classes",
        "title": "Tokenizer vs Vocabulary",
        "body": (
            "anvil has two classes for this. Tokenizer (anvil/core/tokenizer.py) "
            "builds its vocabulary from training documents at construction time. "
            "Vocabulary is reconstructable from a saved chars list — it is what "
            "gets loaded for inference when you register and reload a model. "
            "Both produce identical encode/decode semantics (BOS-wrapped, "
            "same vocab_size calculation, same char-to-id mapping). "
            "The saved model stores its chars list so it can be reloaded "
            "without the original training data."
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
            "Rather than adding a learned position embedding, this model uses RoPE "
            "(Rotary Position Embedding): it rotates the Query and Key vectors by an "
            "angle that depends on the token's position. Position information is encoded "
            "in the direction of these vectors, not added to the token embedding."
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
            "token embedding. Position is encoded via RoPE inside the attention "
            "mechanism, not added to the embedding itself — the widget shows the "
            "pure token embeddings before attention applies position-dependent rotation."
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
            "Position is encoded via RoPE: the Query and Key vectors are rotated by an "
            "angle proportional to their position before the dot product. "
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
    {
        "key": "residual-connections",
        "title": "Residual Connections",
        "body": (
            "After attention, the original input is added back to the output: "
            'output = attention(x) + x. This "add-back" pattern creates a gradient highway '
            "that lets signals flow directly through the network without vanishing or exploding. "
            "Without residuals, deeper models would struggle to learn because gradients "
            "would decay to zero through many layers."
        ),
    },
    {
        "key": "rmsnorm",
        "title": "RMSNorm Explained",
        "body": (
            "Before attention, the model normalises activations with RMSNorm. "
            "Given input values x, it computes RMS = sqrt(mean(x squared)), then scales by "
            "a learned parameter: output = x / RMS. Unlike LayerNorm, RMSNorm does not "
            "subtract the mean — it only divides by the root-mean-square. This is simpler, "
            "faster, and works well for transformer training."
        ),
    },
    {
        "key": "kv-cache-mechanics",
        "title": "KV Cache Mechanics",
        "body": (
            "During autoregressive generation, the model caches Key and Value vectors "
            "for every previous position instead of recomputing them. At each new position, "
            "it computes Q, K, V for the current token, appends K and V to per-layer lists, "
            "then attends to all cached positions. This turns O(n) into O(n) per step. "
            "An important detail: Keys are rotated by RoPE BEFORE caching — each key is "
            "rotated exactly once at its position and never double-rotated. Values are "
            "not rotated (they carry absolute content, not relative position)."
        ),
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
            "The widget below shows the loss curve from your training runs. "
            "If you haven't trained a model yet, head to the "
            '<a href="/v1/training-page" class="action-link">Training Dashboard</a> '
            "first — then come back here to inspect the results."
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
            "Select a finished experiment above and drag the scrubber to see loss at any point."
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
            "is too high. Compare curves from different experiments using the selector above."
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
            "This model uses linear learning rate decay: lr_t = lr * (1 - step/num_steps). "
            "The scrubber below lets you step through the gradient updates at each point."
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
            "No experiments yet? "
            '<a href="/v1/training-page" class="action-link">Go train a model</a> '
            "to populate the loss curve above — then use the selector to switch between runs."
        ),
        "widget": "trainingLoop",
    },
    {
        "key": "dual-backend",
        "title": "CPU vs GPU Training",
        "body": (
            "anvil has two training backends with identical Llama architecture. "
            "The CPU backend uses pure Python (zero dependencies) with a custom "
            "Value autograd graph. The GPU backend uses PyTorch tensors for "
            "10-100x speed on CUDA or MPS. Switching between them is transparent: "
            "TrainingService resolves the device and dispatches automatically. "
            "GPU-trained weights are bridged back into a CPU LlamaModel via "
            "_load_weights_into_model(), so downstream code never knows which "
            "backend ran. See the Architecture reference for details."
        ),
        "widget": "trainingLoop",
    },
]

LOSS_STEPS = [
    {
        "key": "what-is-loss",
        "title": "What is Loss?",
        "body": (
            "Loss measures how wrong the model's predictions are. For each token, "
            "the model outputs a probability distribution over the vocabulary. "
            "If the correct next token gets probability 0.1, the loss is higher "
            "than if it gets 0.9. The widget shows the running loss as training progresses."
        ),
        "widget": "loss",
    },
    {
        "key": "cross-entropy",
        "title": "Cross-Entropy",
        "body": (
            "Cross-entropy loss is defined as -log(p(target)), where p(target) is "
            "the probability the model assigned to the correct next token. "
            "If p(target) = 1.0 (perfect prediction), loss = 0. "
            "If p(target) = 0.5, loss ≈ 0.69. The widget shows this value "
            "for the current training step."
        ),
        "widget": "loss",
    },
    {
        "key": "softmax-connection",
        "title": "Softmax Connection",
        "body": (
            "The model's raw output is logits — unnormalised scores. Softmax converts "
            "them into probabilities that sum to 1.0. The loss is computed from those "
            "probabilities, not from the logits directly. The widget shows the softmax "
            "output for the current batch and highlights p(target)."
        ),
        "widget": "loss",
    },
    {
        "key": "reading-the-curve",
        "title": "Reading the Curve",
        "body": (
            "A smooth downward slope means stable learning — the model is consistently "
            "making better predictions. Plateaus suggest the model needs more capacity "
            "(more parameters) or a different learning rate regime. "
            "The widget annotates each region of the curve with what it indicates."
        ),
        "widget": "loss",
    },
    {
        "key": "the-baseline",
        "title": "The Baseline",
        "body": (
            "Random guessing for a vocabulary of 27 characters (26 letters + BOS) "
            "gives p = 1/27 for each token, so loss = -log(1/27) ≈ 3.3. "
            "If your training loss is above 3.3, the model hasn't even reached "
            "random guessing yet. The widget marks the baseline on the loss curve."
        ),
        "widget": "loss",
    },
]

PARAMS_STEPS = [
    {
        "key": "where-params-live",
        "title": "Where Parameters Live",
        "body": (
            "All model parameters live in a state_dict: a dictionary of PyTorch-like "
            "tensors accessible via model.state_dict(). Each key is a layer name, "
            "each value is a weight matrix. The widget loads the most recent model's "
            "state_dict and shows every parameter with its shape and value range."
        ),
        "widget": "params",
    },
    {
        "key": "token-embeddings",
        "title": "Token Embeddings (WTE)",
        "body": (
            "WTE (Weight Token Embedding) is a matrix of shape vocab_size x n_embd. "
            "Each of the 27 tokens gets one 16-dimensional vector. "
            "These are the learned representations that turn token IDs into dense vectors. "
            "The widget highlights the WTE entry and shows a few rows of values."
        ),
        "widget": "params",
    },
    {
        "key": "rope-position",
        "title": "RoPE (Position Encoding)",
        "body": (
            "This model uses Rotary Position Embedding (RoPE) instead of learned "
            "position embeddings. Precomputed cos and sin tables rotate the Query "
            "and Key vectors by an angle proportional to position. There are no "
            "learned position parameters — position encoding is baked into the "
            "attention computation itself via a rotation matrix."
        ),
        "widget": "params",
    },
    {
        "key": "attention-weights",
        "title": "Attention Weights (Q/K/V/O)",
        "body": (
            "Each attention head has four projection matrices: Query (Q), Key (K), "
            "Value (V), and Output (O). Each is shape n_embd x n_embd (16 x 16). "
            "With 4 heads, that is 4 x 4 x 16 x 16 = 4,096 attention parameters. "
            "The widget breaks down each projection and shows sample values."
        ),
        "widget": "params",
    },
    {
        "key": "mlp-and-output",
        "title": "MLP and Output Head",
        "body": (
            "After attention, a SwiGLU MLP projects through gate, up, and down "
            "matrices. The gate (16 x ~42) is activated by SiLU then multiplied "
            "element-wise with up (16 x ~42). The result projects through down "
            "(~42 x 16). The lm_head (16 x 27) produces logits over the vocabulary. "
            "Total: the widget sums all parameters and verifies the count."
        ),
        "widget": "params",
    },
    {
        "key": "export-mapping",
        "title": "Safetensors Export Names",
        "body": (
            "When exported to safetensors (HF-compatible format), each anvil "
            "parameter maps to a HuggingFace LlamaForCausalLM tensor name. "
            "For example, layer0.attn_wq becomes "
            "model.layers.0.self_attn.q_proj.weight. "
            "layer{i}.rms_1 maps to input_layernorm.weight, and "
            "layer{i}.rms_2 maps to post_attention_layernorm.weight. "
            "No biases are exported (Llama uses bias-free linear layers). "
            "See the Safetensors Export reference for the full mapping table."
        ),
        "widget": "params",
    },
]

ADAM_STEPS = [
    {
        "key": "what-is-adam",
        "title": "What is Adam?",
        "body": (
            "Plain SGD uses a single learning rate for every parameter. "
            "Adam (Adaptive Moment Estimation) maintains two per-parameter values: "
            "m (momentum) and v (adaptive learning rate). This makes training faster "
            "and more stable, especially for transformers with diverse parameter scales."
        ),
        "widget": "adam",
    },
    {
        "key": "momentum",
        "title": "Momentum (m)",
        "body": (
            "Momentum tracks a rolling average of past gradients: "
            "m_t = beta1 * m_{t-1} + (1 - beta1) * g_t. "
            "This smooths out noisy gradients and accelerates progress in consistent "
            "directions. The widget shows how m evolves step by step for a sample parameter."
        ),
        "widget": "adam",
    },
    {
        "key": "adaptive-lr",
        "title": "Adaptive LR (v)",
        "body": (
            "The v term tracks the squared gradient magnitude: "
            "v_t = beta2 * v_{t-1} + (1 - beta2) * g_t^2. "
            "Parameters with large gradients get smaller updates (they are sensitive), "
            "while parameters with small gradients get larger updates. "
            "The widget visualises this per-parameter scaling effect."
        ),
        "widget": "adam",
    },
    {
        "key": "bias-correction",
        "title": "Bias Correction",
        "body": (
            "At the first step, m and v are initialised to zero, so they are biased "
            "toward zero. Adam corrects this: m_hat = m / (1 - beta1^t), "
            "v_hat = v / (1 - beta2^t). Early in training, this correction is large; "
            "it decays toward 1 as t increases. The widget shows the correction curve."
        ),
        "widget": "adam",
    },
    {
        "key": "lr-decay",
        "title": "LR Decay",
        "body": (
            "This model uses a linear learning rate decay schedule: "
            "lr_t = lr * (1 - step / num_steps). The learning rate starts at the "
            "configured value and decreases linearly to zero. This lets the model "
            "make large updates early when it is far from optimal, then fine-tune "
            "with smaller updates later. The widget shows the decay curve."
        ),
        "widget": "adam",
    },
    {
        "key": "weight-decay",
        "title": "Weight Decay (AdamW)",
        "body": (
            "The optimizer in anvil's core engine is technically Adam, not AdamW — "
            "there is no explicit weight decay term. In full AdamW, each parameter "
            "has its own learning rate and a small decay factor that gently pulls "
            "weights toward zero (L2 regularization). This prevents weights from "
            "growing unbounded. For anvil's small educational models, the effect "
            "is negligible. The GPU backend uses torch.optim.Adam (also without "
            "weight decay). Adding weight_decay to the config is a natural "
            "extension for more serious training runs."
        ),
        "widget": "adam",
    },
]

AUTOGRAD_STEPS = [
    {
        "key": "what-is-autograd",
        "title": "What is Autograd?",
        "body": (
            "Autograd is automatic differentiation: it tracks every mathematical operation "
            "to build a computation graph, then walks it backward to compute gradients. "
            "In anvil, each number is wrapped in a Value object that records how it was "
            "computed. Type some text into the widget and watch the computation graph build."
        ),
        "widget": "autograd",
    },
    {
        "key": "building-the-graph",
        "title": "Building the Graph",
        "body": (
            "Every operation (add, multiply, log, exp, relu) creates a new Value node "
            "that points back to its inputs (children). The graph grows from parameters "
            "and input tokens up through embeddings, attention, and finally to the loss. "
            "Each node stores its data value and the local gradient of the operation."
        ),
        "widget": "autograd",
    },
    {
        "key": "topological-sort",
        "title": "Topological Sort",
        "body": (
            "Before backpropagation, the graph must be topologically sorted: ordered so "
            "that every node comes after all nodes it depends on. This ensures gradients "
            "flow in the correct direction — from the loss (output) back to the parameters "
            "(inputs). The widget shows the node depth, with depth 0 at the output."
        ),
        "widget": "autograd",
    },
    {
        "key": "chain-rule",
        "title": "Chain Rule",
        "body": (
            "Backpropagation applies the chain rule: the gradient at each node is the sum "
            "of (local gradient x parent gradient) for all paths to the loss. Each edge in "
            "the graph shows the local gradient contribution. Green values mean positive "
            "influence on the loss, red means negative."
        ),
        "widget": "autograd",
    },
    {
        "key": "gradient-accumulation",
        "title": "Gradient Accumulation",
        "body": (
            "When a Value is used in multiple places (the graph branches), its gradient "
            "is the sum of contributions from each path. This is why the backward pass "
            "uses += (accumulation) rather than simple assignment. The widget shows the "
            "final accumulated gradient (g) at each node."
        ),
        "widget": "autograd",
    },
]

DATA_FLOW_STEPS = [
    {
        "key": "browser-button",
        "title": "Browser Button Click",
        "body": (
            "When you click 'Start Training' in the Training Dashboard, the browser "
            "POSTs a JSON config body to /v1/training/start. This body includes all "
            "hyperparameters (n_embd, n_head, n_layer, num_steps, etc.) along with "
            "the data source ID (dataset_id or corpus_id). The route handler creates "
            "an asyncio task and returns immediately with a run_id — training runs "
            "in the background."
        ),
        "widget": "dataflow",
    },
    {
        "key": "service-orchestration",
        "title": "Service Orchestration",
        "body": (
            "The route delegates to TrainingService.start_training() which: "
            "(1) reserves a run_id with an SSE event queue and stop event, "
            "(2) loads training documents in a thread pool (run_in_executor), "
            "(3) resolves the compute device (CUDA > MPS > CPU), "
            "(4) dispatches to train() or train_torch() — the CPU or GPU backend. "
            "All of this runs in the async event loop, with the sync engine "
            "offloaded to a thread pool to avoid blocking the web server."
        ),
        "widget": "dataflow",
    },
    {
        "key": "sse-bridge",
        "title": "The SSE Bridge",
        "body": (
            "The core engine calls a progress callback every training step. This "
            "callback runs in the thread pool thread, so it uses "
            "asyncio.run_coroutine_threadsafe() to push events into an asyncio.Queue. "
            "The SSE endpoint at /v1/training/stream/{run_id} reads from that same "
            "queue and sends Server-Sent Events to the browser. Events include: "
            "metrics (step, loss, steps/sec, ETA), optimizer_state (per-parameter "
            "m/v/grad snapshots), complete (final loss + samples), and error."
        ),
        "widget": "dataflow",
    },
    {
        "key": "persistence-chain",
        "title": "Persistence Chain",
        "body": (
            "When training finishes, on_complete fires a chain of actions: "
            "(1) TrackingService logs params + metrics to MLflow, "
            "(2) the model.json artifact is uploaded to MLflow storage, "
            "(3) the model is registered in MLflow Model Registry, "
            "(4) the local DB gets an Experiment record, "
            "(5) model.json is saved to data/models/ for inference loading, "
            "(6) SafetensorsExportService generates model.safetensors + "
            "config.json + tokenizer.json for HuggingFace compatibility. "
            "Finally, the SSE 'complete' event reaches the browser."
        ),
        "widget": "dataflow",
    },
    {
        "key": "inference-path",
        "title": "Inference Path",
        "body": (
            "Loading a trained model for inference reverses the pipeline: "
            "POST to /v1/inference/sample with model_id and version. The endpoint "
            "looks up the artifact path in the Model Registry (or falls back to "
            "the experiment), loads model.json from disk, reconstructs a LlamaModel, "
            "and runs autoregressive sampling. The sampling code supports temperature "
            "scaling, top-K filtering, and top-P (nucleus) filtering — the same "
            "techniques explained in the Sampling lesson."
        ),
        "widget": "dataflow",
    },
]

ARCHITECTURE_STEPS = [
    {
        "key": "the-big-picture",
        "title": "The Big Picture",
        "body": (
            "anvil is a Llama-style decoder-only transformer. Text flows in as token "
            "IDs, through a token embedding, then through one or more identical "
            "transformer blocks, and finally through a normalization + output head "
            "that produces logits over the vocabulary. The diagram shows the full "
            "stack — use it as a map for the components you learned in earlier lessons."
        ),
        "widget": "architecture",
    },
    {
        "key": "token-embedding-input",
        "title": "Token Embedding (Input)",
        "body": (
            "Each token ID indexes a row of the wte matrix to produce a dense vector "
            "of size n_embd. Unlike GPT-2, there is NO learned position embedding "
            "added here — position is injected later via RoPE inside attention. The "
            "embedding is the only thing fed into the first transformer block."
        ),
        "widget": "architecture",
    },
    {
        "key": "the-transformer-block",
        "title": "The Transformer Block",
        "body": (
            "The heart of the model is the transformer block, repeated n_layer times. "
            "Each block has two sublayers: a self-attention sublayer and a SwiGLU MLP "
            "sublayer. Both use pre-normalization (RMSNorm before the sublayer) and a "
            "residual connection (the input is added back to the output). Highlighted "
            "in the diagram, this block is where nearly all the parameters live."
        ),
        "widget": "architecture",
    },
    {
        "key": "attention-sublayer",
        "title": "Attention Sublayer",
        "body": (
            "First sublayer: RMSNorm (scaled by rms_1) → Q/K/V projections → RoPE "
            "rotation applied to Q and K → multi-head causal attention → output "
            "projection (Wo) → add residual. RoPE is what encodes position, by "
            "rotating the query and key vectors by an angle proportional to their "
            "position before the attention dot-product."
        ),
        "widget": "architecture",
    },
    {
        "key": "swiglu-sublayer",
        "title": "SwiGLU MLP Sublayer",
        "body": (
            "Second sublayer: RMSNorm (scaled by rms_2) → SwiGLU MLP → add residual. "
            "SwiGLU computes gate = SiLU(x·Wgate), up = x·Wup, then (gate ⊙ up)·Wdown. "
            "The intermediate size is int(8·n_embd/3), preserving parameter parity "
            "with the classic 4x ReLU MLP it replaces. SiLU (Swish) is x·sigmoid(x)."
        ),
        "widget": "architecture",
    },
    {
        "key": "output-head",
        "title": "Output Head",
        "body": (
            "After the final transformer block, one more RMSNorm (rms_final) "
            "normalizes the representation, then the lm_head linear projection maps "
            "it from n_embd back to vocab_size — producing one logit per possible "
            "next character. Softmax turns those logits into probabilities. The lm_head "
            "is a separate matrix from wte (no weight tying)."
        ),
        "widget": "architecture",
    },
]

EXPORT_STEPS = [
    {
        "key": "why-export",
        "title": "Why Export?",
        "body": (
            "After training, the model is stored as model.json — a Python-serializable "
            "dict of Value objects. This format is anvil-native: it preserves autograd "
            "state and is loadable by LlamaModel.load(). But other tools don't understand "
            "anvil's format. The export pipeline converts the trained weights into "
            "safetensors, the standard format for HuggingFace transformers. This lets "
            "you load your trained model in Llama.cpp, vLLM, or any Llama-compatible "
            "inference server."
        ),
    },
    {
        "key": "tensor-mapping",
        "title": "Tensor Name Mapping",
        "body": (
            "The critical bridge is export_state_dict() in anvil/services/export.py. "
            "Every anvil internal key maps to a HuggingFace LlamaForCausalLM tensor name. "
            "For example, layer0.attn_wq becomes model.layers.0.self_attn.q_proj.weight. "
            "layer0.rms_1 maps to input_layernorm.weight. rms_final maps to model.norm.weight. "
            "No biases are exported — Llama uses bias-free linear layers. No wpe is exported "
            " RoPE is a computation, not a parameter. See the Safetensors Export reference "
            "for the full mapping table."
        ),
    },
    {
        "key": "config-generation",
        "title": "Config Generation",
        "body": (
            "Alongside the weights, the export generates a config.json compatible with "
            "HuggingFace LlamaConfig. Key fields: model_type=llama, hidden_size=n_embd, "
            "intermediate_size=int(8*n_embd/3), num_hidden_layers=n_layer, "
            "num_attention_heads=n_head, hidden_act=silu, rms_norm_eps=1e-5, "
            "rope_theta=10000.0. The config also marks tie_word_embeddings=false "
            "(wte and lm_head are separate) and attention_bias=false."
        ),
    },
    {
        "key": "tokenizer-export",
        "title": "Tokenizer Export",
        "body": (
            "The character-level tokenizer is exported as tokenizer.json with: "
            "the sorted character list, char-to-ID mapping, BOS token ID, and "
            "tokenizer type flag. This ensures the same encoding is used at "
            "inference time as during training. The exported tokenizer is not "
            "compatible with HuggingFace tokenizers (which use BPE/WordPiece), "
            "but the format is self-documenting for anvil's use case."
        ),
    },
    {
        "key": "mlflow-pyfunc",
        "title": "MLflow Pyfunc Model",
        "body": (
            "The export also generates MLmodel and conda.yaml for MLflow's pyfunc "
            "loading path. The MLmodel points to anvil._pyfunc_model.AnvilPyfuncModel "
            "as the loader module. The conda.yaml lists anvil, transformers, torch, "
            "safetensors, and numpy as dependencies. This enables MLflow Model Registry "
            "to deploy the model as a REST endpoint or load it in Python for inference. "
            "The demo model at data/models/demo/ is the canonical example."
        ),
    },
]

CLOUD_COMPUTE_STEPS = [
    {
        "key": "why-cloud-compute",
        "title": "Why Cloud Compute?",
        "body": (
            "Local training is limited by your hardware. A 16-parameter model fits anywhere, "
            "but serious models need more memory and faster computation. Cloud compute (Modal) "
            "lets you train on powerful remote GPUs without buying hardware. The workflow "
            "stays the same: config→submit→poll→artifacts. The widget below walks through "
            "each stage of a remote training run."
        ),
        "widget": "cloudCompute",
    },
    {
        "key": "backend-selector",
        "title": "Backend Selector",
        "body": (
            "The Training Dashboard now shows a Compute Backend selector instead of a simple "
            "GPU toggle. Options: Auto (best available), Local (CPU), Local (GPU), and "
            "Modal (cloud GPU). Unavailable options are greyed out with an explanation. "
            "The endpoint /v1/compute/backends returns availability from the compute registry."
        ),
    },
    {
        "key": "submitted-event",
        "title": "The 'submitted' SSE Event",
        "body": (
            'When training is dispatched to Modal, the server sends a new "submitted" '
            "SSE event to the browser with the remote_job_id. This tells the dashboard "
            "the job was accepted by Modal and is waiting in the queue. "
            "The connection state changes to 'submitted' and shows the remote job ID."
        ),
    },
    {
        "key": "status-event",
        "title": "The 'status' SSE Event",
        "body": (
            "As Modal runs the job, the server polls for state transitions and emits "
            '"status" SSE events. These carry the current lifecycle phase: '
            "RUNNING (training started), with step/loss metrics when available, "
            "and COMPLETED (training finished). The dashboard updates the loss chart "
            "and metrics in real time, exactly like local training."
        ),
    },
    {
        "key": "artifact-flow",
        "title": "Artifact Flow",
        "body": (
            "On remote completion, Modal logs artifacts directly to the shared MLflow "
            "server: model.safetensors, config.json, samples.txt, and MLmodel metadata. "
            "The anvil server picks up the completion, records the experiment in the "
            "local SQLite DB, and registers the model in MLflow Model Registry with "
            "a runs:/ URI. No local model download — the artifact stays in MLflow."
        ),
    },
    {
        "key": "d4-failure-mode",
        "title": "D4 Failure Mode",
        "body": (
            "If you select Modal but the modal package is missing or unauthenticated, "
            "the server returns a 422 error with a clear message: "
            '"Modal selected but not available. Install via: pip install anvil[compute] '
            'and authenticate via: modal token new". This follows the D4 rule: '
            "implicit backends (auto, local-cpu/gpu) silently fall back; "
            "explicit selection of an unavailable backend raises an error."
        ),
    },
    {
        "key": "polling-lifecycle",
        "title": "Polling Lifecycle",
        "body": (
            "The polling loop uses exponential backoff: starts at 1-second intervals "
            "during SUBMITTED, extends to 5 seconds during RUNNING, and switches to "
            "15-second intervals once COMPLETED (waiting for artifact sync). "
            "The loop has a configurable timeout (default 30 minutes). "
            "If the timeout expires, the experiment is marked failed."
        ),
    },
]


@router.get("/learn", response_class=HTMLResponse)
async def learn_index(request: Request):
    """Render the learning hub index page."""
    return request.app.state.templates.TemplateResponse(
        request,
        "archetypes/learn-index.html",
        {"arc": LEARNING_ARC},
    )


@router.get("/learn/attention", response_class=HTMLResponse)
async def attention_concept_page(request: Request):
    """Render the attention mechanism walkthrough page with interactive steps."""
    return request.app.state.templates.TemplateResponse(
        request,
        "archetypes/concept.html",
        {"steps": ATTENTION_STEPS, **_arc_context("attention")},
    )


@router.get("/learn/tokenization", response_class=HTMLResponse)
async def tokenization_concept_page(request: Request):
    """Render the tokenization walkthrough page with interactive steps."""
    return request.app.state.templates.TemplateResponse(
        request,
        "archetypes/concept.html",
        {"steps": TOKENIZATION_STEPS, **_arc_context("tokenization")},
    )


@router.get("/learn/embeddings", response_class=HTMLResponse)
async def embeddings_concept_page(request: Request):
    """Render the embeddings walkthrough page with interactive steps."""
    return request.app.state.templates.TemplateResponse(
        request,
        "archetypes/concept.html",
        {"steps": EMBEDDING_STEPS, **_arc_context("embeddings")},
    )


@router.get("/learn/sampling", response_class=HTMLResponse)
async def sampling_concept_page(request: Request):
    """Render the sampling walkthrough page with interactive steps."""
    return request.app.state.templates.TemplateResponse(
        request,
        "archetypes/concept.html",
        {"steps": SAMPLING_STEPS, **_arc_context("sampling")},
    )


@router.get("/learn/training-loop", response_class=HTMLResponse)
async def training_loop_concept_page(request: Request):
    """Render the training loop walkthrough page with interactive steps."""
    return request.app.state.templates.TemplateResponse(
        request,
        "archetypes/concept.html",
        {"steps": TRAINING_LOOP_STEPS, **_arc_context("training-loop")},
    )


@router.get("/learn/autograd", response_class=HTMLResponse)
async def autograd_concept_page(request: Request):
    """Render the autograd walkthrough page with interactive steps."""
    return request.app.state.templates.TemplateResponse(
        request,
        "archetypes/concept.html",
        {"steps": AUTOGRAD_STEPS, **_arc_context("autograd")},
    )


@router.get("/learn/loss", response_class=HTMLResponse)
async def loss_concept_page(request: Request):
    """Render the loss functions walkthrough page with interactive steps."""
    return request.app.state.templates.TemplateResponse(
        request,
        "archetypes/concept.html",
        {"steps": LOSS_STEPS, **_arc_context("loss")},
    )


@router.get("/learn/parameters", response_class=HTMLResponse)
async def params_concept_page(request: Request):
    """Render the model parameters walkthrough page with interactive steps."""
    return request.app.state.templates.TemplateResponse(
        request,
        "archetypes/concept.html",
        {"steps": PARAMS_STEPS, **_arc_context("parameters")},
    )


@router.get("/learn/adam", response_class=HTMLResponse)
async def adam_concept_page(request: Request):
    """Render the Adam optimizer walkthrough page with interactive steps."""
    return request.app.state.templates.TemplateResponse(
        request,
        "archetypes/concept.html",
        {"steps": ADAM_STEPS, **_arc_context("adam")},
    )


@router.get("/learn/architecture", response_class=HTMLResponse)
async def architecture_concept_page(request: Request):
    """Render the transformer architecture walkthrough page."""
    return request.app.state.templates.TemplateResponse(
        request,
        "archetypes/architecture.html",
        {"steps": ARCHITECTURE_STEPS, **_arc_context("architecture")},
    )


@router.get("/learn/data-flow", response_class=HTMLResponse)
async def data_flow_concept_page(request: Request):
    """Render the data flow walkthrough page with interactive steps."""
    return request.app.state.templates.TemplateResponse(
        request,
        "archetypes/concept.html",
        {"steps": DATA_FLOW_STEPS, **_arc_context("data-flow")},
    )


@router.get("/learn/export", response_class=HTMLResponse)
async def export_concept_page(request: Request):
    """Render the model export walkthrough page with interactive steps."""
    return request.app.state.templates.TemplateResponse(
        request,
        "archetypes/concept.html",
        {"steps": EXPORT_STEPS, **_arc_context("export")},
    )


@router.get("/learn/faq", response_class=HTMLResponse)
async def faq_page(request: Request):
    """Render the FAQ walkthrough page."""
    return request.app.state.templates.TemplateResponse(
        request,
        "archetypes/faq.html",
        {"arc": LEARNING_ARC},
    )


@router.get("/learn/cloud-compute", response_class=HTMLResponse)
async def cloud_compute_concept_page(request: Request):
    """Render the cloud compute walkthrough page with interactive steps."""
    return request.app.state.templates.TemplateResponse(
        request,
        "archetypes/concept.html",
        {"steps": CLOUD_COMPUTE_STEPS, **_arc_context("cloud-compute")},
    )


@router.get("/models-page", response_class=HTMLResponse)
async def models_page(request: Request):
    """Render the model registry page."""
    return request.app.state.templates.TemplateResponse(
        request,
        "archetypes/models.html",
    )


@router.get("/model-detail/{model_id}", response_class=HTMLResponse)
async def model_detail_page(request: Request, model_id: str):
    """Render the model detail page for a given model ID.

    Parameters
    ----------
    request : Request
        FastAPI request object.
    model_id : str
        The model ID to display (parsed as integer).

    Returns
    -------
    TemplateResponse
        Model detail page or a 404 response for invalid IDs.
    """
    try:
        parsed = int(model_id)
        if parsed <= 0:
            raise ValueError
    except (ValueError, TypeError):
        return request.app.state.templates.TemplateResponse(
            request,
            "archetypes/model_detail.html",
            {"model_id": 0, "error": f"Invalid model ID: {model_id}"},
            status_code=404,
        )
    return request.app.state.templates.TemplateResponse(
        request,
        "archetypes/model_detail.html",
        {"model_id": parsed},
    )


@router.get("/inference/models")
async def list_inference_models():
    """List all registered models available for inference.

    Returns
    -------
    dict
        Dict with ``models`` (list of model dicts) and optionally a
        ``message`` if no models are registered.
    """
    from anvil.services.tracking import TrackingService

    tracking_svc = TrackingService()
    models = await tracking_svc.list_registered_models()
    if not models:
        return {
            "models": [],
            "message": "No models registered. Train an experiment and register it first.",
        }
    return {"models": models}


@router.post("/inference/sample")
async def inference_sample(body: dict):
    """Generate text samples from a registered model.

    Parameters
    ----------
    body : dict
        Request body with ``model_id``, ``version``, ``prompt``,
        ``temperature``, ``num_samples``, ``top_k``, and ``top_p``.

    Returns
    -------
    dict
        Generated text samples from the model.

    Raises
    ------
    HTTPException
        If ``model_id`` or ``version`` are missing, or parameters are
        invalid.
    """
    from anvil.core.autograd import Value

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

    from anvil.services.inference import InferenceService

    inf_svc = InferenceService()
    try:
        loaded = await inf_svc.load_model(model_id, version)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    model = loaded.model
    chars = loaded.chars

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
