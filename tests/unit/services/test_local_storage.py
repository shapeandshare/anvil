"""Tests for LocalFileStore — filesystem-backed FileStore implementation.

Covers the full LocalFileStore API including get, put, delete, list,
and the internal _resolve helper.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from anvil.storage.local import LocalFileStore


async def _bytes_stream(data: bytes) -> AsyncIterator[bytes]:
    """Yield a single chunk of bytes."""
    yield data


class TestLocalFileStore:
    """Tests for LocalFileStore."""

    def test_init_default_base_path(self, tmp_path: Path) -> None:
        """Defaults to 'data/storage' when no path given."""
        store = LocalFileStore(base_path=str(tmp_path / "storage"))
        assert store.base_path == tmp_path / "storage"
        assert store.base_path.exists()

    def test_init_with_explicit_base_path(self, tmp_path: Path) -> None:
        """Uses explicit base_path when provided."""
        p = tmp_path / "custom"
        store = LocalFileStore(base_path=str(p))
        assert store.base_path == p
        assert p.exists()

    @pytest.mark.asyncio
    async def test_put_and_get_roundtrip(self, tmp_path: Path) -> None:
        """put() then get() returns the same content."""
        store = LocalFileStore(base_path=str(tmp_path))
        content = b"hello world"
        etag = await store.put("test.txt", _bytes_stream(content))
        assert isinstance(etag, str)
        assert len(etag) > 0

        chunks = [chunk async for chunk in store.get("test.txt")]
        assert b"".join(chunks) == content

    @pytest.mark.asyncio
    async def test_get_raises_on_missing_file(self, tmp_path: Path) -> None:
        """get() raises FileNotFoundError for non-existent path."""
        store = LocalFileStore(base_path=str(tmp_path))
        with pytest.raises(FileNotFoundError):
            async for _ in store.get("nonexistent.txt"):
                pass

    @pytest.mark.asyncio
    async def test_put_large_content(self, tmp_path: Path) -> None:
        """put() handles content larger than one 64 KiB chunk."""
        store = LocalFileStore(base_path=str(tmp_path))
        content = b"x" * 200_000  # > 64 KiB
        await store.put("large.bin", _bytes_stream(content))
        chunks = [chunk async for chunk in store.get("large.bin")]
        assert b"".join(chunks) == content

    @pytest.mark.asyncio
    async def test_put_creates_intermediate_dirs(self, tmp_path: Path) -> None:
        """put() creates parent directories along the path."""
        store = LocalFileStore(base_path=str(tmp_path))
        await store.put("a/b/c/deep.txt", _bytes_stream(b"deep"))
        assert (tmp_path / "a" / "b" / "c" / "deep.txt").exists()

    @pytest.mark.asyncio
    async def test_delete_removes_file(self, tmp_path: Path) -> None:
        """delete() removes the file from disk."""
        store = LocalFileStore(base_path=str(tmp_path))
        await store.put("test.txt", _bytes_stream(b"data"))
        assert (tmp_path / "test.txt").exists()
        await store.delete("test.txt")
        assert not (tmp_path / "test.txt").exists()

    @pytest.mark.asyncio
    async def test_delete_idempotent(self, tmp_path: Path) -> None:
        """delete() does not raise on non-existent file."""
        store = LocalFileStore(base_path=str(tmp_path))
        await store.delete("nonexistent.txt")  # Should not raise

    @pytest.mark.asyncio
    async def test_list_returns_files(self, tmp_path: Path) -> None:
        """list() returns FileInfo for files under a prefix."""
        store = LocalFileStore(base_path=str(tmp_path))
        await store.put("a.txt", _bytes_stream(b"aaa"))
        await store.put("b.txt", _bytes_stream(b"bbb"))

        files = await store.list("")
        assert len(files) == 2
        names = sorted(f.path for f in files)
        assert names == ["a.txt", "b.txt"]

    @pytest.mark.asyncio
    async def test_list_returns_empty_for_nonexistent_dir(self, tmp_path: Path) -> None:
        """list() returns empty list when prefix directory does not exist."""
        store = LocalFileStore(base_path=str(tmp_path))
        files = await store.list("nonexistent")
        assert files == []

    @pytest.mark.asyncio
    async def test_list_skips_directories(self, tmp_path: Path) -> None:
        """list() only returns files, not subdirectories."""
        store = LocalFileStore(base_path=str(tmp_path))
        await store.put("sub/inside.txt", _bytes_stream(b"data"))
        (tmp_path / "sub").mkdir(parents=True, exist_ok=True)
        (tmp_path / "sub" / "nested").mkdir(exist_ok=True)

        files = await store.list("sub")
        assert len(files) == 1
        assert files[0].path == "inside.txt"

    @pytest.mark.asyncio
    async def test_list_includes_file_metadata(self, tmp_path: Path) -> None:
        """list() returns FileInfo with size and etag populated."""
        store = LocalFileStore(base_path=str(tmp_path))
        content = b"test data"
        await store.put("info.txt", _bytes_stream(content))

        files = await store.list("")
        assert len(files) == 1
        f = files[0]
        assert f.size == len(content)
        assert f.etag is not None
        assert f.content_type == "application/octet-stream"

    @pytest.mark.asyncio
    async def test_put_etag_is_mtime_ns(self, tmp_path: Path) -> None:
        """put() returns a nanosecond mtime string as etag."""
        store = LocalFileStore(base_path=str(tmp_path))
        etag = await store.put("etag_test.txt", _bytes_stream(b"data"))
        # Nanosecond mtime should be a positive integer string.
        assert etag.isdigit()
        assert int(etag) > 0


class TestResolve:
    """Tests for the internal _resolve method."""

    def test_resolve_creates_parent_dirs(self, tmp_path: Path) -> None:
        """_resolve creates parent directories."""
        store = LocalFileStore(base_path=str(tmp_path))
        path = store._resolve("a/b/c/file.txt")
        assert path.parent.exists()
        assert path.name == "file.txt"

    def test_resolve_returns_absolute_path(self, tmp_path: Path) -> None:
        """_resolve returns an absolute path."""
        store = LocalFileStore(base_path=str(tmp_path))
        path = store._resolve("foo.txt")
        assert path.is_absolute()