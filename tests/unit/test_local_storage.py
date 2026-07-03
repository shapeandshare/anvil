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


class _MultiChunkBytesStream:
    """Async iterable that yields multiple fixed-size bytes chunks."""

    def __init__(self, data: bytes, chunk_size: int = 1024) -> None:
        self._data = data
        self._chunk_size = chunk_size
        self._offset = 0

    def __aiter__(self) -> AsyncIterator[bytes]:
        return self

    async def __anext__(self) -> bytes:
        if self._offset >= len(self._data):
            raise StopAsyncIteration
        chunk = self._data[self._offset : self._offset + self._chunk_size]
        self._offset += self._chunk_size
        return chunk


class _FailingStream:
    """Async iterable that yields one chunk then raises OSError."""

    def __init__(self) -> None:
        self._started = False

    def __aiter__(self) -> AsyncIterator[bytes]:
        return self

    async def __anext__(self) -> bytes:
        if not self._started:
            self._started = True
            return b"partial "
        msg = "simulated write error"
        raise OSError(msg)


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

    def test_explicit_base_path(self, tmp_path):
        """Constructing with an explicit base_path uses it directly."""
        explicit = str(tmp_path / "my_custom_root")
        store = LocalFileStore(base_path=explicit)
        assert str(store.base_path) == explicit
        assert store.base_path.exists()


class TestResolve:
    """Tests for LocalFileStore._resolve path resolution."""

    def test_resolve_creates_parent_dirs(self):
        """_resolve creates parent directories along the path."""
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            resolved = store._resolve("a/b/c.txt")
            assert resolved.parent.exists()
            assert resolved.name == "c.txt"

    def test_resolve_returns_absolute_under_base(self):
        """_resolve returns an absolute path under the store root."""
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            resolved = store._resolve("f.txt")
            assert resolved.is_absolute()
            root = Path(tmp).resolve()
            assert root in resolved.parents

    def test_resolve_handles_deeply_nested_paths(self):
        """_resolve works with many levels of nesting."""
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            resolved = store._resolve("a/b/c/d/e/f/g/h/i/j.txt")
            assert resolved.parent.exists()
            assert resolved.name == "j.txt"

    def test_resolve_handles_trailing_slash(self):
        """_resolve gracefully handles trailing slash in path."""
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            resolved = store._resolve("trailing/")
            expected = (Path(tmp).resolve() / "trailing").resolve()
            assert resolved == expected


class TestPutAndGet:
    """Tests for LocalFileStore.put and get round-trips."""

    async def test_put_and_get_round_trip(self):
        """Writing and then reading a file returns identical content."""
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            etag = await store.put("hello.txt", _BytesStream(b"hello world"))  # NOSONAR
            assert isinstance(etag, str)
            assert len(etag) > 0
            chunks = [c async for c in store.get("hello.txt")]
            assert b"".join(chunks) == b"hello world"

    async def test_put_returns_mtime_etag(self):
        """Put returns a nanosecond-mtime-based etag string."""
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            etag = await store.put("f.bin", _BytesStream(b"data"))  # NOSONAR
            assert etag.isdigit()

    async def test_put_cleanup_on_failure(self):
        """Failed writes clean up the partial temporary file."""
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            with pytest.raises(OSError, match="simulated write error"):
                await store.put("fail.bin", _FailingStream())
            full = store._resolve("fail.bin")
            assert not full.exists()

    async def test_put_with_empty_stream(self):
        """Putting an empty byte stream creates a zero-byte file."""
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            etag = await store.put("empty.bin", _BytesStream(b""))
            assert isinstance(etag, str)
            full = store._resolve("empty.bin")
            assert full.exists()
            assert full.stat().st_size == 0

    async def test_put_with_multiple_chunks(self):
        """Putting a multi-chunk stream reassembles correctly."""
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            data = b"chunk_data " * 1000  # ~12 KiB
            stream = _MultiChunkBytesStream(data, chunk_size=1024)
            etag = await store.put("multi.bin", stream)
            assert isinstance(etag, str)
            chunks = [c async for c in store.get("multi.bin")]
            assert b"".join(chunks) == data

    async def test_get_large_file_multiple_chunks(self):
        """Get reads a file larger than 64 KiB in multiple chunks."""
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            large_data = b"x" * 70000  # > 65536 bytes
            await store.put("large.bin", _BytesStream(large_data))
            chunks = [c async for c in store.get("large.bin")]
            combined = b"".join(chunks)
            assert len(combined) == 70000
            assert combined == large_data
            # Verify more than one chunk was yielded
            assert len(chunks) > 1

    async def test_put_and_get_in_subdirectory(self):
        """Round-trip a file inside a subdirectory."""
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            etag = await store.put("sub/dir/nested.txt", _BytesStream(b"nested"))
            assert isinstance(etag, str)
            chunks = [c async for c in store.get("sub/dir/nested.txt")]
            assert b"".join(chunks) == b"nested"


