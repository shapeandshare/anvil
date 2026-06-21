"""Unit tests for content-addressed blob storage operations.

Tests the blob-store contract that ``LocalVersionedContentStore`` will
implement in T039. Written against a simple in-memory dict-based store
to validate the content-addressing rules:

- **Dedup**: storing identical bytes produces the same ``content_hash``
  irrespective of how many times they are stored.
- **Round-trip**: ``open_blob`` returns the exact bytes that were stored.
- **Hash differentiation**: different content → different hashes.
"""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator
from typing import Any

import pytest

from anvil.services.content.manifest import ManifestEntry
from anvil.services.content.staged_entry import StagedEntry


# ── In-memory content-addressed blob store fixture ──────────────────


class _InMemoryBlobStore:
    """A dict-backed content-addressed blob store for testing.

    Mimics the blob storage contract of ``VersionedContentStore``:
    storing returns a hash, and blobs are retrievable by hash.
    """

    def __init__(self) -> None:
        self._blobs: dict[str, bytes] = {}

    async def store(self, data: bytes) -> str:
        """Store bytes and return their SHA-256 hex digest.

        Parameters
        ----------
        data : bytes
            Raw bytes to store.

        Returns
        -------
        str
            SHA-256 hex digest of the stored content.
        """
        content_hash = hashlib.sha256(data).hexdigest()
        if content_hash not in self._blobs:
            self._blobs[content_hash] = data
        return content_hash

    async def open_blob(self, content_hash: str) -> AsyncIterator[bytes]:
        """Yield the bytes for a given content hash.

        Parameters
        ----------
        content_hash : str
            SHA-256 hex digest of the blob to retrieve.

        Yields
        ------
        bytes
            The blob content.

        Raises
        ------
        KeyError
            If the hash is not found in the store.
        """
        data = self._blobs.get(content_hash)
        if data is None:
            raise KeyError(f"Blob not found: {content_hash}")
        yield data

    def __contains__(self, content_hash: str) -> bool:
        """Check whether a given hash exists in the store."""
        return content_hash in self._blobs

    @property
    def blob_count(self) -> int:
        """Number of unique blobs in the store."""
        return len(self._blobs)


def compute_hash(data: bytes) -> str:
    """Compute the SHA-256 hex digest of *data*.

    Parameters
    ----------
    data : bytes
        Input bytes.

    Returns
    -------
    str
        Lower-case hex digest.
    """
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def blob_store() -> _InMemoryBlobStore:
    """Provide a fresh in-memory content-addressed blob store."""
    return _InMemoryBlobStore()


# ── Deduplication ──────────────────────────────────────────────────


class TestBlobDedup:
    """Content-addressed deduplication: identical bytes produce one entry."""

    async def test_same_bytes_same_hash(self, blob_store: _InMemoryBlobStore) -> None:
        """Storing identical bytes twice returns the same hash."""
        data = b"hello content store"
        h1 = await blob_store.store(data)
        h2 = await blob_store.store(data)
        assert h1 == h2

    async def test_dedup_does_not_increase_blob_count(
        self, blob_store: _InMemoryBlobStore
    ) -> None:
        """Re-storing identical bytes does not increase the blob count."""
        data = b"deduplicated blob"
        await blob_store.store(data)
        count_after_first = blob_store.blob_count
        await blob_store.store(data)
        assert blob_store.blob_count == count_after_first

    async def test_dedup_preserves_single_copy(
        self, blob_store: _InMemoryBlobStore
    ) -> None:
        """After storing the same bytes twice, only one blob exists."""
        data = b"single copy"
        await blob_store.store(data)
        await blob_store.store(data)
        h = compute_hash(data)
        assert h in blob_store

    async def test_identical_staged_entries_share_blob(
        self, blob_store: _InMemoryBlobStore
    ) -> None:
        """Staging two entries with identical content produces the same
        ``content_hash``, verifying that ``StagedEntry`` values match."""
        data = b"shared content across entries"
        h1 = await blob_store.store(data)
        h2 = await blob_store.store(data)

        entry1 = StagedEntry(path="a.txt", content_hash=h1, size_bytes=len(data))
        entry2 = StagedEntry(path="b.txt", content_hash=h2, size_bytes=len(data))

        assert entry1.content_hash == entry2.content_hash
        assert entry1.size_bytes == entry2.size_bytes


# ── Round-trip ─────────────────────────────────────────────────────


