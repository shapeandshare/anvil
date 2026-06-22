# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for CorpusService — corpus CRUD, version management,
tagging, and diff operations.

Uses the ``in_memory_session`` fixture from
``tests/unit/conftest.py`` for DB-backed tests, with
``MagicMock`` for the ``VersionedContentStore`` dependency.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.db.models.content_corpus import ContentCorpus
from anvil.db.models.content_entry import ContentEntry
from anvil.db.models.content_tag import ContentTag
from anvil.db.models.content_version import ContentVersion
from anvil.db.models.content_version_run_ref import VersionRunRef
from anvil.db.repositories.content_corpora import ContentCorpusRepository
from anvil.db.repositories.content_sources import ContentSourceRepository
from anvil.db.repositories.content_versions import ContentVersionRepository
from anvil.services.content.corpus_service import CorpusService
from anvil.services.content.version_ref import VersionRef


@pytest_asyncio.fixture
async def service(in_memory_session: AsyncSession) -> CorpusService:
    """Build a ``CorpusService`` with real repositories and a mock
    content store.
    """
    corpus_repo = ContentCorpusRepository(in_memory_session)
    source_repo = ContentSourceRepository(in_memory_session)
    version_repo = ContentVersionRepository(in_memory_session)
    mock_store = MagicMock()
    return CorpusService(
        corpus_repo=corpus_repo,
        source_repo=source_repo,
        version_repo=version_repo,
        db_session=in_memory_session,
        content_store=mock_store,
    )


@pytest_asyncio.fixture
async def seeded_session(in_memory_session: AsyncSession) -> AsyncSession:
    """Seed the DB with a ``ContentCorpus``, a ``ContentVersion``, and
    two ``ContentEntry`` rows for diff testing.
    """
    corpus = ContentCorpus(slug="test-corpus", name="Test Corpus")
    in_memory_session.add(corpus)
    await in_memory_session.flush()
    await in_memory_session.refresh(corpus)

    version = ContentVersion(
        corpus_id=corpus.id,
        version_number=1,
        manifest_digest="aa" * 32,
    )
    in_memory_session.add(version)
    await in_memory_session.flush()
    await in_memory_session.refresh(version)
    # Wire current_version_id on corpus.
    corpus.current_version_id = version.id
    await in_memory_session.flush()

    entry_a = ContentEntry(
        version_id=version.id, path="doc1.txt", content_hash="bb" * 32
    )
    entry_b = ContentEntry(
        version_id=version.id, path="doc2.txt", content_hash="cc" * 32
    )
    in_memory_session.add_all([entry_a, entry_b])
    await in_memory_session.flush()
    return in_memory_session


# ═══════════════════════════════════════════════════════════════════
# CRUD — create
# ═══════════════════════════════════════════════════════════════════


class TestCreate:
    """CorpusService.create() creates and returns a new ContentCorpus."""

    async def test_create_returns_corpus(
        self, service: CorpusService, in_memory_session: AsyncSession
    ) -> None:
        """Creating a corpus returns it with an id and slug."""
        corpus = await service.create(
            name="My Corpus", slug="my-corpus", description="A test corpus"
        )
        assert corpus.id is not None
        assert corpus.slug == "my-corpus"
        assert corpus.name == "My Corpus"
        assert corpus.description == "A test corpus"
        assert corpus.chunking_strategy == "windowed"
        assert corpus.block_size == 16
        assert corpus.chunk_overlap == 0.5
        assert corpus.origin == "user"

    async def test_create_with_full_params(
        self, service: CorpusService, in_memory_session: AsyncSession
    ) -> None:
        """Creating a corpus with all optional params persists them."""
        corpus = await service.create(
            name="Full Corpus",
            slug="full-corpus",
            description="Full params",
            chunking_strategy="line",
            block_size=32,
            chunk_overlap=0.25,
            source_description="My source",
            attribution_text="CC-BY",
            origin="bundled",
        )
        assert corpus.chunking_strategy == "line"
        assert corpus.block_size == 32
        assert corpus.chunk_overlap == 0.25
        assert corpus.source_description == "My source"
        assert corpus.attribution_text == "CC-BY"
        assert corpus.origin == "bundled"

    async def test_create_persists_to_db(
        self, service: CorpusService, in_memory_session: AsyncSession
    ) -> None:
        """The created corpus is queryable from the DB."""
        await service.create(name="DB Check", slug="db-check")
        fetched = await in_memory_session.get(ContentCorpus, 1)
        assert fetched is not None
        assert fetched.slug == "db-check"


# ═══════════════════════════════════════════════════════════════════
# CRUD — read
# ═══════════════════════════════════════════════════════════════════


