from __future__ import annotations

from abc import ABC, abstractmethod


class Chunker(ABC):

    @abstractmethod
    def chunk(self, text: str) -> list[str]:
        ...