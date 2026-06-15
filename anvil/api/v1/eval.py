"""Eval endpoints for v1 API."""

import math
from pathlib import Path

from fastapi import APIRouter, HTTPException

from anvil.core.engine import LlamaModel, softmax

router = APIRouter()


@router.post("/eval/perplexity")
async def eval_perplexity(body: dict):
    model_id = body.get("model_id")
    version = body.get("version")
    text = body.get("text")

    if model_id is None or version is None:
        raise HTTPException(status_code=400, detail="model_id and version required")

    if not isinstance(text, str) or not text:
        raise HTTPException(status_code=400, detail="text must be a non-empty string")

    from anvil.db.session import AsyncSessionLocal
    from anvil.db.repositories.models import ModelRepository
    from anvil.services.models import ModelRegistryService

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

    model = LlamaModel.load(str(model_path))
    chars = model.chars
    if not chars:
        raise HTTPException(status_code=400, detail="Model has no character mapping")

    BOS = len(chars)
    try:
        tokens = [BOS] + [chars.index(ch) for ch in text]
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Character '{e.args[0]}' not in model vocabulary",
        ) from e

    n = min(model.block_size, len(tokens) - 1)
    keys = [[] for _ in range(model.n_layer)]
    values = [[] for _ in range(model.n_layer)]
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
