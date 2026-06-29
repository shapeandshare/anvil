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


# ═══════════════════════════════════════════════════════════════════
# DEFAULT_CORPUS_NAME constant
# ═══════════════════════════════════════════════════════════════════


class TestDefaultCorpusName:
    def test_default_corpus_name_value(self) -> None:
        """DEFAULT_CORPUS_NAME points to medium/alice."""
        from anvil.services.demo.demo_bootstrap import DEFAULT_CORPUS_NAME

        assert DEFAULT_CORPUS_NAME == "Demo - medium/alice"

    async def test_default_corpus_name_matches_get_default_corpus(self) -> None:
        """get_default_corpus queries using DEFAULT_CORPUS_NAME."""
        from anvil.services.demo.demo_bootstrap import (
            DEFAULT_CORPUS_NAME,
            DemoBootstrapService,
        )

        svc = DemoBootstrapService.__new__(DemoBootstrapService)
        svc._session = MagicMock()
        svc._corpus_repo = MagicMock()
        svc._corpus_repo.get_by_name = AsyncMock(return_value=None)
        svc._dataset_repo = MagicMock()
        svc._corpus_loader = MagicMock()
        svc._corpus_svc = MagicMock()
        svc._dataset_svc = MagicMock()
        svc._provenance_manifest = {}
        svc._license_repo = None

        await svc.get_default_corpus()

        svc._corpus_repo.get_by_name.assert_awaited_once_with(DEFAULT_CORPUS_NAME)


# ═══════════════════════════════════════════════════════════════════
# _bootstrap_corpus — missing-license and success/exception paths
# ═══════════════════════════════════════════════════════════════════


class TestBootstrapCorpusAdvanced:
    async def test_skipped_when_missing_license_in_provenance(
        self, monkeypatch, tmp_path
    ) -> None:
        """_bootstrap_corpus skips when provenance entry has no license key."""
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
        svc._license_repo = None
        # Provenance entry exists but has NO "license" key.
        svc._provenance_manifest = {
            "small/names": {"source": "Test"},
        }

        result_obj = BootstrapResult()
        ok = await svc._bootstrap_corpus(item, result_obj)
        assert ok is False
        assert len(result_obj.errors) == 1
        assert "missing license in provenance manifest" in result_obj.errors[0]

    async def test_success_path(self, monkeypatch, tmp_path) -> None:
        """_bootstrap_corpus succeeds with valid provenance and service calls."""
        from anvil.services.demo import demo_bootstrap as db_mod

        demo_dir = tmp_path / "demo"
        item = demo_dir / "small" / "names"
        item.mkdir(parents=True)
        monkeypatch.setattr(db_mod, "DEMO_DIR", demo_dir)

        mock_corpus = MagicMock()
        mock_corpus.id = 42
        mock_corpus.name = "Demo - small/names"

        svc = db_mod.DemoBootstrapService.__new__(db_mod.DemoBootstrapService)
        svc._session = MagicMock()
        svc._corpus_repo = MagicMock()
        svc._corpus_repo.get_by_name = AsyncMock(return_value=None)
        svc._dataset_repo = MagicMock()
        svc._corpus_loader = MagicMock()
        svc._corpus_svc = MagicMock()
        svc._corpus_svc.create = AsyncMock(return_value=mock_corpus)
        svc._corpus_svc.ingest = AsyncMock(return_value=(mock_corpus, []))
        svc._dataset_svc = MagicMock()
        svc._assign_provenance = AsyncMock()
        svc._license_repo = None
        svc._provenance_manifest = {
            "small/names": {"source": "Test", "license": "MIT"},
        }

        result_obj = BootstrapResult()
        ok = await svc._bootstrap_corpus(item, result_obj)
        assert ok is True

        # Verify the service orchestration.
        svc._corpus_svc.create.assert_awaited_once()
        svc._corpus_svc.ingest.assert_awaited_once_with(42)
        svc._assign_provenance.assert_awaited_once_with(
            mock_corpus,
            {
                "source": "Test",
                "license": "MIT",
            },
        )

    async def test_exception_during_create(self, monkeypatch, tmp_path) -> None:
        """_bootstrap_corpus catches exception from corpus service."""
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
        svc._corpus_svc.create = AsyncMock(side_effect=RuntimeError("disk full"))
        svc._dataset_svc = MagicMock()
        svc._license_repo = None
        svc._provenance_manifest = {
            "small/names": {"source": "Test", "license": "MIT"},
        }

        result_obj = BootstrapResult()
        ok = await svc._bootstrap_corpus(item, result_obj)
        assert ok is False
        assert any("disk full" in e for e in result_obj.errors)


