# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for DatasetImportService — parsing, preview, and import."""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anvil.services.datasets.dataset_import import DatasetImportService
from anvil.services.datasets.parsed_sample import ParsedSample


def _make_svc():
    """Create a bare DatasetImportService for testing _parse."""
    return DatasetImportService.__new__(DatasetImportService)


class TestParsing:
    """Test the _parse method for each format."""

    def test_parse_txt(self):
        svc = _make_svc()
        text = "hello\nworld\n\nskip blank\n"
        samples, errors = svc._parse(text, "txt")
        assert len(errors) == 0
        assert len(samples) == 3
        assert samples[0].text == "hello"
        assert samples[0].index == 0
        assert samples[1].text == "world"
        assert samples[2].text == "skip blank"

    def test_parse_txt_empty(self):
        svc = _make_svc()
        samples, errors = svc._parse("", "txt")
        assert len(samples) == 0
        assert len(errors) == 0

    def test_parse_csv(self):
        svc = _make_svc()
        text = "first\nsecond\nthird"
        samples, errors = svc._parse(text, "csv")
        assert len(errors) == 0
        assert len(samples) == 3

    def test_parse_jsonl(self):
        svc = _make_svc()
        text = '{"text": "first"}\n{"text": "second"}\n{"text": "third"}'
        samples, errors = svc._parse(text, "jsonl")
        assert len(errors) == 0
        assert len(samples) == 3

    def test_parse_jsonl_with_content_field(self):
        svc = _make_svc()
        text = '{"content": "hello"}'
        samples, errors = svc._parse(text, "jsonl")
        assert len(errors) == 0
        assert len(samples) == 1
        assert samples[0].text == "hello"

    def test_parse_jsonl_malformed(self):
        svc = _make_svc()
        text = '{"valid": true}\nnot json\n{"also valid": 1}'
        samples, errors = svc._parse(text, "jsonl")
        assert len(errors) == 1
        assert len(samples) == 2

    def test_parse_json_array(self):
        svc = _make_svc()
        text = '["item1", "item2", "item3"]'
        samples, errors = svc._parse(text, "json")
        assert len(errors) == 0
        assert len(samples) == 3

    def test_parse_json_object_list(self):
        svc = _make_svc()
        text = '[{"text": "a"}, {"text": "b"}]'
        samples, errors = svc._parse(text, "json")
        assert len(errors) == 0
        assert len(samples) == 2

    def test_parse_json_string(self):
        svc = _make_svc()
        text = '"single text string"'
        samples, errors = svc._parse(text, "json")
        assert len(errors) == 0
        assert len(samples) == 1

    def test_parse_paste(self):
        svc = _make_svc()
        text = "line one\nline two\nline three\n"
        samples, errors = svc._parse(text, "paste")
        assert len(errors) == 0
        assert len(samples) == 3

    def test_parse_unknown_format(self):
        svc = _make_svc()
        samples, errors = svc._parse("hello", "unknown")
        assert len(samples) == 0
        assert len(errors) == 0

    def test_content_hash(self):
        text = "hello world"
        sample = ParsedSample(text, 0)
        expected = hashlib.sha256(text.encode("utf-8")).hexdigest()
        assert sample.content_hash == expected

    def test_length(self):
        sample = ParsedSample("hello", 0)
        assert sample.length == 5


class TestCommitImport:
    """Full import commit flow with in-memory DB."""

    async def test_commit_import_creates_samples(self, in_memory_session, tmp_path):
        """commit_import should persist parsed samples and set dataset
        status.
        """
        from anvil.db.models.dataset import Dataset
        from anvil.db.repositories.curation import SampleRepository
        from anvil.storage.local import LocalFileStore

        store_root = tmp_path / "store"
        store_root.mkdir()
        store = LocalFileStore(str(store_root))
        ds = Dataset(
            name="import-test", filename="import.txt", file_path=str(tmp_path / "i.txt")
        )
        in_memory_session.add(ds)
        await in_memory_session.flush()
        await in_memory_session.refresh(ds)

        svc = DatasetImportService(in_memory_session, ds.id, store=store)

        result = await svc.commit_import("hello\nworld", "txt")
        assert result.rows_imported == 2
        assert result.errors == []

        repo = SampleRepository(in_memory_session)
        total = await repo.count_active(ds.id)
        assert total == 2

    async def test_commit_import_empty(self, in_memory_session, tmp_path):
        """commit_import with no samples should not error."""
        from anvil.db.models.dataset import Dataset

        ds = Dataset(
            name="empty-import", filename="empty.txt", file_path=str(tmp_path / "e.txt")
        )
        in_memory_session.add(ds)
        await in_memory_session.flush()
        await in_memory_session.refresh(ds)

        svc = DatasetImportService(in_memory_session, ds.id)
        result = await svc.commit_import("", "txt")
        assert result.rows_imported == 0

    async def test_preview_import(self, in_memory_session, tmp_path):
        """preview_import should return parsed samples without persisting."""
        from anvil.db.models.dataset import Dataset

        ds = Dataset(
            name="preview-ds", filename="prev.txt", file_path=str(tmp_path / "p.txt")
        )
        in_memory_session.add(ds)
        await in_memory_session.flush()
        await in_memory_session.refresh(ds)

        svc = DatasetImportService(in_memory_session, ds.id)
        samples, _ = await svc.preview_import("hello\nworld", "txt")
        assert len(samples) == 2
        assert samples[0]["text_preview"] == "hello"