class TestBlobRoundTrip:
    """Bytes stored can be retrieved intact via open_blob."""

    async def test_open_blob_returns_stored_bytes(
        self, blob_store: _InMemoryBlobStore
    ) -> None:
        """open_blob yields the exact bytes that were stored."""
        data = b"round trip test data"
        h = await blob_store.store(data)

        chunks: list[bytes] = []
        async for chunk in blob_store.open_blob(h):
            chunks.append(chunk)
        retrieved = b"".join(chunks)

        assert retrieved == data

    async def test_large_blob_round_trip(
        self, blob_store: _InMemoryBlobStore
    ) -> None:
        """A large blob (~1 MB) round-trips correctly."""
        data = b"X" * 1_000_000
        h = await blob_store.store(data)

        chunks: list[bytes] = []
        async for chunk in blob_store.open_blob(h):
            chunks.append(chunk)
        retrieved = b"".join(chunks)

        assert len(retrieved) == 1_000_000
        assert retrieved == data

    async def test_binary_blob_round_trip(
        self, blob_store: _InMemoryBlobStore
    ) -> None:
        """Binary content (null bytes, non-UTF8) round-trips intact."""
        data = bytes(range(256))
        h = await blob_store.store(data)

        chunks: list[bytes] = []
        async for chunk in blob_store.open_blob(h):
            chunks.append(chunk)
        retrieved = b"".join(chunks)

        assert retrieved == data

    async def test_zero_length_blob(
        self, blob_store: _InMemoryBlobStore
    ) -> None:
        """Zero-length blob stores and retrieves correctly."""
        data = b""
        h = await blob_store.store(data)

        chunks: list[bytes] = []
        async for chunk in blob_store.open_blob(h):
            chunks.append(chunk)
        retrieved = b"".join(chunks)

        assert retrieved == data
        assert len(retrieved) == 0

    async def test_missing_blob_raises_key_error(
        self, blob_store: _InMemoryBlobStore
    ) -> None:
        """Opening a non-existent blob raises KeyError."""
        fake_hash = "ab" * 32
        with pytest.raises(KeyError, match=fake_hash):
            async for _ in blob_store.open_blob(fake_hash):
                pass  # pragma: no cover


# ── Hash differentiation ───────────────────────────────────────────


class TestBlobHashDifferentiation:
    """Different content must produce different hashes."""

    async def test_different_content_different_hash(
        self, blob_store: _InMemoryBlobStore
    ) -> None:
        """Storing two different byte strings yields different hashes."""
        h_a = await blob_store.store(b"content A")
        h_b = await blob_store.store(b"content B")
        assert h_a != h_b

    async def test_single_byte_difference(
        self, blob_store: _InMemoryBlobStore
    ) -> None:
        """Changing a single byte produces a completely different hash."""
        h1 = await blob_store.store(b"hello world")
        h2 = await blob_store.store(b"hello worlD")  # single char diff
        assert h1 != h2

    async def test_hash_is_sha256_of_content(
        self, blob_store: _InMemoryBlobStore
    ) -> None:
        """The returned hash equals ``sha256(content).hexdigest()``."""
        data = b"verify hash function"
        h = await blob_store.store(data)
        expected = compute_hash(data)
        assert h == expected

    async def test_hash_length_is_64_chars(
        self, blob_store: _InMemoryBlobStore
    ) -> None:
        """All hashes are 64-character hex strings."""
        for content in [b"a", b"bb", b"ccc", b"d" * 1000]:
            h = await blob_store.store(content)
            assert isinstance(h, str)
            assert len(h) == 64
            int(h, 16)  # verify hex

    async def test_different_order_affects_hash(
        self, blob_store: _InMemoryBlobStore
    ) -> None:
        """Same bytes in different order produce different hashes."""
        h_ab = await blob_store.store(b"ab")
        h_ba = await blob_store.store(b"ba")
        assert h_ab != h_ba

    async def test_manifest_entry_hash_derives_from_blob_hash(
        self, blob_store: _InMemoryBlobStore
    ) -> None:
        """A ``ManifestEntry`` created from a stored blob's content hash
        correctly references the blob."""
        data = b"manifest entry blob"
        h = await blob_store.store(data)

        entry = ManifestEntry(path="entry.bin", content_hash=h, weight=1.0)
        assert entry.content_hash == h

        # Verify the blob can be retrieved via the manifest entry hash.
        chunks: list[bytes] = []
        async for chunk in blob_store.open_blob(entry.content_hash):
            chunks.append(chunk)
        retrieved = b"".join(chunks)
        assert retrieved == data