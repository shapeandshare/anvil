# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""AssetDownloadJob ORM entity for async asset-download job tracking."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base
from ..timestamp_mixin import TimestampMixin


class AssetDownloadJob(Base, TimestampMixin):
    """Tracks the lifecycle of an async asset-download job.

    Each job represents a single attempt to download all asset files
    (weights, tokenizer, config) for a model.  The ``source_identifier``
    and ``revision`` fields store the HF Hub coordinates directly so
    the background worker can download without querying any other table.

    Attributes
    ----------
    id : int
        Primary key, auto-increment.
    external_model_id : int
        FK to ``external_models.id`` (ON DELETE CASCADE).  This is dead
        schema since Rev 013 dropped the target table; kept as a plain
        integer column for backward-compat with existing assets.
    source_identifier : str or None
        HF Hub repo ID (e.g. ``"TinyLlama/TinyLlama-1.1B-Chat-v1.0"``).
        Set at submit time by the API layer.
    revision : str or None
        HF Hub revision (commit SHA or branch name).  Set at submit time.
    status : str
        Job lifecycle state (``AssetDownloadJobStatus`` value, 20 chars).
    error_code : str | None
        Typed error code if the job failed (50 chars).
    error_message : str | None
        Human-readable error detail if the job failed.
    started_at : datetime | None
        When download began.
    finished_at : datetime | None
        When download completed or failed.
    created_at : datetime
        TimestampMixin: row creation time.
    updated_at : datetime
        TimestampMixin: row last-update time.
    """

    __tablename__ = "asset_download_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_model_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("external_models.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_identifier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    revision: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