###############################################################################
# Extended tests — additional parsing and commit paths
###############################################################################


class TestParsingExtended:
    """Additional _parse edge cases for uncovered formats and errors."""

    def test_parse_corpus(self):
        svc = _make_svc()
        samples, errors = svc._parse("doc one\ndoc two\n\ndoc three\n", "corpus")
        assert len(errors) == 0
        assert len(samples) == 3
        assert samples[0].text == "doc one"
        assert samples[2].text == "doc three"

    def test_parse_csv_empty_first_column(self):
        svc = _make_svc()
        text = "first\n\nsecond\nthird"
        samples, errors = svc._parse(text, "csv")
        assert len(errors) == 0
        assert len(samples) == 3

    def test_parse_jsonl_non_dict_value(self):
        svc = _make_svc()
        text = '"just a string"\n{"text": "real"}'
        samples, errors = svc._parse(text, "jsonl")
        assert len(errors) == 0
        assert len(samples) == 2
        assert samples[0].text == "just a string"

    def test_parse_json_object_with_content_key(self):
        svc = _make_svc()
        text = '[{"content": "hello"}, {"content": "world"}]'
        samples, errors = svc._parse(text, "json")
        assert len(errors) == 0
        assert len(samples) == 2
        assert samples[0].text == "hello"
        assert samples[1].text == "world"

    def test_parse_json_non_dict_item_in_list(self):
        svc = _make_svc()
        text = '["item1", {"text": "item2"}, "item3"]'
        samples, errors = svc._parse(text, "json")
        assert len(errors) == 0
        assert len(samples) == 3
        assert samples[0].text == "item1"
        assert samples[2].text == "item3"

    def test_parse_catch_broad_exception(self):
        svc = _make_svc()
        samples, errors = svc._parse("x", "json")
        assert len(errors) == 1
        assert errors[0]["row"] == -1
        assert "Parse error" in errors[0]["error"]

    def test_parse_paste_empty(self):
        svc = _make_svc()
        samples, errors = svc._parse("", "paste")
        assert len(samples) == 0
        assert len(errors) == 0


class TestPreviewImportExtended:
    """Additional preview_import edge cases."""

    async def test_preview_with_none_text(self, in_memory_session, tmp_path):
        """preview_import with None text returns empty results."""
        from anvil.db.models.dataset import Dataset

        ds = Dataset(
            name="preview-none",
            filename="pn.txt",
            file_path=str(tmp_path / "pn.txt"),
        )
        in_memory_session.add(ds)
        await in_memory_session.flush()
        await in_memory_session.refresh(ds)

        svc = DatasetImportService(in_memory_session, ds.id)
        samples, errors = await svc.preview_import(text=None, fmt="txt")
        assert len(samples) == 0
        assert len(errors) == 0

    async def test_preview_with_errors(self, in_memory_session, tmp_path):
        """preview_import exposes parse errors."""
        from anvil.db.models.dataset import Dataset

        ds = Dataset(
            name="preview-err",
            filename="pe.txt",
            file_path=str(tmp_path / "pe.txt"),
        )
        in_memory_session.add(ds)
        await in_memory_session.flush()
        await in_memory_session.refresh(ds)

        svc = DatasetImportService(in_memory_session, ds.id)
        samples, errors = await svc.preview_import("not json", fmt="json")
        assert len(samples) == 0
        assert len(errors) == 1

    async def test_preview_with_max_rows(self, in_memory_session, tmp_path):
        """preview_import respects max_rows limit."""
        from anvil.db.models.dataset import Dataset

        ds = Dataset(
            name="preview-max",
            filename="pm.txt",
            file_path=str(tmp_path / "pm.txt"),
        )
        in_memory_session.add(ds)
        await in_memory_session.flush()
        await in_memory_session.refresh(ds)

        svc = DatasetImportService(in_memory_session, ds.id)
        text = "\n".join([f"line {i}" for i in range(50)])
        samples, _ = await svc.preview_import(text, fmt="txt", max_rows=5)
        assert len(samples) == 5


