# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Contract tests for VersionedContentStore guarantees VCS-1 and VCS-2.

Tests two foundational contract guarantees (from
``docs/vault/Specs/019 LakeFS Content Repo/contracts/versioned-content-store.md``):

- **VCS-1**: A ``VersionRef.manifest_digest`` resolves to a byte-identical
  entry set forever. Once frozen, ``resolve()`` returns the exact same
  entries regardless of later corpus changes.
- **VCS-2**: Frozen versions are immutable; any change produces a new
  version with a different ``manifest_digest``. The original is unchanged.

Uses a fully in-memory ``FakeVersionedContentStore`` that implements the
entire ``VersionedContentStore`` ABC contract for testing purposes.
"""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator
from typing import Any

import pytest

from anvil.services.content.accept_result import AcceptResult
from anvil.services.content.ingest_session_ref import IngestSessionRef
from anvil.services.content.manifest import (
    Manifest,
    ManifestEntry,
    compute_manifest_digest,
)
from anvil.services.content.staged_entry import StagedEntry
from anvil.services.content.validation_report import ValidationReport
from anvil.services.content.version_ref import VersionRef
from anvil.services.content.versioned_content_store import VersionedContentStore

# ── In-memory fake implementation ────────────────────────────────


class _FrozenVersion:
    """Immutable snapshot of a frozen version's state."""

    def __init__(self, manifest: Manifest, digest: str) -> None:
        self.manifest = manifest
        self.digest = digest