class TestGetEdgeCases:
    """Tests for get() edge cases — missing files and paths."""

    async def test_get_nonexistent_raises(self, tmp_path):
        """get() on a path that does not exist raises FileNotFoundError."""
        store = LocalFileStore(str(tmp_path))
        with pytest.raises(FileNotFoundError):
            _ = [c async for c in store.get("missing.txt")]

    async def test_get_nonexistent_in_subdirectory_raises(self, tmp_path):
        """get() on a missing file in a non-existent subdir raises."""
        store = LocalFileStore(str(tmp_path))
        with pytest.raises(FileNotFoundError):
            _ = [c async for c in store.get("sub/dir/missing.txt")]


class TestPutOverwrite:
    """Tests that put() correctly overwrites existing files."""

    async def test_put_overwrites_existing_content(self):
        """Overwriting a file replaces its content."""
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            await store.put("overwrite.txt", _BytesStream(b"original"))
            await store.put("overwrite.txt", _BytesStream(b"replacement"))
            chunks = [c async for c in store.get("overwrite.txt")]
            assert b"".join(chunks) == b"replacement"

    async def test_put_overwrite_updates_etag(self):
        """Overwriting a file produces a different etag."""
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            etag1 = await store.put("etag.txt", _BytesStream(b"first"))
            etag2 = await store.put("etag.txt", _BytesStream(b"second"))
            assert etag1 != etag2


class TestDelete:
    """Tests for LocalFileStore.delete idempotent file removal."""

    async def test_delete_existing(self):
        """Deleting an existing file removes it from disk."""
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            await store.put("del.txt", _BytesStream(b"data"))  # NOSONAR
            await store.delete("del.txt")
            full = store._resolve("del.txt")
            assert not full.exists()

    async def test_delete_nonexistent(self):
        """Deleting a non-existent file is idempotent (no error)."""
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            await store.delete("nonexistent.txt")

    async def test_delete_in_subdirectory(self):
        """Deleting a file inside a subdirectory works correctly."""
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            await store.put("sub/dir/nested.txt", _BytesStream(b"nested data"))
            await store.delete("sub/dir/nested.txt")
            full = store._resolve("sub/dir/nested.txt")
            assert not full.exists()
            # Parent directories should remain
            assert store._resolve("sub/dir").exists()


class TestList:
    """Tests for LocalFileStore.list file enumeration."""

    async def test_list_existing_dir(self):
        """Listing an existing directory returns all files."""
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
        """Listing a non-existent directory returns an empty list."""
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            results = await store.list("nonexistent/")
            assert results == []

    async def test_list_includes_metadata(self):
        """Each listed file entry includes correct metadata fields."""
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

    async def test_list_skips_subdirectories(self):
        """Listing only returns files, skipping subdirectory entries."""
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            await store.put("a.txt", _BytesStream(b"aaa"))
            # Create a subdirectory manually via _resolve
            sub_dir = store._resolve("subdir")
            sub_dir.mkdir(parents=True, exist_ok=True)
            _sub_file = sub_dir / "inner.txt"
            _sub_file.write_text("inner")
            # Only a.txt should appear, not subdir/ or subdir/inner.txt
            results = await store.list("")
            assert len(results) == 1
            assert results[0].path == "a.txt"

    async def test_list_nested_prefix(self):
        """Listing with a nested prefix returns files in that subdirectory."""
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            await store.put("root.txt", _BytesStream(b"root"))
            await store.put("sub/inner.txt", _BytesStream(b"inner"))
            await store.put("sub/deep/other.txt", _BytesStream(b"other"))
            # List the root
            root_results = await store.list("")
            assert len(root_results) == 1
            assert root_results[0].path == "root.txt"
            # List the subdir
            sub_results = await store.list("sub")
            assert len(sub_results) == 1
            assert sub_results[0].path == "inner.txt"
            # List empty subdir
            deep_dir = store._resolve("sub/empty")
            deep_dir.mkdir(parents=True, exist_ok=True)
            empty_results = await store.list("sub/empty")
            assert empty_results == []

    async def test_list_empty_dir(self):
        """Listing an existing but empty directory returns an empty list."""
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFileStore(tmp)
            empty_dir = store._resolve("emptydir")
            empty_dir.mkdir(parents=True, exist_ok=True)
            results = await store.list("emptydir")
            assert results == []
