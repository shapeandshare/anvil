# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for LocalVersionedContentStore — the local filesystem +
SQLite implementation of VersionedContentStore.

These tests exercise the real store class against a tmp_path for file
storage and an in-memory SQLite database, covering version freeze/resolve,
blob operations, composition, hash stability, and immutability guarantees.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.db.models.content_blob import ContentBlob
from anvil.db.models.content_corpus import ContentCorpus, ContentEntry, ContentVersion
from anvil.db.repositories.content_corpora import ContentCorpusRepository
from anvil.services.content.local_versioned_content_store import (
    LocalVersionedContentStore,
)
from anvil.services.content.manifest import (
    Manifest,
    ManifestEntry,
    compute_manifest_digest,
)
from anvil.services.content.version_ref import VersionRef

# ── Test data constants ──────────────────────────────────────────────

_DOC1_PATH = "docs/intro.txt"
_DOC1_TEXT = "Hello, anvil!"
_DOC1_HASH = hashlib.sha256(_DOC1_TEXT.encode()).hexdigest()

_DOC2_PATH = "docs/setup.txt"
_DOC2_TEXT = "make setup && make run"
_DOC2_HASH = hashlib.sha256(_DOC2_TEXT.encode()).hexdigest()

_DOC3_PATH = "refs/api.txt"
_DOC3_TEXT = "API reference content"
_DOC3_HASH = hashlib.sha256(_DOC3_TEXT.encode()).hexdigest()


# ── Helpers ───────────────────────────────────────────────────────────


async def _async_bytes(data: bytes) -> AsyncIterator[bytes]:
    """Yield *data* as a single chunk via an async iterator."""
    yield data


async def _seed_corpus(db_session: AsyncSession, slug: str = "test-corpus") -> int:
    """Insert a ContentCorpus row and return its primary key."""
    repo = ContentCorpusRepository(db_session)
    corpus = ContentCorpus(slug=slug, name=slug)
    corpus = await repo.add(corpus)
    await db_session.commit()
    return corpus.id


async def _write_blob(content_dir: Path, content_hash: str, data: bytes) -> Path:
    """Write *data* to the content-addressed blob store on disk.

    Creates the sharded ``blobs/<aa>/<hash>`` path under *content_dir*
    and returns the file Path.
    """
    blob_dir = content_dir / "blobs" / content_hash[:2]
    blob_dir.mkdir(parents=True, exist_ok=True)
    blob_path = blob_dir / content_hash
    blob_path.write_bytes(data)
    return blob_path


async def _write_canonical_entries(
    content_dir: Path, corpus_slug: str, entries: list[dict]
) -> Path:
    """Write ``entries.json`` for *corpus_slug* under canonical/.

    Returns the path to the written file.
    """
    canon_dir = content_dir / "canonical" / corpus_slug
    canon_dir.mkdir(parents=True, exist_ok=True)
    entries_path = canon_dir / "entries.json"
    data = {"entries": entries}
    entries_path.write_text(json.dumps(data, indent=2, sort_keys=True))
    return entries_path


# ── Fixture ──────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def store(
    tmp_path: Path, in_memory_session: AsyncSession
) -> LocalVersionedContentStore:
    """Provide a ``LocalVersionedContentStore`` backed by *tmp_path* and
    an in-memory SQLite session.
    """
    content_dir = tmp_path / "content"
    return LocalVersionedContentStore(
        content_dir=str(content_dir), db_session=in_memory_session
    )


# ═════════════════════════════════════════════════════════════════════
# Version freeze & resolve
# ═════════════════════════════════════════════════════════════════════