class FakeVersionedContentStore(VersionedContentStore):
    """A fully in-memory ``VersionedContentStore`` for contract testing.

    Implements the entire ABC contract with dict-based storage. Every
    ``freeze_version`` creates an immutable snapshot preserved under its
    ``manifest_digest``. Mutations do not affect already-frozen versions
    (VCS-2). Accepting a session advances the HEAD; frozen versions
    remain readable forever (VCS-1).
    """

    def __init__(self) -> None:
        self._corpora: set[str] = set()
        self._head: dict[str, list[tuple[StagedEntry, bytes]]] = {}
        self._frozen: dict[str, _FrozenVersion] = {}
        self._blobs: dict[str, bytes] = {}
        self._next_session_id: int = 1
        self._sessions: dict[int, dict[str, bytes]] = {}
        self._session_refs: dict[int, IngestSessionRef] = {}
        self._next_version_id: int = 1
        self._tags: dict[str, VersionRef] = {}
        self._version_numbers: dict[str, int] = {}

    # ── Corpora ────────────────────────────────────────────────────

    async def ensure_corpus(self, slug: str) -> None:
        self._corpora.add(slug)
        if slug not in self._head:
            self._head[slug] = []
        if slug not in self._version_numbers:
            self._version_numbers[slug] = 0

    # ── Ingestion sessions ─────────────────────────────────────────

    async def open_session(
        self, corpus_slug: str, source_slug: str
    ) -> IngestSessionRef:
        self._assert_corpus_exists(corpus_slug)
        sid = self._next_session_id
        self._next_session_id += 1
        ref = IngestSessionRef(
            session_id=sid,
            corpus_id=hash(corpus_slug),
            staging_key=f"staging-{sid}",
            status="open",
        )
        self._sessions[sid] = {}
        self._session_refs[sid] = ref
        return ref

    async def stage(
        self,
        session: IngestSessionRef,
        path: str,
        data: AsyncIterator[bytes],
    ) -> StagedEntry:
        sid = session.session_id
        if sid not in self._sessions:
            raise ValueError(f"Session {sid} not found")
        if self._session_refs[sid].status != "open":
            raise ValueError(
                f"Session {sid} is not open (status={self._session_refs[sid].status})"
            )

        chunks: list[bytes] = []
        async for chunk in data:
            chunks.append(chunk)
        content = b"".join(chunks)

        content_hash = hashlib.sha256(content).hexdigest()
        self._blobs[content_hash] = content
        self._sessions[sid][path] = content

        return StagedEntry(
            path=path, content_hash=content_hash, size_bytes=len(content)
        )

    async def validate_batch(self, session: IngestSessionRef) -> ValidationReport:
        self._assert_session_open(session.session_id)
        return ValidationReport(ok=True)

    async def accept_session(self, session: IngestSessionRef) -> AcceptResult:
        sid = session.session_id
        self._assert_session_open(sid)

        staged = self._sessions[sid]
        if not staged:
            raise ValueError(f"Session {sid} has no staged content")

        self._session_refs[sid].status = "accepted"

        corpus_slug = self._get_corpus_for_session(sid)

        total_bytes = 0
        accepted_entries: list[tuple[StagedEntry, bytes]] = []
        for path, content in staged.items():
            content_hash = hashlib.sha256(content).hexdigest()
            entry = StagedEntry(
                path=path, content_hash=content_hash, size_bytes=len(content)
            )
            accepted_entries.append((entry, content))
            total_bytes += len(content)

        existing = self._head.get(corpus_slug, [])
        self._head[corpus_slug] = existing + accepted_entries

        version_number = self._version_numbers.get(corpus_slug, 0) + 1
        self._version_numbers[corpus_slug] = version_number

        all_head = self._head[corpus_slug]
        manifest_entries = [
            ManifestEntry(path=e.path, content_hash=e.content_hash, weight=1.0)
            for e, _ in all_head
        ]
        manifest = Manifest(
            corpus_slug=corpus_slug,
            version_number=version_number,
            entries=manifest_entries,
        )
        digest = compute_manifest_digest(manifest)

        return AcceptResult(
            version_id=self._get_next_version_id(),
            manifest_digest=digest,
            version_number=version_number,
            entry_count=len(accepted_entries),
            total_bytes=total_bytes,
        )

    async def abandon_session(self, session: IngestSessionRef) -> None:
        sid = session.session_id
        if sid in self._sessions:
            self._session_refs[sid].status = "failed"
            del self._sessions[sid]

    # ── Versions & composition ─────────────────────────────────────

    async def freeze_version(
        self,
        corpus_slug: str,
        composition: list[ManifestEntry] | None = None,
    ) -> VersionRef:
        self._assert_corpus_exists(corpus_slug)

        if composition is not None:
            entries = composition
        else:
            head_entries = self._head.get(corpus_slug, [])
            entries = [
                ManifestEntry(path=e.path, content_hash=e.content_hash, weight=1.0)
                for e, _ in head_entries
            ]

        version_number = self._version_numbers.get(corpus_slug, 0)
        manifest = Manifest(
            corpus_slug=corpus_slug,
            version_number=version_number,
            entries=entries,
        )
        digest = compute_manifest_digest(manifest)

        version_id = self._get_next_version_id()
        ref = VersionRef(
            manifest_digest=digest,
            version_id=version_id,
            version_number=version_number,
        )

        self._frozen[digest] = _FrozenVersion(manifest=manifest, digest=digest)
        return ref

    async def resolve(self, version_ref: VersionRef) -> Manifest:
        digest = version_ref.manifest_digest
        frozen = self._frozen.get(digest)
        if frozen is None:
            raise KeyError(f"Version not found: {digest}")
        return frozen.manifest

    async def open_blob(self, content_hash: str) -> AsyncIterator[bytes]:
        data = self._blobs.get(content_hash)
        if data is None:
            raise KeyError(f"Blob not found: {content_hash}")

        class _SingleChunk:
            """An async iterator yielding a single chunk of bytes."""

            def __init__(self, content: bytes) -> None:
                self._content = content
                self._exhausted = False

            def __aiter__(self) -> _SingleChunk:
                return self

            async def __anext__(self) -> bytes:
                if self._exhausted:
                    raise StopAsyncIteration
                self._exhausted = True
                return self._content

        return _SingleChunk(data)

    async def revert(self, corpus_slug: str, to_version: VersionRef) -> None:
        self._assert_corpus_exists(corpus_slug)
        manifest = await self.resolve(to_version)

        new_head: list[tuple[StagedEntry, bytes]] = []
        for entry in manifest.entries:
            stream = await self.open_blob(entry.content_hash)
            data = b"".join([chunk async for chunk in stream])
            staged = StagedEntry(
                path=entry.path,
                content_hash=entry.content_hash,
                size_bytes=len(data),
            )
            new_head.append((staged, data))

        self._head[corpus_slug] = new_head

    # ── Promotion tagging (T038a contract) ────────────────────────

    async def tag_version(self, tag_name: str, version_ref: VersionRef) -> None:
        """Tag a frozen version with a human-readable name.

        Parameters
        ----------
        tag_name : str
            Unique tag name.
        version_ref : VersionRef
            Reference to the version to tag.

        Raises
        ------
        ValueError
            If the tag name is already in use.
        KeyError
            If the version digest is not frozen.
        """
        if tag_name in self._tags:
            raise ValueError(f"Tag '{tag_name}' already exists")
        if version_ref.manifest_digest not in self._frozen:
            raise KeyError(f"Version not frozen: {version_ref.manifest_digest}")
        self._tags[tag_name] = version_ref

    async def resolve_by_tag(self, tag_name: str) -> VersionRef:
        """Resolve a tag name to its VersionRef.

        Parameters
        ----------
        tag_name : str
            Tag name to resolve.

        Returns
        -------
        VersionRef
            The tagged version reference.

        Raises
        ------
        KeyError
            If the tag does not exist.
        """
        if tag_name not in self._tags:
            raise KeyError(f"Tag not found: {tag_name}")
        return self._tags[tag_name]

    # ── Internal helpers ───────────────────────────────────────────

    def _assert_corpus_exists(self, slug: str) -> None:
        if slug not in self._corpora:
            raise ValueError(f"Corpus not found: {slug}")

    def _assert_session_open(self, sid: int) -> None:
        if sid not in self._session_refs:
            raise ValueError(f"Session {sid} not found")
        if self._session_refs[sid].status != "open":
            raise ValueError(
                f"Session {sid} is not open (status={self._session_refs[sid].status})"
            )

    def _get_corpus_for_session(self, sid: int) -> str:
        """Reverse-lookup the corpus slug for a given session.

        Iterates the head dict keys; correct for single-corpus testing.
        """
        if self._corpora:
            return next(iter(self._corpora))
        raise ValueError("No corpora exist")

    _next_vid: int = 1

    def _get_next_version_id(self) -> int:
        vid = self._next_vid
        self._next_vid += 1
        return vid


