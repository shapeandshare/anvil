# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Inference endpoints for educational widgets.

Provides HTTP endpoints for model inference operations — tokenization,
embedding extraction, attention visualization, sampling distributions,
computation graphs, and loss breakdowns. All endpoints load model data
from the registry (not hardcoded values).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from ...services.inference.inference import InferenceService
from .inference_schemas import (
    InferenceAttentionBody,
    InferenceAutogradBody,
    InferenceBackwardBody,
    InferenceEmbeddingsBody,
    InferenceLossBody,
    InferenceSamplingBody,
    InferenceTokenizeBody,
)

router = APIRouter()
_svc = InferenceService()


def _call_or_400(svc_method: Any, *args: Any) -> Any:
    """Call an inference service method, converting ``KeyError`` to HTTP 400.

    Parameters
    ----------
    svc_method : callable
        The service method to invoke.
    *args
        Positional arguments forwarded to ``svc_method``.

    Returns
    -------
    object
        The return value of ``svc_method``.

    Raises
    ------
    HTTPException
        If a ``KeyError`` is raised (character not in vocabulary), a 400
        response is returned.
    """
    try:
        return svc_method(*args)
    except KeyError as e:
        missing_char = e.args[0] if e.args else "?"
        raise HTTPException(
            status_code=400,
            detail=f"Character {missing_char!r} is not in the model's vocabulary.",
        ) from e


@router.post("/inference/tokenize")
async def inference_tokenize(body: InferenceTokenizeBody) -> dict[str, Any]:
    """Tokenize input text using the loaded model's character vocabulary.

    Parameters
    ----------
    body : InferenceTokenizeBody
        Request body with fields:
          - ``text``: str — text to tokenize
          - ``model_id``: int, optional — model identifier
          - ``version``: int, optional — model version

    Returns
    -------
    dict
        Token IDs and character mappings for the input text.

    Raises
    ------
    HTTPException
        If ``text`` is empty (400) or the model is not found (404).
    """
    text = body.text
    if not text:
        raise HTTPException(status_code=400, detail="text must be a non-empty string")
    try:
        loaded = await _svc.load_model(body.model_id, body.version)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return _call_or_400(_svc.tokenize, text, loaded)  # type: ignore[no-any-return]


@router.post("/inference/embeddings")
async def inference_embeddings(body: InferenceEmbeddingsBody) -> dict[str, Any]:
    """Extract token embeddings for the input text.

    Parameters
    ----------
    body : InferenceEmbeddingsBody
        Request body with fields:
          - ``text``: str — text to embed
          - ``model_id``: int, optional — model identifier
          - ``version``: int, optional — model version

    Returns
    -------
    dict
        Embedding vectors for each token position.

    Raises
    ------
    HTTPException
        If ``text`` is empty (400) or the model is not found (404).
    """
    text = body.text
    if not text:
        raise HTTPException(status_code=400, detail="text must be a non-empty string")
    try:
        loaded = await _svc.load_model(body.model_id, body.version)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return _call_or_400(_svc.embeddings, text, loaded)  # type: ignore[no-any-return]


@router.post("/inference/attention")
async def inference_attention(body: InferenceAttentionBody) -> dict[str, Any]:
    """Compute attention weights for the input text.

    Parameters
    ----------
    body : InferenceAttentionBody
        Request body with fields:
          - ``text``: str — input text
          - ``model_id``: int, optional — model identifier
          - ``version``: int, optional — model version

    Returns
    -------
    dict
        Attention weight matrices per head.

    Raises
    ------
    HTTPException
        If ``text`` is empty (400) or the model is not found (404).
    """
    text = body.text
    if not text:
        raise HTTPException(status_code=400, detail="text must be a non-empty string")
    try:
        loaded = await _svc.load_model(body.model_id, body.version)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return _call_or_400(_svc.attention, text, loaded)  # type: ignore[no-any-return]


@router.post("/inference/sampling-distribution")
async def inference_sampling_distribution(
    body: InferenceSamplingBody,
) -> dict[str, Any]:
    """Get the sampling probability distribution for a prompt.

    Parameters
    ----------
    body : InferenceSamplingBody
        Request body with fields:
          - ``prompt``: str — prompt text
          - ``temperature``: float, optional — sampling temperature (default 0.5)
          - ``top_k``: int, optional — top-k filtering
          - ``model_id``: int, optional — model identifier
          - ``version``: int, optional — model version

    Returns
    -------
    dict
        Probability distribution over the vocabulary after temperature
        scaling and top-k filtering.

    Raises
    ------
    HTTPException
        If ``prompt`` is not a string (400), temperature is not positive
        (400), or the model is not found (404).
    """
    prompt = body.prompt
    if not isinstance(prompt, str):
        raise HTTPException(status_code=400, detail="prompt must be a string")
    temperature = body.temperature
    if temperature <= 0:
        raise HTTPException(status_code=400, detail="temperature must be positive")
    try:
        loaded = await _svc.load_model(body.model_id, body.version)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return _svc.sampling_distribution(prompt, temperature, body.top_k, loaded)


