"""Tests for topology module — PageRank, communities, sinks."""

from __future__ import annotations

from pathlib import Path

from anvil.services.vault.scanner import GraphHealthRunner
from anvil.services.vault.topology import compute_topological


def _run_topology(test_vault_dir: Path):
    runner = GraphHealthRunner(test_vault_dir, test_vault_dir)
    runner.scan_all_notes()
    runner.build_graph()
    return compute_topological(runner.graph, runner.notes)


class TestTopology:
    """Tests for ``compute_topological``."""

    def test_pagerank(self, test_vault_dir: Path) -> None:
        metrics = _run_topology(test_vault_dir)
        assert len(metrics.pagerank_top) > 0
        # PageRank scores should be valid floats
        for stem, score in metrics.pagerank_top:
            assert 0 <= score <= 1

    def test_communities(self, test_vault_dir: Path) -> None:
        metrics = _run_topology(test_vault_dir)
        # With 5 notes, should form at least 1 community
        assert len(metrics.communities) >= 1

    def test_information_sinks(self, test_vault_dir: Path) -> None:
        metrics = _run_topology(test_vault_dir)
        assert isinstance(metrics.information_sink_rate, float)
