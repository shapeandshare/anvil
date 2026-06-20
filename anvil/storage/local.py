"""Local filesystem implementation of FileStore."""

import os
import shutil
import tempfile
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path

import aiofiles

from .interface import FileInfo, FileStore


class LocalFileStore(FileStore):
    """Filesystem-backed implementation of :class:`FileStore`.

    Stores and retrieves files from a local directory tree. All paths
    are resolved relative to a configurable ``base_path`` root
    directory. Supports atomic writes via a temporary-file-then-rename
    strategy and uses nanosecond mtime for entity-tag generation.

    Parameters
    ----------
    base_path : str, optional
        Root directory for file storage. Created automatically if it
        does not exist. Defaults to ``"data/storage"``.
    """

    def __init__(self, base_path: str = "data/storage"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _resolve(self, path: str) -> Path:
        """Resolve a logical path to an absolute filesystem path.

        Creates parent directories along the way if they do not exist.

        Parameters
        ----------
        path : str
            Logical file path relative to the store root.

        Returns
        -------
        Path
            Absolute :class:`pathlib.Path` pointing into the local
            filesystem.
        """
        full = (self.base_path / path).resolve()
        full.parent.mkdir(parents=True, exist_ok=True)
        return full

    async def get(self, path: str) -> AsyncIterator[bytes]:
        """Read a file as an asynchronous byte stream from disk.

        Parameters
        ----------
        path : str
            Logical path of the file relative to the store root.

        Yields
        ------
        bytes
            Chunks of file content (64 KiB each).
        """
        full = self._resolve(path)
        async with aiofiles.open(full, "rb") as f:
            while chunk := await f.read(65536):
                yield chunk

    async def put(self, path: str, stream: AsyncIterator[bytes]) -> str:
        """Write a file to disk from an asynchronous byte stream.

        Uses an atomic write pattern: data is written to a temporary
        file in the same directory, then renamed to the target path.
        If the write fails, the temporary file is cleaned up.

        Parameters
        ----------
        path : str
            Logical path where the file will be stored.
        stream : AsyncIterator[bytes]
            An asynchronous iterator yielding chunks of data to write.

        Returns
        -------
        str
            Nanosecond mtime string used as an entity tag for change
            detection.

        Raises
        ------
        Exception
            Any exception raised during file I/O; the partial
            temporary file is removed before re-raising.
        """
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
        """Delete a file from the local filesystem.

        Idempotent — no error is raised if the file does not exist.

        Parameters
        ----------
        path : str
            Logical path of the file relative to the store root.
        """
        full = self._resolve(path)
        if full.exists():
            full.unlink()

    async def list(self, prefix: str) -> list[FileInfo]:
        """List all files under a given path prefix.

        Parameters
        ----------
        prefix : str
            Directory path relative to the store root to list.

        Returns
        -------
        list[FileInfo]
            Descriptors for every file directly inside the prefix
            directory. Returns an empty list if the directory does
            not exist.
        """
        results = []
        full_dir = (self.base_path / prefix).resolve()
        if not full_dir.exists():
            return results
        for p in full_dir.iterdir():
            if p.is_file():
                stat = p.stat()
                results.append(
                    FileInfo(
                        path=str(p.relative_to(full_dir)),
                        size=stat.st_size,
                        etag=str(stat.st_mtime_ns),
                        content_type="application/octet-stream",
                        created_at=datetime.fromtimestamp(stat.st_ctime),
                        updated_at=datetime.fromtimestamp(stat.st_mtime),
                    )
                )
        return results
