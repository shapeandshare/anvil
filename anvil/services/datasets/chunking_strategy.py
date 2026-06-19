"""Chunking strategy enumeration for corpus processing."""

from enum import StrEnum


class ChunkingStrategy(StrEnum):
    """Text chunking strategy for corpus ingestion.

    Attributes
    ----------
    LINE : str
        Chunk by individual lines (``"line"``).
    WINDOWED : str
        Sliding window chunking (``"windowed"``).
    FILE : str
        Entire file as single chunk (``"file"``).
    """

    LINE = "line"
    WINDOWED = "windowed"
    FILE = "file"