# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""HF Model Browser search API route.

Provides a ``GET /hf-browser/search`` endpoint that delegates to
``HubClient.search_models()`` when the ``[finetune]`` extra is installed.
Returns a 503 error with a descriptive message when ``huggingface_hub``
is not available.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/hf-browser/search", response_model=None)
async def search_hf_models(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=20, ge=1, le=50),
) -> Any:
    """Search HuggingFace Hub for models matching a query string.

    Requires the ``[finetune]`` extra (``huggingface_hub``).  Returns
    503 with an explanatory error when the extra is not installed.

    Parameters
    ----------
    q : str
        Search query string passed to ``HfApi.list_models()``.
    limit : int
        Maximum number of results (1-50).  Defaults to 20.

    Returns
    -------
    Any
        Search results dict with keys ``results``, ``cached``, and
        ``error``.  On a missing ``[finetune]`` extra, returns a
        ``JSONResponse`` with status 503 and a descriptive error
        body.
    """
    try:
        from ...services.inference_hub.hub_client import HubClient  # finetune extra

        client = HubClient()
    except ImportError:
        return JSONResponse(
            status_code=503,
            content={
                "results": [],
                "cached": False,
                "error": "HF Hub support requires [finetune] extra",
                "code": "missing_extra",
            },
        )

    return await asyncio.to_thread(client.search_models, q, limit)
