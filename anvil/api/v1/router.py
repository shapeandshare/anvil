# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Versioned API v1 router.

Thin aggregator that includes all sub-routers (training, experiments,
datasets, corpora, registry, eval, eval_datasets, inference, compute,
health_ops, pages, learning) under a single ``APIRouter`` instance.
The root page routes (``GET /``) are defined here because sub-routers
cannot have an empty path prefix.
"""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from anvil.api.v1.backup import router as backup_router
from anvil.api.v1.compute import router as compute_router
from anvil.api.v1.content import router as content_router
from anvil.api.v1.corpora import router as corpora_router
from anvil.api.v1.datasets import router as datasets_router
from anvil.api.v1.eval import router as eval_router
from anvil.api.v1.eval_datasets import router as eval_datasets_router
from anvil.api.v1.experiments import router as experiments_router
from anvil.api.v1.governance import router as governance_router
from anvil.api.v1.health_ops import router as health_ops_router
from anvil.api.v1.inference import router as inference_router
from anvil.api.v1.learning import router as learning_router
from anvil.api.v1.pages import router as pages_router
from anvil.api.v1.registry import router as registry_router
from anvil.api.v1.training import router as training_router

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
router.include_router(governance_router)
router.include_router(health_ops_router)
router.include_router(pages_router)
router.include_router(learning_router)
router.include_router(content_router)
router.include_router(backup_router)

MODELS_DIR = Path("data/models")
"""Path: Directory where trained model artifacts are stored on disk."""


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def root(request: Request) -> HTMLResponse:
    """Render the root training dashboard page."""
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "archetypes/training.html",
    )


@router.get("/acceptable-use", response_class=HTMLResponse)
async def acceptable_use_page(request: Request) -> HTMLResponse:
    """Render the acceptable-use policy page.

    Parameters
    ----------
    request : Request
        The incoming HTTP request.

    Returns
    -------
    HTMLResponse
        Rendered ``acceptable_use.html`` template.
    """
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "acceptable_use.html",
    )
