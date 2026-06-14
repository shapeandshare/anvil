"""Pluggable async file storage interface."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from datetime import datetime

from pydantic import BaseModel


class FileInfo(BaseModel):
    path: str
    size: int
    etag: str
    content_type: str
    created_at: datetime
    updated_at: datetime


class FileStore(ABC):
    @abstractmethod
    async def get(self, path: str) -> AsyncIterator[bytes]: ...

    @abstractmethod
    async def put(self, path: str, stream: AsyncIterator[bytes]) -> str: ...

    @abstractmethod
    async def delete(self, path: str) -> None: ...

    @abstractmethod
    async def list(self, prefix: str) -> list[FileInfo]: ...