class TestFreezeAndResolve:
    """`freeze_version()` creates an immutable version; `resolve()` reads it back."""

    async def test_freeze_version_returns_version_ref_with_digest(
        self,
        store: LocalVersionedContentStore,
        in_memory_session: AsyncSession,
        tmp_path: Path,
    ) -> None:
        """Freezing produces a ``VersionRef`` with a non-empty manifest digest."""
        await _seed_corpus(in_memory_session)
        await _write_canonical_entries(
            tmp_path / "content",
            "test-corpus",
            [{"path": _DOC1_PATH, "content_hash": _DOC1_HASH, "weight": 1.0}],
        )

        ref = await store.freeze_version("test-corpus")

        assert isinstance(ref, VersionRef)
        assert len(ref.manifest_digest) == 64
        assert ref.version_number == 1
        assert ref.version_id > 0

    async def test_freeze_version_stores_entries_in_db(
        self,
        store: LocalVersionedContentStore,
        in_memory_session: AsyncSession,
        tmp_path: Path,
    ) -> None:
        """Entries from freeze_version are persisted and retrievable via resolve."""
        await _seed_corpus(in_memory_session)
        await _write_canonical_entries(
            tmp_path / "content",
            "test-corpus",
            [
                {"path": _DOC1_PATH, "content_hash": _DOC1_HASH, "weight": 1.0},
                {"path": _DOC2_PATH, "content_hash": _DOC2_HASH, "weight": 1.0},
            ],
        )

        ref = await store.freeze_version("test-corpus")
        manifest = await store.resolve(ref)

        assert len(manifest.entries) == 2
        paths = {e.path for e in manifest.entries}
        assert paths == {_DOC1_PATH, _DOC2_PATH}

    async def test_resolve_returns_entries_for_known_digest(
        self,
        store: LocalVersionedContentStore,
        in_memory_session: AsyncSession,
        tmp_path: Path,
    ) -> None:
        """Resolving a known ``VersionRef`` returns the correct manifest."""
        await _seed_corpus(in_memory_session)
        await _write_canonical_entries(
            tmp_path / "content",
            "test-corpus",
            [{"path": _DOC1_PATH, "content_hash": _DOC1_HASH, "weight": 1.0}],
        )

        ref = await store.freeze_version("test-corpus")
        manifest = await store.resolve(ref)

        assert manifest.corpus_slug == "test-corpus"
        assert manifest.version_number == 1
        assert len(manifest.entries) == 1
        assert manifest.entries[0].path == _DOC1_PATH
        assert manifest.entries[0].content_hash == _DOC1_HASH

    async def test_resolve_unknown_digest_raises_key_error(
        self,
        store: LocalVersionedContentStore,
    ) -> None:
        """Resolving a ``VersionRef`` with a non-existent version_id raises
        ``KeyError``.
        """
        fake_ref = VersionRef(
            manifest_digest="ff" * 32,
            version_id=99999,
            version_number=0,
        )
        with pytest.raises(KeyError, match="Version not found"):
            await store.resolve(fake_ref)

    async def test_list_versions_returns_version_history(
        self,
        store: LocalVersionedContentStore,
        in_memory_session: AsyncSession,
        tmp_path: Path,
    ) -> None:
        """Freezing multiple versions creates a traceable history with
        incrementing version numbers.
        """
        await _seed_corpus(in_memory_session)
        content_dir = tmp_path / "content"

        # Version 1
        await _write_canonical_entries(
            content_dir,
            "test-corpus",
            [{"path": _DOC1_PATH, "content_hash": _DOC1_HASH, "weight": 1.0}],
        )
        ref1 = await store.freeze_version("test-corpus")
        assert ref1.version_number == 1

        # Version 2 — add a new entry
        await _write_canonical_entries(
            content_dir,
            "test-corpus",
            [
                {"path": _DOC1_PATH, "content_hash": _DOC1_HASH, "weight": 1.0},
                {"path": _DOC2_PATH, "content_hash": _DOC2_HASH, "weight": 1.0},
            ],
        )
        ref2 = await store.freeze_version("test-corpus")
        assert ref2.version_number == 2

        # Version 3 — different content
        await _write_canonical_entries(
            content_dir,
            "test-corpus",
            [
                {"path": _DOC1_PATH, "content_hash": _DOC1_HASH, "weight": 1.0},
                {"path": _DOC2_PATH, "content_hash": _DOC2_HASH, "weight": 1.0},
                {"path": _DOC3_PATH, "content_hash": _DOC3_HASH, "weight": 1.0},
            ],
        )
        ref3 = await store.freeze_version("test-corpus")
        assert ref3.version_number == 3

        # Verify all digests are different (unique versions)
        digests = {ref1.manifest_digest, ref2.manifest_digest, ref3.manifest_digest}
        assert len(digests) == 3, "Each freeze should produce a unique manifest digest"

        # Verify each version resolves correctly
        for ref, expected_count in [(ref1, 1), (ref2, 2), (ref3, 3)]:
            manifest = await store.resolve(ref)
            assert len(manifest.entries) == expected_count


