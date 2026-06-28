# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for report module — Markdown report rendering."""

from __future__ import annotations

from anvil.services.vault.report import render_markdown
from anvil.services.vault.types_connectivity_metrics import ConnectivityMetrics
from anvil.services.vault.types_graph_health_report import GraphHealthReport
from anvil.services.vault.types_health_score import HealthScore
from anvil.services.vault.types_hygiene_metrics import HygieneMetrics
from anvil.services.vault.types_topological_metrics import TopologicalMetrics


class TestRenderMarkdown:
    """Tests for ``render_markdown``."""

    def test_empty_report(self) -> None:
        report = GraphHealthReport()
        md = render_markdown(report, {})
        assert "# Vault Graph Health Report" in md
        assert "Generated:" in md

    def test_connectiveity_section(self) -> None:
        report = GraphHealthReport()
        report.connectivity = ConnectivityMetrics(
            orphan_rate=10.0,
            orphan_count=3,
            orphans=["NoteA", "NoteB", "NoteC"],
            dead_end_rate=5.0,
            dead_end_count=2,
            dead_ends=["NoteD", "NoteE"],
            link_density_avg=2.5,
            link_density_class="warning",
            largest_component_pct=85.0,
            largest_component_class="warning",
            bidirectional_ratio=40.0,
            bidirectional_class="healthy",
        )
        report.health_score = HealthScore(overall=72.5)
        md = render_markdown(report, {})
        assert "Connectivity" in md
        assert "Health Score" in md

    def test_action_items_for_unhealthy(self) -> None:
        report = GraphHealthReport()
        report.connectivity = ConnectivityMetrics(orphans=["NoteA"], orphan_count=1)
        report.hygiene = HygieneMetrics(
            non_conformant_tags=[("NoteA", "bad/tag")],
            phantom_links=[("NoteA", "Ghost")],
        )
        report.health_score = HealthScore(overall=50.0)
        md = render_markdown(report, {})
        assert "Action Items" in md