# ── Fixture ────────────────────────────────────────────────────────


@pytest.fixture
def store() -> FakeVersionedContentStore:
    """Provide a fresh in-memory ``FakeVersionedContentStore`` for contract tests."""
    return FakeVersionedContentStore()


async def _store_blob_bytes(data: bytes) -> AsyncIterator[bytes]:
    """Yield *data* in chunks as an async iterator, mimicking an upload stream."""
    yield data


# ═══════════════════════════════════════════════════════════════════
# VCS-1: manifest_digest → byte-identical entry set forever
# ═══════════════════════════════════════════════════════════════════


class TestVCS1:
    """A ``VersionRef.manifest_digest`` resolves to a byte-identical
    entry set forever (FR-003, SC-001).
    """

    async def test_freeze_then_resolve_returns_entries(
        self, store: FakeVersionedContentStore
    ) -> None:
        """After freezing, ``resolve()`` returns the exact entries frozen."""
        await store.ensure_corpus("corpus-a")

        session = await store.open_session("corpus-a", "source-x")
        await store.stage(session, "doc1.txt", _store_blob_bytes(b"hello"))
        await store.stage(session, "doc2.txt", _store_blob_bytes(b"world"))
        report = await store.validate_batch(session)
        assert report.ok
        await store.accept_session(session)
        ref = await store.freeze_version("corpus-a")
        manifest = await store.resolve(ref)

        assert len(manifest.entries) == 2
        paths = {e.path for e in manifest.entries}
        assert paths == {"doc1.txt", "doc2.txt"}
        assert ref.manifest_digest == compute_manifest_digest(manifest)

    async def test_resolve_digest_matches_manifest_digest(
        self, store: FakeVersionedContentStore
    ) -> None:
        """The ``VersionRef.manifest_digest`` equals the digest computed
        from the resolved manifest.
        """
        await store.ensure_corpus("digest-match")
        session = await store.open_session("digest-match", "src")
        await store.stage(session, "data.csv", _store_blob_bytes(b"a,b,c"))
        assert (await store.validate_batch(session)).ok
        await store.accept_session(session)

        ref = await store.freeze_version("digest-match")
        manifest = await store.resolve(ref)
        recomputed = compute_manifest_digest(manifest)

        assert ref.manifest_digest == recomputed

    async def test_resolve_entries_byte_identical(
        self, store: FakeVersionedContentStore
    ) -> None:
        """Blobs referenced by frozen entries can be opened and match
        the original staged content byte-for-byte.
        """
        await store.ensure_corpus("byte-identity")
        content_a = b"\x00\x01\x02"
        content_b = b"\xff\xfe\xfd"
        session = await store.open_session("byte-identity", "src")
        await store.stage(session, "a.bin", _store_blob_bytes(content_a))
        await store.stage(session, "b.bin", _store_blob_bytes(content_b))
        assert (await store.validate_batch(session)).ok
        await store.accept_session(session)

        ref = await store.freeze_version("byte-identity")
        manifest = await store.resolve(ref)

        expected_by_path = {"a.bin": content_a, "b.bin": content_b}
        for entry in manifest.entries:
            chunks: list[bytes] = []
            stream = await store.open_blob(entry.content_hash)
            async for chunk in stream:
                chunks.append(chunk)
            retrieved = b"".join(chunks)
            assert (
                retrieved == expected_by_path[entry.path]
            ), f"Blob content for {entry.path} does not match original"

    async def test_resolve_same_version_multiple_times(
        self, store: FakeVersionedContentStore
    ) -> None:
        """Resolving the same ``VersionRef`` multiple times produces
        identical manifests.
        """
        await store.ensure_corpus("repeat")
        session = await store.open_session("repeat", "src")
        await store.stage(session, "stable.txt", _store_blob_bytes(b"constant"))
        assert (await store.validate_batch(session)).ok
        await store.accept_session(session)

        ref = await store.freeze_version("repeat")
        m1 = await store.resolve(ref)
        m2 = await store.resolve(ref)

        assert compute_manifest_digest(m1) == compute_manifest_digest(m2)

    async def test_resolve_after_corpus_mutation_unchanged(
        self, store: FakeVersionedContentStore
    ) -> None:
        """VCS-1 (SC-001): A frozen version's resolve is unaffected by
        later corpus changes.
        """
        await store.ensure_corpus("mutate-after-freeze")

        s1 = await store.open_session("mutate-after-freeze", "batch-1")
        await store.stage(s1, "original.txt", _store_blob_bytes(b"original data"))
        assert (await store.validate_batch(s1)).ok
        await store.accept_session(s1)

        ref_original = await store.freeze_version("mutate-after-freeze")
        manifest_original = await store.resolve(ref_original)

        s2 = await store.open_session("mutate-after-freeze", "batch-2")
        await store.stage(s2, "new.txt", _store_blob_bytes(b"new data"))
        assert (await store.validate_batch(s2)).ok
        await store.accept_session(s2)

        manifest_after_mutation = await store.resolve(ref_original)
        assert compute_manifest_digest(manifest_original) == compute_manifest_digest(
            manifest_after_mutation
        )
        paths_original = {e.path for e in manifest_original.entries}
        paths_after = {e.path for e in manifest_after_mutation.entries}
        assert paths_original == paths_after


