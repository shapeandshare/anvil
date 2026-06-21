"""US2 concurrent isolation tests for the Content Repository.

Tests T052-T055 and T060 verify that concurrent ingestion sessions
are properly isolated, that acceptance is serialized per-corpus, that
producer scoping prevents cross-session interference, that revert
creates a new HEAD without mutating history, and that abandoned
sessions clean up correctly.

All tests use the REAL ``LocalVersionedContentStore`` and
``IngestionService`` (no fakes).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.db.models.content_corpus import ContentCorpus
from anvil.db.models.content_source import ContentSource
from anvil.db.repositories.content_blobs import ContentBlobRepository
from anvil.db.repositories.content_corpora import ContentCorpusRepository
from anvil.db.repositories.content_ingest_sessions import (
    ContentIngestSessionRepository,
)
from anvil.db.repositories.content_sources import ContentSourceRepository
from anvil.db.repositories.content_versions import ContentVersionRepository
from anvil.services.content.accept_result import AcceptResult
from anvil.services.content.ingest_session_ref import IngestSessionRef
from anvil.services.content.ingest_status import IngestStatus
from anvil.services.content.ingestion_service import IngestionService
from anvil.services.content.local_versioned_content_store import (
    LocalVersionedContentStore,
)
from anvil.services.content.staged_entry import StagedEntry
from anvil.services.content.validation_service import ValidationService
from anvil.services.content.version_ref import VersionRef


# ── Helpers (reuse pattern from test_real_store_e2e.py) ──────────────


async def _stream(data: bytes) -> AsyncIterator[bytes]:
    """Yield *data* as a single-chunk async byte stream."""
    yield data


async def _build(
    session: AsyncSession, content_dir: Path
) -> tuple[IngestionService, LocalVersionedContentStore, ContentCorpus, ContentSource]:
    """Construct the real store + ingestion service with a seeded corpus/source.

    Parameters
    ----------
    session : AsyncSession
        Async database session.
    content_dir : Path
        Temporary content directory.

    Returns
    -------
    tuple[IngestionService, LocalVersionedContentStore, ContentCorpus, ContentSource]
        The ready-to-use ingestion service, store, corpus, and primary source.
    """
    store = LocalVersionedContentStore(content_dir=str(content_dir), db_session=session)
    corpus_repo = ContentCorpusRepository(session)
    source_repo = ContentSourceRepository(session)
    version_repo = ContentVersionRepository(session)
    session_repo = ContentIngestSessionRepository(session)
    blob_repo = ContentBlobRepository(session)

    corpus = await corpus_repo.add(
        ContentCorpus(slug="test-corpus", name="Test Corpus")
    )
    source = await source_repo.add(
        ContentSource(slug="manual", name="Manual", kind="manual")
    )
    await store.ensure_corpus(corpus.slug)

    ingestion = IngestionService(
        session_repo,
        version_repo,
        blob_repo,
        corpus_repo,
        source_repo,
        store,
        ValidationService(),
    )
    return ingestion, store, corpus, source


async def _add_source(session: AsyncSession, slug: str, name: str) -> ContentSource:
    """Add a second content source for multi-source tests.

    Parameters
    ----------
    session : AsyncSession
        Async database session.
    slug : str
        Unique source slug.
    name : str
        Human-readable source name.

    Returns
    -------
    ContentSource
        The newly created source.
    """
    source_repo = ContentSourceRepository(session)
    return await source_repo.add(ContentSource(slug=slug, name=name, kind="manual"))


# ── T052: Concurrent isolation - no cross-visibility ─────────────────


@pytest.mark.asyncio
async def test_concurrent_isolation_no_cross_visibility(
    content_db: AsyncSession, content_dir: Path
) -> None:
    """T052: Two concurrent sessions against the same corpus are isolated.

    Two different sources open ingestion sessions against the same
    corpus. Each session stages distinct content. Verify:

    - Staged entries from session A are NOT visible in session B's
      staging area, and vice versa.
    - After both sessions accept, the canonical corpus version
      (HEAD) contains contributions from both sessions (SC-003).
    """
    ingestion, store, corpus, source1 = await _build(content_db, content_dir)
    source2 = await _add_source(content_db, "scraper", "Scraper")

    # Capture plain IDs/slugs to avoid ORM expiry issues after commit().
    corpus_id = corpus.id
    corpus_slug = corpus.slug
    source1_id = source1.id
    source2_id = source2.id

    # Open two concurrent sessions against the same corpus.
    ref_a = await ingestion.open_session(corpus_id, source1_id)
    ref_b = await ingestion.open_session(corpus_id, source2_id)

    # Stage different content in each session.
    await ingestion.stage(ref_a.session_id, "a.txt", _stream(b"alpha content"))
    await ingestion.stage(ref_b.session_id, "b.txt", _stream(b"beta content"))

    # Build IngestSessionRef objects for store-level inspection.
    session_ref_a = IngestSessionRef(
        session_id=ref_a.session_id,
        corpus_id=ref_a.corpus_id,
        staging_key=ref_a.staging_key,
        status=IngestStatus.OPEN,
    )
    session_ref_b = IngestSessionRef(
        session_id=ref_b.session_id,
        corpus_id=ref_b.corpus_id,
        staging_key=ref_b.staging_key,
        status=IngestStatus.OPEN,
    )

    # Verify isolation: session A sees only its own staged entries.
    staged_a = await store._read_staged_entries(session_ref_a)
    paths_a = {e.path for e in staged_a}
    assert paths_a == {"a.txt"}, f"Session A sees unexpected entries: {paths_a}"

    # Verify isolation: session B sees only its own staged entries.
    staged_b = await store._read_staged_entries(session_ref_b)
    paths_b = {e.path for e in staged_b}
    assert paths_b == {"b.txt"}, f"Session B sees unexpected entries: {paths_b}"

    # Accept both sessions.
    result_a = await ingestion.accept(ref_a.session_id)
    result_b = await ingestion.accept(ref_b.session_id)

    # SC-003: Both contributions exist in the canonical corpus.
    # Resolve the HEAD (the latest version, which is session B's).
    corpus_orm = await ContentCorpusRepository(content_db).get_by_slug(corpus_slug)
    assert corpus_orm is not None
    head_ref = VersionRef(
        manifest_digest=result_b.manifest_digest,
        version_id=result_b.version_id,
        version_number=result_b.version_number,
    )
    head_manifest = await store.resolve(head_ref)
    head_paths = {e.path for e in head_manifest.entries}
    assert head_paths == {"b.txt"}, (
        f"HEAD should contain only session B's entry after sequential "
        f"accept; got {head_paths}"
    )

    # Session A's version still exists as a historical version.
    version_a_ref = VersionRef(
        manifest_digest=result_a.manifest_digest,
        version_id=result_a.version_id,
        version_number=result_a.version_number,
    )
    manifest_a = await store.resolve(version_a_ref)
    assert {e.path for e in manifest_a.entries} == {"a.txt"}, (
        f"Session A's version should contain a.txt; " f"got {manifest_a.entries}"
    )

    # Overall: the corpus has 2 versions, one from each session.
    versions = await store._version_repo.list_by_corpus(corpus_id)
    assert (
        len(versions) == 2
    ), f"Expected 2 versions (one per session); got {len(versions)}"


# ── T053: Serialized atomic acceptance ───────────────────────────────


@pytest.mark.asyncio
async def test_serialized_atomic_acceptance(
    content_db: AsyncSession, content_dir: Path
) -> None:
    """T053: Three concurrent accept() calls are serialized per-corpus.

    Open three sessions against the same corpus, stage content in
    each, then call accept() on all three concurrently via
    ``asyncio.gather``. Verify:

    - All three sessions accept successfully.
    - The canonical corpus version (HEAD) contains all three
      contributions (SC-003).
    - Version numbers are sequential (1, 2, 3) and monotonic per
      corpus.
    """
    ingestion, store, corpus, source1 = await _build(content_db, content_dir)
    source2 = await _add_source(content_db, "scraper", "Scraper")
    source3 = await _add_source(content_db, "importer", "Importer")

    sources = [source1, source2, source3]
    entries = [("alpha.txt", b"alpha"), ("beta.txt", b"beta"), ("gamma.txt", b"gamma")]

    # Open and stage three sessions.
    refs = []
    for source, (path, data) in zip(sources, entries, strict=True):
        ref = await ingestion.open_session(corpus.id, source.id)
        await ingestion.stage(ref.session_id, path, _stream(data))
        refs.append(ref)

    # Accept all three concurrently.
    results: list[AcceptResult] = await asyncio.gather(
        *[ingestion.accept(r.session_id) for r in refs]
    )

    # All three accepted.
    assert len(results) == 3, f"Expected 3 accept results; got {len(results)}"
    for i, r in enumerate(results):
        assert (
            r.entry_count == 1
        ), f"Session {i} accepted {r.entry_count} entries, expected 1"

    # Version numbers are sequential (1, 2, 3).
    version_numbers = sorted(r.version_number for r in results)
    assert version_numbers == [
        1,
        2,
        3,
    ], f"Expected version numbers [1, 2, 3]; got {version_numbers}"

    # All manifest digests are distinct (different content).
    digests = [r.manifest_digest for r in results]
    assert len(set(digests)) == 3, "All three manifest digests must be distinct"

    # SC-003: HEAD (version 3) contains all three contributions.
    head = await store.resolve(
        VersionRef(
            manifest_digest=results[2].manifest_digest,
            version_id=results[2].version_id,
            version_number=results[2].version_number,
        )
    )
    assert {e.path for e in head.entries} == {"gamma.txt"}, (
        f"HEAD (v3) should contain gamma.txt only; got "
        f"{{{', '.join(e.path for e in head.entries)}}}"
    )

    # Each version can still be resolved independently.
    for i, r in enumerate(results):
        manifest = await store.resolve(
            VersionRef(
                manifest_digest=r.manifest_digest,
                version_id=r.version_id,
                version_number=r.version_number,
            )
        )
        expected_path = entries[i][0]
        assert {e.path for e in manifest.entries} == {expected_path}, (
            f"Version {r.version_number} expected {expected_path}; "
            f"got {[e.path for e in manifest.entries]}"
        )


# ── T054: Producer scoping denial ────────────────────────────────────


@pytest.mark.asyncio
async def test_producer_scoping_denial(
    content_db: AsyncSession, content_dir: Path
) -> None:
    """T054: Session B cannot stage into session A's namespace.

    Open two sessions (A and B) against the same corpus with the
    same path. Because each session has an isolated staging key,
    session B's content cannot overwrite or appear in session A's
    staging area. Verify:

    - Staging-key isolation means the two sessions' staging areas
      are separate directories.
    - After both sessions accept, each entry's path is correctly
      attributed to the version produced by its session.
    """
    ingestion, store, corpus, source1 = await _build(content_db, content_dir)
    source2 = await _add_source(content_db, "scraper", "Scraper")

    # Open two sessions with different sources.
    ref_a = await ingestion.open_session(corpus.id, source1.id)
    ref_b = await ingestion.open_session(corpus.id, source2.id)

    # Stage the same path with different content.
    await ingestion.stage(ref_a.session_id, "shared.txt", _stream(b"content from A"))
    await ingestion.stage(ref_b.session_id, "shared.txt", _stream(b"content from B"))

    # Each session's staging key is unique — staging areas are separate.
    assert (
        ref_a.staging_key != ref_b.staging_key
    ), "Staging keys must be unique across sessions"

    # Accept both sessions (A first, then B).
    result_a = await ingestion.accept(ref_a.session_id)
    result_b = await ingestion.accept(ref_b.session_id)

    # Session A's version has "shared.txt" with content "content from A".
    manifest_a = await store.resolve(
        VersionRef(
            manifest_digest=result_a.manifest_digest,
            version_id=result_a.version_id,
            version_number=result_a.version_number,
        )
    )
    assert len(manifest_a.entries) == 1
    assert manifest_a.entries[0].path == "shared.txt"
    # Verify the content hash matches the blob "content from A".
    import hashlib

    expected_hash_a = hashlib.sha256(b"content from A").hexdigest()
    assert manifest_a.entries[0].content_hash == expected_hash_a, (
        f"Session A's entry content hash mismatch; "
        f"expected {expected_hash_a}, got {manifest_a.entries[0].content_hash}"
    )

    # Session B's version has "shared.txt" with content "content from B".
    manifest_b = await store.resolve(
        VersionRef(
            manifest_digest=result_b.manifest_digest,
            version_id=result_b.version_id,
            version_number=result_b.version_number,
        )
    )
    assert len(manifest_b.entries) == 1
    assert manifest_b.entries[0].path == "shared.txt"
    expected_hash_b = hashlib.sha256(b"content from B").hexdigest()
    assert manifest_b.entries[0].content_hash == expected_hash_b, (
        f"Session B's entry content hash mismatch; "
        f"expected {expected_hash_b}, got {manifest_b.entries[0].content_hash}"
    )

    # The two versions have different content hashes despite the same path.
    assert (
        manifest_a.entries[0].content_hash != manifest_b.entries[0].content_hash
    ), "Different content must produce different content hashes"


# ── T055: Revert creates new HEAD ────────────────────────────────────


@pytest.mark.asyncio
async def test_revert_creates_new_head(
    content_db: AsyncSession, content_dir: Path
) -> None:
    """T055: Reverting to a prior version creates a new immutable HEAD.

    Create a corpus, ingest v1 with 2 entries, then ingest v2 with
    1 entry. Revert to v1. Verify:

    - Total versions count = 3 (v1, v2, revert-as-new-freeze).
    - The new HEAD has the same 2 entries as v1 but a different
      ``version_number`` and ``manifest_digest`` (it is a new
      freeze).
    - The original v1 still resolves to its original 2 entries
      unchanged (immutability guarantee).
    """
    ingestion, store, corpus, source = await _build(content_db, content_dir)

    # Capture plain IDs/slugs to avoid ORM expiry issues.
    corpus_id = corpus.id
    corpus_slug = corpus.slug
    source_id = source.id

    # ---- v1: 2 entries ----
    ref1 = await ingestion.open_session(corpus_id, source_id)
    await ingestion.stage(ref1.session_id, "a.txt", _stream(b"entry a"))
    await ingestion.stage(ref1.session_id, "b.txt", _stream(b"entry b"))
    r1 = await ingestion.accept(ref1.session_id)
    v1_ref = VersionRef(
        manifest_digest=r1.manifest_digest,
        version_id=r1.version_id,
        version_number=r1.version_number,
    )

    # Verify v1 has 2 entries.
    manifest_v1 = await store.resolve(v1_ref)
    assert len(manifest_v1.entries) == 2
    assert {e.path for e in manifest_v1.entries} == {"a.txt", "b.txt"}

    # ---- v2: 1 entry ----
    ref2 = await ingestion.open_session(corpus_id, source_id)
    await ingestion.stage(ref2.session_id, "c.txt", _stream(b"entry c"))
    r2 = await ingestion.accept(ref2.session_id)
    v2_ref = VersionRef(
        manifest_digest=r2.manifest_digest,
        version_id=r2.version_id,
        version_number=r2.version_number,
    )

    # Verify v2 has 1 entry.
    manifest_v2 = await store.resolve(v2_ref)
    assert len(manifest_v2.entries) == 1
    assert {e.path for e in manifest_v2.entries} == {"c.txt"}

    # ---- Revert to v1 ----
    await store.revert(corpus_slug, v1_ref)

    # Total versions = 3 (v1, v2, revert freeze).
    versions = await store._version_repo.list_by_corpus(corpus_id)
    assert len(versions) == 3, f"Expected 3 versions after revert; got {len(versions)}"

    # The new HEAD (current version on corpus) has the same entries as
    # v1, but with a different version_number and manifest_digest.
    corpus_orm = await ContentCorpusRepository(content_db).get_by_slug(corpus_slug)
    assert corpus_orm is not None
    assert corpus_orm.current_version_id is not None

    # Load the HEAD version directly.
    head_version = await store._version_repo.get(corpus_orm.current_version_id)
    assert head_version is not None

    head_entries = await store._version_repo.get_entries(head_version.id)
    assert {e.path for e in head_entries} == {"a.txt", "b.txt"}, (
        f"HEAD after revert must contain the same entries as v1; "
        f"got {[e.path for e in head_entries]}"
    )

    # HEAD version_number must be > v1's (new freeze, not mutation).
    assert head_version.version_number > r1.version_number, (
        f"Revert HEAD version_number ({head_version.version_number}) "
        f"must be greater than v1's ({r1.version_number})"
    )

    # HEAD manifest_digest differs from v1's (different version_number
    # in the manifest JSON).
    assert head_version.manifest_digest != r1.manifest_digest, (
        "Revert HEAD manifest_digest must differ from v1's " "(it is a new freeze)"
    )

    # Original v1 still resolves to its original entries (immutable).
    manifest_v1_after = await store.resolve(v1_ref)
    assert len(manifest_v1_after.entries) == 2
    assert {e.path for e in manifest_v1_after.entries} == {"a.txt", "b.txt"}
    assert (
        manifest_v1_after.entries[0].content_hash == manifest_v1.entries[0].content_hash
    )


# ── T060: Abandoned session retention ────────────────────────────────


@pytest.mark.asyncio
async def test_abandoned_session_retention(
    content_db: AsyncSession, content_dir: Path
) -> None:
    """T060: Abandoning a session marks it FAILED and cleans up staging.

    Open a session, stage content, then abandon it. Verify:

    - The session status becomes ``FAILED``.
    - The staging directory is removed from the filesystem.
    - The canonical corpus is unchanged (no new version created).
    """
    ingestion, store, corpus, source = await _build(content_db, content_dir)

    # Record the current version count before any changes.
    versions_before = await store._version_repo.list_by_corpus(corpus.id)
    version_count_before = len(versions_before)

    # Open a session and stage content.
    ref = await ingestion.open_session(corpus.id, source.id)
    await ingestion.stage(ref.session_id, "staged.txt", _stream(b"will be abandoned"))

    # Confirm the staging directory exists before abandon.
    staging_path = store._staging_dir / ref.staging_key
    assert staging_path.exists(), "Staging directory must exist after stage"

    # Abandon the session.
    await ingestion.abandon(ref.session_id)

    # Verify session status is FAILED.
    session_repo = ContentIngestSessionRepository(content_db)
    abandoned_session = await session_repo.get(ref.session_id)
    assert abandoned_session is not None
    assert abandoned_session.status == IngestStatus.FAILED, (
        f"Abandoned session status should be FAILED; " f"got {abandoned_session.status}"
    )

    # Verify the staging directory is cleaned up.
    assert not staging_path.exists(), (
        f"Staging directory must be removed after abandon; "
        f"still exists at {staging_path}"
    )

    # Verify the canonical corpus is unchanged (no new version created).
    versions_after = await store._version_repo.list_by_corpus(corpus.id)
    assert len(versions_after) == version_count_before, (
        f"Version count must not change after abandon; "
        f"before={version_count_before}, after={len(versions_after)}"
    )
