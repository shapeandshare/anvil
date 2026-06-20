"""Tests for structural module — chain gaps, silos, broken cycles."""

from __future__ import annotations

from pathlib import Path

from anvil.services.vault.scanner import GraphHealthRunner
from anvil.services.vault.structural import compute_structural


def _run_structural(test_vault_dir: Path):
    runner = GraphHealthRunner(test_vault_dir, test_vault_dir)
    runner.scan_all_notes()
    runner.build_graph()
    from anvil.services.vault.topology import compute_topological

    topo = compute_topological(runner.graph, runner.notes)
    return compute_structural(runner.graph, runner.notes, topo)


class TestStructural:
    """Tests for ``compute_structural``."""

    def test_chain_gaps(self, test_vault_dir: Path) -> None:
        metrics = _run_structural(test_vault_dir)
        assert isinstance(metrics.chain_gaps, list)

    def test_potential_silos(self, test_vault_dir: Path) -> None:
        metrics = _run_structural(test_vault_dir)
        assert isinstance(metrics.potential_silos, list)

    def test_broken_cycles(self, test_vault_dir: Path) -> None:
        metrics = _run_structural(test_vault_dir)
        assert isinstance(metrics.broken_cycles, list)
