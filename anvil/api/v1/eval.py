# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Eval endpoints for v1 API."""

import math
from typing import Any

from fastapi import APIRouter, HTTPException

from .schemas_eval import EvalPerplexityBody
from ...core.engine import softmax
from ...services.inference.inference import InferenceService

router = APIRouter()


@router.post("/eval/perplexity")
async def eval_perplexity(body: EvalPerplexityBody) -> dict[str, Any]:
    """Compute perplexity of a model on a given text string.

    Loads the specified model version, tokenizes the input text, and computes
    the average cross-entropy loss over the first ``block_size`` tokens.
    Perplexity is ``exp(avg_loss)``.

    Parameters
    ----------
    body : EvalPerplexityBody
        Request body with ``model_id``, ``version``, and ``text``.

    Returns
    -------
    dict
        Perplexity, average loss, number of positions evaluated, vocabulary
        size, and model configuration.

    Raises
    ------
    HTTPException
        If ``model_id`` or ``version`` is missing (400), ``text`` is empty
        (400), the model is not found (404), or a character is not in the
        vocabulary (400).
    """
    model_id = body.model_id
    version = body.version
    text = body.text

    inf_svc = InferenceService()
    try:
        loaded = await inf_svc.load_model(model_id, version)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    model = loaded.model
    chars = loaded.chars

    BOS = len(chars)
    try:
        tokens = [BOS] + [chars.index(ch) for ch in text]
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Character '{e.args[0]}' not in model vocabulary",
        ) from e

    n = min(model.block_size, len(tokens) - 1)
    keys: list[list[list[Any]]] = [[] for _ in range(model.n_layer)]
    values: list[list[list[Any]]] = [[] for _ in range(model.n_layer)]
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
