# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for DemoBootstrapService — naming helpers, provenance, and bootstrap orchestration.

Uses mock-based tests for methods that depend on async DB access.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anvil.services.demo.bootstrap_result import BootstrapResult

# ═══════════════════════════════════════════════════════════════════
# Static / pure-function helpers
# ═══════════════════════════════════════════════════════════════════


class TestCorpusNameFor:
    def test_generates_prefixed_name(self) -> None:
        from anvil.services.demo.demo_bootstrap import DEMO_DIR, DemoBootstrapService

        item = DEMO_DIR / "small" / "names"
        name = DemoBootstrapService._corpus_name_for(item)
        assert name == "Demo - small/names"

    def test_nested_path(self) -> None:
        from anvil.services.demo.demo_bootstrap import DEMO_DIR, DemoBootstrapService

        item = DEMO_DIR / "medium" / "alice"
        name = DemoBootstrapService._corpus_name_for(item)
        assert name == "Demo - medium/alice"


class TestDatasetNameFor:
    def test_generates_prefixed_name(self) -> None:
        from anvil.services.demo.demo_bootstrap import DEMO_DIR, DemoBootstrapService

        item = DEMO_DIR / "small" / "names.txt"
        name = DemoBootstrapService._dataset_name_for(item)
        assert name == "Demo - small/names"

    def test_stem_removes_suffix(self) -> None:
        from anvil.services.demo.demo_bootstrap import DEMO_DIR, DemoBootstrapService

        item = DEMO_DIR / "medium" / "readme.txt"
        name = DemoBootstrapService._dataset_name_for(item)
        assert name == "Demo - medium/readme"


class TestIsDemoEntity:
    def test_demo_prefix_returns_true(self) -> None:
        from anvil.services.demo.demo_bootstrap import DemoBootstrapService

        assert DemoBootstrapService.is_demo_entity("Demo - small/names") is True

    def test_non_demo_returns_false(self) -> None:
        from anvil.services.demo.demo_bootstrap import DemoBootstrapService

        assert DemoBootstrapService.is_demo_entity("my-corpus") is False

    def test_empty_returns_false(self) -> None:
        from anvil.services.demo.demo_bootstrap import DemoBootstrapService

        assert DemoBootstrapService.is_demo_entity("") is False


# ═══════════════════════════════════════════════════════════════════
# Provenance helpers
# ═══════════════════════════════════════════════════════════════════


class TestGetProvenanceFor:
    def test_finds_item_in_manifest(self) -> None:
        from anvil.services.demo.demo_bootstrap import DEMO_DIR, DemoBootstrapService

        svc = DemoBootstrapService.__new__(DemoBootstrapService)
        svc._session = MagicMock()
        svc._corpus_repo = MagicMock()
        svc._dataset_repo = MagicMock()
        svc._corpus_loader = MagicMock()
        svc._corpus_svc = MagicMock()
        svc._dataset_svc = MagicMock()
        svc._provenance_manifest = {
            "medium/alice": {
                "source": "Project Gutenberg",
                "license": "Public Domain",
            },
        }
        svc._license_repo = None

        item = DEMO_DIR / "medium" / "alice"
        result = svc._get_provenance_for(item)
        assert result is not None
        assert result["source"] == "Project Gutenberg"

    def test_not_in_manifest_returns_none(self) -> None:
        from anvil.services.demo.demo_bootstrap import DEMO_DIR, DemoBootstrapService

        svc = DemoBootstrapService.__new__(DemoBootstrapService)
        svc._session = MagicMock()
        svc._corpus_repo = MagicMock()
        svc._dataset_repo = MagicMock()
        svc._corpus_loader = MagicMock()
        svc._corpus_svc = MagicMock()
        svc._dataset_svc = MagicMock()
        svc._provenance_manifest = {}
        svc._license_repo = None

        item = DEMO_DIR / "small" / "unknown"
        result = svc._get_provenance_for(item)
        assert result is None

    def test_strips_txt_suffix_for_datasets(self) -> None:
        from anvil.services.demo.demo_bootstrap import DEMO_DIR, DemoBootstrapService

        svc = DemoBootstrapService.__new__(DemoBootstrapService)
        svc._session = MagicMock()
        svc._corpus_repo = MagicMock()
        svc._dataset_repo = MagicMock()
        svc._corpus_loader = MagicMock()
        svc._corpus_svc = MagicMock()
        svc._dataset_svc = MagicMock()
        svc._provenance_manifest = {
            "small/names": {"source": "Test", "license": "MIT"},
        }
        svc._license_repo = None

        item = DEMO_DIR / "small" / "names.txt"
        result = svc._get_provenance_for(item)
        assert result is not None


