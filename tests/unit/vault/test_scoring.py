"""Unit tests for anvil/services/vault/scoring.py.

Tests the ``compute_health_score`` function across all grade boundaries,
edge cases, and the overall score calculation.
"""

import pytest

from anvil.services.vault.scoring import compute_health_score
from anvil.services.vault.types_connectivity_metrics import ConnectivityMetrics
from anvil.services.vault.types_graph_health_report import GraphHealthReport
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
    """Build a ``GraphHealthReport`` with the given metric values."""
    return GraphHealthReport(
        connectivity=ConnectivityMetrics(
            orphan_rate=orphan_rate,
            dead_end_rate=dead_end_rate,
            link_density_avg=link_density_avg,
            largest_component_pct=largest_component_pct,
            bidirectional_ratio=bidirectional_ratio,
        ),
        topological=TopologicalMetrics(information_sink_rate=sink_rate),
        hygiene=HygieneMetrics(
            tag_conformity_pct=tag_conformity_pct,
            frontmatter_completeness_pct=frontmatter_pct,
        ),
    )


#############################################################################
# Orphan rate tests
#############################################################################


def test_orphan_rate_healthy() -> None:
    """Orphan rate < 5% yields full weight (0.20)."""
    report = _make_report(orphan_rate=4.9)
    score = compute_health_score(report)
    assert score.orphan_score == 0.20
    assert score.breakdown["orphan_rate"] == 20.0


def test_orphan_rate_warning_lower_bound() -> None:
    """Orphan rate exactly 5.0% yields half weight (0.10)."""
    report = _make_report(orphan_rate=5.0)
    score = compute_health_score(report)
    assert score.orphan_score == 0.10


def test_orphan_rate_warning_upper_bound() -> None:
    """Orphan rate exactly 15.0% yields half weight (0.10)."""
    report = _make_report(orphan_rate=15.0)
    score = compute_health_score(report)
    assert score.orphan_score == 0.10


def test_orphan_rate_critical() -> None:
    """Orphan rate > 15% yields zero weight."""
    report = _make_report(orphan_rate=15.1)
    score = compute_health_score(report)
    assert score.orphan_score == 0.0


def test_orphan_rate_zero() -> None:
    """Orphan rate of 0% yields full weight."""
    report = _make_report(orphan_rate=0.0)
    score = compute_health_score(report)
    assert score.orphan_score == 0.20


#############################################################################
# Dead end rate tests
#############################################################################


def test_dead_end_healthy() -> None:
    """Dead-end rate < 10% yields full weight (0.15)."""
    report = _make_report(dead_end_rate=9.9)
    score = compute_health_score(report)
    assert score.dead_end_score == 0.15


def test_dead_end_warning_lower_bound() -> None:
    """Dead-end rate exactly 10% yields half weight (0.075)."""
    report = _make_report(dead_end_rate=10.0)
    score = compute_health_score(report)
    assert score.dead_end_score == 0.075


def test_dead_end_warning_upper_bound() -> None:
    """Dead-end rate exactly 20% yields half weight (0.075)."""
    report = _make_report(dead_end_rate=20.0)
    score = compute_health_score(report)
    assert score.dead_end_score == 0.075


def test_dead_end_critical() -> None:
    """Dead-end rate > 20% yields zero weight."""
    report = _make_report(dead_end_rate=20.1)
    score = compute_health_score(report)
    assert score.dead_end_score == 0.0


#############################################################################
# Link density tests
#############################################################################


def test_link_density_healthy_mid() -> None:
    """Link density in [3, 8] range yields full weight (0.20)."""
    report = _make_report(link_density_avg=5.0)
    score = compute_health_score(report)
    assert score.link_density_score == 0.20


def test_link_density_healthy_lower_bound() -> None:
    """Link density exactly 3.0 yields full weight."""
    report = _make_report(link_density_avg=3.0)
    score = compute_health_score(report)
    assert score.link_density_score == 0.20


