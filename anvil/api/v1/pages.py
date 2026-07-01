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
from ...services.inference.model_browser import ModelBrowserService
from ...services.model_import.model_import_service import _ALLOWED_ARCHITECTURES
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


@router.get("/hf-browser", response_class=HTMLResponse)
async def hf_browser_page(
    request: Request,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> HTMLResponse:
    """Render the HuggingFace Model Browser page.

    Builds a catalog context with hardware eligibility computed for
    each curated entry, along with host resource info and feature
    flags for the template layer.

    Parameters
    ----------
    request : Request
        The incoming HTTP request.
    workbench : AnvilWorkbench
        Injected session-bound workbench for model browser access.

    Returns
    -------
    HTMLResponse
        Rendered ``hf_browser.html`` template.
    """
    browser = workbench.model_browser
    gpu, ram_gb = browser.detect_resources()
    catalog: list[dict[str, object]] = []
    for entry in browser.catalog:
        eligible = ModelBrowserService.check_eligibility(
            entry.resource_envelope, gpu, ram_gb
        )
        runnable = browser.runnable_status(entry.architecture)
        catalog.append(
            {
                "hf_id": entry.hf_id,
                "display_name": entry.display_name,
                "params": entry.params,
                "license": entry.license,
                "architecture": entry.architecture,
                "tokenizer_family": entry.tokenizer_family,
                "url": entry.url,
                "tags": entry.tags,
                "resource_envelope": entry.resource_envelope,
                "eligible": eligible,
                "runnable_status": runnable,
            }
        )
    import_jobs_raw = await workbench.model_imports.list_jobs()
    import_jobs: list[dict[str, object]] = [
        {
            "job_id": j.id,
            "status": j.status,
            "source_type": j.source_type,
            "source_identifier": j.source_identifier,
            "revision": j.revision,
            "started_at": j.started_at.isoformat() if j.started_at else None,
            "finished_at": j.finished_at.isoformat() if j.finished_at else None,
            "error_code": j.error_code,
            "error_message": j.error_message,
            "external_model_id": j.external_model_id,
            "created_at": j.created_at.isoformat(),
        }
        for j in import_jobs_raw
    ]
    host_backend = str(gpu.backend) if gpu.backend else "cpu"
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "hf_browser.html",
        {
            "catalog": catalog,
            "allow_list": list(_ALLOWED_ARCHITECTURES),
            "accepted_format": browser.accepted_format(),
            "host_backend": host_backend,
            "host_ram_gb": ram_gb,
            "import_jobs": import_jobs,
            "lesson_049_available": False,
            "hf_available": browser.hf_available(),
        },
    )
