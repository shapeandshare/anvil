# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""FineTuneDataset ORM model for prepared fine-tuning datasets."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base
from ..timestamp_mixin import TimestampMixin


class FineTuneDataset(Base, TimestampMixin):
    """A prepared, tracked dataset of SFT or preference records.

    Maps to the ``fine_tune_datasets`` table. Each row represents a
    dataset that has been processed through chat-template rendering,
    producing ready-to-consume training records for a fine-tune job
    (044/047).

    Attributes
    ----------
    id : int
        Primary key, auto-increment.
    dataset_id : int
        Foreign key to ``datasets.id`` — the source curated dataset.
    chat_template_id : int or None
        Foreign key to ``chat_templates.id`` — the template applied.
    base_model_ref : int or None
        Foreign key to ``external_models.id`` — the base model whose
        chat template was used.
    status : str
        Preparation job lifecycle status (default ``"preparing"``,
        20 chars max).
    record_type : str
        Type of prepared records (``"sft"`` or ``"preference"``,
        20 chars max).
    summary_json : str or None
        JSON blob with ``total``/``succeeded``/``failed`` counts and
        per-record errors.
    prepared_file_path : str or None
        Path to the prepared JSONL file in FileStore (500 chars max).
    record_count : int
        Number of successfully prepared records (default ``0``).
    started_at : datetime or None
        When the preparation job started.
    finished_at : datetime or None
        When the preparation job finished (success or failure).
    created_at : datetime
        TimestampMixin: row creation time.
    updated_at : datetime
        TimestampMixin: row last-update time.
    """

    __tablename__ = "fine_tune_datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False
    )
    chat_template_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("chat_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    base_model_ref: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("external_models.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(20), default="preparing")
    record_type: Mapped[str] = mapped_column(String(20), nullable=False)
    summary_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    prepared_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
