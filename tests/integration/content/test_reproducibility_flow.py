# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Integration tests for the content reproducibility guarantee.

Tests the full create → stage → validate → accept → freeze → resolve
pipeline, verifying the core reproducibility properties:

- **SC-001**: A pinned ``VersionRef`` resolves to identical content
  after later corpus mutations (new sessions, accepts, freezes).
- **Version isolation**: After accepting new content and freezing a new
  version, the original version's ``resolve()`` still returns exactly
  the original entries.
- **Staged content isolation**: Content staged in one session is never
  visible to other sessions or to resolution until accepted.

Uses the ``FakeVersionedContentStore`` (fully in-memory) and the
``content_dir`` fixture for path scaffolding.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from anvil.services.content.manifest import compute_manifest_digest
from tests.unit.services.content.test_versioned_content_store_contract import (
    FakeVersionedContentStore,
)


@pytest.fixture
def store() -> FakeVersionedContentStore:
    """Provide a fresh in-memory ``FakeVersionedContentStore`` for the
    reproducibility flow.
    """
    return FakeVersionedContentStore()


async def _stream(data: bytes) -> AsyncIterator[bytes]:
    """Yield *data* as a single-chunk async iterator, mimicking an
    upload stream.

    Parameters
    ----------
    data : bytes
        Content to yield.

    Yields
    ------
    bytes
        The full content in one chunk.
    """
    yield data


# ═══════════════════════════════════════════════════════════════════
# Full pipeline: create → stage → validate → accept → freeze → resolve
# ═══════════════════════════════════════════════════════════════════


class TestFullPipeline:
    """End-to-end pipeline: every step executes without error and
    produces a consistent final state.
    """

    async def test_full_pipeline_round_trip(
        self, store: FakeVersionedContentStore
    ) -> None:
        """Create corpus, open session, stage multiple entries, validate,
        accept, freeze, and resolve. The resolved manifest entries match
        what was staged.
        """
        await store.ensure_corpus("pipeline-test")
        session = await store.open_session("pipeline-test", "test-source")

        staged_content = {
            "doc1.txt": b"content for document one",
            "doc2.txt": b"content for document two",
            "sub/doc3.txt": b"nested content",
        }

        for path, data in staged_content.items():
            await store.stage(session, path, _stream(data))

        report = await store.validate_batch(session)
        assert report.ok, f"Validation failed with: {report.problems}"

        accept_result = await store.accept_session(session)
        assert accept_result.entry_count == len(staged_content)
        assert accept_result.total_bytes > 0

        ref = await store.freeze_version("pipeline-test")
        manifest = await store.resolve(ref)

        resolved_paths = {e.path for e in manifest.entries}
        assert resolved_paths == set(staged_content.keys())

    async def test_accept_result_has_valid_manifest_digest(
        self, store: FakeVersionedContentStore
    ) -> None:
        """The ``AcceptResult.manifest_digest`` matches the digest
        computed from the frozen manifest.
        """
        await store.ensure_corpus("digest-in-accept")
        session = await store.open_session("digest-in-accept", "src")
        await store.stage(session, "data.bin", _stream(b"important data"))
        assert (await store.validate_batch(session)).ok

        accept_result = await store.accept_session(session)
        ref = await store.freeze_version("digest-in-accept")
        manifest = await store.resolve(ref)

        assert accept_result.manifest_digest == compute_manifest_digest(manifest)


# ═══════════════════════════════════════════════════════════════════
# SC-001: Reproducibility after mutation
# ═══════════════════════════════════════════════════════════════════


class TestReproducibilityAfterMutation:
    """SC-001: A pinned version re-resolves to identical content after
    later corpus changes.
    """

    async def test_pinned_version_survives_new_content(
        self, store: FakeVersionedContentStore
    ) -> None:
        """Freeze a version, add new content, accept a new version,
        then resolve the original — the original entries are unchanged.
        """
        await store.ensure_corpus("survives-new")

        s1 = await store.open_session("survives-new", "phase-1")
        await store.stage(s1, "original.txt", _stream(b"original content"))
        assert (await store.validate_batch(s1)).ok
        await store.accept_session(s1)

        ref_v1 = await store.freeze_version("survives-new")
        manifest_v1 = await store.resolve(ref_v1)
        v1_paths = {e.path for e in manifest_v1.entries}
        assert v1_paths == {"original.txt"}

        s2 = await store.open_session("survives-new", "phase-2")
        await store.stage(s2, "new.txt", _stream(b"new content"))
        assert (await store.validate_batch(s2)).ok
        await store.accept_session(s2)

        ref_v2 = await store.freeze_version("survives-new")
        manifest_v2 = await store.resolve(ref_v2)
        v2_paths = {e.path for e in manifest_v2.entries}
        assert v2_paths == {"original.txt", "new.txt"}

        manifest_v1_again = await store.resolve(ref_v1)
        v1_paths_again = {e.path for e in manifest_v1_again.entries}
        assert v1_paths_again == {"original.txt"}
        assert compute_manifest_digest(manifest_v1) == compute_manifest_digest(
            manifest_v1_again
        )

    async def test_pinned_version_survives_revert(
        self, store: FakeVersionedContentStore
    ) -> None:
        """Freeze a version, add content, revert to original, then
        resolve the pinned version — still returns original entries.
        """
        await store.ensure_corpus("survives-revert")

        s1 = await store.open_session("survives-revert", "phase-1")
        await store.stage(s1, "stable.txt", _stream(b"stable data"))
        assert (await store.validate_batch(s1)).ok
        await store.accept_session(s1)

        ref = await store.freeze_version("survives-revert")
        manifest_before = await store.resolve(ref)

        s2 = await store.open_session("survives-revert", "phase-2")
        await store.stage(s2, "ephemeral.txt", _stream(b"will be reverted"))
        assert (await store.validate_batch(s2)).ok
        await store.accept_session(s2)

        await store.revert("survives-revert", ref)

        manifest_after_revert = await store.resolve(ref)
        assert compute_manifest_digest(manifest_before) == compute_manifest_digest(
            manifest_after_revert
        )

    async def test_multiple_pinned_versions_isolated(
        self, store: FakeVersionedContentStore
    ) -> None:
        """Multiple frozen versions coexist, each returning their own
        entry set regardless of later changes.
        """
        await store.ensure_corpus("multi-pin")

        s1 = await store.open_session("multi-pin", "batch-1")
        await store.stage(s1, "v1-file.txt", _stream(b"version one"))
        assert (await store.validate_batch(s1)).ok
        await store.accept_session(s1)
        ref_v1 = await store.freeze_version("multi-pin")

        s2 = await store.open_session("multi-pin", "batch-2")
        await store.stage(s2, "v2-file.txt", _stream(b"version two"))
        assert (await store.validate_batch(s2)).ok
        await store.accept_session(s2)
        ref_v2 = await store.freeze_version("multi-pin")

        s3 = await store.open_session("multi-pin", "batch-3")
        await store.stage(s3, "v3-file.txt", _stream(b"version three"))
        assert (await store.validate_batch(s3)).ok
        await store.accept_session(s3)
        ref_v3 = await store.freeze_version("multi-pin")

        m1 = await store.resolve(ref_v1)
        m2 = await store.resolve(ref_v2)
        m3 = await store.resolve(ref_v3)

        assert {e.path for e in m1.entries} == {"v1-file.txt"}
        assert {e.path for e in m2.entries} == {"v1-file.txt", "v2-file.txt"}
        assert {e.path for e in m3.entries} == {
            "v1-file.txt",
            "v2-file.txt",
            "v3-file.txt",
        }


