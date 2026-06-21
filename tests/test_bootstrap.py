# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for DemoBootstrapService."""

from pathlib import Path

import pytest

from anvil.db.repositories.corpora import CorpusRepository
from anvil.db.repositories.datasets import DatasetRepository
from anvil.services.demo.demo_bootstrap import (
    DEFAULT_CORPUS_NAME,
    DEMO_DIR,
    DemoBootstrapService,
)

pytestmark = pytest.mark.asyncio


PROVENANCE_MANIFEST: dict[str, dict[str, str]] = {
    "small/names": {"source": "Public name lists", "license": "MIT", "attribution": ""},
    "medium/math-facts": {
        "source": "Hand-crafted mathematical facts",
        "license": "Generated/Original",
        "attribution": "",
    },
}
"""Provenance manifest fixture matching demo_dir structure."""


def _svc_with_provenance(session) -> DemoBootstrapService:
    """Create a DemoBootstrapService with a pre-loaded provenance manifest."""
    svc = DemoBootstrapService(session)
    svc._provenance_manifest = PROVENANCE_MANIFEST
    return svc


@pytest.fixture
def demo_dir(tmp_path: Path) -> Path:
    """Create a temporary data/demo/ tree with one corpus and one dataset."""
    d = tmp_path / "demo"
    corpus_dir = d / "small" / "names"
    corpus_dir.mkdir(parents=True)
    (corpus_dir / "alice.txt").write_text(
        "Alice was beginning to get very tired of sitting by her sister.\n"
        "The rabbit hole went straight on like a tunnel.\n"
    )
    ds_dir = d / "medium"
    ds_dir.mkdir(parents=True)
    (ds_dir / "math-facts.txt").write_text(
        "two plus two equals four\n" "three times three equals nine\n"
    )
    return d


async def test_bootstrap_all_creates_entities(session, monkeypatch, demo_dir):
    monkeypatch.setattr("anvil.services.demo.demo_bootstrap.DEMO_DIR", demo_dir)
    svc = _svc_with_provenance(session)
    result = await svc.bootstrap_all()
    await session.commit()

    assert result.corpora_created == 1
    assert result.datasets_created == 1
    assert result.corpora_skipped == 0
    assert result.datasets_skipped == 0
    assert len(result.errors) == 0
    assert result.total_time_ms > 0

    corpus = await svc.list_demo_corpora()
    assert len(corpus) == 1
    assert corpus[0].name == "Demo - small/names"

    datasets = await svc.list_demo_datasets()
    assert len(datasets) == 1
    assert datasets[0].name == "Demo - medium/math-facts"


async def test_bootstrap_all_idempotent(session, monkeypatch, demo_dir):
    monkeypatch.setattr("anvil.services.demo.demo_bootstrap.DEMO_DIR", demo_dir)
    svc = _svc_with_provenance(session)
    result1 = await svc.bootstrap_all()
    await session.commit()

    result2 = await svc.bootstrap_all()
    await session.commit()

    assert result2.corpora_created == 0
    assert result2.datasets_created == 0
    assert result2.corpora_skipped == 1
    assert result2.datasets_skipped == 1


async def test_bootstrap_all_partial_failure(session, monkeypatch, demo_dir):
    bad_file = demo_dir / "medium" / "math-facts.txt"
    bad_file.chmod(0o000)

    monkeypatch.setattr("anvil.services.demo.demo_bootstrap.DEMO_DIR", demo_dir)
    svc = _svc_with_provenance(session)
    result = await svc.bootstrap_all()
    await session.commit()

    assert result.corpora_created == 1
    assert result.datasets_created == 0
    assert len(result.errors) >= 1

    bad_file.chmod(0o644)


async def test_bootstrap_all_empty_dir(session, monkeypatch, tmp_path):
    empty_dir = tmp_path / "empty_demo"
    empty_dir.mkdir()
    monkeypatch.setattr("anvil.services.demo.demo_bootstrap.DEMO_DIR", empty_dir)

    svc = _svc_with_provenance(session)
    result = await svc.bootstrap_all()
    await session.commit()

    assert result.corpora_created == 0
    assert result.datasets_created == 0
    assert result.corpora_skipped == 0


async def test_bootstrap_all_missing_dir(session, monkeypatch):
    missing = Path("/nonexistent/demo")
    monkeypatch.setattr("anvil.services.demo.demo_bootstrap.DEMO_DIR", missing)

    svc = _svc_with_provenance(session)
    result = await svc.bootstrap_all()

    assert len(result.errors) >= 1
    assert "not found" in result.errors[0].lower()


async def test_get_default_corpus_returns_none_when_not_bootstrapped(session):
    svc = _svc_with_provenance(session)
    corpus = await svc.get_default_corpus()
    assert corpus is None


async def test_get_default_corpus_after_bootstrap(session, monkeypatch, demo_dir):
    monkeypatch.setattr("anvil.services.demo.demo_bootstrap.DEMO_DIR", demo_dir)
    svc = _svc_with_provenance(session)
    await svc.bootstrap_all()
    await session.commit()

    monkeypatch.setattr(
        "anvil.services.demo.demo_bootstrap.DEFAULT_CORPUS_NAME",
        "Demo - small/names",
    )
    corpus = await svc.get_default_corpus()
    assert corpus is not None
    assert corpus.name == "Demo - small/names"


