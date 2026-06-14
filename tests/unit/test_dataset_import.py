"""Unit tests for DatasetImportService."""

import hashlib

import pytest

from anvil.services.dataset_import import DatasetImportService, ParsedSample


class TestParsing:
    """Test the _parse method for each format."""

    def _make_service(self):
        return DatasetImportService.__new__(DatasetImportService)

    def test_parse_txt(self):
        svc = self._make_service()
        text = "hello\nworld\n\nskip blank\n"
        samples, errors = svc._parse(text, "txt")
        assert len(errors) == 0
        assert len(samples) == 3
        assert samples[0].text == "hello"
        assert samples[0].index == 0
        assert samples[1].text == "world"
        assert samples[1].index == 1
        assert samples[2].text == "skip blank"

    def test_parse_txt_empty(self):
        svc = self._make_service()
        samples, errors = svc._parse("", "txt")
        assert len(samples) == 0
        assert len(errors) == 0

    def test_parse_csv(self):
        svc = self._make_service()
        text = "first\nsecond\nthird"
        samples, errors = svc._parse(text, "csv")
        assert len(errors) == 0
        assert len(samples) == 3

    def test_parse_jsonl(self):
        svc = self._make_service()
        text = '{"text": "first"}\n{"text": "second"}\n{"text": "third"}'
        samples, errors = svc._parse(text, "jsonl")
        assert len(errors) == 0
        assert len(samples) == 3
        assert samples[0].text == "first"

    def test_parse_jsonl_with_content_field(self):
        svc = self._make_service()
        text = '{"content": "hello"}'
        samples, errors = svc._parse(text, "jsonl")
        assert len(errors) == 0
        assert len(samples) == 1
        assert samples[0].text == "hello"

    def test_parse_jsonl_malformed(self):
        svc = self._make_service()
        text = '{"valid": true}\nnot json\n{"also valid": 1}'
        samples, errors = svc._parse(text, "jsonl")
        assert len(errors) == 1
        assert len(samples) == 2

    def test_parse_json_array(self):
        svc = self._make_service()
        text = '["item1", "item2", "item3"]'
        samples, errors = svc._parse(text, "json")
        assert len(errors) == 0
        assert len(samples) == 3

    def test_parse_json_object_list(self):
        svc = self._make_service()
        text = '[{"text": "a"}, {"text": "b"}]'
        samples, errors = svc._parse(text, "json")
        assert len(errors) == 0
        assert len(samples) == 2

    def test_parse_json_string(self):
        svc = self._make_service()
        text = '"single text string"'
        samples, errors = svc._parse(text, "json")
        assert len(errors) == 0
        assert len(samples) == 1

    def test_parse_paste(self):
        svc = self._make_service()
        text = "line one\nline two\nline three\n"
        samples, errors = svc._parse(text, "paste")
        assert len(errors) == 0
        assert len(samples) == 3

    def test_content_hash(self):
        svc = self._make_service()
        text = "hello world"
        sample = ParsedSample(text, 0)
        expected = hashlib.sha256(text.encode("utf-8")).hexdigest()
        assert sample.content_hash == expected

    def test_length(self):
        svc = self._make_service()
        sample = ParsedSample("hello", 0)
        assert sample.length == 5


class TestPreviewImport:
    def test_preview_returns_preview(self):
        from anvil.db.repositories.curation import SampleRepository
        from anvil.db.repositories.datasets import DatasetRepository

        svc = DatasetImportService.__new__(DatasetImportService)
        assert hasattr(svc, "preview_import")

    def test_preview_respects_max_rows(self):
        svc = DatasetImportService.__new__(DatasetImportService)
        text = "\n".join(f"line {i}" for i in range(50))
        samples, errors = svc._parse(text, "txt")
        preview = [
            {"index": s.index, "text_preview": s.text[:200], "length": s.length}
            for s in samples[:20]
        ]
        assert len(preview) == 20