class TestLoadManifest:
    def test_loads_manifest_successfully(self, monkeypatch) -> None:
        """_load_manifest parses JSON from the bundled provenance file."""
        import json

        fake_data = {"medium/alice": {"source": "Test", "license": "MIT"}}
        mock_resource = MagicMock()
        mock_resource.read_text.return_value = json.dumps(fake_data)

        monkeypatch.setattr(
            "importlib.resources.files",
            lambda pkg: MagicMock(
                joinpath=lambda *args: mock_resource,
            ),
        )

        from anvil.services.demo.demo_bootstrap import DemoBootstrapService

        svc = DemoBootstrapService.__new__(DemoBootstrapService)
        svc._session = MagicMock()
        svc._corpus_repo = MagicMock()
        svc._dataset_repo = MagicMock()
        svc._corpus_loader = MagicMock()
        svc._corpus_svc = MagicMock()
        svc._dataset_svc = MagicMock()
        svc._license_repo = None
        svc._provenance_manifest = {}

        svc._load_manifest()
        assert "medium/alice" in svc._provenance_manifest

    def test_load_manifest_fallback_on_error(self, monkeypatch) -> None:
        """_load_manifest falls back to empty dict on error."""
        monkeypatch.setattr(
            "importlib.resources.files",
            lambda pkg: MagicMock(
                joinpath=lambda *args: MagicMock(
                    read_text=MagicMock(side_effect=FileNotFoundError)
                )
            ),
        )

        from anvil.services.demo.demo_bootstrap import DemoBootstrapService

        svc = DemoBootstrapService.__new__(DemoBootstrapService)
        svc._session = MagicMock()
        svc._corpus_repo = MagicMock()
        svc._dataset_repo = MagicMock()
        svc._corpus_loader = MagicMock()
        svc._corpus_svc = MagicMock()
        svc._dataset_svc = MagicMock()
        svc._license_repo = None
        svc._provenance_manifest = {}

        svc._load_manifest()
        assert svc._provenance_manifest == {}


# ═══════════════════════════════════════════════════════════════════
# Resolve DEMO_DIR
# ═══════════════════════════════════════════════════════════════════


class TestResolveDemoDir:
    def test_resolve_demo_dir_returns_path(self) -> None:
        from anvil.services.demo.demo_bootstrap import _resolve_demo_dir

        result = _resolve_demo_dir()
        assert isinstance(result, Path)
        assert "data" in str(result)
        assert "demo" in str(result)

    def test_demo_dir_is_absolute(self) -> None:
        from anvil.services.demo.demo_bootstrap import DEMO_DIR

        assert DEMO_DIR.is_absolute()


# ═══════════════════════════════════════════════════════════════════
# Query methods (mocked DB)
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_db_objects():
    from anvil.db.models.corpus import Corpus
    from anvil.db.models.dataset import Dataset

    corpus_a = MagicMock(spec=Corpus)
    corpus_a.name = "Demo - small/names"
    corpus_b = MagicMock(spec=Corpus)
    corpus_b.name = "Demo - medium/alice"
    non_demo_corpus = MagicMock(spec=Corpus)
    non_demo_corpus.name = "my-own-corpus"

    dataset_a = MagicMock(spec=Dataset)
    dataset_a.name = "Demo - small/names"
    non_demo_dataset = MagicMock(spec=Dataset)
    non_demo_dataset.name = "my-own-dataset"

    return {
        "corpus_a": corpus_a,
        "corpus_b": corpus_b,
        "non_demo_corpus": non_demo_corpus,
        "dataset_a": dataset_a,
        "non_demo_dataset": non_demo_dataset,
    }


@pytest.fixture
def bootstrap_service(mock_db_objects):
    from anvil.services.demo.demo_bootstrap import DemoBootstrapService

    svc = DemoBootstrapService.__new__(DemoBootstrapService)
    svc._session = AsyncMock()
    svc._corpus_repo = MagicMock()
    svc._dataset_repo = MagicMock()
    svc._corpus_loader = MagicMock()
    svc._corpus_svc = MagicMock()
    svc._dataset_svc = MagicMock()
    svc._provenance_manifest = {
        "small/names": {"source": "Test", "license": "MIT"},
        "medium/alice": {"source": "Project Gutenberg", "license": "Public Domain"},
    }
    svc._license_repo = None
    svc._corpus_repo.get_by_name = AsyncMock()
    svc._corpus_repo.get_all = AsyncMock()
    svc._dataset_repo.get_by_name = AsyncMock()
    svc._dataset_repo.get_all = AsyncMock()
    return svc


