"""Local filesystem implementation of FileStore."""

import os
import shutil
import tempfile
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path

import aiofiles

from anvil.storage.interface import FileInfo, FileStore


class LocalFileStore(FileStore):
    def __init__(self, base_path: str = "data/storage"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _resolve(self, path: str) -> Path:
        full = (self.base_path / path).resolve()
        full.parent.mkdir(parents=True, exist_ok=True)
        return full

    async def get(self, path: str) -> AsyncIterator[bytes]:
        full = self._resolve(path)
        async with aiofiles.open(full, "rb") as f:
            while chunk := await f.read(65536):
                yield chunk

    async def put(self, path: str, stream: AsyncIterator[bytes]) -> str:
        full = self._resolve(path)
        tmp = tempfile.NamedTemporaryFile(delete=False, dir=full.parent)
        try:
            async with aiofiles.open(tmp.name, "wb") as f:
                async for chunk in stream:
                    await f.write(chunk)
            shutil.move(tmp.name, full)
        except Exception:
            os.unlink(tmp.name)
            raise
        return str(full.stat().st_mtime_ns)

    async def delete(self, path: str) -> None:
        full = self._resolve(path)
        if full.exists():
            full.unlink()

    async def list(self, prefix: str) -> list[FileInfo]:
        results = []
        full_dir = (self.base_path / prefix).resolve()
        if not full_dir.exists():
            return results
        for p in full_dir.iterdir():
            if p.is_file():
                stat = p.stat()
                results.append(
                    FileInfo(
                        path=str(p.relative_to(self.base_path)),
                        size=stat.st_size,
                        etag=str(stat.st_mtime_ns),
                        content_type="application/octet-stream",
                        created_at=datetime.fromtimestamp(stat.st_ctime),
                        updated_at=datetime.fromtimestamp(stat.st_mtime),
                    )
                )
        return results
