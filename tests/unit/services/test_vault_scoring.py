# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for vault health score computation (anvil/services/vault/scoring.py)."""

from __future__ import annotations

from anvil.services.vault._types import (
    ConnectivityMetrics,
    GraphHealthReport,
    HygieneMetrics,
    TopologicalMetrics,
)
from anvil.services.vault.scoring import compute_health_score


def _report(
    orphan_rate: float = 0.0,
    dead_end_rate: float = 0.0,
    link_density_avg: float = 4.0,
    largest_component_pct: float = 100.0,
    bidirectional_ratio: float = 50.0,
    sink_rate: float = 0.0,
    tag_conformity_pct: float = 100.0,
    frontmatter_completeness_pct: float = 100.0,
) -> GraphHealthReport:
    """Build a GraphHealthReport with the given metric values."""
    return GraphHealthReport(
        connectivity=ConnectivityMetrics(
            orphan_rate=orphan_rate,
            dead_end_rate=dead_end_rate,
            link_density_avg=link_density_avg,
            largest_component_pct=largest_component_pct,
            bidirectional_ratio=bidirectional_ratio,
        ),
        topological=TopologicalMetrics(
            information_sink_rate=sink_rate,
        ),
        hygiene=HygieneMetrics(
            tag_conformity_pct=tag_conformity_pct,
            frontmatter_completeness_pct=frontmatter_completeness_pct,
        ),
    )


class TestComputeHealthScore:
    """Tests for compute_health_score."""

    def test_perfect_score(self) -> None:
        """All metrics healthy => overall ~100."""
        score = compute_health_score(_report())
        assert score.overall == 100.0
        assert score.orphan_score > 0
        assert score.dead_end_score > 0
        assert score.link_density_score > 0
        assert score.largest_component_score > 0
        assert score.bidirectional_score > 0
        assert score.sink_score > 0
        assert score.tag_conformity_score > 0
        assert score.frontmatter_score > 0

    def test_all_critical(self) -> None:
        """All metrics critical => overall 0."""
        score = compute_health_score(
            _report(
                orphan_rate=50.0,
                dead_end_rate=50.0,
                link_density_avg=0.5,
                largest_component_pct=30.0,
                bidirectional_ratio=5.0,
                sink_rate=50.0,
                tag_conformity_pct=50.0,
                frontmatter_completeness_pct=50.0,
            )
        )
        assert score.overall == 0.0

    def test_mixed_scores(self) -> None:
        score = compute_health_score(
            _report(
                orphan_rate=10.0,
                dead_end_rate=5.0,
                link_density_avg=2.0,
                largest_component_pct=80.0,
                bidirectional_ratio=20.0,
                sink_rate=7.0,
                tag_conformity_pct=95.0,
                frontmatter_completeness_pct=85.0,
            )
        )
        assert 0 < score.overall < 100
        assert score.dead_end_score > 0
        assert score.frontmatter_score == 0.0

    def test_orphan_thresholds(self) -> None:
        healthy = compute_health_score(_report(orphan_rate=4.0))
        warning = compute_health_score(_report(orphan_rate=10.0))
        critical = compute_health_score(_report(orphan_rate=20.0))
        assert healthy.orphan_score > warning.orphan_score
        assert warning.orphan_score > critical.orphan_score
        assert critical.orphan_score == 0.0

    def test_dead_end_thresholds(self) -> None:
        healthy = compute_health_score(_report(dead_end_rate=5.0))
        warning = compute_health_score(_report(dead_end_rate=15.0))
        critical = compute_health_score(_report(dead_end_rate=25.0))
        assert healthy.dead_end_score > warning.dead_end_score
        assert warning.dead_end_score > critical.dead_end_score
        assert critical.dead_end_score == 0.0

    def test_link_density_thresholds(self) -> None:
        optimal = compute_health_score(_report(link_density_avg=4.0))
        suboptimal = compute_health_score(_report(link_density_avg=2.0))
        critical = compute_health_score(_report(link_density_avg=0.5))
        assert optimal.link_density_score > suboptimal.link_density_score
        assert suboptimal.link_density_score > critical.link_density_score
        assert critical.link_density_score == 0.0

    def test_link_density_too_high(self) -> None:
        score = compute_health_score(_report(link_density_avg=15.0))
        assert score.link_density_score == 0.0

    def test_largest_component_thresholds(self) -> None:
        healthy = compute_health_score(_report(largest_component_pct=95.0))
        warning = compute_health_score(_report(largest_component_pct=80.0))
        critical = compute_health_score(_report(largest_component_pct=60.0))
        assert healthy.largest_component_score > warning.largest_component_score
        assert warning.largest_component_score > critical.largest_component_score
        assert critical.largest_component_score == 0.0

    def test_bidirectional_thresholds(self) -> None:
        healthy = compute_health_score(_report(bidirectional_ratio=40.0))
        warning = compute_health_score(_report(bidirectional_ratio=20.0))
        critical = compute_health_score(_report(bidirectional_ratio=10.0))
        assert healthy.bidirectional_score > warning.bidirectional_score
        assert warning.bidirectional_score > critical.bidirectional_score
        assert critical.bidirectional_score == 0.0

    def test_sink_thresholds(self) -> None:
        healthy = compute_health_score(_report(sink_rate=2.0))
        warning = compute_health_score(_report(sink_rate=7.0))
        critical = compute_health_score(_report(sink_rate=15.0))
        assert healthy.sink_score > warning.sink_score
        assert warning.sink_score > critical.sink_score
        assert critical.sink_score == 0.0

    def test_tag_conformity_thresholds(self) -> None:
        healthy = compute_health_score(_report(tag_conformity_pct=100.0))
        warning = compute_health_score(_report(tag_conformity_pct=95.0))
        critical = compute_health_score(_report(tag_conformity_pct=80.0))
        assert healthy.tag_conformity_score > warning.tag_conformity_score
        assert warning.tag_conformity_score > critical.tag_conformity_score
        assert critical.tag_conformity_score == 0.0

    def test_frontmatter_thresholds(self) -> None:
        healthy = compute_health_score(_report(frontmatter_completeness_pct=100.0))
        warning = compute_health_score(_report(frontmatter_completeness_pct=95.0))
        critical = compute_health_score(_report(frontmatter_completeness_pct=80.0))
        assert healthy.frontmatter_score > warning.frontmatter_score
        assert warning.frontmatter_score > critical.frontmatter_score
        assert critical.frontmatter_score == 0.0

    def test_breakdown_keys(self) -> None:
        score = compute_health_score(_report())
        expected_keys = {
            "orphan_rate",
            "dead_end_rate",
            "link_density",
            "largest_component",
            "bidirectional",
            "information_sink",
            "tag_conformity",
            "frontmatter",
        }
        assert set(score.breakdown.keys()) == expected_keys