# ═══════════════════════════════════════════════════════════════════
# _bootstrap_dataset — missing-license and success/exception paths
# ═══════════════════════════════════════════════════════════════════


class TestBootstrapDatasetAdvanced:
    async def test_skipped_when_missing_license_in_provenance(
        self, monkeypatch, tmp_path
    ) -> None:
        """_bootstrap_dataset skips when provenance entry has no license key."""
        from anvil.services.demo import demo_bootstrap as db_mod

        demo_dir = tmp_path / "demo"
        item = demo_dir / "small" / "names.txt"
        item.parent.mkdir(parents=True)
        item.write_text("some content")
        monkeypatch.setattr(db_mod, "DEMO_DIR", demo_dir)

        svc = db_mod.DemoBootstrapService.__new__(db_mod.DemoBootstrapService)
        svc._session = MagicMock()
        svc._corpus_repo = MagicMock()
        svc._dataset_repo = MagicMock()
        svc._dataset_repo.get_by_name = AsyncMock(return_value=None)
        svc._corpus_loader = MagicMock()
        svc._corpus_svc = MagicMock()
        svc._dataset_svc = MagicMock()
        svc._license_repo = None
        svc._provenance_manifest = {
            "small/names": {"source": "Test"},
        }

        result_obj = BootstrapResult()
        ok = await svc._bootstrap_dataset(item, result_obj)
        assert ok is False
        assert len(result_obj.errors) == 1
        assert "missing license in provenance manifest" in result_obj.errors[0]

    async def test_success_path(self, monkeypatch, tmp_path) -> None:
        """_bootstrap_dataset succeeds with valid provenance and service calls."""
        from anvil.services.demo import demo_bootstrap as db_mod

        demo_dir = tmp_path / "demo"
        item = demo_dir / "small" / "names.txt"
        item.parent.mkdir(parents=True)
        item.write_text("line1\nline2\n")
        monkeypatch.setattr(db_mod, "DEMO_DIR", demo_dir)

        mock_dataset = MagicMock()
        mock_dataset.id = 99
        mock_dataset.name = "Demo - small/names"

        # Patch DatasetImportService to avoid real session ops.
        mock_import_svc = MagicMock()
        mock_import_svc.commit_import = AsyncMock()

        svc = db_mod.DemoBootstrapService.__new__(db_mod.DemoBootstrapService)
        svc._session = MagicMock()
        svc._corpus_repo = MagicMock()
        svc._dataset_repo = MagicMock()
        svc._dataset_repo.get_by_name = AsyncMock(return_value=None)
        svc._corpus_loader = MagicMock()
        svc._corpus_svc = MagicMock()
        svc._dataset_svc = MagicMock()
        svc._dataset_svc.create_dataset = AsyncMock(return_value=mock_dataset)
        svc._assign_provenance = AsyncMock()
        svc._license_repo = None
        svc._provenance_manifest = {
            "small/names": {"source": "Test", "license": "MIT"},
        }

        with patch.object(db_mod, "DatasetImportService", return_value=mock_import_svc):
            result_obj = BootstrapResult()
            ok = await svc._bootstrap_dataset(item, result_obj)
        assert ok is True

        svc._dataset_svc.create_dataset.assert_awaited_once()
        svc._assign_provenance.assert_awaited_once_with(
            mock_dataset,
            {
                "source": "Test",
                "license": "MIT",
            },
        )

    async def test_exception_during_create(self, monkeypatch, tmp_path) -> None:
        """_bootstrap_dataset catches exception from dataset service."""
        from anvil.services.demo import demo_bootstrap as db_mod

        demo_dir = tmp_path / "demo"
        item = demo_dir / "small" / "names.txt"
        item.parent.mkdir(parents=True)
        item.write_text("some content")
        monkeypatch.setattr(db_mod, "DEMO_DIR", demo_dir)

        svc = db_mod.DemoBootstrapService.__new__(db_mod.DemoBootstrapService)
        svc._session = MagicMock()
        svc._corpus_repo = MagicMock()
        svc._dataset_repo = MagicMock()
        svc._dataset_repo.get_by_name = AsyncMock(return_value=None)
        svc._corpus_loader = MagicMock()
        svc._corpus_svc = MagicMock()
        svc._dataset_svc = MagicMock()
        svc._dataset_svc.create_dataset = AsyncMock(
            side_effect=ValueError("invalid name")
        )
        svc._license_repo = None
        svc._provenance_manifest = {
            "small/names": {"source": "Test", "license": "MIT"},
        }

        result_obj = BootstrapResult()
        ok = await svc._bootstrap_dataset(item, result_obj)
        assert ok is False
        assert any("invalid name" in e for e in result_obj.errors)


