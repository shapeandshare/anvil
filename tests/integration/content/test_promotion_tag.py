"""Integration tests for promotion tagging of frozen content versions.

Tests that frozen versions can be tagged with human-readable names,
that duplicate tag names are rejected, and that tagged versions are
resolvable by tag. Uses the in-memory ``FakeVersionedContentStore``
from the contract tests.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from tests.unit.services.content.test_versioned_content_store_contract import (
    FakeVersionedContentStore,
)


@pytest.fixture
def store() -> FakeVersionedContentStore:
    """Provide a fresh in-memory ``FakeVersionedContentStore`` for tag tests."""
    return FakeVersionedContentStore()


async def _stream(data: bytes) -> AsyncIterator[bytes]:
    """Yield *data* as a single-chunk async iterator.

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


async def _seed_version(
    store: FakeVersionedContentStore,
    corpus: str,
    path: str,
    content: bytes,
) -> None:
    """Stage, validate, and accept a single-entry session in *corpus*.

    Parameters
    ----------
    store : FakeVersionedContentStore
        The content store.
    corpus : str
        Corpus slug.
    path : str
        Entry path to stage.
    content : bytes
        Blob content to stage.
    """
    await store.ensure_corpus(corpus)
    session = await store.open_session(corpus, "test-source")
    await store.stage(session, path, _stream(content))
    assert (await store.validate_batch(session)).ok
    await store.accept_session(session)


# ═══════════════════════════════════════════════════════════════════
# Tag life cycle
# ═══════════════════════════════════════════════════════════════════


class TestTagLifecycle:
    """Tag a frozen version, then verify tag resolution."""

    async def test_tag_frozen_version(self, store: FakeVersionedContentStore) -> None:
        """A frozen version can be tagged with a human-readable name."""
        await _seed_version(store, "tag-test", "data.txt", b"production data")
        ref = await store.freeze_version("tag-test")

        await store.tag_version("production-v1", ref)

        resolved = await store.resolve_by_tag("production-v1")
        assert resolved.manifest_digest == ref.manifest_digest
        assert resolved.version_id == ref.version_id

    async def test_tagged_version_resolves_to_correct_content(
        self, store: FakeVersionedContentStore
    ) -> None:
        """A tagged version's content matches the original frozen version."""
        await _seed_version(store, "tag-content", "important.bin", b"critical data")
        ref = await store.freeze_version("tag-content")
        await store.tag_version("golden", ref)

        tagged_ref = await store.resolve_by_tag("golden")
        manifest = await store.resolve(tagged_ref)

        assert len(manifest.entries) == 1
        assert manifest.entries[0].path == "important.bin"

    async def test_multiple_tags_on_same_version(
        self, store: FakeVersionedContentStore
    ) -> None:
        """Multiple tags can point to the same frozen version."""
        await _seed_version(store, "multi-tag", "data.bin", b"multi-tagged")
        ref = await store.freeze_version("multi-tag")

        await store.tag_version("alias-a", ref)
        await store.tag_version("alias-b", ref)
        await store.tag_version("alias-c", ref)

        ref_a = await store.resolve_by_tag("alias-a")
        ref_b = await store.resolve_by_tag("alias-b")
        ref_c = await store.resolve_by_tag("alias-c")

        assert ref_a.manifest_digest == ref.manifest_digest
        assert ref_b.manifest_digest == ref.manifest_digest
        assert ref_c.manifest_digest == ref.manifest_digest

    async def test_tagged_version_exposes_tag_name(
        self, store: FakeVersionedContentStore
    ) -> None:
        """A tagged ``VersionRef`` is resolvable by its tag name, and
        the resolved ref carries the same manifest digest.
        """
        await _seed_version(store, "name-check", "a.txt", b"alpha")
        ref = await store.freeze_version("name-check")
        await store.tag_version("release-1", ref)

        resolved = await store.resolve_by_tag("release-1")
        assert resolved.manifest_digest == ref.manifest_digest


