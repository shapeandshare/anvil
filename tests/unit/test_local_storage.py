# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pragma: allowlist secret
"""Unit tests for LocalFileStore — async filesystem storage."""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from anvil.storage.local import LocalFileStore
from anvil.workspace.workspace_paths import WorkspacePaths


class _BytesStream:
    """Async iterable that yields a single bytes chunk."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._consumed = False

    def __aiter__(self) -> AsyncIterator[bytes]:
        return self

    async def __anext__(self) -> bytes:
        if self._consumed:
            raise StopAsyncIteration
        self._consumed = True
        return self._data


class TestConstructor:
    """Tests for LocalFileStore.__init__ constructor paths."""

    def test_default_base_path_uses_data_storage(self, tmp_path):
        """Constructing with no args defaults base_path to data/storage."""
        store = LocalFileStore()
        assert store.base_path.name == "storage"
        assert store.base_path.parent.name == "data"

    def test_paths_constructor_uses_storage_dir(self, tmp_path):
        """Constructing with WorkspacePaths uses its storage_dir."""
        paths = WorkspacePaths(root=tmp_path)
        store = LocalFileStore(paths=paths)
        assert store.base_path == (tmp_path / "data" / "storage")


class TestResolve:
    def test_resolve_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            resolved = store._resolve("a/b/c.txt")
            assert resolved.parent.exists()
            assert resolved.name == "c.txt"

    def test_resolve_returns_absolute_under_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            resolved = store._resolve("f.txt")
            assert resolved.is_absolute()
            root = Path(tmp).resolve()
            assert root in resolved.parents


class TestPutAndGet:
    async def test_put_and_get_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            etag = await store.put("hello.txt", _BytesStream(b"hello world"))  # NOSONAR
            assert isinstance(etag, str)
            assert len(etag) > 0
            chunks = [c async for c in store.get("hello.txt")]
            assert b"".join(chunks) == b"hello world"

    async def test_put_returns_mtime_etag(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            etag = await store.put("f.bin", _BytesStream(b"data"))  # NOSONAR
            assert etag.isdigit()

    async def test_put_cleanup_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)

            class _FailingStream:
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
            full = store._resolve("fail.bin")
            assert not full.exists()


class TestGetEdgeCases:
    """Tests for get() edge cases — missing files."""

    async def test_get_nonexistent_raises(self, tmp_path):
        """get() on a path that does not exist raises FileNotFoundError."""
        store = LocalFileStore(str(tmp_path))
        with pytest.raises(FileNotFoundError):
            _ = [c async for c in store.get("missing.txt")]


class TestPutOverwrite:
    """Tests that put() correctly overwrites existing files."""

    async def test_put_overwrites_existing_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            await store.put("overwrite.txt", _BytesStream(b"original"))
            await store.put("overwrite.txt", _BytesStream(b"replacement"))
            chunks = [c async for c in store.get("overwrite.txt")]
            assert b"".join(chunks) == b"replacement"

    async def test_put_overwrite_updates_etag(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            etag1 = await store.put("etag.txt", _BytesStream(b"first"))
            etag2 = await store.put("etag.txt", _BytesStream(b"second"))
            assert etag1 != etag2


class TestDelete:
    async def test_delete_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            await store.put("del.txt", _BytesStream(b"data"))  # NOSONAR
            await store.delete("del.txt")
            full = store._resolve("del.txt")
            assert not full.exists()

    async def test_delete_nonexistent(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            await store.delete("nonexistent.txt")


class TestList:
    async def test_list_existing_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            await store.put("a.txt", _BytesStream(b"aaa"))  # NOSONAR
            await store.put("b.txt", _BytesStream(b"bbb"))  # NOSONAR
            results = await store.list("")
            assert len(results) == 2
            paths = {r.path for r in results}
            assert "a.txt" in paths
            assert "b.txt" in paths

    async def test_list_nonexistent_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            results = await store.list("nonexistent/")
            assert results == []

    async def test_list_includes_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            await store.put("meta.txt", _BytesStream(b"metadata"))  # NOSONAR
            results = await store.list("")
            assert len(results) == 1
            info = results[0]
            assert info.size > 0
            assert info.etag is not None
            assert info.content_type == "application/octet-stream"
            assert info.created_at is not None
            assert info.updated_at is not None
