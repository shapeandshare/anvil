"""Tests for DemoBootstrapService."""

from pathlib import Path

import pytest

from anvil.db.repositories.corpora import CorpusRepository
from anvil.db.repositories.datasets import DatasetRepository
from anvil.services.demo.demo_bootstrap import DEMO_DIR, DemoBootstrapService, DEFAULT_CORPUS_NAME

pytestmark = pytest.mark.asyncio


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
        "two plus two equals four\n"
        "three times three equals nine\n"
    )
    return d


async def test_bootstrap_all_creates_entities(session, monkeypatch, demo_dir):
    monkeypatch.setattr("anvil.services.demo_bootstrap.DEMO_DIR", demo_dir)
    svc = DemoBootstrapService(session)
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
    monkeypatch.setattr("anvil.services.demo_bootstrap.DEMO_DIR", demo_dir)
    svc = DemoBootstrapService(session)
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

    monkeypatch.setattr("anvil.services.demo_bootstrap.DEMO_DIR", demo_dir)
    svc = DemoBootstrapService(session)
    result = await svc.bootstrap_all()
    await session.commit()

    assert result.corpora_created == 1
    assert result.datasets_created == 0
    assert len(result.errors) >= 1

    bad_file.chmod(0o644)


async def test_bootstrap_all_empty_dir(session, monkeypatch, tmp_path):
    empty_dir = tmp_path / "empty_demo"
    empty_dir.mkdir()
    monkeypatch.setattr("anvil.services.demo_bootstrap.DEMO_DIR", empty_dir)

    svc = DemoBootstrapService(session)
    result = await svc.bootstrap_all()
    await session.commit()

    assert result.corpora_created == 0
    assert result.datasets_created == 0
    assert result.corpora_skipped == 0


async def test_bootstrap_all_missing_dir(session, monkeypatch):
    missing = Path("/nonexistent/demo")
    monkeypatch.setattr("anvil.services.demo_bootstrap.DEMO_DIR", missing)

    svc = DemoBootstrapService(session)
    result = await svc.bootstrap_all()

    assert len(result.errors) >= 1
    assert "not found" in result.errors[0].lower()


async def test_get_default_corpus_returns_none_when_not_bootstrapped(session):
    svc = DemoBootstrapService(session)
    corpus = await svc.get_default_corpus()
    assert corpus is None


async def test_get_default_corpus_after_bootstrap(session, monkeypatch, demo_dir):
    monkeypatch.setattr("anvil.services.demo_bootstrap.DEMO_DIR", demo_dir)
    svc = DemoBootstrapService(session)
    await svc.bootstrap_all()
    await session.commit()

    monkeypatch.setattr(
        "anvil.services.demo_bootstrap.DEFAULT_CORPUS_NAME",
        "Demo - small/names",
    )
    corpus = await svc.get_default_corpus()
    assert corpus is not None
    assert corpus.name == "Demo - small/names"