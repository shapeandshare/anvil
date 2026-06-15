"""Tests for TrainingService training data fallback."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from anvil.services.training import TrainingService

pytestmark = pytest.mark.asyncio


async def test_load_docs_raises_error_when_no_demo_corpus(session):
    svc = TrainingService()

    with pytest.raises(RuntimeError) as exc:
        with patch(
            "anvil.services.demo_bootstrap.DemoBootstrapService.get_default_corpus",
            new_callable=AsyncMock,
            return_value=None,
        ):
            with patch(
                "anvil.db.session.AsyncSessionLocal",
                return_value=MagicMock(
                    __aenter__=AsyncMock(return_value=session),
                    __aexit__=AsyncMock(),
                ),
            ):
                svc._load_docs(corpus_id=None, dataset_id=None)

    assert "bootstrap" in str(exc.value).lower()
    assert "Demo - medium/alice" in str(exc.value)


async def test_load_docs_uses_demo_corpus_when_specified(session, monkeypatch):
    svc = TrainingService()

    from anvil.db.models.corpus import Corpus
    from anvil.db.repositories.corpora import CorpusRepository

    repo = CorpusRepository(session)
    corpus = await repo.add(
        Corpus(
            name="test-corpus",
            root_path="/tmp/nonexistent",
            chunking_strategy="file",
        )
    )
    await session.commit()

    result = svc._load_docs(corpus_id=corpus.id)
    assert isinstance(result, list)


async def test_load_docs_uses_demo_dataset_when_specified(session):
    svc = TrainingService()

    from anvil.db.models.training_config import Dataset
    from anvil.db.repositories.datasets import DatasetRepository

    repo = DatasetRepository(session)
    ds = await repo.add(Dataset(name="test-ds", filename="", file_path=""))
    await session.commit()

    result = svc._load_docs(dataset_id=ds.id)
    assert isinstance(result, list)