# ═══════════════════════════════════════════════════════════════════
# Version isolation
# ═══════════════════════════════════════════════════════════════════


class TestVersionIsolation:
    """Each version is an independent snapshot; mutations to one do
    not affect others.
    """

    async def test_original_version_entries_unchanged_after_new_accept(
        self, store: FakeVersionedContentStore
    ) -> None:
        """After accepting new content into the same corpus, the
        original frozen version's entries remain unchanged.
        """
        await store.ensure_corpus("isolation")

        s1 = await store.open_session("isolation", "src")
        await store.stage(s1, "a.txt", _stream(b"aaa"))
        assert (await store.validate_batch(s1)).ok
        await store.accept_session(s1)
        ref_a = await store.freeze_version("isolation")
        manifest_a = await store.resolve(ref_a)

        s2 = await store.open_session("isolation", "src")
        await store.stage(s2, "b.txt", _stream(b"bbb"))
        assert (await store.validate_batch(s2)).ok
        await store.accept_session(s2)
        ref_b = await store.freeze_version("isolation")

        manifest_a_again = await store.resolve(ref_a)
        assert len(manifest_a_again.entries) == len(manifest_a.entries)
        assert {e.path for e in manifest_a_again.entries} == {"a.txt"}

        manifest_b = await store.resolve(ref_b)
        assert {e.path for e in manifest_b.entries} == {"a.txt", "b.txt"}

    async def test_blob_content_unchanged_across_versions(
        self, store: FakeVersionedContentStore
    ) -> None:
        """Blobs referenced by a frozen version are preserved even
        after the HEAD has moved to different content.
        """
        await store.ensure_corpus("blob-preservation")

        content_v1 = b"original blob content"
        s1 = await store.open_session("blob-preservation", "src")
        await store.stage(s1, "data.bin", _stream(content_v1))
        assert (await store.validate_batch(s1)).ok
        await store.accept_session(s1)
        ref_v1 = await store.freeze_version("blob-preservation")

        content_v2 = b"completely different content"
        s2 = await store.open_session("blob-preservation", "src")
        await store.stage(s2, "data.bin", _stream(content_v2))
        assert (await store.validate_batch(s2)).ok
        await store.accept_session(s2)

        manifest_v1 = await store.resolve(ref_v1)
        entry = manifest_v1.entries[0]

        chunks: list[bytes] = []
        stream = await store.open_blob(entry.content_hash)
        async for chunk in stream:
            chunks.append(chunk)
        retrieved = b"".join(chunks)
        assert retrieved == content_v1


# ═══════════════════════════════════════════════════════════════════
# Staged content isolation
# ═══════════════════════════════════════════════════════════════════


class TestStagedContentIsolation:
    """Content staged in one session is not visible to other sessions
    or to resolution until accepted.
    """

    async def test_unaccepted_content_not_in_freeze(
        self, store: FakeVersionedContentStore
    ) -> None:
        """Staging content then freezing without accepting should NOT
        include the staged content in the frozen version.
        """
        await store.ensure_corpus("staged-not-accepted")

        session = await store.open_session("staged-not-accepted", "src")
        await store.stage(
            session, "not-accepted.txt", _stream(b"staged but not accepted")
        )
        assert (await store.validate_batch(session)).ok

        ref = await store.freeze_version("staged-not-accepted")
        manifest = await store.resolve(ref)

        assert len(manifest.entries) == 0

    async def test_abandoned_session_leaves_no_trace(
        self, store: FakeVersionedContentStore
    ) -> None:
        """Abandoning a session discards all staged content."""
        await store.ensure_corpus("abandoned")

        session = await store.open_session("abandoned", "src")
        await store.stage(session, "ghost.txt", _stream(b"will be abandoned"))
        await store.abandon_session(session)

        ref = await store.freeze_version("abandoned")
        manifest = await store.resolve(ref)
        assert len(manifest.entries) == 0
