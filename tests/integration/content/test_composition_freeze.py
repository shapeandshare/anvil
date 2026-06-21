"""Integration tests for freeze composition + identical re-resolution +
weighted apply (T069).

Tests the composition freeze contract using the real
``LocalVersionedContentStore``, real SQLite session, and the
``CompositionService`` facade:

- **T069a**: Freeze with weighted entries from two sources (70/30 split)
  → verify ``is_composition=True`` and correct entries/weights.
- **T069b**: Re-resolve the same composition version → byte-identical
  manifest (VCS-1 contract).
- **T069c**: Freeze with a high-weight single-entry composition (100/0)
  → verify weight propagated correctly.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.db.models.content_source import ContentSource
from anvil.db.repositories.content_corpora import ContentCorpusRepository
from anvil.db.repositories.content_sources import ContentSourceRepository
from anvil.db.repositories.content_versions import ContentVersionRepository
from anvil.services.content.composition_service import CompositionService
from anvil.services.content.manifest import compute_manifest_digest

from .test_real_store_e2e import _build, _stream


@pytest.mark.asyncio
async def test_composition_freeze_weighted_entries(
    content_db: AsyncSession,
    content_dir: Path,
) -> None:
    """Freeze a composition with weighted entries from two sources (70/30).

    Stages 2 entries from source A and 1 from source B, accepts both
    sessions, then freezes via ``CompositionService.freeze()`` with a
    70/30 weight split.  Verifies the manifest has ``is_composition=True``
    and the correct entries with their assigned weights.
    """
    ingestion, store, corpus, source_a = await _build(content_db, content_dir)

    # ── Add a second source ──────────────────────────────────────────
    source_repo = ContentSourceRepository(content_db)
    source_b = await source_repo.add(
        ContentSource(slug="injector-b", name="Injector B", kind="injector"),
    )
    # Capture PKs before any commit() call in accept() expires ORM objects.
    src_a_id, src_b_id = source_a.id, source_b.id
    corpus_id = corpus.id

    # ── Stage and accept entries from source A ───────────────────────
    ref_a = await ingestion.open_session(corpus_id, src_a_id)
    a1 = await ingestion.stage(
        ref_a.session_id, "a1.txt", _stream(b"content from source A - part one")
    )
    a2 = await ingestion.stage(
        ref_a.session_id, "a2.txt", _stream(b"content from source A - part two")
    )
    r_a = await ingestion.accept(ref_a.session_id)
    assert r_a.entry_count == 2

    # ── Stage and accept entries from source B ───────────────────────
    ref_b = await ingestion.open_session(corpus_id, src_b_id)
    b1 = await ingestion.stage(
        ref_b.session_id, "b1.txt", _stream(b"content from source B")
    )
    r_b = await ingestion.accept(ref_b.session_id)
    assert r_b.entry_count == 1

    # ── Build CompositionService with real repos ─────────────────────
    corpus_repo = ContentCorpusRepository(content_db)
    version_repo = ContentVersionRepository(content_db)
    comp_svc = CompositionService(
        store=store,
        version_repo=version_repo,
        corpus_repo=corpus_repo,
        db_session=content_db,
    )

    # ── Freeze with weighted composition (70/30 split) ───────────────
    spec = [
        {"content_hash": a1.content_hash, "weight": 0.7},
        {"content_hash": a2.content_hash, "weight": 0.7},
        {"content_hash": b1.content_hash, "weight": 0.3},
    ]
    ref = await comp_svc.freeze(corpus_id, spec)

    # ── Verify frozen manifest via store.resolve ─────────────────────
    manifest = await store.resolve(ref)
    assert manifest.is_composition is True
    assert len(manifest.entries) == 3

    entries_by_path = {e.path: e for e in manifest.entries}
    # Entries are keyed by content_hash (the path set by CompositionService).
    assert entries_by_path[a1.content_hash].weight == 0.7
    assert entries_by_path[a2.content_hash].weight == 0.7
    assert entries_by_path[b1.content_hash].weight == 0.3

    # ── Verify content hashes match the staged entries ──────────────
    expected_hashes = {a1.content_hash, a2.content_hash, b1.content_hash}
    actual_hashes = {e.content_hash for e in manifest.entries}
    assert actual_hashes == expected_hashes


@pytest.mark.asyncio
async def test_composition_identical_re_resolution(
    content_db: AsyncSession,
    content_dir: Path,
) -> None:
    """Re-resolving the same composition version produces an identical
    manifest (VCS-1 contract / SC-001).

    Freeze a composition version, resolve it twice, and verify the
    digests and entry contents match.
    """
    ingestion, store, corpus, source_a = await _build(content_db, content_dir)

    source_repo = ContentSourceRepository(content_db)
    source_b = await source_repo.add(
        ContentSource(slug="src-b", name="Source B", kind="injector"),
    )
    # Capture PKs before any commit() call in accept() expires ORM objects.
    src_a_id, src_b_id = source_a.id, source_b.id
    corpus_id = corpus.id

    # Stage and accept from both sources.
    ref_a = await ingestion.open_session(corpus_id, src_a_id)
    a1 = await ingestion.stage(ref_a.session_id, "x.txt", _stream(b"data X"))
    await ingestion.accept(ref_a.session_id)

    ref_b = await ingestion.open_session(corpus_id, src_b_id)
    b1 = await ingestion.stage(ref_b.session_id, "y.txt", _stream(b"data Y"))
    await ingestion.accept(ref_b.session_id)

    # Freeze composition.
    corpus_repo = ContentCorpusRepository(content_db)
    version_repo = ContentVersionRepository(content_db)
    comp_svc = CompositionService(
        store=store,
        version_repo=version_repo,
        corpus_repo=corpus_repo,
        db_session=content_db,
    )
    ref = await comp_svc.freeze(
        corpus_id,
        [
            {"content_hash": a1.content_hash, "weight": 0.5},
            {"content_hash": b1.content_hash, "weight": 0.5},
        ],
    )

    # ── Resolve twice ────────────────────────────────────────────────
    m1 = await store.resolve(ref)
    m2 = await store.resolve(ref)

    assert compute_manifest_digest(m1) == compute_manifest_digest(m2)
    assert len(m1.entries) == len(m2.entries)
    for e1, e2 in zip(m1.entries, m2.entries, strict=True):
        assert e1.path == e2.path
        assert e1.content_hash == e2.content_hash
        assert e1.weight == e2.weight


@pytest.mark.asyncio
async def test_composition_freeze_single_entry_weight_one(
    content_db: AsyncSession,
    content_dir: Path,
) -> None:
    """Freeze a single-entry composition with ``weight=1.0`` (100%).

    The simplest valid composition: one entry at full weight.  Verifies
    the manifest is marked as a composition and the single entry has the
    correct weight.
    """
    ingestion, store, corpus, source = await _build(content_db, content_dir)
    corpus_id = corpus.id

    ref = await ingestion.open_session(corpus_id, source.id)
    staged = await ingestion.stage(ref.session_id, "only.txt", _stream(b"sole entry"))
    await ingestion.accept(ref.session_id)

    corpus_repo = ContentCorpusRepository(content_db)
    version_repo = ContentVersionRepository(content_db)
    comp_svc = CompositionService(
        store=store,
        version_repo=version_repo,
        corpus_repo=corpus_repo,
        db_session=content_db,
    )

    ref = await comp_svc.freeze(
        corpus_id,
        [
            {"content_hash": staged.content_hash, "weight": 1.0},
        ],
    )

    manifest = await store.resolve(ref)
    assert manifest.is_composition is True
    assert len(manifest.entries) == 1
    assert manifest.entries[0].weight == 1.0
    assert manifest.entries[0].content_hash == staged.content_hash
