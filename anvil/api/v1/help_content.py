# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Help content data model and section definitions for the non-educational help guide.

Provides the ``HelpSection`` Pydantic model and the ``HELP_SECTIONS``
collection used by the ``/v1/help`` page route. Each section covers one
non-educational workspace page (training, data, experiments, models,
playground, operations, content library).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class HelpSection(BaseModel):
    """Help content for one non-educational workspace page.

    Each instance represents a single workspace page entry in the
    ``/v1/help`` anchor-index layout. The ``content`` field holds
    the full help body as HTML, rendered by the Jinja2 template.

    Parameters
    ----------
    anchor_id : str
        URL anchor ID for deep-linking (e.g. ``"training"``, ``"data"``).
        MUST be unique across all sections and match ``^[a-z0-9-]+$``.
    title : str
        Display heading (e.g. ``"Training Dashboard"``). MUST be non-empty.
    route : str
        Path to the workspace page (e.g. ``"/v1/training-page"``).
    description : str
        One-sentence summary for the index listing.
    content : str
        Full help body — HTML rendered by the template. Supports inline
        tags for emphasis, links, and code.
    related_lesson_keys : list[str]
        Keys into ``LEARNING_ARC`` for "Related lessons" links.
        Defaults to ``[]``.
    """

    anchor_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    route: str
    description: str
    content: str
    related_lesson_keys: list[str] = []


HELP_SECTIONS: list[HelpSection] = [
    HelpSection(
        anchor_id="training",
        title="Training Dashboard",
        route="/v1/training-page",
        description=(
            "Configure hyperparameters, start training runs, "
            "and monitor loss curves in real time."
        ),
        content=(
            "<p>The Training Dashboard is the main workspace for "
            "configuring and running model training. Select a data source, "
            "set hyperparameters, choose a compute backend, and watch "
            "results stream in as the model learns.</p>"
        ),
        related_lesson_keys=["parameters", "training-loop", "architecture"],
    ),
    HelpSection(
        anchor_id="data",
        title="Data",
        route="/v1/datasets-page",
        description=(
            "Upload, curate, and manage text corpora and datasets " "for training."
        ),
        content=(
            "<p>The Data page manages all training data. Upload text "
            "files, create datasets, configure corpora as read-only views "
            "over directory structures, and curate content through "
            "deduplication, filtering, and inline editing.</p>"
        ),
        related_lesson_keys=["data-fundamentals", "tokenization", "chunking"],
    ),
    HelpSection(
        anchor_id="experiments",
        title="Experiments",
        route="/v1/experiments-page",
        description=(
            "Compare experiment history, loss curves, and "
            "registered models side by side."
        ),
        content=(
            "<p>The Experiments page shows all training runs and their "
            "results. Compare loss curves, inspect hyperparameters, "
            "and register the best-performing models for deployment "
            "or further experimentation.</p>"
        ),
        related_lesson_keys=["loss", "adam", "experiment-tracking"],
    ),
    HelpSection(
        anchor_id="models",
        title="Models",
        route="/v1/models-page",
        description=(
            "Browse, register, and manage trained models in " "the model registry."
        ),
        content=(
            "<p>The Models page provides access to the model registry. "
            "Browse all trained models, inspect their metadata, register "
            "promising checkpoints, and manage model versions ready for "
            "inference or export.</p>"
        ),
        related_lesson_keys=["export", "memory-divergence"],
    ),
    HelpSection(
        anchor_id="playground",
        title="Playground",
        route="/v1/inference-page",
        description=(
            "Load a trained model and generate text interactively "
            "with configurable sampling parameters."
        ),
        content=(
            "<p>The Playground is the inference and sampling workspace. "
            "Select a registered model, configure temperature and top-K "
            "sampling, and generate text character by character. Watch "
            "the probability distribution adjust in real time as you "
            "change sampling parameters.</p>"
        ),
        related_lesson_keys=["sampling", "attention", "embeddings"],
    ),
    HelpSection(
        anchor_id="operations",
        title="Operations",
        route="/v1/operations-page",
        description=(
            "Monitor system health, manage services, and " "tail service logs."
        ),
        content=(
            "<p>The Operations dashboard provides system-level monitoring "
            "and management. View CPU, memory, and disk metrics, check "
            "service health (web, MLflow), tail service logs, restart "
            "services, and manage the demo data bootstrap.</p>"
        ),
        related_lesson_keys=["cloud-compute", "faq", "glossary"],
    ),
    HelpSection(
        anchor_id="content-library",
        title="Content Library",
        route="/v1/content-page",
        description=(
            "Manage content versioning, provenance, and "
            "governance for training data."
        ),
        content=(
            "<p>The Content Library manages training data versioning "
            "and provenance. Track where data came from, what license "
            "it uses, and how it has changed over time. Every dataset "
            "change is recorded in a hash-chained audit trail.</p>"
        ),
        related_lesson_keys=[
            "content-versioning",
            "governance",
            "data-fundamentals",
        ],
    ),
]
