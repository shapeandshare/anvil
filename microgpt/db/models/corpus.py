"""Corpus and CorpusFile ORM models for directory-based training corpora."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from microgpt.db.base import Base, TimestampMixin


class Corpus(Base, TimestampMixin):
    """A named collection of source files ingested from a directory."""

    __tablename__ = "corpora"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    root_path: Mapped[str] = mapped_column(String(500), nullable=False)
    include_patterns: Mapped[str | None] = mapped_column(Text, nullable=True)
    exclude_patterns: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunking_strategy: Mapped[str] = mapped_column(
        String(20), nullable=False, default="windowed"
    )
    chunk_overlap: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.5
    )
    file_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    document_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    language_map: Mapped[str | None] = mapped_column(Text, nullable=True)

    files: Mapped[list["CorpusFile"]] = relationship(
        "CorpusFile", back_populates="corpus", cascade="all, delete-orphan"
    )


class CorpusFile(Base, TimestampMixin):
    """An individual file within an ingested corpus."""

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

    corpus: Mapped["Corpus"] = relationship(
        "Corpus", back_populates="files"
    )