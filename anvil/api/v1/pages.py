# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""HTML page rendering routes for the v1 API.

Provides Jinja2-based page rendering for all UI pages (training dashboard,
experiments, datasets, inference, operations, learning). Extracted from
``router.py`` as part of structural decomposition.
"""

from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from ...api.deps import get_workbench
from ...db.models.license_entry import LicenseEntry
from ...workbench import AnvilWorkbench
from .learning import _arc_context as _ctx
from .learning import related_lessons

router = APIRouter()


@router.get("/training-page", response_class=HTMLResponse)
async def training_page(request: Request) -> HTMLResponse:
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
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "archetypes/training.html",
        {
            "related_lessons": related_lessons(
                "parameters", "architecture", "autograd", "adam", "attention"
            ),
        },
    )


@router.get("/experiments-page", response_class=HTMLResponse)
async def experiments_page(request: Request) -> HTMLResponse:
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
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "archetypes/experiment.html",
        {
            "related_lessons": related_lessons(
                "loss", "training-loop", "adam", "experiment-tracking"
            ),
        },
    )


@router.get("/learn/graph", response_class=HTMLResponse)
async def graph_concept_page(request: Request) -> HTMLResponse:
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
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "archetypes/graph.html",
        _arc_context("graph"),
    )


@router.get("/datasets-page", response_class=HTMLResponse)
async def datasets_page(
    request: Request,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> HTMLResponse:
    """Render the dataset management page.

    Parameters
    ----------
    request : Request
        The incoming HTTP request.
    workbench : AnvilWorkbench
        Injected session-bound workbench for fetching license catalog.

    Returns
    -------
    HTMLResponse
        Rendered ``datasets.html`` template with license catalog context.
    """
    licenses = await workbench.governance.list_licenses(
        include_own_content=False,
    )
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "datasets.html",
        {
            "licenses": licenses,
            "related_lessons": related_lessons(
                "data-fundamentals", "tokenization", "chunking", "governance"
            ),
        },
    )


@router.get("/operations-page", response_class=HTMLResponse)
async def operations_page(request: Request) -> HTMLResponse:
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
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "operations.html",
        {
            "related_lessons": related_lessons(
                "cloud-compute", "memory-divergence", "faq", "glossary"
            ),
        },
    )


@router.get("/inference-page", response_class=HTMLResponse)
async def inference_page(request: Request) -> HTMLResponse:
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
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "archetypes/playground.html",
        {
            "related_lessons": related_lessons(
                "sampling", "attention", "embeddings", "graph"
            ),
        },
    )


def _arc_context(key: str) -> dict[str, Any]:
    """Look up the learning arc context dictionary for a given key.

    Delegates to :func:`anvil.api.v1.learning._arc_context` to avoid
    duplicating the ``LEARNING_ARC`` data structure.

    Parameters
    ----------
    key : str
        The learning step key (e.g. ``"graph"``).

    Returns
    -------
    dict
        Context dict with ``arc``, ``prev``, ``next``, and ``total`` keys
        for navigation within the progressive learning content, or an
        empty dict if the key is not found.
    """
    return _ctx(key)


@router.get("/content-page", response_class=HTMLResponse)
async def content_page(request: Request) -> HTMLResponse:
    """Render the content library management page.

    Parameters
    ----------
    request : Request
        The incoming HTTP request.

    Returns
    -------
    HTMLResponse
        Rendered ``archetypes/content_library.html`` template.
    """
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "archetypes/content_library.html",
        {
            "related_lessons": related_lessons(
                "data-fundamentals", "content-versioning", "governance", "chunking"
            ),
        },
    )


@router.get("/config-page", response_class=HTMLResponse)
async def config_page(request: Request) -> HTMLResponse:
    """Render the runtime configuration management page.

    Parameters
    ----------
    request : Request
        The incoming HTTP request.

    Returns
    -------
    HTMLResponse
        Rendered ``config.html`` template with related learning context.
    """
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "config.html",
        {
            "related_lessons": related_lessons(
                "runtime-config", "cloud-compute", "faq", "glossary"
            ),
        },
    )


@router.get("/about", response_class=HTMLResponse)
async def about_page(
    request: Request,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> HTMLResponse:
    """Render the about page with governance info, licenses, and project overview.

    Parameters
    ----------
    request : Request
        The incoming HTTP request.
    workbench : AnvilWorkbench
        Injected session-bound workbench for fetching license catalog.

    Returns
    -------
    HTMLResponse
        Rendered ``about.html`` template with license catalog context.
    """
    licenses: Sequence[LicenseEntry] = await workbench.governance.list_licenses(
        include_own_content=False,
    )
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "about.html",
        {"licenses": licenses},
    )
