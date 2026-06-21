# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Corpus ORM model for directory-based training corpora."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ...services.datasets.chunking_strategy import ChunkingStrategy
from ..base import Base
from ..timestamp_mixin import TimestampMixin

if TYPE_CHECKING:
    from .corpus_file import (  # TYPE_CHECKING-only: breaks Corpus<->CorpusFile ORM bidirectional-FK cycle
        CorpusFile,
    )


class Corpus(Base, TimestampMixin):
    """A named collection of source files ingested from a directory.

    Maps to the ``corpora`` table. Each corpus represents a directory
    of source files that have been ingested, chunked, and prepared for
    training. Supports hierarchical organization via ``parent``/``forks``
    relationships and configurable chunking strategies.

    Mapped columns
    --------------
    id : int
        Primary key, auto-increment.
    name : str
        Unique corpus name (255 chars max).
    description : str or None
        Optional human-readable description (1000 chars max).
    root_path : str
        Absolute filesystem path to the corpus source directory.
    include_patterns : str or None
        Gitignore-style patterns for files to include (text blob).
    exclude_patterns : str or None
        Gitignore-style patterns for files to exclude (text blob).
    chunking_strategy : str
        Chunking algorithm name (default ``ChunkingStrategy.WINDOWED``).
    chunk_overlap : float
        Fractional overlap between adjacent chunks (default ``0.5``).
    block_size : int
        Token block size for chunking (default ``16``).
    parent_id : int or None
        Foreign key to parent corpus in ``corpora`` table,
        enabling fork hierarchies.
    file_count : int
        Number of ingested files (default ``0``).
    document_count : int
        Number of total documents across all files (default ``0``).
    language_map : str or None
        JSON-encoded mapping of detected languages (text blob).
    errors : str or None
        Error messages from ingestion (text blob).

    Relationships
    -------------
    files : list of CorpusFile
        Individual files belonging to this corpus, cascade-deleted.
    parent : Corpus or None
        The parent corpus this corpus was forked from.
    forks : list of Corpus
        Child corpora forked from this corpus.
    """

    __tablename__ = "corpora"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    root_path: Mapped[str] = mapped_column(String(500), nullable=False)
    include_patterns: Mapped[str | None] = mapped_column(Text, nullable=True)
    exclude_patterns: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunking_strategy: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ChunkingStrategy.WINDOWED
    )
    chunk_overlap: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    block_size: Mapped[int] = mapped_column(Integer, nullable=False, default=16)
    parent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("corpora.id", ondelete="SET NULL"), nullable=True
    )
    file_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    document_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    language_map: Mapped[str | None] = mapped_column(Text, nullable=True)
    errors: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Provenance fields.
    source_description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    license_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("license_catalog.id", ondelete="RESTRICT"), nullable=True
    )
    attribution_text: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    origin: Mapped[str] = mapped_column(String(20), default="user")
    parent_provenance_ref: Mapped[int | None] = mapped_column(Integer, nullable=True)

    files: Mapped[list[CorpusFile]] = relationship(
        "CorpusFile", back_populates="corpus", cascade="all, delete-orphan"
    )
    parent: Mapped[Corpus | None] = relationship(
        "Corpus", remote_side="Corpus.id", back_populates="forks"
    )
    forks: Mapped[list[Corpus]] = relationship("Corpus", back_populates="parent")
