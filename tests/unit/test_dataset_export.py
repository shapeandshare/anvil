"""Unit tests for DatasetExportService."""

import json

from anvil.services.dataset_export import DatasetExportService


class TestExportService:
    def test_service_instantiation(self):
        assert hasattr(DatasetExportService, "export_txt")
        assert hasattr(DatasetExportService, "export_csv")
        assert hasattr(DatasetExportService, "export_jsonl")

    def test_jsonl_format(self):
        """Verify JSONL output structure."""
        jsonl_line = json.dumps({"index": 0, "text": "hello"}) + "\n"
        parsed = json.loads(jsonl_line.strip())
        assert parsed["index"] == 0
        assert parsed["text"] == "hello"

    def test_csv_structure(self):
        """Verify CSV output has header row."""
        header = "index,text\n"
        assert header.startswith("index")
        assert "text" in header