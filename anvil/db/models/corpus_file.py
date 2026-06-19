"""CorpusFile ORM model for individual files within an ingested corpus."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from .corpus import Corpus

from ..base import Base
from ..timestamp_mixin import TimestampMixin


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