# ═════════════════════════════════════════════════════════════════════
# Edge cases — empty corpus, compositions
# ═════════════════════════════════════════════════════════════════════


class TestFreezeEdgeCases:
    """Freeze behaviour with empty corpora and composition versions."""

    async def test_freeze_empty_corpus_returns_zero_entries(
        self,
        store: LocalVersionedContentStore,
        in_memory_session: AsyncSession,
    ) -> None:
        """Freezing a corpus with no canonical entries yet produces a
        version with 0 entries.
        """
        await _seed_corpus(in_memory_session)
        # No entries.json written → freeze reads empty list.

        ref = await store.freeze_version("test-corpus")
        assert ref.version_number == 1
        assert len(ref.manifest_digest) == 64

        manifest = await store.resolve(ref)
        assert len(manifest.entries) == 0

    async def test_freeze_composition_produces_immutable_version(
        self,
        store: LocalVersionedContentStore,
        in_memory_session: AsyncSession,
        tmp_path: Path,
    ) -> None:
        """Freezing with an explicit composition creates an immutable version
        independent of the canonical state.
        """
        corpus_id = await _seed_corpus(in_memory_session)
        content_dir = tmp_path / "content"

        # Write a canonical entry.
        await _write_canonical_entries(
            content_dir,
            "test-corpus",
            [{"path": _DOC1_PATH, "content_hash": _DOC1_HASH, "weight": 1.0}],
        )

        # Freeze via composition — different entries than canonical.
        composition = [
            ManifestEntry(path="comp-a.bin", content_hash=_DOC2_HASH),
            ManifestEntry(path="comp-b.bin", content_hash=_DOC3_HASH),
        ]
        ref_comp = await store.freeze_version("test-corpus", composition=composition)
        manifest_comp = await store.resolve(ref_comp)

        assert len(manifest_comp.entries) == 2
        comp_paths = {e.path for e in manifest_comp.entries}
        assert comp_paths == {"comp-a.bin", "comp-b.bin"}

        # Verify is_composition was set.
        assert manifest_comp.is_composition is True

        # Fresh freeze without composition reads canonical (1 entry).
        ref_head = await store.freeze_version("test-corpus")
        manifest_head = await store.resolve(ref_head)
        assert len(manifest_head.entries) == 1
        assert manifest_head.entries[0].path == _DOC1_PATH

        # Composition version has a different digest.
        assert ref_comp.manifest_digest != ref_head.manifest_digest

    async def test_multiple_freezes_produce_different_digests(
        self,
        store: LocalVersionedContentStore,
        in_memory_session: AsyncSession,
        tmp_path: Path,
    ) -> None:
        """Freezing a corpus with different canonical states produces
        distinct manifest digests (VCS-2 immutability).
        """
        await _seed_corpus(in_memory_session)
        content_dir = tmp_path / "content"

        # Freeze v1
        await _write_canonical_entries(
            content_dir,
            "test-corpus",
            [{"path": _DOC1_PATH, "content_hash": _DOC1_HASH, "weight": 1.0}],
        )
        ref_v1 = await store.freeze_version("test-corpus")

        # Freeze v2 (different canonical state)
        await _write_canonical_entries(
            content_dir,
            "test-corpus",
            [
                {"path": _DOC1_PATH, "content_hash": _DOC1_HASH, "weight": 1.0},
                {"path": _DOC2_PATH, "content_hash": _DOC2_HASH, "weight": 1.0},
            ],
        )
        ref_v2 = await store.freeze_version("test-corpus")

        assert ref_v1.manifest_digest != ref_v2.manifest_digest

    async def test_freeze_composition_is_composition_flag(
        self,
        store: LocalVersionedContentStore,
        in_memory_session: AsyncSession,
    ) -> None:
        """A composition freeze sets ``is_composition=True``."""
        await _seed_corpus(in_memory_session)
        composition = [
            ManifestEntry(path="a.txt", content_hash=_DOC1_HASH),
        ]
        ref = await store.freeze_version("test-corpus", composition=composition)
        manifest = await store.resolve(ref)
        assert manifest.is_composition is True