# ═══════════════════════════════════════════════════════════════════
# Duplicate tag rejection
# ═══════════════════════════════════════════════════════════════════


class TestDuplicateTagRejection:
    """Duplicate tag names must be rejected with an error."""

    async def test_duplicate_tag_raises_value_error(
        self, store: FakeVersionedContentStore
    ) -> None:
        """Tagging a second version with an existing tag name raises
        ``ValueError``.
        """
        await _seed_version(store, "dup", "v1.txt", b"version one")
        ref1 = await store.freeze_version("dup")
        await store.tag_version("my-tag", ref1)

        await _seed_version(store, "dup", "v2.txt", b"version two")
        ref2 = await store.freeze_version("dup")

        with pytest.raises(ValueError, match="my-tag"):
            await store.tag_version("my-tag", ref2)

    async def test_duplicate_tag_leaves_first_tag_intact(
        self, store: FakeVersionedContentStore
    ) -> None:
        """After a failed duplicate tag attempt, the original tag still
        resolves correctly.
        """
        await _seed_version(store, "dup-safe", "a.txt", b"first")
        ref1 = await store.freeze_version("dup-safe")
        await store.tag_version("safe-tag", ref1)

        await _seed_version(store, "dup-safe", "b.txt", b"second")
        ref2 = await store.freeze_version("dup-safe")

        with pytest.raises(ValueError):
            await store.tag_version("safe-tag", ref2)

        resolved = await store.resolve_by_tag("safe-tag")
        assert resolved.manifest_digest == ref1.manifest_digest

    async def test_tag_name_case_sensitivity(
        self, store: FakeVersionedContentStore
    ) -> None:
        """Tag names are case-sensitive; ``"Release"`` and ``"release"``
        are distinct tags.
        """
        await _seed_version(store, "case", "x.txt", b"content")
        ref1 = await store.freeze_version("case")
        ref2 = await store.freeze_version("case")

        await store.tag_version("Release", ref1)
        await store.tag_version("release", ref2)

        r1 = await store.resolve_by_tag("Release")
        r2 = await store.resolve_by_tag("release")
        assert r1.version_id != r2.version_id


# ═══════════════════════════════════════════════════════════════════
# Edge cases
# ═══════════════════════════════════════════════════════════════════


class TestTagEdgeCases:
    """Tag edge cases: non-existent tags, unfrozen versions, etc."""

    async def test_resolve_nonexistent_tag_raises_key_error(
        self, store: FakeVersionedContentStore
    ) -> None:
        """Resolving a tag that has never been set raises ``KeyError``."""
        with pytest.raises(KeyError, match="nonexistent-tag"):
            await store.resolve_by_tag("nonexistent-tag")

    async def test_tag_unfrozen_version_raises_key_error(
        self, store: FakeVersionedContentStore
    ) -> None:
        """Tagging a version that has not been frozen raises ``KeyError``."""
        await _seed_version(store, "unfrozen", "data.txt", b"not frozen")
        from anvil.services.content.version_ref import VersionRef

        fake_ref = VersionRef(
            manifest_digest="aa" * 32,
            version_id=0,
            version_number=1,
        )
        with pytest.raises(KeyError):
            await store.tag_version("bad-tag", fake_ref)

    async def test_tag_after_revert_still_resolves(
        self, store: FakeVersionedContentStore
    ) -> None:
        """A tag pointing to a frozen version survives a revert operation."""
        await _seed_version(store, "revert-tag", "stable.txt", b"golden data")
        ref = await store.freeze_version("revert-tag")
        await store.tag_version("golden", ref)

        await _seed_version(store, "revert-tag", "bad.txt", b"bad data")
        await store.revert("revert-tag", ref)

        tagged = await store.resolve_by_tag("golden")
        manifest = await store.resolve(tagged)
        assert {e.path for e in manifest.entries} == {"stable.txt"}
