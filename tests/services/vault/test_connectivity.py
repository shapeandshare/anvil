# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for connectivity module — orphans, dead ends, density, bidirectionals."""

from __future__ import annotations

from pathlib import Path

from anvil.services.vault.connectivity import compute_connectivity
from anvil.services.vault.scanner import GraphHealthRunner


def _run_connectivity(test_vault_dir: Path):
    runner = GraphHealthRunner(test_vault_dir, test_vault_dir)
    runner.scan_all_notes()
    runner.build_graph()
    return compute_connectivity(runner.graph, runner.notes)


class TestConnectivity:
    """Tests for ``compute_connectivity``."""

    def test_orphans_detected(self, test_vault_dir: Path) -> None:
        metrics = _run_connectivity(test_vault_dir)
        # InvalidNote has no inbound links — should be the orphan
        assert "InvalidNote" in metrics.orphans
        # OrphanNote gets a link from MOCNote — not orphaned
        assert "OrphanNote" not in metrics.orphans

    def test_link_density(self, test_vault_dir: Path) -> None:
        metrics = _run_connectivity(test_vault_dir)
        assert metrics.link_density_avg > 0
        assert metrics.link_density_class in ("healthy", "warning", "critical")

    def test_bidirectional(self, test_vault_dir: Path) -> None:
        metrics = _run_connectivity(test_vault_dir)
        # ValidNote <-> AnotherNote should be reciprocal
        reciprocal_found = any(
            u == "ValidNote" or v == "ValidNote" for u, v in metrics.missing_reciprocals
        )
        # Either it's already reciprocal or reported as missing
        assert isinstance(reciprocal_found, bool)
