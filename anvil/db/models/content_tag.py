"""ContentTag ORM model — named, GC-protected version tag.

Tags provide human-friendly aliases for specific version snapshots
and can optionally pin versions to prevent garbage collection.
"""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base
from ..timestamp_mixin import TimestampMixin


class ContentTag(Base, TimestampMixin):
    """A named alias for a specific content version.

    Maps to the ``content_tags`` table.  Tags provide human-friendly
    names (e.g. ``"production"``, ``"staging"``) for version snapshots.
    The ``gc_protected`` flag prevents the tagged version from being
    garbage-collected.

    Parameters
    ----------
    version_id : int
        FK to ``content_versions.id`` (CASCADE on delete). Unique.
    name : str
        Unique tag name (256 chars max).
    gc_protected : bool
        Whether the tagged version is protected from GC, default ``True``.
    """

    __tablename__ = "content_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("content_versions.id", ondelete="CASCADE"),
        unique=True,
    )
    name: Mapped[str] = mapped_column(String(256), unique=True)
    gc_protected: Mapped[bool] = mapped_column(Boolean, default=True)