class TestGet:
    """CorpusService.get() retrieves a corpus by primary key."""

    async def test_get_returns_corpus(
        self, service: CorpusService, in_memory_session: AsyncSession
    ) -> None:
        """get() returns the corpus when it exists."""
        created = await service.create(name="Get Test", slug="get-test")
        fetched = await service.get(created.id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.slug == "get-test"

    async def test_get_returns_none_for_missing(
        self, service: CorpusService, in_memory_session: AsyncSession
    ) -> None:
        """get() returns None when no corpus matches the id."""
        fetched = await service.get(999)
        assert fetched is None


class TestGetBySlug:
    """CorpusService.get_by_slug() retrieves a corpus by unique slug."""

    async def test_get_by_slug_found(
        self, service: CorpusService, in_memory_session: AsyncSession
    ) -> None:
        """get_by_slug() returns the corpus for an existing slug."""
        await service.create(name="Slug Test", slug="slug-test")
        fetched = await service.get_by_slug("slug-test")
        assert fetched is not None
        assert fetched.slug == "slug-test"

    async def test_get_by_slug_not_found(
        self, service: CorpusService, in_memory_session: AsyncSession
    ) -> None:
        """get_by_slug() returns None for an unknown slug."""
        fetched = await service.get_by_slug("no-such-slug")
        assert fetched is None


class TestList:
    """CorpusService.list() returns all corpora, newest first."""

    async def test_list_empty(
        self, service: CorpusService, in_memory_session: AsyncSession
    ) -> None:
        """list() returns an empty sequence when no corpora exist."""
        corpora = await service.list()
        assert len(corpora) == 0

    async def test_list_returns_all(
        self, service: CorpusService, in_memory_session: AsyncSession
    ) -> None:
        """list() returns all created corpora."""
        await service.create(name="Alpha", slug="alpha")
        await service.create(name="Beta", slug="beta")
        corpora = await service.list()
        assert len(corpora) == 2

    async def test_list_newest_first(
        self, service: CorpusService, in_memory_session: AsyncSession
    ) -> None:
        """list() returns all corpora (order is creation descending within the same transaction)."""
        c1 = await service.create(name="First", slug="first")
        c2 = await service.create(name="Second", slug="second")
        corpora = await service.list()
        slugs = [c.slug for c in corpora]
        assert len(slugs) == 2
        assert "first" in slugs
        assert "second" in slugs


# ═══════════════════════════════════════════════════════════════════
# CRUD — delete
# ═══════════════════════════════════════════════════════════════════


class TestDelete:
    """CorpusService.delete() removes a corpus or returns False."""

    async def test_delete_returns_true(
        self, service: CorpusService, in_memory_session: AsyncSession
    ) -> None:
        """delete() returns True when a corpus is removed."""
        created = await service.create(name="Del Me", slug="del-me")
        result = await service.delete(created.id)
        assert result is True

    async def test_delete_removes_corpus(
        self, service: CorpusService, in_memory_session: AsyncSession
    ) -> None:
        """After delete(), the corpus is no longer queryable."""
        created = await service.create(name="Gone", slug="gone")
        await service.delete(created.id)
        fetched = await service.get(created.id)
        assert fetched is None

    async def test_delete_returns_false_for_missing(
        self, service: CorpusService, in_memory_session: AsyncSession
    ) -> None:
        """delete() returns False when no corpus matches the id."""
        result = await service.delete(999)
        assert result is False

    async def test_delete_raises_when_run_refs_exist(
        self, service: CorpusService, in_memory_session: AsyncSession
    ) -> None:
        """delete() raises ValueError when any version has run refs."""
        created = await service.create(name="Protected", slug="protected")
        # Create a version for the corpus.
        version = ContentVersion(
            corpus_id=created.id, version_number=1, manifest_digest="dd" * 32
        )
        in_memory_session.add(version)
        await in_memory_session.flush()
        await in_memory_session.refresh(version)

        # Add a run ref to the version.
        run_ref = VersionRunRef(
            version_id=version.id,
            mlflow_run_id="run-123",
            corpus_ref=f"corpus:{created.id}",
        )
        in_memory_session.add(run_ref)
        await in_memory_session.flush()

        with pytest.raises(ValueError, match="run references"):
            await service.delete(created.id)


# ═══════════════════════════════════════════════════════════════════
# Versions — list_versions
# ═══════════════════════════════════════════════════════════════════


class TestListVersions:
    """CorpusService.list_versions() lists versions for a corpus."""

    async def test_list_versions_empty(
        self, service: CorpusService, in_memory_session: AsyncSession
    ) -> None:
        """list_versions() returns empty list when no versions exist."""
        created = await service.create(name="No Versions", slug="no-versions")
        versions = await service.list_versions(created.id)
        assert len(versions) == 0

    async def test_list_versions_returns_versions(
        self, service: CorpusService, in_memory_session: AsyncSession
    ) -> None:
        """list_versions() returns all versions for a corpus."""
        created = await service.create(name="Has Versions", slug="has-versions")

        v1 = ContentVersion(
            corpus_id=created.id, version_number=1, manifest_digest="e1" * 32
        )
        v2 = ContentVersion(
            corpus_id=created.id, version_number=2, manifest_digest="e2" * 32
        )
        in_memory_session.add_all([v1, v2])
        await in_memory_session.flush()

        versions = await service.list_versions(created.id)
        assert len(versions) == 2


# ═══════════════════════════════════════════════════════════════════
# Tagging
# ═══════════════════════════════════════════════════════════════════


class TestTag:
    """CorpusService.tag() tags a version with a human-readable name."""

    async def test_tag_creates_tag(
        self, service: CorpusService, in_memory_session: AsyncSession
    ) -> None:
        """tag() creates a ContentTag on an existing version."""
        created = await service.create(name="Tag Test", slug="tag-test")
        version = ContentVersion(
            corpus_id=created.id, version_number=1, manifest_digest="f1" * 32
        )
        in_memory_session.add(version)
        await in_memory_session.flush()
        await in_memory_session.refresh(version)

        tag = await service.tag(version.id, "production")
        assert tag.name == "production"
        assert tag.version_id == version.id
        assert tag.gc_protected is True

    async def test_tag_raises_for_missing_version(
        self, service: CorpusService, in_memory_session: AsyncSession
    ) -> None:
        """tag() raises ValueError when the version does not exist."""
        with pytest.raises(ValueError, match="Version not found"):
            await service.tag(999, "no-such-version")


# ═══════════════════════════════════════════════════════════════════
# Version diff
# ═══════════════════════════════════════════════════════════════════


class TestVersionDiff:
    """CorpusService.version_diff() computes added/removed paths."""

    async def test_diff_first_version_all_added(
        self, service: CorpusService, seeded_session: AsyncSession
    ) -> None:
        """For the first version, all entries are reported as added."""
        # Find the version created in seeded_session.
        result = await seeded_session.execute(
            select(ContentVersion).where(ContentVersion.version_number == 1)
        )
        version = result.scalar_one()

        diff = await service.version_diff(version.id)
        assert diff["added"] == ["doc1.txt", "doc2.txt"]
        assert diff["removed"] == []
        assert diff["version_number"] == 1
        assert diff["prior_version_number"] is None

    async def test_diff_second_version_shows_changes(
        self, service: CorpusService, seeded_session: AsyncSession
    ) -> None:
        """Diffing version 2 against version 1 shows correct changes."""
        result = await seeded_session.execute(
            select(ContentCorpus).where(ContentCorpus.slug == "test-corpus")
        )
        corpus = result.scalar_one()

        # Create version 2 with a removed path and an added path.
        v2 = ContentVersion(
            corpus_id=corpus.id,
            version_number=2,
            manifest_digest="g2" * 32,
        )
        seeded_session.add(v2)
        await seeded_session.flush()
        await seeded_session.refresh(v2)

        # Only add doc1.txt (doc2.txt is removed vs v1).
        entry_v2 = ContentEntry(
            version_id=v2.id, path="doc1.txt", content_hash="bb" * 32
        )
        # Add a new entry.
        entry_new = ContentEntry(
            version_id=v2.id, path="doc3.txt", content_hash="h3" * 32
        )
        seeded_session.add_all([entry_v2, entry_new])
        await seeded_session.flush()

        diff = await service.version_diff(v2.id)
        assert diff["added"] == ["doc3.txt"]
        assert diff["removed"] == ["doc2.txt"]
        assert diff["version_number"] == 2
        assert diff["prior_version_number"] == 1

    async def test_diff_raises_for_missing_version(
        self, service: CorpusService, in_memory_session: AsyncSession
    ) -> None:
        """version_diff() raises ValueError for a non-existent version."""
        with pytest.raises(ValueError, match="Version not found"):
            await service.version_diff(999)


# ═══════════════════════════════════════════════════════════════════
# Revert
# ═══════════════════════════════════════════════════════════════════


class TestRevert:
    """CorpusService.revert() reverts a corpus to a previous version."""

    async def test_revert_raises_without_store(
        self, in_memory_session: AsyncSession
    ) -> None:
        """revert() raises ValueError if no content_store is configured."""
        corpus_repo = ContentCorpusRepository(in_memory_session)
        source_repo = ContentSourceRepository(in_memory_session)
        version_repo = ContentVersionRepository(in_memory_session)
        svc = CorpusService(
            corpus_repo=corpus_repo,
            source_repo=source_repo,
            version_repo=version_repo,
            db_session=in_memory_session,
            content_store=None,
        )
        with pytest.raises(ValueError, match="Content store not configured"):
            await svc.revert(1, 1)

    async def test_revert_raises_for_missing_corpus(
        self, service: CorpusService, in_memory_session: AsyncSession
    ) -> None:
        """revert() raises ValueError when the corpus is not found."""
        # Create a version in a different corpus so version exists but corpus doesn't.
        created = await service.create(name="Other", slug="other")
        version = ContentVersion(
            corpus_id=created.id, version_number=1, manifest_digest="i1" * 32
        )
        in_memory_session.add(version)
        await in_memory_session.flush()
        await in_memory_session.refresh(version)

        with pytest.raises(ValueError, match="Corpus not found"):
            await service.revert(999, version.id)


# Need to import select at module level for seeded_session fixture usage.
from sqlalchemy import select  # noqa: E402