class TestCommitImportExtended:
    """Additional commit_import edge cases."""

    async def test_commit_import_unknown_format(self, in_memory_session, tmp_path):
        """Unknown format results in zero rows imported."""
        from anvil.db.models.dataset import Dataset

        ds = Dataset(
            name="unknown-fmt",
            filename="uf.txt",
            file_path=str(tmp_path / "uf.txt"),
        )
        in_memory_session.add(ds)
        await in_memory_session.flush()
        await in_memory_session.refresh(ds)

        svc = DatasetImportService(in_memory_session, ds.id)
        result = await svc.commit_import("hello\nworld", "unknown")
        assert result.rows_imported == 0

    async def test_commit_import_dataset_not_found(self, in_memory_session, tmp_path):
        """commit_import raises ValueError when dataset_id does not exist."""
        svc = DatasetImportService(in_memory_session, 99999)
        with pytest.raises(ValueError, match="not found"):
            await svc.commit_import("hello", "txt")

    async def test_commit_import_csv_format(self, in_memory_session, tmp_path):
        """commit_import works with CSV format."""
        from anvil.db.models.dataset import Dataset
        from anvil.db.repositories.curation import SampleRepository
        from anvil.storage.local import LocalFileStore

        store_root = tmp_path / "store_csv"
        store_root.mkdir()
        store = LocalFileStore(str(store_root))
        ds = Dataset(
            name="csv-test",
            filename="csv.txt",
            file_path=str(tmp_path / "csv.txt"),
        )
        in_memory_session.add(ds)
        await in_memory_session.flush()
        await in_memory_session.refresh(ds)

        svc = DatasetImportService(in_memory_session, ds.id, store=store)
        result = await svc.commit_import("a\nb\nc", "csv")
        assert result.rows_imported == 3

        repo = SampleRepository(in_memory_session)
        assert await repo.count_active(ds.id) == 3


class TestCommitDocsImport:
    """commit_docs_import and commit_corpus_import."""

    async def test_commit_docs_import_empty(self, in_memory_session, tmp_path):
        from anvil.db.models.dataset import Dataset

        ds = Dataset(
            name="docs-empty",
            filename="de.txt",
            file_path=str(tmp_path / "de.txt"),
        )
        in_memory_session.add(ds)
        await in_memory_session.flush()
        await in_memory_session.refresh(ds)

        svc = DatasetImportService(in_memory_session, ds.id)
        result = await svc.commit_docs_import([])
        assert result.rows_imported == 0
        assert result.errors == []

    async def test_commit_docs_import_happy_path(self, in_memory_session, tmp_path):
        from anvil.db.models.dataset import Dataset
        from anvil.db.repositories.curation import SampleRepository
        from anvil.storage.local import LocalFileStore

        store_root = tmp_path / "store_docs"
        store_root.mkdir()
        store = LocalFileStore(str(store_root))
        ds = Dataset(
            name="docs-happy",
            filename="dh.txt",
            file_path=str(tmp_path / "dh.txt"),
        )
        in_memory_session.add(ds)
        await in_memory_session.flush()
        await in_memory_session.refresh(ds)

        svc = DatasetImportService(in_memory_session, ds.id, store=store)
        result = await svc.commit_docs_import(
            ["doc1", "doc2", "doc3"], source_label="test", source_format="docs"
        )
        assert result.rows_imported == 3
        assert result.errors == []
        assert result.import_source_id > 0

        repo = SampleRepository(in_memory_session)
        assert await repo.count_active(ds.id) == 3

    async def test_commit_docs_import_dataset_not_found(
        self, in_memory_session, tmp_path
    ):
        svc = DatasetImportService(in_memory_session, 99999)
        with pytest.raises(ValueError, match="not found"):
            await svc.commit_docs_import(["hello"])

    async def test_commit_corpus_import(self, in_memory_session, tmp_path):
        from anvil.db.models.dataset import Dataset
        from anvil.db.repositories.curation import SampleRepository
        from anvil.storage.local import LocalFileStore

        store_root = tmp_path / "store_corpus"
        store_root.mkdir()
        store = LocalFileStore(str(store_root))
        ds = Dataset(
            name="corpus-test",
            filename="ct.txt",
            file_path=str(tmp_path / "ct.txt"),
        )
        in_memory_session.add(ds)
        await in_memory_session.flush()
        await in_memory_session.refresh(ds)

        svc = DatasetImportService(in_memory_session, ds.id, store=store)
        result = await svc.commit_corpus_import(["chapter 1", "chapter 2", "chapter 3"])
        assert result.rows_imported == 3

        repo = SampleRepository(in_memory_session)
        assert await repo.count_active(ds.id) == 3
