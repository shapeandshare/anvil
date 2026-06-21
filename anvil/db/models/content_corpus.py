# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""ContentCorpus ORM model — versioned content corpus.

A named, versioned collection of training content. Each corpus tracks
its current (canonical) version via a forward FK to
``content_versions.id``, creating a circular dependency that is
resolved with a string FK reference and a ``TYPE_CHECKING``-guarded
import.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ...services.content.content_corpus_status import ContentCorpusStatus
from ...services.datasets.chunking_strategy import ChunkingStrategy
from ..base import Base
from ..timestamp_mixin import TimestampMixin

if TYPE_CHECKING:
    from .content_version import (  # TYPE_CHECKING-only: breaks ContentCorpus↔ContentVersion cycle
        ContentVersion,
    )


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