class TestGetDefaultCorpus:
    async def test_returns_corpus_when_found(self, bootstrap_service) -> None:
        from anvil.db.models.corpus import Corpus

        mock_corpus = MagicMock(spec=Corpus)
        mock_corpus.name = "Demo - medium/alice"
        bootstrap_service._corpus_repo.get_by_name = AsyncMock(return_value=mock_corpus)

        result = await bootstrap_service.get_default_corpus()
        assert result is not None
        assert result.name == "Demo - medium/alice"

    async def test_returns_none_when_missing(self, bootstrap_service) -> None:
        bootstrap_service._corpus_repo.get_by_name = AsyncMock(return_value=None)
        result = await bootstrap_service.get_default_corpus()
        assert result is None


class TestListDemoCorpora:
    async def test_returns_only_demo_prefixed(self, bootstrap_service) -> None:
        from anvil.db.models.corpus import Corpus

        demo1 = MagicMock(spec=Corpus)
        demo1.name = "Demo - small/names"
        demo2 = MagicMock(spec=Corpus)
        demo2.name = "Demo - medium/alice"
        non_demo = MagicMock(spec=Corpus)
        non_demo.name = "my-own-corpus"

        bootstrap_service._corpus_repo.get_all = AsyncMock(
            return_value=[demo1, demo2, non_demo]
        )

        result = await bootstrap_service.list_demo_corpora()
        assert len(result) == 2
        names = [c.name for c in result]
        assert "Demo - small/names" in names
        assert "Demo - medium/alice" in names
        assert "my-own-corpus" not in names


class TestListDemoDatasets:
    async def test_returns_only_demo_prefixed(self, bootstrap_service) -> None:
        from anvil.db.models.dataset import Dataset

        demo = MagicMock(spec=Dataset)
        demo.name = "Demo - small/names"
        non_demo = MagicMock(spec=Dataset)
        non_demo.name = "my-own-dataset"

        bootstrap_service._dataset_repo.get_all = AsyncMock(
            return_value=[demo, non_demo]
        )

        result = await bootstrap_service.list_demo_datasets()
        assert len(result) == 1
        assert result[0].name == "Demo - small/names"


class TestGetDemoCorpus:
    async def test_returns_by_prefixed_name(self, bootstrap_service) -> None:
        from anvil.db.models.corpus import Corpus

        mock_corpus = MagicMock(spec=Corpus)
        mock_corpus.name = "Demo - small/names"
        bootstrap_service._corpus_repo.get_by_name = AsyncMock(return_value=mock_corpus)

        result = await bootstrap_service.get_demo_corpus("small/names")
        assert result is not None
        assert result.name == "Demo - small/names"

    async def test_returns_none_for_missing(self, bootstrap_service) -> None:
        bootstrap_service._corpus_repo.get_by_name = AsyncMock(return_value=None)
        result = await bootstrap_service.get_demo_corpus("nonexistent")
        assert result is None


class TestGetDemoDataset:
    async def test_returns_by_prefixed_name(self, bootstrap_service) -> None:
        from anvil.db.models.dataset import Dataset

        mock_dataset = MagicMock(spec=Dataset)
        mock_dataset.name = "Demo - small/names"
        bootstrap_service._dataset_repo.get_by_name = AsyncMock(
            return_value=mock_dataset
        )

        result = await bootstrap_service.get_demo_dataset("small/names")
        assert result is not None
        assert result.name == "Demo - small/names"

    async def test_returns_none_for_missing(self, bootstrap_service) -> None:
        bootstrap_service._dataset_repo.get_by_name = AsyncMock(return_value=None)
        result = await bootstrap_service.get_demo_dataset("nonexistent")
        assert result is None


