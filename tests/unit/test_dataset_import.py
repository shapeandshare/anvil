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
        status."""
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