# ═══════════════════════════════════════════════════════════════════
# _assign_provenance
# ═══════════════════════════════════════════════════════════════════


class TestAssignProvenance:
    async def test_sets_all_fields_with_license(self) -> None:
        """_assign_provenance sets source, license_id, attribution, origin."""
        from anvil.services.demo.demo_bootstrap import DemoBootstrapService

        mock_entity = MagicMock()
        mock_entity.id = 1
        mock_lic = MagicMock()
        mock_lic.id = 77
        mock_lic_repo = MagicMock()
        mock_lic_repo.get_by_identifier = AsyncMock(return_value=mock_lic)

        svc = DemoBootstrapService.__new__(DemoBootstrapService)
        svc._session = MagicMock()
        svc._session.flush = AsyncMock()
        svc._corpus_repo = MagicMock()
        svc._dataset_repo = MagicMock()
        svc._corpus_loader = MagicMock()
        svc._corpus_svc = MagicMock()
        svc._dataset_svc = MagicMock()
        svc._provenance_manifest = {}
        svc._license_repo = mock_lic_repo

        prov = {
            "source": "Project Gutenberg",
            "license": "Public Domain",
            "attribution": "E-text prepared by volunteers",
        }
        await svc._assign_provenance(mock_entity, prov)

        assert mock_entity.source_description == "Project Gutenberg"
        assert mock_entity.license_id == 77
        assert mock_entity.attribution_text == "E-text prepared by volunteers"
        assert mock_entity.origin == "bundled"
        mock_lic_repo.get_by_identifier.assert_awaited_once_with("Public Domain")
        svc._session.flush.assert_awaited_once()

    async def test_handles_license_not_in_catalog(self) -> None:
        """_assign_provenance sets license_id to None when catalog lookup misses."""
        from anvil.services.demo.demo_bootstrap import DemoBootstrapService

        mock_entity = MagicMock()
        mock_entity.id = 2
        mock_lic_repo = MagicMock()
        mock_lic_repo.get_by_identifier = AsyncMock(return_value=None)

        svc = DemoBootstrapService.__new__(DemoBootstrapService)
        svc._session = MagicMock()
        svc._session.flush = AsyncMock()
        svc._corpus_repo = MagicMock()
        svc._dataset_repo = MagicMock()
        svc._corpus_loader = MagicMock()
        svc._corpus_svc = MagicMock()
        svc._dataset_svc = MagicMock()
        svc._provenance_manifest = {}
        svc._license_repo = mock_lic_repo

        prov = {"source": "Test", "license": "Unknown-1.0", "attribution": ""}
        await svc._assign_provenance(mock_entity, prov)

        assert mock_entity.license_id is None
        assert mock_entity.origin == "bundled"

    async def test_initialises_license_repo_lazily(self) -> None:
        """_assign_provenance creates LicenseRepository when _license_repo is None."""
        from unittest.mock import patch

        from anvil.services.demo.demo_bootstrap import DemoBootstrapService

        mock_entity = MagicMock()
        mock_lic_repo = MagicMock()
        mock_lic_repo.get_by_identifier = AsyncMock(return_value=None)

        svc = DemoBootstrapService.__new__(DemoBootstrapService)
        svc._session = MagicMock()
        svc._session.flush = AsyncMock()
        svc._corpus_repo = MagicMock()
        svc._dataset_repo = MagicMock()
        svc._corpus_loader = MagicMock()
        svc._corpus_svc = MagicMock()
        svc._dataset_svc = MagicMock()
        svc._provenance_manifest = {}
        svc._license_repo = None  # Not yet initialised.

        with patch(
            "anvil.services.demo.demo_bootstrap.LicenseRepository",
            return_value=mock_lic_repo,
        ) as mock_repo_cls:
            await svc._assign_provenance(mock_entity, {"source": "", "license": "MIT"})

        mock_repo_cls.assert_called_once_with(svc._session)
        assert svc._license_repo is mock_lic_repo
        mock_lic_repo.get_by_identifier.assert_awaited_once_with("MIT")

    async def test_sets_defaults_for_missing_keys(self) -> None:
        """_assign_provenance falls back to empty/None for missing optional keys."""
        from anvil.services.demo.demo_bootstrap import DemoBootstrapService

        mock_entity = MagicMock()
        mock_lic_repo = MagicMock()
        mock_lic_repo.get_by_identifier = AsyncMock(return_value=None)

        svc = DemoBootstrapService.__new__(DemoBootstrapService)
        svc._session = MagicMock()
        svc._session.flush = AsyncMock()
        svc._corpus_repo = MagicMock()
        svc._dataset_repo = MagicMock()
        svc._corpus_loader = MagicMock()
        svc._corpus_svc = MagicMock()
        svc._dataset_svc = MagicMock()
        svc._provenance_manifest = {}
        svc._license_repo = mock_lic_repo

        # Empty prov dict — all keys missing.
        await svc._assign_provenance(mock_entity, {})

        # source defaults to ""
        assert mock_entity.source_description == ""
        # license defaults to "Public Domain"
        mock_lic_repo.get_by_identifier.assert_awaited_once_with("Public Domain")


