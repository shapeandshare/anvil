# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""ModelImportJob ORM entity for async model-import job tracking."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ...services._shared.import_types import ModelImportJobStatus, SourceType
from ..base import Base
from ..timestamp_mixin import TimestampMixin


class ModelImportJob(Base, TimestampMixin):
    """Tracks the lifecycle of an asynchronous model-import job.

    Each job represents a single attempt to resolve metadata for an
    external model and create an ``ExternalModel`` entry.

    Attributes
    ----------
    id : int
        Primary key, auto-increment.
    status : str
        Job lifecycle state (``ModelImportJobStatus`` value, 20 chars).
    source_type : str
        Source type passed at job creation (20 chars).
    source_identifier : str
        Source identifier passed at job creation (255 chars).
    revision : str
        Source revision requested at job creation (255 chars).
    error_code : str | None
        Typed error code if the job failed (50 chars).
    error_message : str | None
        Human-readable error detail if the job failed.
    external_model_id : int | None
        FK to ``external_models.id``, set on successful completion.
    started_at : datetime | None
        When metadata resolution began.
    finished_at : datetime | None
        When resolution completed or failed.
    created_at : datetime
        TimestampMixin: row creation time.
    updated_at : datetime
        TimestampMixin: row last-update time.
    """

    __tablename__ = "model_import_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ModelImportJobStatus.QUEUED
    )
    source_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=SourceType.HUGGINGFACE
    )
    source_identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    revision: Mapped[str] = mapped_column(String(255), nullable=False, default="main")
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_model_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("external_models.id", ondelete="SET NULL"),
        nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
