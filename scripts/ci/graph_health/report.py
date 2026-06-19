"""Markdown report renderer for vault graph health analysis."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from . import (
        GraphHealthReport,
        NoteMetadata,
        HealthScore,
        ConnectivityMetrics,
        TopologicalMetrics,
        TemporalMetrics,
        HygieneMetrics,
        StructuralMetrics,
        LinkPredictionResult,
    )


def render_markdown(
    report: GraphHealthReport, notes: dict[str, NoteMetadata]
) -> str:
    """Render a GraphHealthReport as a Markdown string.

    Args:
        report: Fully-populated GraphHealthReport with all metrics computed.
        notes: Dict mapping stem -> NoteMetadata for resolving note titles/paths.

    Returns:
        Markdown string with the full health report.
    """
    lines: list[str] = []

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines.append("# Vault Graph Health Report")
    lines.append(f"*Generated: {timestamp}*")
    lines.append("")

    lines.append(_render_health_score(report.health_score))
    lines.append("")

    lines.append(_render_connectivity(report.connectivity, notes))
    lines.append("")

    lines.append(_render_topological(report.topological, notes))
    lines.append("")

    lines.append(_render_temporal(report.temporal, notes))
    lines.append("")

    lines.append(_render_hygiene(report.hygiene, notes))
    lines.append("")

    lines.append(_render_structural(report.structural, notes))
    lines.append("")

    if report.link_prediction and report.link_prediction.scored_pairs:
        lines.append(_render_link_prediction(report.link_prediction))
        lines.append("")

    lines.append(_render_action_items(report, notes))

    return "\n".join(lines)


def _render_health_score(score: HealthScore) -> str:
    """Render overall health score section.

    Args:
        score: HealthScore to render.

    Returns:
        Markdown string for the health score section.
    """
    lines: list[str] = ["## Overall Health Score"]

    if score.overall >= 70:
        indicator = "🟢"
        status = "healthy"
    elif score.overall >= 40:
        indicator = "🟡"
        status = "warning"
    else:
        indicator = "🔴"
        status = "critical"

    lines.append(f"{indicator} **{score.overall:.1f}/100** — {status}")
    lines.append("")
    lines.append("| Metric | Score | Contribution |")
    lines.append("|--------|-------|--------------|")

    for metric, val in sorted(score.breakdown.items()):
        contribution = val / 100.0
        lines.append(
            f"| {metric.replace('_', ' ').title()} | {val:.1f} | {contribution:.3f} |"
        )

    lines.append("")
    lines.append(f"*Weighted sum: {score.overall:.1f}*")

    return "\n".join(lines)


def _render_connectivity(
    metrics: ConnectivityMetrics, notes: dict[str, NoteMetadata]
) -> str:
    """Render connectivity metrics section.

    Args:
        metrics: ConnectivityMetrics to render.
        notes: Dict mapping stem -> NoteMetadata.

    Returns:
        Markdown string for the connectivity section.
    """
    lines: list[str] = ["## Connectivity Metrics"]

    def _classify(
        value: float, thresholds: tuple[float, float] = (70.0, 40.0)
    ) -> str:
        if value >= thresholds[0]:
            return "healthy"
        elif value >= thresholds[1]:
            return "warning"
        else:
            return "critical"

    # Orphan rate
    orphan_class = _classify(100 - metrics.orphan_rate)
    orphan_emoji = "🟢" if orphan_class == "healthy" else "🟡" if orphan_class == "warning" else "🔴"
    lines.append(
        f"{orphan_emoji} **Orphan rate**: {metrics.orphan_rate:.1f}% "
        f"({metrics.orphan_count} notes) — {orphan_class}"
    )
    if metrics.orphans:
        orphans_str = ", ".join(
            f"[[{stem}]]" for stem in metrics.orphans[:10]
        )
        lines.append(f"  - Orphans: {orphans_str}")
        if len(metrics.orphans) > 10:
            lines.append(f"  - ... and {len(metrics.orphans) - 10} more")

    # Dead end rate
    dead_end_class = _classify(100 - metrics.dead_end_rate)
    dead_end_emoji = "🟢" if dead_end_class == "healthy" else "🟡" if dead_end_class == "warning" else "🔴"
    lines.append(
        f"{dead_end_emoji} **Dead end rate**: {metrics.dead_end_rate:.1f}% "
        f"({metrics.dead_end_count} notes) — {dead_end_class}"
    )
    if metrics.dead_ends:
        dead_ends_str = ", ".join(
            f"[[{stem}]]" for stem in metrics.dead_ends[:10]
        )
        lines.append(f"  - Dead ends: {dead_ends_str}")
        if len(metrics.dead_ends) > 10:
            lines.append(f"  - ... and {len(metrics.dead_ends) - 10} more")

    # Link density
    density_class = metrics.link_density_class
    density_emoji = "🟢" if density_class == "healthy" else "🟡" if density_class == "warning" else "🔴"
    lines.append(
        f"{density_emoji} **Link density**: {metrics.link_density_avg:.2f} "
        f"avg links per note — {density_class}"
    )

    # Largest component
    component_class = _classify(metrics.largest_component_pct)
    component_emoji = "🟢" if component_class == "healthy" else "🟡" if component_class == "warning" else "🔴"
    lines.append(
        f"{component_emoji} **Largest component**: "
        f"{metrics.largest_component_pct:.1f}% of notes — {component_class}"
    )

    # Bidirectional ratio
    bidirectional_class = metrics.bidirectional_class
    bidirectional_emoji = "🟢" if bidirectional_class == "healthy" else "🟡" if bidirectional_class == "warning" else "🔴"
    lines.append(
        f"{bidirectional_emoji} **Bidirectional ratio**: "
        f"{metrics.bidirectional_ratio:.1f}% — {bidirectional_class}"
    )

    if metrics.missing_reciprocals:
        lines.append("**Missing reciprocals**:")
        for source, target in metrics.missing_reciprocals[:10]:
            lines.append(f"  - [[{source}]] → [[{target}]] (no backlink)")
        if len(metrics.missing_reciprocals) > 10:
            lines.append(
                f"  - ... and {len(metrics.missing_reciprocals) - 10} more"
            )

    return "\n".join(lines)


def _render_topological(
    metrics: TopologicalMetrics, notes: dict[str, NoteMetadata]
) -> str:
    """Render topological health section.

    Args:
        metrics: TopologicalMetrics to render.
        notes: Dict mapping stem -> NoteMetadata.

    Returns:
        Markdown string for the topological section.
    """
    lines: list[str] = ["## Topological Health"]

    if metrics.pagerank_top:
        lines.append("**Authority notes** (PageRank top 5%):")
        for stem, score in metrics.pagerank_top[:10]:
            lines.append(f"  - [[{stem}]] ({score:.4f})")
        if len(metrics.pagerank_top) > 10:
            lines.append(
                f"  - ... and {len(metrics.pagerank_top) - 10} more"
            )

    if metrics.betweenness_bridges:
        lines.append("**Bridge notes** (high betweenness centrality):")
        for stem, score in metrics.betweenness_bridges[:10]:
            lines.append(f"  - [[{stem}]] ({score:.4f})")
        if len(metrics.betweenness_bridges) > 10:
            lines.append(
                f"  - ... and {len(metrics.betweenness_bridges) - 10} more"
            )

    lines.append(
        f"**Communities**: {len(metrics.communities)} communities found"
    )

    if metrics.communities_needing_moc:
        lines.append(
            f"**Communities needing MOC**: "
            f"{len(metrics.communities_needing_moc)} communities with >=5 "
            f"notes and no MOC"
        )
        for i, community in enumerate(
            metrics.communities_needing_moc[:5], 1
        ):
            comm_str = ", ".join(
                f"[[{stem}]]" for stem in community[:5]
            )
            lines.append(
                f"  {i}. {len(community)} notes: {comm_str}"
            )
            if len(community) > 5:
                lines.append(f"     ... and {len(community) - 5} more")

    # Information sinks
    sink_class = metrics.information_sink_class
    sink_emoji = "🟢" if sink_class == "healthy" else "🟡" if sink_class == "warning" else "🔴"
    lines.append(
        f"{sink_emoji} **Information sink rate**: "
        f"{metrics.information_sink_rate:.1f}% — {sink_class}"
    )

    if metrics.information_sinks:
        lines.append("**Information sinks**:")
        for stem in metrics.information_sinks[:10]:
            lines.append(f"  - [[{stem}]]")
        if len(metrics.information_sinks) > 10:
            lines.append(
                f"  - ... and {len(metrics.information_sinks) - 10} more"
            )

    return "\n".join(lines)


def _render_temporal(
    metrics: TemporalMetrics, notes: dict[str, NoteMetadata]
) -> str:
    """Render temporal decay section.

    Args:
        metrics: TemporalMetrics to render.
        notes: Dict mapping stem -> NoteMetadata.

    Returns:
        Markdown string for the temporal section.
    """
    lines: list[str] = ["## Temporal Decay"]

    if metrics.stale_notes:
        lines.append(
            f"**Stale notes**: {len(metrics.stale_notes)} notes"
        )
        stale_str = ", ".join(
            f"[[{stem}]]" for stem in metrics.stale_notes[:10]
        )
        lines.append(f"  - {stale_str}")
        if len(metrics.stale_notes) > 10:
            lines.append(
                f"  - ... and {len(metrics.stale_notes) - 10} more"
            )

    if metrics.dead_weight:
        lines.append(
            f"**Dead weight**: {len(metrics.dead_weight)} notes "
            f"(stale + orphaned)"
        )
        dead_str = ", ".join(
            f"[[{stem}]]" for stem in metrics.dead_weight[:10]
        )
        lines.append(f"  - {dead_str}")
        if len(metrics.dead_weight) > 10:
            lines.append(
                f"  - ... and {len(metrics.dead_weight) - 10} more"
            )

    lines.append("**Temporal coherence**:")
    lines.append(
        f"  - High coherence (<=90 days): "
        f"{metrics.high_coherence_pct:.1f}% of links"
    )
    lines.append(
        f"  - Low coherence (>365 days): "
        f"{metrics.low_coherence_pct:.1f}% of links"
    )

    if metrics.temporally_distant_pairs:
        lines.append(
            "**Temporally distant pairs** (>365 days):"
        )
        for a, b, delta in metrics.temporally_distant_pairs[:10]:
            lines.append(f"  - [[{a}]] ↔ [[{b}]] ({delta} days)")
        if len(metrics.temporally_distant_pairs) > 10:
            lines.append(
                f"  - ... and "
                f"{len(metrics.temporally_distant_pairs) - 10} more"
            )

    return "\n".join(lines)


def _render_hygiene(
    metrics: HygieneMetrics, notes: dict[str, NoteMetadata]
) -> str:
    """Render semantic hygiene section.

    Args:
        metrics: HygieneMetrics to render.
        notes: Dict mapping stem -> NoteMetadata.

    Returns:
        Markdown string for the hygiene section.
    """
    lines: list[str] = ["## Semantic Hygiene"]

    # Tag conformity
    tag_class = metrics.tag_conformity_class
    tag_emoji = "🟢" if tag_class == "healthy" else "🟡" if tag_class == "warning" else "🔴"
    lines.append(
        f"{tag_emoji} **Tag conformity**: "
        f"{metrics.tag_conformity_pct:.1f}% — {tag_class}"
    )

    if metrics.non_conformant_tags:
        lines.append(
            f"**Non-conformant tags**: "
            f"{len(metrics.non_conformant_tags)} issues"
        )
        for note, tag in metrics.non_conformant_tags[:10]:
            lines.append(f"  - [[{note}]]: `{tag}`")
        if len(metrics.non_conformant_tags) > 10:
            lines.append(
                f"  - ... and {len(metrics.non_conformant_tags) - 10} more"
            )

    if metrics.near_duplicate_tags:
        lines.append(
            f"**Near-duplicate tags**: "
            f"{len(metrics.near_duplicate_tags)} pairs"
        )
        for tag_a, tag_b in metrics.near_duplicate_tags[:10]:
            lines.append(f"  - `{tag_a}` ≈ `{tag_b}`")
        if len(metrics.near_duplicate_tags) > 10:
            lines.append(
                f"  - ... and {len(metrics.near_duplicate_tags) - 10} more"
            )

    if metrics.single_use_tags:
        lines.append(
            f"**Single-use tags**: {len(metrics.single_use_tags)} tags"
        )
        single_str = ", ".join(
            f"`{tag}`" for tag in metrics.single_use_tags[:10]
        )
        lines.append(f"  - {single_str}")
        if len(metrics.single_use_tags) > 10:
            lines.append(
                f"  - ... and {len(metrics.single_use_tags) - 10} more"
            )

    if metrics.unused_tags:
        lines.append(
            f"**Unused tags**: {len(metrics.unused_tags)} tags"
        )
        unused_str = ", ".join(
            f"`{tag}`" for tag in metrics.unused_tags[:10]
        )
        lines.append(f"  - {unused_str}")
        if len(metrics.unused_tags) > 10:
            lines.append(
                f"  - ... and {len(metrics.unused_tags) - 10} more"
            )

    # Frontmatter completeness
    fm_class = metrics.frontmatter_completeness_class
    fm_emoji = "🟢" if fm_class == "healthy" else "🟡" if fm_class == "warning" else "🔴"
    lines.append(
        f"{fm_emoji} **Frontmatter completeness**: "
        f"{metrics.frontmatter_completeness_pct:.1f}% — {fm_class}"
    )

    if metrics.missing_fields:
        lines.append(
            f"**Missing fields**: {len(metrics.missing_fields)} issues"
        )
        for note, field in metrics.missing_fields[:10]:
            lines.append(f"  - [[{note}]]: missing `{field}`")
        if len(metrics.missing_fields) > 10:
            lines.append(
                f"  - ... and {len(metrics.missing_fields) - 10} more"
            )

    if metrics.type_mismatches:
        lines.append(
            f"**Type mismatches**: {len(metrics.type_mismatches)} issues"
        )
        for note, field, expected in metrics.type_mismatches[:10]:
            lines.append(
                f"  - [[{note}]]: `{field}` should be {expected}"
            )
        if len(metrics.type_mismatches) > 10:
            lines.append(
                f"  - ... and {len(metrics.type_mismatches) - 10} more"
            )

    if metrics.inconsistent_dates:
        lines.append(
            f"**Inconsistent dates**: "
            f"{len(metrics.inconsistent_dates)} issues"
        )
        for note, desc in metrics.inconsistent_dates[:10]:
            lines.append(f"  - [[{note}]]: {desc}")
        if len(metrics.inconsistent_dates) > 10:
            lines.append(
                f"  - ... and {len(metrics.inconsistent_dates) - 10} more"
            )

    if metrics.phantom_links:
        lines.append(
            f"**Phantom links**: "
            f"{len(metrics.phantom_links)} broken wikilinks"
        )
        for source, target in metrics.phantom_links[:10]:
            lines.append(
                f"  - [[{source}]] → [[{target}]] (target missing)"
            )
        if len(metrics.phantom_links) > 10:
            lines.append(
                f"  - ... and {len(metrics.phantom_links) - 10} more"
            )

    if metrics.over_linking:
        lines.append(
            f"**Over-linking**: {len(metrics.over_linking)} issues"
        )
        for note, section, target in metrics.over_linking[:10]:
            lines.append(
                f"  - [[{note}]]: {section} → [[{target}]] (excessive)"
            )
        if len(metrics.over_linking) > 10:
            lines.append(
                f"  - ... and {len(metrics.over_linking) - 10} more"
            )

    return "\n".join(lines)


def _render_structural(
    metrics: StructuralMetrics, notes: dict[str, NoteMetadata]
) -> str:
    """Render structural gaps section.

    Args:
        metrics: StructuralMetrics to render.
        notes: Dict mapping stem -> NoteMetadata.

    Returns:
        Markdown string for the structural section.
    """
    lines: list[str] = ["## Structural Gaps"]

    if metrics.chain_gaps:
        lines.append(
            f"**Chain gaps**: {len(metrics.chain_gaps)} "
            f"missing intermediate notes"
        )
        for a, c, b in metrics.chain_gaps[:10]:
            lines.append(f"  - [[{a}]] ↔ [[{c}]] (missing [[{b}]])")
        if len(metrics.chain_gaps) > 10:
            lines.append(
                f"  - ... and {len(metrics.chain_gaps) - 10} more"
            )

    if metrics.potential_silos:
        lines.append(
            f"**Potential silos**: "
            f"{len(metrics.potential_silos)} low-density connections"
        )
        for cluster_a, cluster_b, density in metrics.potential_silos[:10]:
            lines.append(
                f"  - Cluster {cluster_a} ↔ Cluster {cluster_b} "
                f"(density: {density:.3f})"
            )
        if len(metrics.potential_silos) > 10:
            lines.append(
                f"  - ... and {len(metrics.potential_silos) - 10} more"
            )

    if metrics.broken_cycles:
        lines.append(
            f"**Broken cycles**: "
            f"{len(metrics.broken_cycles)} incomplete cycles"
        )
        for i, cycle in enumerate(metrics.broken_cycles[:5], 1):
            if len(cycle) <= 5:
                cycle_str = " → ".join(
                    f"[[{stem}]]" for stem in cycle
                )
                lines.append(f"  {i}. {cycle_str}")
            else:
                cycle_str = (
                    " → ".join(f"[[{stem}]]" for stem in cycle[:3])
                    + f" → ... → [[{cycle[-1]}]]"
                )
                lines.append(
                    f"  {i}. {cycle_str} ({len(cycle)} notes)"
                )

    return "\n".join(lines)


def _render_link_prediction(lp_result: LinkPredictionResult) -> str:
    """Render link prediction section.

    Args:
        lp_result: LinkPredictionResult to render.

    Returns:
        Markdown string for the link prediction section.
    """
    lines: list[str] = ["## Link Prediction"]
    top = lp_result.scored_pairs[: lp_result.top_n]
    lines.append(
        f"Top {len(top)} candidates most likely to need reciprocation"
        f" (ensemble score >= {lp_result.threshold:.1f} threshold "
        f"for auto-fix):"
    )
    lines.append("")
    lines.append(
        "| Rank | Score | Source | Target | Adamic-Adar | "
        "TF-IDF | Community |"
    )
    lines.append(
        "|------|-------|--------|--------|-------------|"
        "--------|-----------|"
    )
    for i, pair in enumerate(top, 1):
        comm = "same" if pair.community_match >= 0.5 else "diff"
        lines.append(
            f"| {i} | {pair.ensemble_score:.2f} "
            f"| {pair.source} | {pair.target} "
            f"| {pair.adamic_adar:.2f} "
            f"| {pair.tfidf_cosine:.2f} | {comm} |"
        )
    if lp_result.took_action:
        n = sum(
            1
            for p in lp_result.scored_pairs
            if p.ensemble_score >= lp_result.threshold
        )
        lines.append("")
        lines.append(
            f"*Applied reciprocals for {n} candidates "
            f"(threshold: {lp_result.threshold}).*"
        )
    return "\n".join(lines)


def _render_action_items(
    report: GraphHealthReport, notes: dict[str, NoteMetadata]
) -> str:
    """Render prioritized action items section.

    Prioritized list of issues to address from highest to lowest priority.

    Args:
        report: Fully-populated GraphHealthReport.
        notes: Dict mapping stem -> NoteMetadata.

    Returns:
        Markdown string for the action items section.
    """
    lines: list[str] = ["## Action Items"]
    lines.append("Prioritized list of issues to address:")
    lines.append("")

    action_items: list[tuple[int, str]] = []

    # 1. Orphans
    for stem in report.connectivity.orphans:
        action_items.append(
            (1, f"Fix orphan note: [[{stem}]] — add inbound links")
        )

    # 2. Dead ends
    for stem in report.connectivity.dead_ends:
        action_items.append(
            (2, f"Fix dead end: [[{stem}]] — add outbound links")
        )

    # 3. Information sinks
    for stem in report.topological.information_sinks:
        action_items.append(
            (
                3,
                f"Fix information sink: [[{stem}]] — "
                f"reduce inbound/outbound imbalance",
            )
        )

    # 4. Phantom links
    for source, target in report.hygiene.phantom_links:
        action_items.append(
            (
                4,
                f"Fix phantom link: [[{source}]] → [[{target}]] "
                f"— create target or remove link",
            )
        )

    # 5. Tag issues
    for note, tag in report.hygiene.non_conformant_tags:
        action_items.append(
            (
                5,
                f"Fix non-conformant tag: [[{note}]] — fix tag `{tag}`",
            )
        )
    for tag_a, tag_b in report.hygiene.near_duplicate_tags:
        action_items.append(
            (
                5,
                f"Merge near-duplicate tags: `{tag_a}` and `{tag_b}`",
            )
        )
    for tag in report.hygiene.single_use_tags:
        action_items.append(
            (
                5,
                f"Review single-use tag: `{tag}` — "
                f"expand usage or remove",
            )
        )
    for tag in report.hygiene.unused_tags:
        action_items.append(
            (5, f"Remove unused tag: `{tag}`")
        )

    # 6. Frontmatter issues
    for note, field in report.hygiene.missing_fields:
        action_items.append(
            (
                6,
                f"Add missing field: [[{note}]] — add `{field}`",
            )
        )
    for note, field, expected in report.hygiene.type_mismatches:
        action_items.append(
            (
                6,
                f"Fix type mismatch: [[{note}]] — "
                f"`{field}` should be {expected}",
            )
        )
    for note, description in report.hygiene.inconsistent_dates:
        action_items.append(
            (
                6,
                f"Fix inconsistent dates: [[{note}]] — {description}",
            )
        )

    # 7. Over-linking
    for note, section, target in report.hygiene.over_linking:
        action_items.append(
            (
                7,
                f"Reduce over-linking: [[{note}]] — "
                f"{section} → [[{target}]]",
            )
        )

    # 8. Missing reciprocals
    for source, target in report.connectivity.missing_reciprocals:
        action_items.append(
            (
                8,
                f"Add reciprocal link: [[{target}]] → [[{source}]]",
            )
        )

    # 9. Stale notes
    for stem in report.temporal.stale_notes:
        action_items.append(
            (9, f"Update stale note: [[{stem}]]")
        )

    # 10. Dead weight
    for stem in report.temporal.dead_weight:
        action_items.append(
            (
                10,
                f"Review dead weight: [[{stem}]] (stale + orphaned)",
            )
        )

    # 11. Chain gaps
    for a, c, b in report.structural.chain_gaps:
        action_items.append(
            (
                11,
                f"Fill chain gap: [[{a}]] ↔ [[{c}]] — "
                f"create [[{b}]]",
            )
        )

    # 12. Potential silos
    for cluster_a, cluster_b, density in report.structural.potential_silos:
        action_items.append(
            (
                12,
                f"Bridge potential silo: Cluster {cluster_a} "
                f"↔ Cluster {cluster_b}",
            )
        )

    # 13. Broken cycles
    for i, cycle in enumerate(report.structural.broken_cycles):
        if cycle:
            action_items.append(
                (
                    13,
                    f"Complete broken cycle: {cycle[0]} → ... → "
                    f"{cycle[-1]}",
                )
            )

    action_items.sort(key=lambda x: x[0])

    for priority, item in action_items[:50]:
        lines.append(f"1. {item}")

    if len(action_items) > 50:
        lines.append(
            f"*... and {len(action_items) - 50} more action items*"
        )

    return "\n".join(lines)