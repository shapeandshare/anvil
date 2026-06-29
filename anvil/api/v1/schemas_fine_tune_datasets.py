# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Request/response body models for fine-tune dataset endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class CreateChatTemplateBody(BaseModel):
    """Request body for creating a new chat template.

    Parameters
    ----------
    name : str
        Unique template name.
    template_string : str
        Jinja-like template string.
    tokenizer_family : str
        Valid ``TokenizerFamily`` value.
    base_model_ref : int, optional
        FK to the base model this template originates from.
    description : str, optional
        Optional description.
    """

    name: str
    template_string: str
    tokenizer_family: str
    base_model_ref: int | None = None
    description: str | None = None


class ChatTemplateResponse(BaseModel):
    """Response model for a single chat template.

    Parameters
    ----------
    id : int
        Template primary key.
    name : str
        Template name.
    tokenizer_family : str
        Tokenizer family.
    status : str
        Template lifecycle status.
    created_at : datetime
        Row creation timestamp.
    """

    id: int
    name: str
    tokenizer_family: str
    status: str
    created_at: datetime


class CreateFineTuneDatasetBody(BaseModel):
    """Request body for creating a new fine-tune dataset (preparation job).

    Parameters
    ----------
    dataset_id : int
        Source curated dataset ID.
    chat_template_id : int, optional
        Explicit chat template ID. If omitted, FR-005 resolution applies.
    base_model_ref : int, optional
        Base model to derive template from. Required if ``chat_template_id``
        is omitted and no default template exists.
    record_type : str
        ``"sft"`` or ``"preference"``.
    batch_size : int, optional
        Records per batch (default ``1000``).
    """

    dataset_id: int
    chat_template_id: int | None = None
    base_model_ref: int | None = None
    record_type: str = "sft"
    batch_size: int = 1000


class PreparationSummary(BaseModel):
    """Summary of a preparation job outcome.

    Parameters
    ----------
    total : int
        Total records processed.
    succeeded : int
        Records that passed validation and were rendered.
    failed : int
        Records that failed validation.
    errors : list[dict]
        Per-record error details.
    """

    total: int
    succeeded: int
    failed: int
    errors: list[dict[str, Any]] = []


class JobStatusResponse(BaseModel):
    """Response model for job status polling.

    Parameters
    ----------
    job_id : int
        The preparation job identifier.
    fine_tune_dataset_id : int
        The ``FineTuneDataset`` entry being prepared.
    status : str
        Current job status (``preparing`` | ``ready`` | ``failed``).
    started_at : datetime or None
        When the job started.
    finished_at : datetime or None
        When the job finished.
    summary : PreparationSummary or None
        Job summary (populated on completion).
    """

    job_id: int
    fine_tune_dataset_id: int
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    summary: PreparationSummary | None = None


class FineTuneDatasetResponse(BaseModel):
    """Response model for a fine-tune dataset entry.

    Parameters
    ----------
    id : int
        Entry primary key.
    dataset_id : int
        Source dataset ID.
    chat_template_id : int or None
        Applied template ID.
    base_model_ref : int or None
        Base model reference.
    status : str
        Job status.
    record_type : str
        SFT or preference.
    record_count : int
        Number of successfully prepared records.
    summary : PreparationSummary or None
        Job summary.
    created_at : datetime
        Row creation timestamp.
    updated_at : datetime
        Row last-update timestamp.
    """

    id: int
    dataset_id: int
    chat_template_id: int | None = None
    base_model_ref: int | None = None
    status: str
    record_type: str
    record_count: int = 0
    summary: PreparationSummary | None = None
    created_at: datetime
    updated_at: datetime
