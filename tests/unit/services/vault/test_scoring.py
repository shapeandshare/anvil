"""Tests for compute_health_score — weighted health score computation.

Tests all 8 component scoring thresholds and the overall score calculation
for the vault wikilink graph health scoring system.
"""

from __future__ import annotations

import pytest

from anvil.services.vault.scoring import compute_health_score
from anvil.services.vault.types_connectivity_metrics import ConnectivityMetrics
from anvil.services.vault.types_graph_health_report import GraphHealthReport
from anvil.services.vault.types_health_score import HealthScore
from anvil.services.vault.types_hygiene_metrics import HygieneMetrics
from anvil.services.vault.types_topological_metrics import TopologicalMetrics


def _make_report(
    orphan_rate: float = 0.0,
    dead_end_rate: float = 0.0,
    link_density_avg: float = 5.0,
    largest_component_pct: float = 100.0,
    bidirectional_ratio: float = 50.0,
    sink_rate: float = 0.0,
    tag_conformity_pct: float = 100.0,
    frontmatter_pct: float = 100.0,
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
            frontmatter_completeness_pct=frontmatter_pct,
        ),
    )


class TestOrphanScore:
    """Tests for orphan score thresholds."""

    def test_low_orphan_rate_scores_full(self) -> None:
        """Orphan rate < 5% gives full weight (0.20)."""
        report = _make_report(orphan_rate=4.9)
        score = compute_health_score(report)
        assert score.orphan_score == pytest.approx(0.20 * 1.0)

    def test_medium_orphan_rate_scores_half(self) -> None:
        """Orphan rate 5-15% gives half weight (0.10)."""
        report = _make_report(orphan_rate=10.0)
        score = compute_health_score(report)
        assert score.orphan_score == pytest.approx(0.20 * 0.5)

    def test_high_orphan_rate_scores_zero(self) -> None:
        """Orphan rate > 15% gives zero."""
        report = _make_report(orphan_rate=20.0)
        score = compute_health_score(report)
        assert score.orphan_score == 0.0


class TestDeadEndScore:
    """Tests for dead-end score thresholds."""

    def test_low_dead_end_rate_scores_full(self) -> None:
        """Dead-end rate < 10% gives full weight."""
        report = _make_report(dead_end_rate=5.0)
        score = compute_health_score(report)
        assert score.dead_end_score == pytest.approx(0.15 * 1.0)

    def test_medium_dead_end_rate_scores_half(self) -> None:
        """Dead-end rate 10-20% gives half weight."""
        report = _make_report(dead_end_rate=15.0)
        score = compute_health_score(report)
        assert score.dead_end_score == pytest.approx(0.15 * 0.5)

    def test_high_dead_end_rate_scores_zero(self) -> None:
        """Dead-end rate > 20% gives zero."""
        report = _make_report(dead_end_rate=25.0)
        score = compute_health_score(report)
        assert score.dead_end_score == 0.0


class TestLinkDensityScore:
    """Tests for link density score thresholds."""

    def test_healthy_density_scores_full(self) -> None:
        """Link density 3-8 gives full weight."""
        report = _make_report(link_density_avg=5.0)
        score = compute_health_score(report)
        assert score.link_density_score == pytest.approx(0.20 * 1.0)

    def test_moderate_density_scores_half(self) -> None:
        """Link density 1-3 gives half weight."""
        report = _make_report(link_density_avg=2.0)
        score = compute_health_score(report)
        assert score.link_density_score == pytest.approx(0.20 * 0.5)

    def test_low_density_scores_zero(self) -> None:
        """Link density < 1 gives zero."""
        report = _make_report(link_density_avg=0.5)
        score = compute_health_score(report)
        assert score.link_density_score == 0.0

    def test_high_density_scores_zero(self) -> None:
        """Link density > 8 gives zero."""
        report = _make_report(link_density_avg=10.0)
        score = compute_health_score(report)
        assert score.link_density_score == 0.0


class TestLargestComponentScore:
    """Tests for largest component score thresholds."""

    def test_high_coverage_scores_full(self) -> None:
        """Component > 90% gives full weight."""
        report = _make_report(largest_component_pct=95.0)
        score = compute_health_score(report)
        assert score.largest_component_score == pytest.approx(0.20 * 1.0)

    def test_moderate_coverage_scores_half(self) -> None:
        """Component 70-90% gives half weight."""
        report = _make_report(largest_component_pct=80.0)
        score = compute_health_score(report)
        assert score.largest_component_score == pytest.approx(0.20 * 0.5)

    def test_low_coverage_scores_zero(self) -> None:
        """Component < 70% gives zero."""
        report = _make_report(largest_component_pct=50.0)
        score = compute_health_score(report)
        assert score.largest_component_score == 0.0


class TestBidirectionalScore:
    """Tests for bidirectional ratio thresholds."""

    def test_high_ratio_scores_full(self) -> None:
        """Bidirectional >= 30% gives full weight."""
        report = _make_report(bidirectional_ratio=30.0)
        score = compute_health_score(report)
        assert score.bidirectional_score == pytest.approx(0.10 * 1.0)

    def test_medium_ratio_scores_half(self) -> None:
        """Bidirectional 15-30% gives half weight."""
        report = _make_report(bidirectional_ratio=20.0)
        score = compute_health_score(report)
        assert score.bidirectional_score == pytest.approx(0.10 * 0.5)

    def test_low_ratio_scores_zero(self) -> None:
        """Bidirectional < 15% gives zero."""
        report = _make_report(bidirectional_ratio=10.0)
        score = compute_health_score(report)
        assert score.bidirectional_score == 0.0


