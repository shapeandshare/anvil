"""Unit tests for LocalFileStore — async filesystem storage.

Tests the _resolve path helper, atomic put/get round-trip,
idempotent delete, and prefix-based listing.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from anvil.storage.local import LocalFileStore


class TestResolve:
    """_resolve path creation and parent-directory creation."""

    def test_resolve_creates_parent_dirs(self):
        """_resolve should create parent directories along the path."""
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            resolved = store._resolve("a/b/c.txt")
            assert resolved.parent.exists()
            assert resolved.name == "c.txt"

    def test_resolve_returns_absolute_under_base(self):
        """_resolve should return an absolute path under base_path."""
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            resolved = store._resolve("f.txt")
            assert resolved.is_absolute()
            root = Path(tmp).resolve()
            assert root in resolved.parents


async def _stream(data: bytes):
    """Helper to produce an async byte-stream from bytes."""
    yield data


async def _empty_stream():
    """Helper to yield an empty async byte-stream."""
    return
    yield  # pragma: no cover


class TestPutAndGet:
    """Round-trip put then get for LocalFileStore."""

    async def test_put_and_get_round_trip(self):
        """Written data should be readable via get."""
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            etag = await store.put("hello.txt", _stream(b"hello world"))
            assert isinstance(etag, str)
            assert len(etag) > 0

            chunks = [c async for c in store.get("hello.txt")]
            assert b"".join(chunks) == b"hello world"

    async def test_put_returns_mtime_etag(self):
        """put should return a nanosecond-mtime string."""
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            etag = await store.put("f.bin", _stream(b"data"))
            assert etag.isdigit()

    async def test_put_cleanup_on_failure(self):
        """put should remove the temp file if the write fails."""
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)

            class _FailingStream:
                """An async stream that fails after yielding partial data."""

                def __init__(self):
                    self._started = False

                def __aiter__(self):
                    return self

                async def __anext__(self) -> bytes:
                    if not self._started:
                        self._started = True
                        return b"partial "
                    msg = "simulated write error"
                    raise OSError(msg)

            with pytest.raises(OSError, match="simulated write error"):
                await store.put("fail.bin", _FailingStream())
            # The temp file should be cleaned up.
            full = store._resolve("fail.bin")
            assert not full.exists()


class TestDelete:
    """Idempotent delete behaviour."""

    async def test_delete_existing(self):
        """Deleting an existing file should remove it."""
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            await store.put("del.txt", _stream(b"data"))
            await store.delete("del.txt")
            full = store._resolve("del.txt")
            assert not full.exists()

    async def test_delete_nonexistent(self):
        """Deleting a non-existent file should not raise."""
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            await store.delete("nonexistent.txt")


class TestList:
    """Prefix-based listing."""

    async def test_list_existing_dir(self):
        """list should return FileInfo for each file."""
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            await store.put("a.txt", _stream(b"aaa"))
            await store.put("b.txt", _stream(b"bbb"))
            results = await store.list("")
            assert len(results) == 2
            paths = {r.path for r in results}
            assert "a.txt" in paths
            assert "b.txt" in paths

    async def test_list_nonexistent_dir(self):
        """list should return empty list for non-existent prefix."""
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            results = await store.list("nonexistent/")
            assert results == []

    async def test_list_includes_metadata(self):
        """FileInfo entries should include size, etag, timestamps."""
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            await store.put("meta.txt", _stream(b"metadata"))
            results = await store.list("")
            assert len(results) == 1
            info = results[0]
            assert info.size > 0
            assert info.etag is not None
            assert info.content_type == "application/octet-stream"
            assert info.created_at is not None
            assert info.updated_at is not None