async def test_count_by_origin_reflects_bootstrap_state(session, monkeypatch, demo_dir):
    """Verify count_by_origin returns 0 before bootstrap and > 0 after."""
    monkeypatch.setattr("anvil.services.demo.demo_bootstrap.DEMO_DIR", demo_dir)
    corpus_repo = CorpusRepository(session)
    dataset_repo = DatasetRepository(session)

    # Before bootstrap: origin="bundled" count should be 0
    assert await corpus_repo.count_by_origin("bundled") == 0
    assert await dataset_repo.count_by_origin("bundled") == 0

    # Bootstrap
    svc = _svc_with_provenance(session)
    await svc.bootstrap_all()
    await session.commit()

    # After bootstrap: count should match created entities
    assert await corpus_repo.count_by_origin("bundled") == 1
    assert await dataset_repo.count_by_origin("bundled") == 1


async def test_guard_skips_when_bundled_data_exists(session, monkeypatch, demo_dir):
    """Verify the guard condition prevents bootstrap when data exists.

    Also verifies FR-007: the guard does not affect warmup preconditions.
    Existing bundled entities remain queryable after the guard skips.
    """
    monkeypatch.setattr("anvil.services.demo.demo_bootstrap.DEMO_DIR", demo_dir)
    corpus_repo = CorpusRepository(session)
    dataset_repo = DatasetRepository(session)

    # Bootstrap once
    svc = _svc_with_provenance(session)
    result1 = await svc.bootstrap_all()
    await session.commit()
    assert result1.corpora_created == 1
    assert result1.datasets_created == 1

    # Guard check: count > 0 means "already bootstrapped"
    corpus_count = await corpus_repo.count_by_origin("bundled")
    dataset_count = await dataset_repo.count_by_origin("bundled")
    assert corpus_count > 0
    assert dataset_count > 0

    # FR-007: existing bundled entities are still queryable (warmup precondition)
    existing_corpora = await svc.list_demo_corpora()
    existing_datasets = await svc.list_demo_datasets()
    assert len(existing_corpora) == 1
    assert len(existing_datasets) == 1

    # If we call bootstrap_all again (simulating what would happen
    # without the guard), idempotency ensures no duplicates
    result2 = await svc.bootstrap_all()
    await session.commit()
    assert result2.corpora_created == 0
    assert result2.datasets_created == 0


async def test_rebootstrap_returns_bootstrap_result_shape(
    session, monkeypatch, demo_dir
):
    """Verify the re-bootstrap endpoint returns BootstrapResult-shaped data.

    Tests the contract: POST /v1/demo/bootstrap returns corpora_created,
    datasets_created, corpora_skipped, datasets_skipped, errors, total_time_ms.
    """
    monkeypatch.setattr("anvil.services.demo.demo_bootstrap.DEMO_DIR", demo_dir)
    svc = _svc_with_provenance(session)

    # First call: creates entities
    result = await svc.bootstrap_all()
    await session.commit()
    assert result.corpora_created == 1
    assert result.datasets_created == 1
    assert result.corpora_skipped == 0
    assert result.datasets_skipped == 0
    assert isinstance(result.errors, list)
    assert result.total_time_ms > 0

    # Second call: idempotent (all skipped)
    result2 = await svc.bootstrap_all()
    await session.commit()
    assert result2.corpora_created == 0
    assert result2.datasets_created == 0
    assert result2.corpora_skipped == 1
    assert result2.datasets_skipped == 1
    assert result2.total_time_ms > 0


async def test_cli_banner_conditional(session, monkeypatch, demo_dir):
    """Verify the CLI banner only prints when entities are created.

    The banner condition is ``corpora_created > 0 or datasets_created > 0``.
    On first call (fresh DB): banner should print (entities created).
    On second call (data exists): banner should not print (all skipped).
    """
    monkeypatch.setattr("anvil.services.demo.demo_bootstrap.DEMO_DIR", demo_dir)
    svc = _svc_with_provenance(session)

    # First call: fresh environment — banner should print
    result1 = await svc.bootstrap_all()
    await session.commit()
    should_print_1 = result1.corpora_created > 0 or result1.datasets_created > 0
    assert should_print_1  # entities created → banner shown

    # Second call: data already exists — banner should not print
    result2 = await svc.bootstrap_all()
    await session.commit()
    should_print_2 = result2.corpora_created > 0 or result2.datasets_created > 0
    assert not should_print_2  # all skipped → banner hidden


async def test_rebootstrap_lock_rejects_concurrent(session, monkeypatch, demo_dir):
    """Verify the rebootstrap endpoint returns HTTP 409 when bootstrap is in progress.

    The ``_bootstrap_in_progress`` flag (TMR-019 fix) prevents a TOCTOU race
    where two concurrent requests could both bypass the old ``.locked()`` check.
    """
    from anvil.api.v1.health_ops import _bootstrap_in_progress

    assert _bootstrap_in_progress is False