# ═══════════════════════════════════════════════════════════════════
# bootstrap_all — happy path with real directory structure
# ═══════════════════════════════════════════════════════════════════


class TestBootstrapAllAdvanced:
    async def test_full_happy_path(self, monkeypatch, tmp_path) -> None:
        """bootstrap_all creates corpora and datasets from demo directory."""
        from anvil.services.demo import demo_bootstrap as db_mod

        demo_dir = tmp_path / "demo"
        # Create a full directory structure matching the expected layout.
        (demo_dir / "small" / "names").mkdir(parents=True)
        (demo_dir / "small" / "hello-world").mkdir(parents=True)
        names_txt = demo_dir / "small" / "names.txt"
        names_txt.write_text("Alice\nBob\n")
        hello_txt = demo_dir / "small" / "hello-world.txt"
        hello_txt.write_text("Hello, world!\n")
        monkeypatch.setattr(db_mod, "DEMO_DIR", demo_dir)

        mock_corpus_1 = MagicMock()
        mock_corpus_1.id = 10
        mock_corpus_1.name = "Demo - small/names"
        mock_corpus_2 = MagicMock()
        mock_corpus_2.id = 11
        mock_corpus_2.name = "Demo - small/hello-world"
        mock_dataset_1 = MagicMock()
        mock_dataset_1.id = 20
        mock_dataset_1.name = "Demo - small/names"
        mock_dataset_2 = MagicMock()
        mock_dataset_2.id = 21
        mock_dataset_2.name = "Demo - small/hello-world"

        corpus_create_responses = [mock_corpus_1, mock_corpus_2]
        dataset_create_responses = [mock_dataset_1, mock_dataset_2]

        svc = db_mod.DemoBootstrapService.__new__(db_mod.DemoBootstrapService)
        svc._session = MagicMock()
        svc._corpus_repo = MagicMock()
        svc._corpus_repo.get_by_name = AsyncMock(return_value=None)
        svc._dataset_repo = MagicMock()
        svc._dataset_repo.get_by_name = AsyncMock(return_value=None)
        svc._corpus_loader = MagicMock()
        svc._corpus_svc = MagicMock()
        svc._corpus_svc.create = AsyncMock(side_effect=corpus_create_responses)
        svc._corpus_svc.ingest = AsyncMock(return_value=(mock_corpus_1, []))
        svc._dataset_svc = MagicMock()
        svc._dataset_svc.create_dataset = AsyncMock(
            side_effect=dataset_create_responses
        )
        svc._assign_provenance = AsyncMock()
        svc._license_repo = None
        svc._provenance_manifest = {
            "small/names": {"source": "Test", "license": "MIT"},
            "small/hello-world": {"source": "Test", "license": "MIT"},
        }

        mock_import_svc = MagicMock()
        mock_import_svc.commit_import = AsyncMock()
        with patch.object(db_mod, "DatasetImportService", return_value=mock_import_svc):
            result = await svc.bootstrap_all()

        assert result.corpora_created == 2
        assert result.datasets_created == 2
        assert result.corpora_skipped == 0
        assert result.datasets_skipped == 0
        assert result.errors == []
        assert result.total_time_ms > 0

    async def test_skips_non_txt_files(self, monkeypatch, tmp_path) -> None:
        """bootstrap_all only processes .txt files as datasets, not .py/.md etc."""
        from anvil.services.demo import demo_bootstrap as db_mod

        demo_dir = tmp_path / "demo"
        (demo_dir / "small" / "names").mkdir(parents=True)
        # A .py file should NOT be processed as a dataset.
        script = demo_dir / "small" / "script.py"
        script.write_text("print('hello')")
        # A .txt file SHOULD be processed.
        data_txt = demo_dir / "small" / "names.txt"
        data_txt.write_text("data\n")
        monkeypatch.setattr(db_mod, "DEMO_DIR", demo_dir)

        mock_corpus = MagicMock()
        mock_corpus.id = 1
        mock_corpus.name = "Demo - small/names"
        mock_dataset = MagicMock()
        mock_dataset.id = 2
        mock_dataset.name = "Demo - small/names"

        svc = db_mod.DemoBootstrapService.__new__(db_mod.DemoBootstrapService)
        svc._session = MagicMock()
        svc._corpus_repo = MagicMock()
        svc._corpus_repo.get_by_name = AsyncMock(return_value=None)
        svc._dataset_repo = MagicMock()
        svc._dataset_repo.get_by_name = AsyncMock(return_value=None)
        svc._corpus_loader = MagicMock()
        svc._corpus_svc = MagicMock()
        svc._corpus_svc.create = AsyncMock(return_value=mock_corpus)
        svc._corpus_svc.ingest = AsyncMock(return_value=(mock_corpus, []))
        svc._dataset_svc = MagicMock()
        svc._dataset_svc.create_dataset = AsyncMock(return_value=mock_dataset)
        svc._assign_provenance = AsyncMock()
        svc._license_repo = None
        svc._provenance_manifest = {
            "small/names": {"source": "Test", "license": "MIT"},
        }

        mock_import_svc = MagicMock()
        mock_import_svc.commit_import = AsyncMock()
        with patch.object(db_mod, "DatasetImportService", return_value=mock_import_svc):
            result = await svc.bootstrap_all()

        # 1 corpus (small/names dir), 1 dataset (names.txt), script.py ignored.
        assert result.corpora_created == 1
        assert result.datasets_created == 1
        assert result.errors == []

    async def test_error_collected_when_dir_missing(
        self, monkeypatch, tmp_path
    ) -> None:
        """bootstrap_all collects error when directory structure fails."""
        from anvil.services.demo import demo_bootstrap as db_mod

        demo_dir = tmp_path / "demo"
        monkeypatch.setattr(db_mod, "DEMO_DIR", demo_dir)
        # Create only a size_dir — no nested items to trigger issues.
        # Instead, test that errors in _bootstrap_corpus propagate.
        (demo_dir / "small" / "names").mkdir(parents=True)
        (demo_dir / "small" / "bad-dir").mkdir(parents=True)

        svc = db_mod.DemoBootstrapService.__new__(db_mod.DemoBootstrapService)
        svc._session = MagicMock()
        svc._corpus_repo = MagicMock()
        svc._corpus_repo.get_by_name = AsyncMock(return_value=None)
        svc._dataset_repo = MagicMock()
        svc._corpus_loader = MagicMock()
        svc._corpus_svc = MagicMock()
        svc._corpus_svc.create = AsyncMock(side_effect=RuntimeError("unexpected error"))
        svc._dataset_svc = MagicMock()
        svc._assign_provenance = AsyncMock()
        svc._license_repo = None
        svc._provenance_manifest = {
            "small/names": {"source": "Test", "license": "MIT"},
            "small/bad-dir": {"source": "Test", "license": "MIT"},
        }

        result = await svc.bootstrap_all()

        assert result.corpora_created == 0
        assert result.datasets_created == 0
        assert len(result.errors) == 2
        assert all("unexpected error" in e for e in result.errors)
        assert result.total_time_ms > 0


