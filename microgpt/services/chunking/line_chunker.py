from __future__ import annotations

from microgpt.services.chunking.base import Chunker


class LineAsDocChunker(Chunker):
    """Split text into one document per non-empty line."""

    def chunk(self, text: str) -> list[str]:
        return [line.strip() for line in text.splitlines() if line.strip()]