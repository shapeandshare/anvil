# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for MlflowInputResolver — resolves DB entities to MLflow dataset inputs."""

import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestContentDigest:
    def test_same_docs_same_digest(self):
        from anvil.services.tracking.mlflow_inputs import MlflowInputResolver

        d1 = MlflowInputResolver.content_digest(["hello", "world"])
        d2 = MlflowInputResolver.content_digest(["hello", "world"])
        assert d1 == d2
        assert len(d1) == 64

    def test_different_docs_different_digest(self):
        from anvil.services.tracking.mlflow_inputs import MlflowInputResolver

        d1 = MlflowInputResolver.content_digest(["hello"])
        d2 = MlflowInputResolver.content_digest(["world"])
        assert d1 != d2

    def test_empty_docs_stable(self):
        from anvil.services.tracking.mlflow_inputs import MlflowInputResolver

        d = MlflowInputResolver.content_digest([])
        assert isinstance(d, str)
        assert len(d) == 64


class TestResolveDataset:
    @pytest.mark.asyncio
    async def test_returns_dataset_with_digest(self, tmp_path: Path):
        from anvil.services.tracking.mlflow_inputs import MlflowInputResolver

        file = tmp_path / "data.txt"
        file.write_text("hello world")

        mock_session = AsyncMock()
        mock_ds = MagicMock()
        mock_ds.id = 1
        mock_ds.name = "test-ds"
        mock_ds.file_path = str(file)

        with patch(
            "anvil.services.tracking.mlflow_inputs.DatasetRepository"
        ) as repo_cls:
            repo = repo_cls.return_value
            repo.get = AsyncMock(return_value=mock_ds)

            resolver = MlflowInputResolver(mock_session)
            result, digest = await resolver.resolve_dataset(1)
            assert digest == hashlib.sha256(b"hello world").hexdigest()
            assert hasattr(result, "name")
            assert hasattr(result, "digest")

    @pytest.mark.asyncio
    async def test_with_validation_role(self, tmp_path: Path):
        from anvil.services.tracking.mlflow_inputs import MlflowInputResolver

        file = tmp_path / "val.txt"
        file.write_text("val data")

        mock_session = AsyncMock()
        mock_ds = MagicMock()
        mock_ds.id = 2
        mock_ds.name = "val-ds"
        mock_ds.file_path = str(file)

        with patch(
            "anvil.services.tracking.mlflow_inputs.DatasetRepository"
        ) as repo_cls:
            repo = repo_cls.return_value
            repo.get = AsyncMock(return_value=mock_ds)

            resolver = MlflowInputResolver(mock_session)
            _, digest = await resolver.resolve_dataset(2, role="validation")
            assert digest == hashlib.sha256(b"val data").hexdigest()

    @pytest.mark.asyncio
    async def test_dataset_not_found_raises(self):
        from anvil.services.tracking.mlflow_inputs import MlflowInputResolver

        mock_session = AsyncMock()
        with patch(
            "anvil.services.tracking.mlflow_inputs.DatasetRepository"
        ) as repo_cls:
            repo = repo_cls.return_value
            repo.get = AsyncMock(return_value=None)

            resolver = MlflowInputResolver(mock_session)
            with pytest.raises(ValueError, match="Dataset 999 not found"):
                await resolver.resolve_dataset(999)


class TestResolveCorpus:
    @pytest.mark.asyncio
    async def test_returns_metadataset_and_artifact_paths(self, tmp_path: Path):
        from anvil.services.tracking.mlflow_inputs import MlflowInputResolver

        root = tmp_path / "corpus_root"
        root.mkdir()
        (root / "a.py").write_text("def foo(): pass")
        (root / "b.py").write_text("def bar(): pass")

        mock_session = AsyncMock()
        mock_corpus = MagicMock()
        mock_corpus.id = 1
        mock_corpus.name = "test-corpus"
        mock_corpus.root_path = str(root)

        with patch(
            "anvil.services.tracking.mlflow_inputs.CorpusRepository"
        ) as repo_cls:
            repo = repo_cls.return_value
            repo.get = AsyncMock(return_value=mock_corpus)

            resolver = MlflowInputResolver(mock_session)
            meta_ds, artifact_paths, digest = await resolver.resolve_corpus(1)

            assert isinstance(digest, str)
            assert len(digest) == 64
            expected = b"def foo(): pass" + b"def bar(): pass"
            assert digest == hashlib.sha256(expected).hexdigest()
            assert len(artifact_paths) == 2
            assert hasattr(meta_ds, "name")
            assert hasattr(meta_ds, "digest")

    @pytest.mark.asyncio
    async def test_no_files_returns_empty_artifacts(self, tmp_path: Path):
        from anvil.services.tracking.mlflow_inputs import MlflowInputResolver

        root = tmp_path / "empty_corpus"
        root.mkdir()

        mock_session = AsyncMock()
        mock_corpus = MagicMock()
        mock_corpus.id = 2
        mock_corpus.name = "empty"
        mock_corpus.root_path = str(root)

        with patch(
            "anvil.services.tracking.mlflow_inputs.CorpusRepository"
        ) as repo_cls:
            repo = repo_cls.return_value
            repo.get = AsyncMock(return_value=mock_corpus)

            resolver = MlflowInputResolver(mock_session)
            _, artifact_paths, digest = await resolver.resolve_corpus(2)

            assert artifact_paths == []
            assert isinstance(digest, str)

    @pytest.mark.asyncio
    async def test_corpus_not_found_raises(self):
        from anvil.services.tracking.mlflow_inputs import MlflowInputResolver

        mock_session = AsyncMock()
        with patch(
            "anvil.services.tracking.mlflow_inputs.CorpusRepository"
        ) as repo_cls:
            repo = repo_cls.return_value
            repo.get = AsyncMock(return_value=None)

            resolver = MlflowInputResolver(mock_session)
            with pytest.raises(ValueError, match="Corpus 999 not found"):
                await resolver.resolve_corpus(999)


class TestFR024NoCustomCorpusAbstraction:
    def test_no_custom_corpus_store_class_defined(self):
        import inspect

        import anvil.services.tracking.mlflow_inputs as mod

        for name, obj in inspect.getmembers(mod):
            if inspect.isclass(obj):
                cls_name_lower = name.lower()
                assert (
                    "store" not in cls_name_lower
                ), f"FR-024 violation: custom store class '{name}' defined in mlflow_inputs"