# ═══════════════════════════════════════════════════════════════════
# __init__, _get_provenance_for ValueError, dataset no-provenance
# ═══════════════════════════════════════════════════════════════════


class TestInitAndEdgeCases:
    async def test_init_with_mock_session(self, monkeypatch) -> None:
        """DemoBootstrapService.__init__ creates repos and loads manifest."""
        from unittest.mock import AsyncMock

        # Bypass real importlib.resources lookups.
        monkeypatch.setattr(
            "importlib.resources.files",
            lambda pkg: MagicMock(
                joinpath=lambda *args: MagicMock(
                    read_text=MagicMock(side_effect=FileNotFoundError)
                )
            ),
        )

        from anvil.services.demo.demo_bootstrap import DemoBootstrapService

        session = AsyncMock()
        svc = DemoBootstrapService(session)
        assert svc._session is session
        assert svc._corpus_repo is not None
        assert svc._dataset_repo is not None
        assert svc._corpus_loader is not None
        assert svc._corpus_svc is not None
        assert svc._dataset_svc is not None
        assert svc._provenance_manifest == {}
        assert svc._license_repo is None

    def test_get_provenance_for_value_error(self) -> None:
        """_get_provenance_for returns None when item is outside DEMO_DIR."""
        from anvil.services.demo.demo_bootstrap import DemoBootstrapService

        svc = DemoBootstrapService.__new__(DemoBootstrapService)
        svc._session = MagicMock()
        svc._corpus_repo = MagicMock()
        svc._dataset_repo = MagicMock()
        svc._corpus_loader = MagicMock()
        svc._corpus_svc = MagicMock()
        svc._dataset_svc = MagicMock()
        svc._provenance_manifest = {}
        svc._license_repo = None

        # An item on a completely different path — not under DEMO_DIR.
        item = Path("/some/other/path/data.txt")
        result = svc._get_provenance_for(item)
        assert result is None

    async def test_bootstrap_dataset_skipped_no_provenance(
        self, monkeypatch, tmp_path
    ) -> None:
        """_bootstrap_dataset skips when provenance manifest has no entry."""
        from anvil.services.demo import demo_bootstrap as db_mod

        demo_dir = tmp_path / "demo"
        item = demo_dir / "small" / "names.txt"
        item.parent.mkdir(parents=True)
        item.write_text("some content")
        monkeypatch.setattr(db_mod, "DEMO_DIR", demo_dir)

        svc = db_mod.DemoBootstrapService.__new__(db_mod.DemoBootstrapService)
        svc._session = MagicMock()
        svc._corpus_repo = MagicMock()
        svc._dataset_repo = MagicMock()
        svc._dataset_repo.get_by_name = AsyncMock(return_value=None)
        svc._corpus_loader = MagicMock()
        svc._corpus_svc = MagicMock()
        svc._dataset_svc = MagicMock()
        svc._license_repo = None
        # Empty manifest — no entry for "small/names".
        svc._provenance_manifest = {}

        result_obj = BootstrapResult()
        ok = await svc._bootstrap_dataset(item, result_obj)
        assert ok is False
        assert len(result_obj.errors) == 1
        assert "no provenance manifest entry" in result_obj.errors[0]
