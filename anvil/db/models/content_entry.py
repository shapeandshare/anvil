"""ContentEntry ORM model — single entry within a version.

Each entry represents an individual piece of content (e.g. a file,
document, or text chunk) that belongs to a specific version of a
corpus.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base
from ..timestamp_mixin import TimestampMixin

if TYPE_CHECKING:
    from .content_version import (
        ContentVersion,
    )  # TYPE_CHECKING-only: breaks ContentEntry↔ContentVersion cycle


class ContentEntry(Base, TimestampMixin):
    """A single content item within a version snapshot.

    Maps to the ``content_entries`` table. Each row represents an
    individual piece of content (file, document, or chunk) that
    belongs to a specific version of a corpus.  Content is referenced
    by its hash for deduplication via :class:`ContentBlob`.

    Parameters
    ----------
    version_id : int
        FK to ``content_versions.id`` (CASCADE on delete).
    path : str
        Virtual path within the version (1024 chars max).
    content_hash : str
        SHA-256 hex digest of the content body (64 chars).
    weight : float
        Sampling weight for this entry, default ``1.0``.
    source_id : int or None
        FK to ``content_sources.id`` (SET NULL on delete).
    size_bytes : int
        Content size in bytes, default ``0``.

    Relationships
    -------------
    version : ContentVersion
        The version that owns this entry.
    """

    __tablename__ = "content_entries"

    __table_args__ = (Index("ix_content_entries_version_path", "version_id", "path"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("content_versions.id", ondelete="CASCADE"), nullable=False
    )
    path: Mapped[str] = mapped_column(String(1024))
    content_hash: Mapped[str] = mapped_column(String(64))
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    source_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("content_sources.id", ondelete="SET NULL"), nullable=True
    )
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)

    version: Mapped[ContentVersion] = relationship(
        "ContentVersion", back_populates="entries"
    )
