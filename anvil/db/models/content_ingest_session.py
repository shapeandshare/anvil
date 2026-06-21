# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""IngestSession ORM model — isolated content staging session.

A session provides an isolated workspace for staging content before
it is validated and folded into the canonical corpus version.  Each
session is associated with a single corpus and source.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ...services.content.ingest_status import IngestStatus
from ..base import Base
from ..timestamp_mixin import TimestampMixin


class IngestSession(Base, TimestampMixin):
    """An isolated content staging session.

    Maps to the ``content_ingest_sessions`` table.  Each row represents
    a staging session that collects content before validation gates are
    applied and the content is folded into the canonical corpus as a
    new version.

    Parameters
    ----------
    corpus_id : int
        FK to ``content_corpora.id`` (CASCADE on delete).
    source_id : int
        FK to ``content_sources.id`` (RESTRICT on delete).
    staging_key : str
        Unique key identifying the staging area (512 chars max).
    status : str
        Session status from ``IngestStatus``, default
        ``IngestStatus.OPEN``.
    staged_entry_count : int
        Number of entries staged so far, default ``0``.
    problems_json : str or None
        JSON-serialised validation problems (text blob).
    accepted_version_id : int or None
        FK to ``content_versions.id``, set when the session content is
        accepted (SET NULL on delete).
    opened_at : datetime
        Timestamp when the session was opened (server default now).
    closed_at : datetime or None
        Timestamp when the session was closed.
    """

    __tablename__ = "content_ingest_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    corpus_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("content_corpora.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("content_sources.id", ondelete="RESTRICT"), nullable=False
    )
    staging_key: Mapped[str] = mapped_column(String(512), unique=True)
    status: Mapped[str] = mapped_column(String(20), default=IngestStatus.OPEN)
    staged_entry_count: Mapped[int] = mapped_column(Integer, default=0)
    problems_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    accepted_version_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("content_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    opened_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
