"""ContentVersion ORM model — immutable version snapshot.

Each version represents an immutable snapshot of a corpus's content
at a point in time, identified by a monotonically increasing version
number and content-addressed via a manifest digest.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base
from ..timestamp_mixin import TimestampMixin

if TYPE_CHECKING:
    from .content_corpus import ContentCorpus  # TYPE_CHECKING-only: breaks cycle
    from .content_entry import (
        ContentEntry,
    )  # TYPE_CHECKING-only: breaks ContentVersion↔ContentEntry cycle


class ContentVersion(Base, TimestampMixin):
    """An immutable snapshot of a corpus's content.

    Maps to the ``content_versions`` table. Each row is a point-in-time
    version of a corpus identified by a monotonically increasing version
    number and a content-addressed manifest digest.

    Parameters
    ----------
    corpus_id : int
        FK to ``content_corpora.id`` (CASCADE on delete).
    version_number : int
        Monotonically increasing version number within the corpus.
    manifest_digest : str
        SHA-256 hex digest of the version manifest (64 chars).
    label : str or None
        Optional human-readable label (64 chars max).
    note : str or None
        Optional version note (1000 chars max).
    is_composition : bool
        Whether this version is a composition of other versions,
        default ``False``.
    entry_count : int
        Number of entries in this version, default ``0``.
    total_bytes : int
        Total size of all entries in bytes, default ``0``.

    Relationships
    -------------
    corpus : ContentCorpus
        The parent corpus this version belongs to.
    entries : list of ContentEntry
        Entries comprising this version, cascade-deleted.

    Notes
    -----
    ``(corpus_id, version_number)`` is unique — no two versions of the
    same corpus share the same number.  ``(corpus_id, manifest_digest)``
    is also unique — the same digest cannot be recorded twice for the
    same corpus (enforces content-addressed idempotency).
    """

    __tablename__ = "content_versions"

    __table_args__ = (
        UniqueConstraint(
            "corpus_id", "version_number", name="uq_content_versions_corpus_number"
        ),
        UniqueConstraint(
            "corpus_id", "manifest_digest", name="uq_content_versions_corpus_digest"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    corpus_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("content_corpora.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    manifest_digest: Mapped[str] = mapped_column(String(64))
    label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    is_composition: Mapped[bool] = mapped_column(Boolean, default=False)
    entry_count: Mapped[int] = mapped_column(Integer, default=0)
    total_bytes: Mapped[int] = mapped_column(Integer, default=0)

    corpus: Mapped[ContentCorpus] = relationship(
        "ContentCorpus",
        back_populates="versions",
        foreign_keys="ContentVersion.corpus_id",
    )
    entries: Mapped[list[ContentEntry]] = relationship(
        "ContentEntry", back_populates="version", cascade="all, delete-orphan"
    )