class TestSinkScore:
    """Tests for information sink rate thresholds."""

    def test_low_sink_rate_scores_full(self) -> None:
        """Sink rate < 5% gives full weight."""
        report = _make_report(sink_rate=2.0)
        score = compute_health_score(report)
        assert score.sink_score == pytest.approx(0.05 * 1.0)

    def test_medium_sink_rate_scores_half(self) -> None:
        """Sink rate 5-10% gives half weight."""
        report = _make_report(sink_rate=7.0)
        score = compute_health_score(report)
        assert score.sink_score == pytest.approx(0.05 * 0.5)

    def test_high_sink_rate_scores_zero(self) -> None:
        """Sink rate > 10% gives zero."""
        report = _make_report(sink_rate=15.0)
        score = compute_health_score(report)
        assert score.sink_score == 0.0


class TestTagConformityScore:
    """Tests for tag conformity thresholds."""

    def test_perfect_conformity_scores_full(self) -> None:
        """100% conformity gives full weight."""
        report = _make_report(tag_conformity_pct=100.0)
        score = compute_health_score(report)
        assert score.tag_conformity_score == pytest.approx(0.05 * 1.0)

    def test_high_conformity_scores_half(self) -> None:
        """90-100% conformity gives half weight."""
        report = _make_report(tag_conformity_pct=95.0)
        score = compute_health_score(report)
        assert score.tag_conformity_score == pytest.approx(0.05 * 0.5)

    def test_low_conformity_scores_zero(self) -> None:
        """< 90% conformity gives zero."""
        report = _make_report(tag_conformity_pct=85.0)
        score = compute_health_score(report)
        assert score.tag_conformity_score == 0.0


class TestFrontmatterScore:
    """Tests for frontmatter completeness thresholds."""

    def test_perfect_frontmatter_scores_full(self) -> None:
        """100% completeness gives full weight."""
        report = _make_report(frontmatter_pct=100.0)
        score = compute_health_score(report)
        assert score.frontmatter_score == pytest.approx(0.05 * 1.0)

    def test_high_frontmatter_scores_half(self) -> None:
        """90-100% completeness gives half weight."""
        report = _make_report(frontmatter_pct=95.0)
        score = compute_health_score(report)
        assert score.frontmatter_score == pytest.approx(0.05 * 0.5)

    def test_low_frontmatter_scores_zero(self) -> None:
        """< 90% completeness gives zero."""
        report = _make_report(frontmatter_pct=80.0)
        score = compute_health_score(report)
        assert score.frontmatter_score == 0.0


class TestOverallScore:
    """Tests for overall composite score calculation."""

    def test_perfect_score_is_100(self) -> None:
        """All metrics at healthy thresholds give a score of 100."""
        report = _make_report()
        score = compute_health_score(report)
        assert score.overall == pytest.approx(100.0)

    def test_worst_score_is_0(self) -> None:
        """All metrics at worst thresholds give a score of 0."""
        report = _make_report(
            orphan_rate=100.0,
            dead_end_rate=100.0,
            link_density_avg=0.0,
            largest_component_pct=0.0,
            bidirectional_ratio=0.0,
            sink_rate=100.0,
            tag_conformity_pct=0.0,
            frontmatter_pct=0.0,
        )
        score = compute_health_score(report)
        assert score.overall == pytest.approx(0.0)

    def test_mixed_scores_produce_intermediate_value(self) -> None:
        """Half-weight on all metrics gives 50."""
        report = _make_report(
            orphan_rate=10.0,
            dead_end_rate=15.0,
            link_density_avg=2.0,
            largest_component_pct=80.0,
            bidirectional_ratio=20.0,
            sink_rate=7.0,
            tag_conformity_pct=95.0,
            frontmatter_pct=95.0,
        )
        score = compute_health_score(report)
        # All 8 components at half weight: 0.5 * 1.0 * 100 = 50
        assert score.overall == pytest.approx(50.0)


class TestBreakdown:
    """Tests for the breakdown dict."""

    def test_breakdown_has_all_components(self) -> None:
        """Breakdown contains all 8 component keys."""
        report = _make_report()
        score = compute_health_score(report)
        assert set(score.breakdown.keys()) == {
            "orphan_rate",
            "dead_end_rate",
            "link_density",
            "largest_component",
            "bidirectional",
            "information_sink",
            "tag_conformity",
            "frontmatter",
        }

    def test_breakdown_values_are_scaled_by_100(self) -> None:
        """Breakdown values are component_score * 100."""
        report = _make_report(orphan_rate=4.9)
        score = compute_health_score(report)
        assert score.breakdown["orphan_rate"] == pytest.approx(20.0)

    def test_breakdown_zero_for_worst_case(self) -> None:
        """Breakdown shows 0 for failing components."""
        report = _make_report(orphan_rate=100.0)
        score = compute_health_score(report)
        assert score.breakdown["orphan_rate"] == 0.0


class TestReturnType:
    """Tests that compute_health_score returns the correct type."""

    def test_returns_health_score(self) -> None:
        """Returns a HealthScore instance."""
        report = _make_report()
        score = compute_health_score(report)
        assert isinstance(score, HealthScore)

    def test_score_has_all_components(self) -> None:
        """HealthScore has all component attributes."""
        report = _make_report()
        score = compute_health_score(report)
        assert hasattr(score, "overall")
        assert hasattr(score, "orphan_score")
        assert hasattr(score, "dead_end_score")
