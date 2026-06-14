from __future__ import annotations

from anvil.services.chunking.base import Chunker


class FixedSizeWindowChunker(Chunker):
    """Split text into fixed-size windows with configurable overlap."""

    def __init__(self, block_size: int = 16, overlap: float = 0.5):
        if not 0.0 <= overlap < 1.0:
            raise ValueError(f"overlap must be in [0.0, 1.0), got {overlap}")
        if block_size < 1:
            raise ValueError(f"block_size must be >= 1, got {block_size}")
        self._block_size = block_size
        self._overlap = overlap

    def chunk(self, text: str) -> list[str]:
        if not text:
            return []
        stride = max(1, int(self._block_size * (1 - self._overlap)))
        chunks = []
        start = 0
        while start < len(text):
            end = start + self._block_size
            chunks.append(text[start:end])
            start += stride
        return chunks