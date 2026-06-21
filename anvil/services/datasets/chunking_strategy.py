# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

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