# ═══════════════════════════════════════════════════════════════════
# VCS-2: Frozen versions are immutable
# ═══════════════════════════════════════════════════════════════════


class TestVCS2:
    """Frozen versions are immutable; mutation creates a new version
    (FR-004).
    """

    async def test_freeze_twice_produces_different_digests(
        self, store: FakeVersionedContentStore
    ) -> None:
        """Freezing the same corpus after mutating HEAD produces a
        different ``manifest_digest``.
        """
        await store.ensure_corpus("freeze-twice")

        s1 = await store.open_session("freeze-twice", "src")
        await store.stage(s1, "v1.txt", _store_blob_bytes(b"version one"))
        assert (await store.validate_batch(s1)).ok
        await store.accept_session(s1)

        ref_v1 = await store.freeze_version("freeze-twice")

        s2 = await store.open_session("freeze-twice", "src")
        await store.stage(s2, "v2.txt", _store_blob_bytes(b"version two"))
        assert (await store.validate_batch(s2)).ok
        await store.accept_session(s2)

        ref_v2 = await store.freeze_version("freeze-twice")

        assert ref_v1.manifest_digest != ref_v2.manifest_digest

    async def test_original_version_unchanged_after_new_accept(
        self, store: FakeVersionedContentStore
    ) -> None:
        """Accepting new content does not mutate previously frozen versions."""
        await store.ensure_corpus("immutable-after-freeze")

        s1 = await store.open_session("immutable-after-freeze", "batch-1")
        await store.stage(s1, "frozen.txt", _store_blob_bytes(b"freeze me"))
        assert (await store.validate_batch(s1)).ok
        await store.accept_session(s1)

        ref1 = await store.freeze_version("immutable-after-freeze")

        s2 = await store.open_session("immutable-after-freeze", "batch-2")
        await store.stage(s2, "new.txt", _store_blob_bytes(b"new content"))
        assert (await store.validate_batch(s2)).ok
        await store.accept_session(s2)

        ref2 = await store.freeze_version("immutable-after-freeze")

        assert (
            ref1.version_number != ref2.version_number
            or ref1.manifest_digest != ref2.manifest_digest
        )

        manifest1 = await store.resolve(ref1)
        assert len(manifest1.entries) == 1
        assert manifest1.entries[0].path == "frozen.txt"

    async def test_resolve_unknown_digest_raises_key_error(
        self, store: FakeVersionedContentStore
    ) -> None:
        """Attempting to resolve a non-existent digest raises ``KeyError``."""
        fake_ref = VersionRef(
            manifest_digest="ff" * 32,
            version_id=999,
            version_number=0,
        )
        with pytest.raises(KeyError, match=fake_ref.manifest_digest):
            await store.resolve(fake_ref)

    async def test_freeze_empty_corpus_returns_zero_entries(
        self, store: FakeVersionedContentStore
    ) -> None:
        """Freezing a corpus with no accepted content produces a zero-entry manifest."""
        await store.ensure_corpus("empty-corpus")
        ref = await store.freeze_version("empty-corpus")
        manifest = await store.resolve(ref)
        assert len(manifest.entries) == 0

    async def test_freeze_composition_produces_immutable_version(
        self, store: FakeVersionedContentStore
    ) -> None:
        """Freezing with an explicit composition creates an immutable version
        that is independent of the corpus HEAD.
        """
        await store.ensure_corpus("composition-corpus")

        s1 = await store.open_session("composition-corpus", "src")
        await store.stage(s1, "seed.txt", _store_blob_bytes(b"seed content"))
        assert (await store.validate_batch(s1)).ok
        await store.accept_session(s1)

        composition = [
            ManifestEntry(
                path="comp-a.bin", content_hash=hashlib.sha256(b"comp A").hexdigest()
            ),
            ManifestEntry(
                path="comp-b.bin", content_hash=hashlib.sha256(b"comp B").hexdigest()
            ),
        ]
        for entry in composition:
            if entry.content_hash not in store._blobs:
                data = b"comp A" if "comp-a" in entry.path else b"comp B"
                store._blobs[entry.content_hash] = data

        ref_comp = await store.freeze_version(
            "composition-corpus", composition=composition
        )
        manifest_comp = await store.resolve(ref_comp)

        assert len(manifest_comp.entries) == 2
        comp_paths = {e.path for e in manifest_comp.entries}
        assert comp_paths == {"comp-a.bin", "comp-b.bin"}

        ref_head = await store.freeze_version("composition-corpus")
        assert ref_comp.manifest_digest != ref_head.manifest_digest
