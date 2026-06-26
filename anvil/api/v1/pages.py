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
    from .learning import _arc_context as _ctx

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


THEMES_CATALOG: list[dict[str, object]] = [
    {
        "id": "default",
        "display_name": "Default",
        "preview_hint": "Clean iOS-modern light & dark",
        "modes": ["light", "dark"],
        "css_layer": None,
        "excited_desc": "Crank the animated beat — accent glow pulses live",
        "particles": None,
    },
    {
        "id": "forge",
        "display_name": "Forge",
        "preview_hint": "Sparks flying from the anvil",
        "modes": ["dark"],
        "css_layer": "/static/css/themes/forge.css",
        "excited_desc": "Heat soars, loss quenches the forge in a bright flash",
        "particles": "spark",
    },
    {
        "id": "oldgrowth",
        "display_name": "Old Growth",
        "preview_hint": "Signal degrades with instability",
        "modes": ["single"],
        "css_layer": "/static/css/themes/oldgrowth.css",
        "excited_desc": "Gradient volatility rattles the canopy — leaves fall in bursts",
        "particles": "leaf",
    },
    {
        "id": "aurora",
        "display_name": "Aurora",
        "preview_hint": "Loss as northern lights",
        "modes": ["light", "dark"],
        "css_layer": "/static/css/themes/aurora.css",
        "excited_desc": "Borealis pulses and ripples across the sky",
        "particles": "aurora",
    },
    {
        "id": "tide",
        "display_name": "Tide",
        "preview_hint": "Loss as a rising shoreline",
        "modes": ["light", "dark"],
        "css_layer": "/static/css/themes/tide.css",
        "excited_desc": "Waves surge, bubbles churn with throughput",
        "particles": "bubble",
    },
    {
        "id": "unicorn",
        "display_name": "Unicorn",
        "preview_hint": "Training brings out the rainbow",
        "modes": ["light", "dark"],
        "css_layer": "/static/css/themes/unicorn.css",
        "excited_desc": "Magic soars — unicorns stampede, rainbows flood the screen",
        "particles": "css",
    },
    {
        "id": "bloom",
        "display_name": "Bloom",
        "preview_hint": "Convergence opens the garden",
        "modes": ["light", "dark"],
        "css_layer": "/static/css/themes/bloom.css",
        "excited_desc": "Petal burst on every milestone — the garden erupts",
        "particles": "petal",
    },
    {
        "id": "tectonic",
        "display_name": "Tectonic",
        "preview_hint": "Gradient spikes shake the ground",
        "modes": ["light", "dark"],
        "css_layer": "/static/css/themes/tectonic.css",
        "excited_desc": "Spikes trigger tremors and debris showers",
        "particles": "debris",
    },
    {
        "id": "glacier",
        "display_name": "Glacier",
        "preview_hint": "Convergence crystallizes the ice, freeze brings the snow",
        "modes": ["light", "dark"],
        "css_layer": "/static/css/themes/glacier.css",
        "excited_desc": "Rapid convergence — blizzard conditions, snow thickens",
        "particles": "snow",
    },
    {
        "id": "reactor",
        "display_name": "Reactor",
        "preview_hint": "Throughput drives the core",
        "modes": ["single"],
        "css_layer": "/static/css/themes/reactor.css",
        "excited_desc": "Core plasma pulses hotter with every token",
        "particles": "energy",
    },
    {
        "id": "hyperspace",
        "display_name": "Hyperspace",
        "preview_hint": "Throughput stretches the stars",
        "modes": ["single"],
        "css_layer": "/static/css/themes/hyperspace.css",
        "excited_desc": "Star streaks intensify — warp speed engaged",
        "particles": "streak",
    },
    {
        "id": "mainframe",
        "display_name": "Mainframe",
        "preview_hint": "A calm terminal that ticks with throughput",
        "modes": ["light", "dark"],
        "css_layer": "/static/css/themes/mainframe.css",
        "excited_desc": "Matrix rain accelerates, cursor flickers faster",
        "particles": "matrix",
    },
    {
        "id": "grid",
        "display_name": "Grid",
        "preview_hint": "Light-ribbons race the grid",
        "modes": ["single"],
        "css_layer": "/static/css/themes/grid.css",
        "excited_desc": "Ribbons streak faster, neon traces linger",
        "particles": "ribbon",
    },
    {
        "id": "stormfront",
        "display_name": "Storm Front",
        "preview_hint": "Gradient charge, loss clears the sky",
        "modes": ["light", "dark"],
        "css_layer": "/static/css/themes/stormfront.css",
        "excited_desc": "Lightning cracks, rain hammers — gradient storm",
        "particles": "rain",
    },
    {
        "id": "emberdrift",
        "display_name": "Ember Drift",
        "preview_hint": "Drifting sparks, quietly forging",
        "modes": ["single"],
        "css_layer": "/static/css/themes/emberdrift.css",
        "excited_desc": "Embers cascade faster, forge heat intensifies",
        "particles": "ember",
    },
    {
        "id": "resonance",
        "display_name": "Resonance",
        "preview_hint": "Signal as light & (opt-in) sound",
        "modes": ["light", "dark"],
        "css_layer": "/static/css/themes/resonance.css",
        "excited_desc": "Light stroboscopic and audio tones sync to training rhythm",
        "particles": "css",
    },
    {
        "id": "inkwash",
        "display_name": "Inkwash",
        "preview_hint": "Loss bleeds the brushstroke",
        "modes": ["light", "dark"],
        "css_layer": "/static/css/themes/inkwash.css",
        "excited_desc": "Brushstrokes bleed heavier, ink pools with each step",
        "particles": "ink",
    },
    {
        "id": "arcade",
        "display_name": "Arcade",
        "preview_hint": "Neon 80s party — loss drives the glow",
        "modes": ["light", "dark"],
        "css_layer": "/static/css/themes/arcade.css",
        "excited_desc": "Neon flares on milestones, confetti cannon bursts",
        "particles": "confetti",
    },
    {
        "id": "ash",
        "display_name": "Ash",
        "preview_hint": "Loss as falling black soot — training gone wrong",
        "modes": ["single"],
        "css_layer": "/static/css/themes/ash.css",
        "excited_desc": "Soot thickens into near-blackout — divergence is total",
        "particles": "css",
    },
    {
        "id": "deepsea",
        "display_name": "Deep Sea",
        "preview_hint": "Loss as bioluminescent depth",
        "modes": ["light", "dark"],
        "css_layer": "/static/css/themes/deepsea.css",
        "excited_desc": "Bioluminescent creatures flash brighter, depth pulses",
        "particles": "biolum",
    },
    {
        "id": "echo",
        "display_name": "Echo",
        "preview_hint": "Gradient spikes as sonar pings",
        "modes": ["single"],
        "css_layer": "/static/css/themes/echo.css",
        "excited_desc": "Sonar pings intensify, rings ripple faster",
        "particles": "css",
    },
    {
        "id": "loom",
        "display_name": "Loom",
        "preview_hint": "Throughput as a weaving shuttle",
        "modes": ["light", "dark"],
        "css_layer": "/static/css/themes/loom.css",
        "excited_desc": "Shuttle races, threads interweave in rapid patterns",
        "particles": "thread",
    },
    {
        "id": "prism",
        "display_name": "Prism",
        "preview_hint": "Loss as spectrum intensity, milestones shift the hue",
        "modes": ["light", "dark"],
        "css_layer": "/static/css/themes/prism.css",
        "excited_desc": "Spectrum flares intense white — hue-shifts celebrate milestones",
        "particles": "prism",
    },
    {
        "id": "pulse",
        "display_name": "Pulse",
        "preview_hint": "Throughput as a heartbeat rhythm",
        "modes": ["light", "dark"],
        "css_layer": "/static/css/themes/pulse.css",
        "excited_desc": "Heart races — pulse quickens with every token processed",
        "particles": "pulse",
    },
    {
        "id": "solarflare",
        "display_name": "Solar Flare",
        "preview_hint": "Gradient spikes as coronal eruptions",
        "modes": ["single"],
        "css_layer": "/static/css/themes/solarflare.css",
        "excited_desc": "Coronal mass ejections timed to gradient spikes",
        "particles": "flare",
    },
    {
        "id": "static",
        "display_name": "Static",
        "preview_hint": "Loss volatility as CRT noise",
        "modes": ["single"],
        "css_layer": "/static/css/themes/static.css",
        "excited_desc": "CRT noise intensifies — scanlines glitch with volatility",
        "particles": "css",
    },
    {
        "id": "vinyl",
        "display_name": "Vinyl",
        "preview_hint": "Warm analog tape deck — reels spin with throughput, VU meters track loss",
        "modes": ["light", "dark"],
        "css_layer": "/static/css/themes/vinyl.css",
        "excited_desc": "Reels spin at max RPM, VU needles slam — analog maxed out",
        "particles": "css",
    },
]
"""Catalog of all available themes for the theme gallery page."""


_MODE_LABELS: dict[str, str] = {
    "light": "Light",
    "dark": "Dark",
    "single": "Single",
}
"""Human-readable labels for theme mode badges."""


@router.get("/themes", response_class=HTMLResponse)
async def themes_page(request: Request) -> HTMLResponse:
    """Render the theme gallery showcasing all available themes.

    Displays each theme's normal and excited state preview with
    descriptions, mode support, and particle system info.

    Parameters
    ----------
    request : Request
        The incoming HTTP request.

    Returns
    -------
    HTMLResponse
        Rendered ``archetypes/themes.html`` template.
    """
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "archetypes/themes.html",
        {
            "themes": THEMES_CATALOG,
            "mode_labels": _MODE_LABELS,
        },
    )