def test_link_density_healthy_upper_bound() -> None:
    """Link density exactly 8.0 yields full weight."""
    report = _make_report(link_density_avg=8.0)
    score = compute_health_score(report)
    assert score.link_density_score == 0.20


def test_link_density_warning_low() -> None:
    """Link density in [1, 3) yields half weight (0.10)."""
    report = _make_report(link_density_avg=2.0)
    score = compute_health_score(report)
    assert score.link_density_score == 0.10


def test_link_density_warning_high() -> None:
    """Link density > 8.0 yields zero weight."""
    report = _make_report(link_density_avg=9.0)
    score = compute_health_score(report)
    assert score.link_density_score == 0.0


def test_link_density_critical_low() -> None:
    """Link density < 1.0 yields zero weight."""
    report = _make_report(link_density_avg=0.5)
    score = compute_health_score(report)
    assert score.link_density_score == 0.0


#############################################################################
# Largest component tests
#############################################################################


def test_largest_component_healthy() -> None:
    """Largest component > 90% yields full weight (0.20)."""
    report = _make_report(largest_component_pct=95.0)
    score = compute_health_score(report)
    assert score.largest_component_score == 0.20


def test_largest_component_warning_upper_bound() -> None:
    """Largest component exactly 90% yields half weight (0.10)."""
    report = _make_report(largest_component_pct=90.0)
    score = compute_health_score(report)
    assert score.largest_component_score == 0.10


def test_largest_component_warning_lower_bound() -> None:
    """Largest component exactly 70% yields half weight (0.10)."""
    report = _make_report(largest_component_pct=70.0)
    score = compute_health_score(report)
    assert score.largest_component_score == 0.10


def test_largest_component_critical() -> None:
    """Largest component < 70% yields zero weight."""
    report = _make_report(largest_component_pct=69.9)
    score = compute_health_score(report)
    assert score.largest_component_score == 0.0


#############################################################################
# Bidirectional ratio tests
#############################################################################


def test_bidirectional_healthy() -> None:
    """Bidirectional ratio >= 30 yields full weight (0.10)."""
    report = _make_report(bidirectional_ratio=30.0)
    score = compute_health_score(report)
    assert score.bidirectional_score == 0.10


def test_bidirectional_warning() -> None:
    """Bidirectional ratio in [15, 30) yields half weight (0.05)."""
    report = _make_report(bidirectional_ratio=20.0)
    score = compute_health_score(report)
    assert score.bidirectional_score == 0.05


def test_bidirectional_warning_lower_bound() -> None:
    """Bidirectional ratio exactly 15 yields half weight (0.05)."""
    report = _make_report(bidirectional_ratio=15.0)
    score = compute_health_score(report)
    assert score.bidirectional_score == 0.05


def test_bidirectional_critical() -> None:
    """Bidirectional ratio < 15 yields zero weight."""
    report = _make_report(bidirectional_ratio=14.9)
    score = compute_health_score(report)
    assert score.bidirectional_score == 0.0


#############################################################################
# Information sink rate tests
#############################################################################


def test_sink_healthy() -> None:
    """Sink rate < 5% yields full weight (0.05)."""
    report = _make_report(sink_rate=4.9)
    score = compute_health_score(report)
    assert score.sink_score == 0.05


def test_sink_warning_lower_bound() -> None:
    """Sink rate exactly 5% yields half weight (0.025)."""
    report = _make_report(sink_rate=5.0)
    score = compute_health_score(report)
    assert score.sink_score == 0.025


def test_sink_warning_upper_bound() -> None:
    """Sink rate exactly 10% yields half weight (0.025)."""
    report = _make_report(sink_rate=10.0)
    score = compute_health_score(report)
    assert score.sink_score == 0.025


def test_sink_critical() -> None:
    """Sink rate > 10% yields zero weight."""
    report = _make_report(sink_rate=10.1)
    score = compute_health_score(report)
    assert score.sink_score == 0.0


#############################################################################
# Tag conformity tests
#############################################################################


