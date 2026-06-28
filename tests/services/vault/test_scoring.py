# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for scoring module — health score computation."""

from __future__ import annotations

from anvil.services.vault.types_connectivity_metrics import ConnectivityMetrics
from anvil.services.vault.types_graph_health_report import GraphHealthReport
from anvil.services.vault.types_health_score import HealthScore
from anvil.services.vault.types_hygiene_metrics import HygieneMetrics
from anvil.services.vault.types_topological_metrics import TopologicalMetrics
from anvil.services.vault.scoring import compute_health_score


class _Builder:
    """Helper to build a GraphHealthReport with given class thresholds."""

    @staticmethod
    def build(
        orphan_rate: float = 0.0,
        dead_end_rate: float = 0.0,
        link_density_avg: float = 4.0,
        largest_component_pct: float = 100.0,
        bidirectional_ratio: float = 50.0,
        sink_rate: float = 0.0,
        tag_pct: float = 100.0,
        fm_pct: float = 100.0,
    ) -> GraphHealthReport:
        report = GraphHealthReport()
        report.connectivity = ConnectivityMetrics(
            orphan_rate=orphan_rate,
            dead_end_rate=dead_end_rate,
            link_density_avg=link_density_avg,
            largest_component_pct=largest_component_pct,
            bidirectional_ratio=bidirectional_ratio,
        )
        report.topological = TopologicalMetrics(information_sink_rate=sink_rate)
        report.hygiene = HygieneMetrics(
            tag_conformity_pct=tag_pct,
            frontmatter_completeness_pct=fm_pct,
        )
        return report


class TestScoring:
    """Tests for ``compute_health_score``."""

    def test_perfect_score(self) -> None:
        report = _Builder.build()
        score = compute_health_score(report)
        assert score.overall == 100.0

    def test_zero_score(self) -> None:
        report = _Builder.build(
            orphan_rate=50.0,
            dead_end_rate=50.0,
            link_density_avg=0.5,
            largest_component_pct=10.0,
            bidirectional_ratio=0.0,
            sink_rate=50.0,
            tag_pct=0.0,
            fm_pct=0.0,
        )
        score = compute_health_score(report)
        assert score.overall == 0.0

    def test_mid_score(self) -> None:
        report = _Builder.build(
            orphan_rate=10.0,
            dead_end_rate=15.0,
            link_density_avg=2.0,
            largest_component_pct=80.0,
            bidirectional_ratio=20.0,
            sink_rate=7.0,
            tag_pct=95.0,
            fm_pct=95.0,
        )
        score = compute_health_score(report)
        assert 0 < score.overall < 100

    def test_breakdown(self) -> None:
        report = _Builder.build()
        score = compute_health_score(report)
        assert len(score.breakdown) == 8
