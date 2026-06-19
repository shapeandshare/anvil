"""Health score computation for vault wikilink graph.

Weighted health scoring based on connectivity, topological, and hygiene metrics.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from . import HealthScore, GraphHealthReport


def compute_health_score(report: GraphHealthReport) -> HealthScore:
    """Compute weighted health score from graph health report.

    Follows FR-023 scoring table with threshold boundaries (no interpolation).
    Each component contributes weight * (1.0 for healthy, 0.5 for warning, 0.0 for critical).
    Overall score is sum of all component scores, scaled to 0-100.

    Args:
        report: Fully-populated GraphHealthReport with all metrics.

    Returns:
        HealthScore with overall score and individual component scores.
    """
    from . import HealthScore

    score = HealthScore()

    # Component weights from FR-023
    weights: dict[str, float] = {
        "orphan": 0.20,
        "dead_end": 0.15,
        "link_density": 0.20,
        "largest_component": 0.20,
        "bidirectional": 0.10,
        "sink": 0.05,
        "tag_conformity": 0.05,
        "frontmatter": 0.05,
    }

    # 1. Orphan rate
    orphan_rate = report.connectivity.orphan_rate
    if orphan_rate < 5.0:
        score.orphan_score = weights["orphan"] * 1.0
    elif orphan_rate <= 15.0:
        score.orphan_score = weights["orphan"] * 0.5
    else:
        score.orphan_score = 0.0

    # 2. Dead end rate
    dead_end_rate = report.connectivity.dead_end_rate
    if dead_end_rate < 10.0:
        score.dead_end_score = weights["dead_end"] * 1.0
    elif dead_end_rate <= 20.0:
        score.dead_end_score = weights["dead_end"] * 0.5
    else:
        score.dead_end_score = 0.0

    # 3. Link density
    link_density = report.connectivity.link_density_avg
    if 3.0 <= link_density <= 8.0:
        score.link_density_score = weights["link_density"] * 1.0
    elif 1.0 <= link_density < 3.0:
        score.link_density_score = weights["link_density"] * 0.5
    else:
        score.link_density_score = 0.0

    # 4. Largest component
    largest_component_pct = report.connectivity.largest_component_pct
    if largest_component_pct > 90.0:
        score.largest_component_score = weights["largest_component"] * 1.0
    elif 70.0 <= largest_component_pct <= 90.0:
        score.largest_component_score = weights["largest_component"] * 0.5
    else:
        score.largest_component_score = 0.0

    # 5. Bidirectional ratio
    bidirectional_ratio = report.connectivity.bidirectional_ratio
    if bidirectional_ratio >= 30.0:
        score.bidirectional_score = weights["bidirectional"] * 1.0
    elif bidirectional_ratio >= 15.0:
        score.bidirectional_score = weights["bidirectional"] * 0.5
    else:
        score.bidirectional_score = 0.0

    # 6. Information sink rate
    sink_rate = report.topological.information_sink_rate
    if sink_rate < 5.0:
        score.sink_score = weights["sink"] * 1.0
    elif sink_rate <= 10.0:
        score.sink_score = weights["sink"] * 0.5
    else:
        score.sink_score = 0.0

    # 7. Tag conformity
    tag_conformity_pct = report.hygiene.tag_conformity_pct
    if tag_conformity_pct >= 100.0:
        score.tag_conformity_score = weights["tag_conformity"] * 1.0
    elif 90.0 <= tag_conformity_pct < 100.0:
        score.tag_conformity_score = weights["tag_conformity"] * 0.5
    else:
        score.tag_conformity_score = 0.0

    # 8. Frontmatter completeness
    frontmatter_pct = report.hygiene.frontmatter_completeness_pct
    if frontmatter_pct >= 100.0:
        score.frontmatter_score = weights["frontmatter"] * 1.0
    elif 90.0 <= frontmatter_pct < 100.0:
        score.frontmatter_score = weights["frontmatter"] * 0.5
    else:
        score.frontmatter_score = 0.0

    # Calculate overall score (0-100)
    component_scores = [
        score.orphan_score,
        score.dead_end_score,
        score.link_density_score,
        score.largest_component_score,
        score.bidirectional_score,
        score.sink_score,
        score.tag_conformity_score,
        score.frontmatter_score,
    ]
    score.overall = sum(component_scores) * 100.0

    # Populate breakdown dictionary
    score.breakdown = {
        "orphan_rate": score.orphan_score * 100.0,
        "dead_end_rate": score.dead_end_score * 100.0,
        "link_density": score.link_density_score * 100.0,
        "largest_component": score.largest_component_score * 100.0,
        "bidirectional": score.bidirectional_score * 100.0,
        "information_sink": score.sink_score * 100.0,
        "tag_conformity": score.tag_conformity_score * 100.0,
        "frontmatter": score.frontmatter_score * 100.0,
    }

    return score