@router.get("/inference/forward-graph")
async def inference_forward_graph(
    model_id: int | None = Query(None),
    version: int | None = Query(None),
) -> dict[str, Any]:
    """Get the forward computation graph structure for the loaded model.

    Parameters
    ----------
    model_id : int | None, optional
        Model identifier. Defaults to ``None`` (loads demo model).
    version : int | None, optional
        Model version. Defaults to ``None`` (loads latest).

    Returns
    -------
    dict
        Forward pass graph structure with node and edge descriptions.

    Raises
    ------
    HTTPException
        If the model is not found (404).
    """
    try:
        loaded = await _svc.load_model(model_id, version)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return _svc.forward_graph(loaded)


@router.post("/inference/backward-graph")
async def inference_backward_graph(body: InferenceBackwardBody) -> dict[str, Any]:
    """Get the backward (autograd) computation graph for the input text.

    Parameters
    ----------
    body : InferenceBackwardBody
        Request body with fields:
          - ``text``: str — input text
          - ``model_id``: int, optional — model identifier
          - ``version``: int, optional — model version

    Returns
    -------
    dict
        Backward pass graph showing gradient flow.

    Raises
    ------
    HTTPException
        If ``text`` is empty (400) or the model is not found (404).
    """
    text = body.text
    if not text:
        raise HTTPException(status_code=400, detail="text must be a non-empty string")
    try:
        loaded = await _svc.load_model(body.model_id, body.version)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return _call_or_400(_svc.backward_graph, text, loaded)  # type: ignore[no-any-return]


@router.post("/inference/autograd-example")
async def inference_autograd_example(body: InferenceAutogradBody) -> dict[str, Any]:
    """Get an autograd computation graph example for the input text.

    Parameters
    ----------
    body : InferenceAutogradBody
        Request body with fields:
          - ``text``: str — input text
          - ``model_id``: int, optional — model identifier
          - ``version``: int, optional — model version

    Returns
    -------
    dict
        Autograd example graph with Value node details.

    Raises
    ------
    HTTPException
        If ``text`` is empty (400) or the model is not found (404).
    """
    text = body.text
    if not text:
        raise HTTPException(status_code=400, detail="text must be a non-empty string")
    try:
        loaded = await _svc.load_model(body.model_id, body.version)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return _call_or_400(_svc.autograd_example_graph, text, loaded)  # type: ignore[no-any-return]


@router.post("/inference/loss-breakdown")
async def inference_loss_breakdown(body: InferenceLossBody) -> dict[str, Any]:
    """Get a per-token loss breakdown for the input text.

    Parameters
    ----------
    body : InferenceLossBody
        Request body with fields:
          - ``text``: str — input text
          - ``model_id``: int, optional — model identifier
          - ``version``: int, optional — model version

    Returns
    -------
    dict
        Per-position loss values and probabilities.

    Raises
    ------
    HTTPException
        If ``text`` is empty (400) or the model is not found (404).
    """
    text = body.text
    if not text:
        raise HTTPException(status_code=400, detail="text must be a non-empty string")
    try:
        loaded = await _svc.load_model(body.model_id, body.version)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return _call_or_400(_svc.loss_breakdown, text, loaded)  # type: ignore[no-any-return]


@router.get("/inference/model-params")
async def inference_model_params(
    model_id: int | None = Query(None),
    version: int | None = Query(None),
) -> dict[str, Any]:
    """Get the loaded model's parameter list with shapes and values.

    Parameters
    ----------
    model_id : int | None, optional
        Model identifier. Defaults to ``None`` (loads demo model).
    version : int | None, optional
        Model version. Defaults to ``None`` (loads latest).

    Returns
    -------
    dict
        Model parameter details including names, shapes, and value ranges.

    Raises
    ------
    HTTPException
        If the model is not found (404).
    """
    try:
        loaded = await _svc.load_model(model_id, version)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return _svc.model_params(loaded)
