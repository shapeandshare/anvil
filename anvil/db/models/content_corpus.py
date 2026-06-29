# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Versioned content corpus ORM models.

ContentCorpus, ContentVersion, and ContentEntry are defined in a single
module to eliminate circular imports between their bidirectional ORM
relationships. No ``TYPE_CHECKING``-guarded imports are needed since all
three classes share the same module scope.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ...services.content.content_corpus_status import ContentCorpusStatus
from ...services.datasets.chunking_strategy import ChunkingStrategy
from ..base import Base
from ..timestamp_mixin import TimestampMixin


class ContentCorpus(Base, TimestampMixin):
    """A named, versioned collection of training content.

    Maps to the ``content_corpora`` table. Each corpus represents a
    versioned content substrate with configurable chunking strategy,
    block size, overlap, and provenance metadata.

    Parameters
    ----------
    slug : str
        Unique machine-readable identifier (128 chars max).
    name : str
        Human-readable corpus name (255 chars max).
    description : str or None
        Optional description (1000 chars max).
    chunking_strategy : str
        Chunking algorithm name, default ``ChunkingStrategy.WINDOWED``.
    block_size : int
        Token block size, default ``16``.
    chunk_overlap : float
        Fractional overlap between chunks, default ``0.5``.
    default_language : str
        Default language code, default ``"en"``.
    status : str
        Lifecycle status from ``ContentCorpusStatus``, default
        ``ContentCorpusStatus.DRAFT``.
    current_version_id : int or None
        Forward FK to the current ``ContentVersion`` (nullable).
    source_description : str or None
        Provenance source description (1000 chars max).
    license_id : int or None
        FK to ``license_catalog.id`` (RESTRICT on delete).
    attribution_text : str or None
        Attribution text for license compliance (1000 chars max).
    origin : str
        Origin discriminator, default ``"user"``.
    parent_provenance_ref : int or None
        Optional reference to a parent provenance record.

    Relationships
    -------------
    versions : list of ContentVersion
        All versions belonging to this corpus, cascade-deleted.
    """

    __tablename__ = "content_corpora"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    chunking_strategy: Mapped[str] = mapped_column(
        String(20), default=ChunkingStrategy.WINDOWED
    )
    block_size: Mapped[int] = mapped_column(Integer, default=16)
    chunk_overlap: Mapped[float] = mapped_column(Float, default=0.5)
    default_language: Mapped[str] = mapped_column(String(16), default="en")
    status: Mapped[str] = mapped_column(String(20), default=ContentCorpusStatus.DRAFT)
    current_version_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("content_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Provenance fields.
    source_description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    license_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("license_catalog.id", ondelete="RESTRICT"),
        nullable=True,
    )
    attribution_text: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    origin: Mapped[str] = mapped_column(String(20), default="user")
    parent_provenance_ref: Mapped[int | None] = mapped_column(Integer, nullable=True)

    versions: Mapped[list[ContentVersion]] = relationship(
        "ContentVersion",
        back_populates="corpus",
        cascade="all, delete-orphan",
        foreign_keys="ContentVersion.corpus_id",
    )


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