class TestBootstrapAll:
    async def test_returns_error_when_demo_dir_missing(self, monkeypatch) -> None:
        """bootstrap_all returns error when DEMO_DIR does not exist."""
        from anvil.services.demo import demo_bootstrap as db_mod

        monkeypatch.setattr(db_mod, "DEMO_DIR", Path("/nonexistent/demo"))
        svc = db_mod.DemoBootstrapService.__new__(db_mod.DemoBootstrapService)
        svc._session = MagicMock()
        svc._corpus_repo = MagicMock()
        svc._dataset_repo = MagicMock()
        svc._corpus_loader = MagicMock()
        svc._corpus_svc = MagicMock()
        svc._dataset_svc = MagicMock()
        svc._provenance_manifest = {}
        svc._license_repo = None

        result = await svc.bootstrap_all()
        assert isinstance(result, BootstrapResult)
        assert len(result.errors) == 1
        assert "Demo directory not found" in result.errors[0]

    async def test_bootstrap_all_skips_hidden_dirs(self, monkeypatch, tmp_path) -> None:
        """bootstrap_all skips directories starting with a dot."""
        from anvil.services.demo import demo_bootstrap as db_mod

        demo_dir = tmp_path / "demo"
        (demo_dir / ".hidden").mkdir(parents=True)
        (demo_dir / "small").mkdir()

        monkeypatch.setattr(db_mod, "DEMO_DIR", demo_dir)

        svc = db_mod.DemoBootstrapService.__new__(db_mod.DemoBootstrapService)
        svc._session = MagicMock()
        svc._corpus_repo = MagicMock()
        svc._dataset_repo = MagicMock()
        svc._corpus_loader = MagicMock()
        svc._corpus_svc = MagicMock()
        svc._dataset_svc = MagicMock()
        svc._provenance_manifest = {}
        svc._license_repo = None

        result = await svc.bootstrap_all()
        assert isinstance(result, BootstrapResult)

    async def test_bootstrap_corpus_skips_existing(self, monkeypatch, tmp_path) -> None:
        """_bootstrap_corpus skips when corpus already exists."""
        from anvil.services.demo import demo_bootstrap as db_mod

        demo_dir = tmp_path / "demo"
        item = demo_dir / "small" / "names"
        item.mkdir(parents=True)
        monkeypatch.setattr(db_mod, "DEMO_DIR", demo_dir)

        svc = db_mod.DemoBootstrapService.__new__(db_mod.DemoBootstrapService)
        svc._session = MagicMock()
        svc._corpus_repo = MagicMock()
        svc._dataset_repo = MagicMock()
        svc._corpus_loader = MagicMock()
        svc._corpus_svc = MagicMock()
        svc._dataset_svc = MagicMock()
        svc._provenance_manifest = {}
        svc._license_repo = None
        svc._corpus_repo.get_by_name = AsyncMock(return_value=MagicMock())

        result_obj = BootstrapResult()
        ok = await svc._bootstrap_corpus(item, result_obj)
        assert ok is False
        assert result_obj.corpora_skipped == 1

    async def test_bootstrap_corpus_skips_without_provenance(
        self, monkeypatch, tmp_path
    ) -> None:
        """_bootstrap_corpus skips when provenance manifest entry is missing."""
        from anvil.services.demo import demo_bootstrap as db_mod

        demo_dir = tmp_path / "demo"
        item = demo_dir / "small" / "names"
        item.mkdir(parents=True)
        monkeypatch.setattr(db_mod, "DEMO_DIR", demo_dir)

        svc = db_mod.DemoBootstrapService.__new__(db_mod.DemoBootstrapService)
        svc._session = MagicMock()
        svc._corpus_repo = MagicMock()
        svc._corpus_repo.get_by_name = AsyncMock(return_value=None)
        svc._dataset_repo = MagicMock()
        svc._corpus_loader = MagicMock()
        svc._corpus_svc = MagicMock()
        svc._dataset_svc = MagicMock()
        svc._provenance_manifest = {}
        svc._license_repo = None

        result_obj = BootstrapResult()
        ok = await svc._bootstrap_corpus(item, result_obj)
        assert ok is False
        assert len(result_obj.errors) > 0
        assert "no provenance manifest entry" in result_obj.errors[0]

    async def test_bootstrap_dataset_skips_existing(
        self, monkeypatch, tmp_path
    ) -> None:
        """_bootstrap_dataset skips when dataset already exists."""
        from anvil.services.demo import demo_bootstrap as db_mod

        demo_dir = tmp_path / "demo"
        item = demo_dir / "small" / "names.txt"
        item.parent.mkdir(parents=True)
        item.write_text("test content")
        monkeypatch.setattr(db_mod, "DEMO_DIR", demo_dir)

        svc = db_mod.DemoBootstrapService.__new__(db_mod.DemoBootstrapService)
        svc._session = MagicMock()
        svc._corpus_repo = MagicMock()
        svc._corpus_repo.get_by_name = AsyncMock(return_value=None)
        svc._dataset_repo = MagicMock()
        svc._dataset_repo.get_by_name = AsyncMock(return_value=MagicMock())
        svc._corpus_loader = MagicMock()
        svc._corpus_svc = MagicMock()
        svc._dataset_svc = MagicMock()
        svc._provenance_manifest = {}
        svc._license_repo = None

        result_obj = BootstrapResult()
        ok = await svc._bootstrap_dataset(item, result_obj)
        assert ok is False
        assert result_obj.datasets_skipped == 1


# ═══════════════════════════════════════════════════════════════════
# BootstrapResult unit tests
# ═══════════════════════════════════════════════════════════════════


class TestBootstrapResult:
    def test_default_values(self) -> None:
        result = BootstrapResult()
        assert result.corpora_created == 0
        assert result.datasets_created == 0
        assert result.corpora_skipped == 0
        assert result.datasets_skipped == 0
        assert result.errors == []
        assert result.total_time_ms == 0.0

    def test_can_accumulate(self) -> None:
        result = BootstrapResult()
        result.corpora_created += 2
        result.datasets_created += 1
        result.corpora_skipped += 1
        result.errors.append("test error")
        assert result.corpora_created == 2
        assert result.datasets_created == 1
        assert result.corpora_skipped == 1
        assert len(result.errors) == 1
