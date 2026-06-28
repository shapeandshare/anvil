# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""ImportJob ORM model — declarative import configuration.

An import job declares a configuration for pulling content from an
external source into a corpus.  Jobs may produce an ingest session
that tracks the actual staging and validation lifecycle.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ...services.content.ingest_status import IngestStatus
from ..base import Base
from ..timestamp_mixin import TimestampMixin


class ImportJob(Base, TimestampMixin):
    """A declarative import job configuration.

    Maps to the ``content_import_jobs`` table.  Each row represents an
    A job that pulls content from a source into a corpus.  Jobs
    are associated with an optional ingest session that handles the
    staging and validation lifecycle.

    Parameters
    ----------
    corpus_id : int
        FK to ``content_corpora.id`` (CASCADE on delete).
    source_id : int
        FK to ``content_sources.id`` (RESTRICT on delete).
    config_json : str
        JSON-serialised job configuration (text blob).
    status : str
        Job status from ``IngestStatus``, default
        ``IngestStatus.OPEN``.
    session_id : int or None
        FK to ``content_ingest_sessions.id`` (SET NULL on delete).
    message : str or None
        Status or error message (1000 chars max).
    started_at : datetime
        Timestamp when the job was started (server default now).
    finished_at : datetime or None
        Timestamp when the job finished.
    """

    __tablename__ = "content_import_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    corpus_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("content_corpora.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("content_sources.id", ondelete="RESTRICT"), nullable=False
    )
    config_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default=IngestStatus.OPEN)
    session_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("content_ingest_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
