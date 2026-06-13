"""Unit tests for DatasetCurationService."""

import json

from microgpt.services.dataset_curation import DatasetCurationService, MetricsResult


class TestMetrics:
    def test_metrics_empty(self):
        result = MetricsResult(
            sample_count=0, total_chars=0, estimated_tokens=0,
            vocabulary_size=0,
            length_distribution={"min": 0, "max": 0, "mean": 0, "median": 0},
            duplicate_count=0,
        )
        assert result.sample_count == 0
        assert result.estimated_tokens == 0

    def test_metrics_with_data(self):
        result = MetricsResult(
            sample_count=100,
            total_chars=50000,
            estimated_tokens=12500,
            vocabulary_size=80,
            length_distribution={"min": 10, "max": 1000, "mean": 500.0, "median": 450},
            duplicate_count=20,
        )
        assert result.sample_count == 100
        assert result.estimated_tokens == 12500
        assert result.duplicate_count == 20
        assert result.length_distribution["mean"] == 500.0

    def test_token_estimation(self):
        """Token estimation is chars/4 heuristic."""
        total_chars = 1000
        estimated = total_chars // 4
        assert estimated == 250


class TestCurationService:
    def test_service_instantiation(self):
        """Verify DatasetCurationService can be instantiated with a session."""
        from microgpt.services.dataset_curation import DatasetCurationService
        assert hasattr(DatasetCurationService, "deduplicate")
        assert hasattr(DatasetCurationService, "filter_by_length")
        assert hasattr(DatasetCurationService, "regex_replace")
        assert hasattr(DatasetCurationService, "delete_sample")
        assert hasattr(DatasetCurationService, "get_metrics")

    def test_serialization_roundtrip(self):
        """Verify curation result can be serialized to JSON."""
        from microgpt.services.dataset_curation import CurationResult
        result = CurationResult(
            operation_id=1,
            samples_removed=10,
            samples_before=100,
            samples_after=90,
        )
        data = {
            "operation_id": result.operation_id,
            "samples_removed": result.samples_removed,
            "samples_before": result.samples_before,
            "samples_after": result.samples_after,
        }
        serialized = json.dumps(data)
        assert json.loads(serialized)["operation_id"] == 1