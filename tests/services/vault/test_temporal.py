"""Tests for temporal module — staleness, coherence."""

from __future__ import annotations

from pathlib import Path

from anvil.services.vault.scanner import GraphHealthRunner
from anvil.services.vault.temporal import compute_temporal


def _run_temporal(test_vault_dir: Path):
    runner = GraphHealthRunner(test_vault_dir, test_vault_dir)
    runner.scan_all_notes()
    runner.build_graph()
    return compute_temporal(runner.graph, runner.notes)


class TestTemporal:
    """Tests for ``compute_temporal``."""

    def test_stale_notes(self, test_vault_dir: Path) -> None:
        metrics = _run_temporal(test_vault_dir)
        assert isinstance(metrics.stale_notes, list)

    def test_temporal_coherence(self, test_vault_dir: Path) -> None:
        metrics = _run_temporal(test_vault_dir)
        assert 0 <= metrics.high_coherence_pct <= 100
        assert 0 <= metrics.low_coherence_pct <= 100