def test_tag_conformity_healthy() -> None:
    """100% conformity yields full weight (0.05)."""
    report = _make_report(tag_conformity_pct=100.0)
    score = compute_health_score(report)
    assert score.tag_conformity_score == 0.05


def test_tag_conformity_warning_upper_bound() -> None:
    """Exactly 99.9% conformity yields half weight (0.025)."""
    report = _make_report(tag_conformity_pct=99.9)
    score = compute_health_score(report)
    assert score.tag_conformity_score == 0.025


def test_tag_conformity_warning_lower_bound() -> None:
    """Exactly 90% conformity yields half weight (0.025)."""
    report = _make_report(tag_conformity_pct=90.0)
    score = compute_health_score(report)
    assert score.tag_conformity_score == 0.025


def test_tag_conformity_critical() -> None:
    """Below 90% yields zero weight."""
    report = _make_report(tag_conformity_pct=89.9)
    score = compute_health_score(report)
    assert score.tag_conformity_score == 0.0


#############################################################################
# Frontmatter completeness tests
#############################################################################


def test_frontmatter_healthy() -> None:
    """100% completeness yields full weight (0.05)."""
    report = _make_report(frontmatter_pct=100.0)
    score = compute_health_score(report)
    assert score.frontmatter_score == 0.05


def test_frontmatter_warning_upper_bound() -> None:
    """99.9% completeness yields half weight (0.025)."""
    report = _make_report(frontmatter_pct=99.9)
    score = compute_health_score(report)
    assert score.frontmatter_score == 0.025


def test_frontmatter_warning_lower_bound() -> None:
    """90% completeness yields half weight (0.025)."""
    report = _make_report(frontmatter_pct=90.0)
    score = compute_health_score(report)
    assert score.frontmatter_score == 0.025


def test_frontmatter_critical() -> None:
    """Below 90% yields zero weight."""
    report = _make_report(frontmatter_pct=89.9)
    score = compute_health_score(report)
    assert score.frontmatter_score == 0.0


#############################################################################
# Overall score and breakdown
#############################################################################


def test_overall_perfect_score() -> None:
    """All metrics healthy => overall = 100.0."""
    report = _make_report()
    score = compute_health_score(report)
    assert score.overall == 100.0


def test_overall_worst_score() -> None:
    """All metrics critical => overall = 0.0."""
    report = _make_report(
        orphan_rate=20.0,
        dead_end_rate=30.0,
        link_density_avg=0.0,
        largest_component_pct=50.0,
        bidirectional_ratio=0.0,
        sink_rate=20.0,
        tag_conformity_pct=0.0,
        frontmatter_pct=0.0,
    )
    score = compute_health_score(report)
    assert score.overall == 0.0


def test_overall_half_score() -> None:
    """All metrics at warning thresholds => overall = 100 * 0.5 = 50.0."""
    report = _make_report(
        orphan_rate=10.0,
        dead_end_rate=15.0,
        link_density_avg=2.0,
        largest_component_pct=80.0,
        bidirectional_ratio=20.0,
        sink_rate=7.5,
        tag_conformity_pct=95.0,
        frontmatter_pct=95.0,
    )
    score = compute_health_score(report)
    # 0.5 * sum(weights) = 0.5 * 1.0 = 0.5 => 0.5 * 100 = 50.0
    assert score.overall == 50.0


def test_breakdown_present() -> None:
    """Breakdown dict contains all expected keys."""
    report = _make_report()
    score = compute_health_score(report)
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


def test_breakdown_values_match_scores() -> None:
    """Breakdown values are component_scores * 100 (so 20%*100=20)."""
    report = _make_report(orphan_rate=4.9)
    score = compute_health_score(report)
    assert score.breakdown["orphan_rate"] == score.orphan_score * 100.0
    assert score.breakdown["dead_end_rate"] == score.dead_end_score * 100.0


def test_empty_report() -> None:
    """A default-constructed report (all zeros) should produce a known score."""
    report = GraphHealthReport()
    score = compute_health_score(report)
    assert score.overall == pytest.approx(50.0, rel=1e-3)
