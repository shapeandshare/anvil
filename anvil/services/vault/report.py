# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Markdown report renderer for vault graph health analysis."""

from __future__ import annotations

from datetime import datetime

from ._types import (
    ConnectivityMetrics,
    GraphHealthReport,
    HealthScore,
    HygieneMetrics,
    LinkPredictionResult,
    NoteMetadata,
    StructuralMetrics,
    TemporalMetrics,
    TopologicalMetrics,
)


def render_markdown(
    report: GraphHealthReport,
    notes: dict[str, NoteMetadata],
) -> str:
    """Render a ``GraphHealthReport`` as a Markdown string.

    Parameters
    ----------
    report : GraphHealthReport
        Fully-populated report with all metrics computed.
    notes : dict[str, NoteMetadata]
        Stem -> ``NoteMetadata`` for resolving note titles/paths.

    Returns
    -------
    str
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
    """Render the health score summary section.

    Parameters
    ----------
    score : HealthScore
        Composite health score.

    Returns
    -------
    str
        Markdown section.
    """
    lines = ["## Health Score", ""]

    if score.overall >= 80:
        emoji = "🟢"
    elif score.overall >= 50:
        emoji = "🟡"
    else:
        emoji = "🔴"

    lines.append(f"**Overall: {emoji} {score.overall:.1f}/100**")
    lines.append("")
    lines.append("| Component | Score |")
    lines.append("|-----------|-------|")

    breakdown = score.breakdown or {}
    for key, val in breakdown.items():
        label = key.replace("_", " ").title()
        lines.append(f"| {label} | {val:.1f}/100 |")

    return "\n".join(lines)


def _render_connectivity(
    metrics: ConnectivityMetrics,
    notes: dict[str, NoteMetadata],
) -> str:
    """Render the connectivity metrics section.

    Parameters
    ----------
    metrics : ConnectivityMetrics
        Connectivity analysis.
    notes : dict[str, NoteMetadata]
        Note lookup for resolving stems to titles.

    Returns
    -------
    str
        Markdown section.
    """
    lines = ["## Connectivity", ""]
    lines.append(
        f"- **Orphan rate**: {metrics.orphan_rate:.1f}% "
        f"({metrics.orphan_count} orphans) — *{metrics.link_density_class}*"
    )
    lines.append(
        f"- **Dead-end rate**: {metrics.dead_end_rate:.1f}% "
        f"({metrics.dead_end_count} dead ends)"
    )
    lines.append(
        f"- **Link density**: {metrics.link_density_avg:.1f} avg — "
        f"*{metrics.link_density_class}*"
    )
    lines.append(
        f"- **Largest component**: {metrics.largest_component_pct:.1f}% "
        f"— *{metrics.largest_component_class}*"
    )
    lines.append(
        f"- **Bidirectional ratio**: {metrics.bidirectional_ratio:.1f}% "
        f"— *{metrics.bidirectional_class}*"
    )

    if metrics.orphans:
        lines.append("")
        lines.append("### Orphans (no inbound links)")
        for stem in metrics.orphans[:10]:
            title = _note_title(stem, notes)
            lines.append(f"- {title} (`{stem}`)")
        if len(metrics.orphans) > 10:
            lines.append(f"- *...and {len(metrics.orphans) - 10} more*")
    if metrics.missing_reciprocals:
        lines.append("")
        lines.append(f"- *{len(metrics.missing_reciprocals)} missing reciprocal links*")

    return "\n".join(lines)


def _render_topological(
    metrics: TopologicalMetrics,
    notes: dict[str, NoteMetadata],
) -> str:
    """Render the topological metrics section.

    Parameters
    ----------
    metrics : TopologicalMetrics
        Topological analysis.
    notes : dict[str, NoteMetadata]
        Note lookup.

    Returns
    -------
    str
        Markdown section.
    """
    lines = ["## Topology", ""]

    lines.append(
        f"- **Information sink rate**: {metrics.information_sink_rate:.1f}% "
        f"— *{metrics.information_sink_class}*"
    )
    lines.append(f"- **Communities**: {len(metrics.communities)} detected")
    lines.append(
        f"- **Communities needing MOC**: {len(metrics.communities_needing_moc)}"
    )

    if metrics.pagerank_top:
        lines.append("")
        lines.append("### Top Hub Notes")
        for stem, score in metrics.pagerank_top[:5]:
            title = _note_title(stem, notes)
            lines.append(f"- {title} (`{stem}`) — *{score:.4f}*")

    if metrics.information_sinks:
        lines.append("")
        lines.append("### Information Sinks")
        for stem in metrics.information_sinks[:5]:
            title = _note_title(stem, notes)
            lines.append(f"- {title} (`{stem}`)")
        if len(metrics.information_sinks) > 5:
            lines.append(f"- *...and {len(metrics.information_sinks) - 5} more*")

    return "\n".join(lines)


def _render_temporal(
    metrics: TemporalMetrics,
    notes: dict[str, NoteMetadata],
) -> str:
    """Render the temporal metrics section.

    Parameters
    ----------
    metrics : TemporalMetrics
        Temporal decay analysis.
    notes : dict[str, NoteMetadata]
        Note lookup.

    Returns
    -------
    str
        Markdown section.
    """
    lines = ["## Temporal Health", ""]
    lines.append(f"- **Stale notes**: {len(metrics.stale_notes)} (>180 days)")
    lines.append(f"- **Dead weight**: {len(metrics.dead_weight)} (stale + orphaned)")
    lines.append(f"- **High coherence**: {metrics.high_coherence_pct:.1f}% of links")
    lines.append(f"- **Low coherence**: {metrics.low_coherence_pct:.1f}% of links")

    if metrics.stale_notes:
        lines.append("")
        lines.append("### Stale Notes")
        for stem in metrics.stale_notes[:10]:
            title = _note_title(stem, notes)
            lines.append(f"- {title} (`{stem}`)")
        if len(metrics.stale_notes) > 10:
            lines.append(f"- *...and {len(metrics.stale_notes) - 10} more*")

    return "\n".join(lines)


def _render_hygiene(
    metrics: HygieneMetrics,
    notes: dict[str, NoteMetadata],
) -> str:
    """Render the hygiene metrics section.

    Parameters
    ----------
    metrics : HygieneMetrics
        Hygiene analysis.
    notes : dict[str, NoteMetadata]
        Note lookup.

    Returns
    -------
    str
        Markdown section.
    """
    lines = ["## Hygiene", ""]
    lines.append(
        f"- **Tag conformity**: {metrics.tag_conformity_pct:.1f}% "
        f"— *{metrics.tag_conformity_class}*"
    )
    lines.append(
        f"- **Frontmatter completeness**: "
        f"{metrics.frontmatter_completeness_pct:.1f}% "
        f"— *{metrics.frontmatter_completeness_class}*"
    )
    lines.append(f"- **Non-conformant tags**: {len(metrics.non_conformant_tags)}")
    lines.append(f"- **Near-duplicate tags**: {len(metrics.near_duplicate_tags)}")
    lines.append(f"- **Phantom links**: {len(metrics.phantom_links)}")
    lines.append(f"- **Over-linking instances**: {len(metrics.over_linking)}")

    if metrics.non_conformant_tags:
        lines.append("")
        lines.append("### Non-conformant Tags")
        for stem, tag in metrics.non_conformant_tags[:10]:
            title = _note_title(stem, notes)
            lines.append(f"- {title}: `{tag}`")
    if metrics.phantom_links:
        lines.append("")
        lines.append("### Phantom Links")
        for stem, target in metrics.phantom_links[:10]:
            title = _note_title(stem, notes)
            lines.append(f"- {title} → `{target}`")

    return "\n".join(lines)


def _render_structural(
    metrics: StructuralMetrics,
    notes: dict[str, NoteMetadata],
) -> str:
    """Render the structural metrics section.

    Parameters
    ----------
    metrics : StructuralMetrics
        Structural gap analysis.
    notes : dict[str, NoteMetadata]
        Note lookup.

    Returns
    -------
    str
        Markdown section.
    """
    lines = ["## Structural Health", ""]
    lines.append(f"- **Chain gaps**: {len(metrics.chain_gaps)}")
    lines.append(f"- **Potential silos**: {len(metrics.potential_silos)}")
    lines.append(f"- **Broken cycles**: {len(metrics.broken_cycles)}")

    if metrics.broken_cycles:
        lines.append("")
        lines.append("### Broken Cycles")
        for cycle in metrics.broken_cycles[:5]:
            names = [_note_title(s, notes) for s in cycle]
            lines.append(f"- {' → '.join(names)}")

    return "\n".join(lines)


def _render_link_prediction(result: object) -> str:
    """Render the link prediction section.

    Parameters
    ----------
    result : LinkPredictionResult
        Link prediction result.

    Returns
    -------
    str
        Markdown section.
    """
    assert isinstance(result, LinkPredictionResult)

    lines = ["## Link Prediction", ""]
    if not result.scored_pairs:
        lines.append("No candidates above threshold.")
    else:
        lines.append(
            f"Top {min(result.top_n, len(result.scored_pairs))} candidates "
            f"(threshold >= {result.threshold}):"
        )
        lines.append("")
        lines.append("| Source | Target | Score |")
        lines.append("|--------|--------|-------|")
        for pair in result.scored_pairs[: result.top_n]:
            lines.append(
                f"| {pair.source} | {pair.target} | {pair.ensemble_score:.3f} |"
            )
        if result.took_action:
            lines.append("")
            lines.append("*Auto-fixes were applied.*")

    return "\n".join(lines)


def _render_action_items(
    report: GraphHealthReport,
    notes: dict[str, NoteMetadata],
) -> str:
    """Render action items based on report findings.

    Parameters
    ----------
    report : GraphHealthReport
        Full report.
    notes : dict[str, NoteMetadata]
        Note lookup.

    Returns
    -------
    str
        Markdown action items section.
    """
    lines = ["## Action Items", ""]
    count = 0

    if report.connectivity.orphans:
        lines.append(
            f"- 🔗 Add inbound links to "
            f"{len(report.connectivity.orphans)} orphan notes"
        )
        count += 1
    if report.hygiene.non_conformant_tags:
        lines.append(
            f"- 🏷️ Fix {len(report.hygiene.non_conformant_tags)} " f"non-conformant tags"
        )
        count += 1
    if report.hygiene.phantom_links:
        lines.append(f"- 👻 Resolve {len(report.hygiene.phantom_links)} phantom links")
        count += 1
    if report.temporal.stale_notes:
        lines.append(f"- 📅 Review {len(report.temporal.stale_notes)} stale notes")
        count += 1
    if report.topological.communities_needing_moc:
        lines.append(
            f"- 🗺️ Create MOCs for "
            f"{len(report.topological.communities_needing_moc)} communities"
        )
        count += 1
    if report.hygiene.missing_fields:
        lines.append(
            f"- 📝 Fix {len(report.hygiene.missing_fields)} "
            f"missing frontmatter fields"
        )
        count += 1

    if count == 0:
        lines.append("No action items — vault is healthy! ✨")

    return "\n".join(lines)


def _note_title(stem: str, notes: dict[str, NoteMetadata]) -> str:
    """Get the display title for a note stem.

    Parameters
    ----------
    stem : str
        Note stem.
    notes : dict[str, NoteMetadata]
        Note lookup.

    Returns
    -------
    str
        Title string (with wikilink formatting).
    """
    meta = notes.get(stem)
    if meta and meta.title:
        return meta.title
    return f"`{stem}`"
