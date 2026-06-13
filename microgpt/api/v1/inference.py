"""Inference endpoints for educational widgets — real model data, not hardcoded."""

from fastapi import APIRouter, HTTPException, Query

from microgpt.services.inference import InferenceService

router = APIRouter()
_svc = InferenceService()


def _call_or_400(svc_method, *args):
    try:
        return svc_method(*args)
    except KeyError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Character {e!r} is not in the model's vocabulary.",
        ) from e


@router.post("/inference/tokenize")
async def inference_tokenize(body: dict):
    text = body.get("text")
    if not isinstance(text, str) or not text:
        raise HTTPException(status_code=400, detail="text must be a non-empty string")
    try:
        loaded = await _svc.load_model(body.get("model_id"), body.get("version"))
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return _call_or_400(_svc.tokenize, text, loaded)


@router.post("/inference/embeddings")
async def inference_embeddings(body: dict):
    text = body.get("text")
    if not isinstance(text, str) or not text:
        raise HTTPException(status_code=400, detail="text must be a non-empty string")
    try:
        loaded = await _svc.load_model(body.get("model_id"), body.get("version"))
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return _call_or_400(_svc.embeddings, text, loaded)


@router.post("/inference/attention")
async def inference_attention(body: dict):
    text = body.get("text")
    if not isinstance(text, str) or not text:
        raise HTTPException(status_code=400, detail="text must be a non-empty string")
    try:
        loaded = await _svc.load_model(body.get("model_id"), body.get("version"))
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return _call_or_400(_svc.attention, text, loaded)


@router.post("/inference/sampling-distribution")
async def inference_sampling_distribution(body: dict):
    prompt = body.get("prompt", "")
    if not isinstance(prompt, str):
        raise HTTPException(status_code=400, detail="prompt must be a string")
    temperature = body.get("temperature", 0.5)
    if not isinstance(temperature, (int, float)) or temperature <= 0:
        raise HTTPException(status_code=400, detail="temperature must be positive")
    try:
        loaded = await _svc.load_model(body.get("model_id"), body.get("version"))
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return _svc.sampling_distribution(prompt, temperature, body.get("top_k"), loaded)


@router.get("/inference/forward-graph")
async def inference_forward_graph(
    model_id: int | None = Query(None),
    version: int | None = Query(None),
):
    try:
        loaded = await _svc.load_model(model_id, version)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return _svc.forward_graph(loaded)