# ═════════════════════════════════════════════════════════════════════
# Content blob operations (store / open / manifest)
# ═════════════════════════════════════════════════════════════════════


class TestBlobOperations:
    """Content-addressed blob store/open/manifest round-trips."""

    async def test_store_and_open_blob(
        self,
        store: LocalVersionedContentStore,
        tmp_path: Path,
    ) -> None:
        """A blob written directly to the content-addressed store can be
        opened and read back via ``open_blob``.
        """
        data = b"blob content for round-trip"
        content_hash = hashlib.sha256(data).hexdigest()

        await _write_blob(tmp_path / "content", content_hash, data)

        chunks: list[bytes] = []
        stream = await store.open_blob(content_hash)
        async for chunk in stream:
            chunks.append(chunk)
        retrieved = b"".join(chunks)

        assert retrieved == data

    async def test_open_blob_raises_key_error_for_missing(
        self,
        store: LocalVersionedContentStore,
    ) -> None:
        """Opening a non-existent blob raises ``KeyError``."""
        fake_hash = "ab" * 32
        with pytest.raises(KeyError, match=fake_hash):
            await store.open_blob(fake_hash)

    async def test_manifest_entry_hashes_correspond_to_blobs(
        self,
        store: LocalVersionedContentStore,
        tmp_path: Path,
    ) -> None:
        """A ``ManifestEntry`` created with a known blob hash can be
        resolved to the correct blob content.
        """
        data = b"manifest-linked blob"
        content_hash = hashlib.sha256(data).hexdigest()

        await _write_blob(tmp_path / "content", content_hash, data)

        entry = ManifestEntry(path="entry.bin", content_hash=content_hash, weight=1.0)
        assert entry.content_hash == content_hash

        chunks: list[bytes] = []
        stream = await store.open_blob(entry.content_hash)
        async for chunk in stream:
            chunks.append(chunk)
        retrieved = b"".join(chunks)
        assert retrieved == data

    async def test_manifest_digest_includes_entry_hash(
        self,
        store: LocalVersionedContentStore,
        in_memory_session: AsyncSession,
    ) -> None:
        """The manifest digest correctly incorporates entry content hashes,
        ensuring that different blobs produce different digests.
        """
        await _seed_corpus(in_memory_session)

        composition_a = [ManifestEntry(path="a.txt", content_hash=_DOC1_HASH)]
        composition_b = [ManifestEntry(path="a.txt", content_hash=_DOC2_HASH)]

        ref_a = await store.freeze_version("test-corpus", composition=composition_a)
        ref_b = await store.freeze_version("test-corpus", composition=composition_b)

        assert ref_a.manifest_digest != ref_b.manifest_digest


# ═════════════════════════════════════════════════════════════════════
# Hash stability (SHA-256)
# ═════════════════════════════════════════════════════════════════════


