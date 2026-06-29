# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Corpus ORM models for directory-based training corpora.

Corpus and CorpusFile are defined in a single module to eliminate
circular imports between their bidirectional ORM relationship.
No ``TYPE_CHECKING``-guarded imports are needed since both classes
share the same module scope.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ...services.datasets.chunking_strategy import ChunkingStrategy
from ..base import Base
from ..timestamp_mixin import TimestampMixin


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


class CorpusFile(Base, TimestampMixin):
    """An individual file within an ingested corpus.

    Maps to the ``corpus_files`` table. Each row represents a single
    source file discovered during corpus ingestion, tracking metadata
    such as language, line count, character count, chunk count, and
    last-modified timestamp.

    Mapped columns
    --------------
    id : int
        Primary key, auto-increment.
    corpus_id : int
        Foreign key to ``corpora.id`` (CASCADE on delete).
    relative_path : str
        Path of the file relative to the corpus root directory.
    language : str or None
        Detected programming or markup language (50 chars max).
    line_count : int or None
        Number of lines in the file.
    char_count : int or None
        Number of characters in the file.
    chunk_count : int or None
        Number of chunks produced from this file.
    encoding : str or None
        Detected file encoding (20 chars max).
    size_bytes : int or None
        File size in bytes.
    last_modified : datetime or None
        File modification timestamp from the filesystem.

    Relationships
    -------------
    corpus : Corpus
        The parent corpus that owns this file.
    """

    __tablename__ = "corpus_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    corpus_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("corpora.id", ondelete="CASCADE"), nullable=False
    )
    relative_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    line_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    encoding: Mapped[str | None] = mapped_column(String(20), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_modified: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    corpus: Mapped[Corpus] = relationship("Corpus", back_populates="files")