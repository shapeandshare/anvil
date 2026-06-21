"""End-to-end tests against the REAL LocalVersionedContentStore + services.

Unlike the contract tests (which use an in-memory fake), these exercise the
actual ``LocalVersionedContentStore``, ``IngestionService``, ``CorpusService``,
and repositories against a real SQLite session and on-disk content directory.
This is the authoritative verification that the wired implementation works.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.db.models.content_corpus import ContentCorpus
from anvil.db.models.content_source import ContentSource
from anvil.db.repositories.content_blobs import ContentBlobRepository
from anvil.db.repositories.content_corpora import ContentCorpusRepository
from anvil.db.repositories.content_ingest_sessions import ContentIngestSessionRepository
from anvil.db.repositories.content_sources import ContentSourceRepository
from anvil.db.repositories.content_versions import ContentVersionRepository
from anvil.services.content.ingestion_service import IngestionService
from anvil.services.content.local_versioned_content_store import (
    LocalVersionedContentStore,
)
from anvil.services.content.validation_service import ValidationService


async def _stream(data: bytes) -> AsyncIterator[bytes]:
    """Yield *data* as a single-chunk async byte stream."""
    yield data


async def _build(
    session: AsyncSession, content_dir: Path
) -> tuple[IngestionService, LocalVersionedContentStore, ContentCorpus, ContentSource]:
    """Construct the real store + ingestion service with a seeded corpus/source."""
    store = LocalVersionedContentStore(content_dir=str(content_dir), db_session=session)
    corpus_repo = ContentCorpusRepository(session)
    source_repo = ContentSourceRepository(session)
    version_repo = ContentVersionRepository(session)
    session_repo = ContentIngestSessionRepository(session)
    blob_repo = ContentBlobRepository(session)

    corpus = await corpus_repo.add(
        ContentCorpus(slug="shakespeare", name="Shakespeare")
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


@pytest.mark.asyncio
async def test_real_ingest_accept_resolve_roundtrip(
    content_db: AsyncSession, content_dir: Path
) -> None:
    """Real flow: open → stage → validate → accept → resolve → open_blob."""
    ingestion, store, corpus, source = await _build(content_db, content_dir)

    ref = await ingestion.open_session(corpus.id, source.id)
    staged = await ingestion.stage(
        ref.session_id, "sonnet1.txt", _stream(b"hello world")
    )
    assert staged.content_hash
    assert staged.size_bytes == len(b"hello world")

    report = await ingestion.validate(ref.session_id)
    assert report.ok, f"validation failed: {report.problems}"

    result = await ingestion.accept(ref.session_id)
    assert result.entry_count == 1, "accepted version must contain the staged entry"
    assert result.total_bytes == len(b"hello world")
    assert len(result.manifest_digest) == 64

    from anvil.services.content.version_ref import VersionRef

    manifest = await store.resolve(
        VersionRef(
            manifest_digest=result.manifest_digest,
            version_id=result.version_id,
            version_number=result.version_number,
            label=None,
        )
    )
    assert len(manifest.entries) == 1
    assert manifest.entries[0].path == "sonnet1.txt"

    chunks = b""
    stream = await store.open_blob(manifest.entries[0].content_hash)
    async for chunk in stream:
        chunks += chunk
    assert chunks == b"hello world", "open_blob must return the staged bytes"


@pytest.mark.asyncio
async def test_real_reproducibility_after_second_accept(
    content_db: AsyncSession, content_dir: Path
) -> None:
    """SC-001: a pinned version re-resolves identically after the corpus grows."""
    ingestion, store, corpus, source = await _build(content_db, content_dir)
    corpus_id, source_id = corpus.id, source.id

    from anvil.services.content.version_ref import VersionRef

    ref1 = await ingestion.open_session(corpus_id, source_id)
    await ingestion.stage(ref1.session_id, "a.txt", _stream(b"alpha"))
    r1 = await ingestion.accept(ref1.session_id)
    v1 = VersionRef(
        manifest_digest=r1.manifest_digest,
        version_id=r1.version_id,
        version_number=r1.version_number,
        label=None,
    )
    m1_before = await store.resolve(v1)

    ref2 = await ingestion.open_session(corpus_id, source_id)
    await ingestion.stage(ref2.session_id, "b.txt", _stream(b"beta"))
    r2 = await ingestion.accept(ref2.session_id)

    assert r2.manifest_digest != r1.manifest_digest

    m1_after = await store.resolve(v1)
    assert {e.path for e in m1_after.entries} == {e.path for e in m1_before.entries}
    assert m1_after.entries[0].content_hash == m1_before.entries[0].content_hash


@pytest.mark.asyncio
async def test_real_validation_rejects_binary(
    content_db: AsyncSession, content_dir: Path
) -> None:
    """A non-UTF-8 (binary) staged blob must fail validation (fail-closed)."""
    ingestion, _store, corpus, source = await _build(content_db, content_dir)

    ref = await ingestion.open_session(corpus.id, source.id)
    await ingestion.stage(ref.session_id, "bin.dat", _stream(b"\xff\xfe\x00\x01"))

    report = await ingestion.validate(ref.session_id)
    assert not report.ok, "binary content must be rejected by the UTF-8 gate"