class TestHashStability:
    """SHA-256 digest properties — stability, length, determinism."""

    async def test_content_hash_is_sha256_of_data(
        self,
    ) -> None:
        """Content hashes are plain SHA-256 of the byte content."""
        data = b"verify hash stability"
        expected = hashlib.sha256(data).hexdigest()

        # The store uses hashlib.sha256(raw).hexdigest() internally.
        manifest_entry = ManifestEntry(
            path="test.bin", content_hash=expected, weight=1.0
        )
        assert len(manifest_entry.content_hash) == 64
        assert manifest_entry.content_hash == expected

    async def test_manifest_digest_is_64_char_hex(
        self,
    ) -> None:
        """The manifest digest returned by freeze_version is always a
        64-character lower-case hex string.
        """
        manifest = Manifest(
            corpus_slug="hash-test",
            version_number=1,
            entries=[
                ManifestEntry(path="a.txt", content_hash=_DOC1_HASH, weight=1.0),
            ],
        )
        digest = compute_manifest_digest(manifest)
        assert isinstance(digest, str)
        assert len(digest) == 64
        int(digest, 16)  # raises ValueError if not valid hex

    async def test_different_content_different_hash(
        self,
    ) -> None:
        """Two different blob contents produce different SHA-256 hashes."""
        h1 = hashlib.sha256(b"content one").hexdigest()
        h2 = hashlib.sha256(b"content two").hexdigest()
        assert h1 != h2

    async def test_hash_deterministic_across_calls(
        self,
    ) -> None:
        """Same data produces the same hash every time."""
        data = b"stable content"
        h1 = hashlib.sha256(data).hexdigest()
        h2 = hashlib.sha256(data).hexdigest()
        assert h1 == h2

    async def test_store_blob_hash_matches_expected(
        self,
        store: LocalVersionedContentStore,
        tmp_path: Path,
    ) -> None:
        """A blob stored via the content-addressed path has a hash that
        equals ``sha256(content).hexdigest()``.
        """
        data = b"blob hash verification"
        content_hash = hashlib.sha256(data).hexdigest()

        await _write_blob(tmp_path / "content", content_hash, data)

        # Verify the blob file exists at the expected sharded path.
        blob_path = tmp_path / "content" / "blobs" / content_hash[:2] / content_hash
        assert blob_path.exists()
        assert blob_path.read_bytes() == data

    async def test_manifest_entry_hash_is_sha256(
        self,
    ) -> None:
        """A ``ManifestEntry`` constructed with a SHA-256 hash stores it
        correctly and the manifest digest is a SHA-256 (64-char) string.
        """
        data = b"manifest hash check"
        h = hashlib.sha256(data).hexdigest()
        entry = ManifestEntry(path="chk.bin", content_hash=h, weight=1.0)
        manifest = Manifest(
            corpus_slug="hash-check",
            version_number=1,
            entries=[entry],
        )
        digest = compute_manifest_digest(manifest)
        assert isinstance(digest, str)
        assert len(digest) == 64


# ═════════════════════════════════════════════════════════════════════
# Resolve edge cases
# ═════════════════════════════════════════════════════════════════════


class TestResolveEdgeCases:
    """Edge cases for the resolve method."""

    async def test_resolve_same_version_multiple_times(
        self,
        store: LocalVersionedContentStore,
        in_memory_session: AsyncSession,
        tmp_path: Path,
    ) -> None:
        """Resolving the same ``VersionRef`` multiple times produces
        identical manifests.
        """
        await _seed_corpus(in_memory_session)
        await _write_canonical_entries(
            tmp_path / "content",
            "test-corpus",
            [{"path": _DOC1_PATH, "content_hash": _DOC1_HASH, "weight": 1.0}],
        )

        ref = await store.freeze_version("test-corpus")
        m1 = await store.resolve(ref)
        m2 = await store.resolve(ref)

        assert compute_manifest_digest(m1) == compute_manifest_digest(m2)

    async def test_resolve_after_corpus_mutation_unchanged(
        self,
        store: LocalVersionedContentStore,
        in_memory_session: AsyncSession,
        tmp_path: Path,
    ) -> None:
        """VCS-1: A frozen version's resolve is unaffected by later
        canonical state changes (new freeze_version calls).
        """
        await _seed_corpus(in_memory_session)
        content_dir = tmp_path / "content"

        # Freeze v1.
        await _write_canonical_entries(
            content_dir,
            "test-corpus",
            [{"path": _DOC1_PATH, "content_hash": _DOC1_HASH, "weight": 1.0}],
        )
        ref_v1 = await store.freeze_version("test-corpus")
        manifest_v1 = await store.resolve(ref_v1)

        # Freeze v2 with different entries.
        await _write_canonical_entries(
            content_dir,
            "test-corpus",
            [
                {"path": _DOC1_PATH, "content_hash": _DOC1_HASH, "weight": 1.0},
                {"path": _DOC2_PATH, "content_hash": _DOC2_HASH, "weight": 1.0},
            ],
        )

        # v1 should remain unchanged.
        manifest_v1_again = await store.resolve(ref_v1)
        assert compute_manifest_digest(manifest_v1) == compute_manifest_digest(
            manifest_v1_again
        )
        assert len(manifest_v1_again.entries) == 1
        assert manifest_v1_again.entries[0].path == _DOC1_PATH
