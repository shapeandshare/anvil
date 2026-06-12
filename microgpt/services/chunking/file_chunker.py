from __future__ import annotations

from microgpt.services.chunking.base import Chunker


class FileAsDocChunker(Chunker):
    """Treat the entire file content as a single document."""

    def chunk(self, text: str) -> list[str]:
        if not text:
            return []
        return [text]