"""Tests for report.py — Markdown report renderer for vault graph health.

Covers render_markdown and all internal _render_* functions including
render_health_score, render_connectivity, render_topological,
render_temporal, render_hygiene, render_structural,
render_link_prediction, render_action_items, and note_title.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from anvil.services.vault.report import (
    _note_title,
    _render_action_items,
    _render_connectivity,
    _render_health_score,
    _render_hygiene,
    _render_link_prediction,
    _render_structural,
    _render_temporal,
    _render_topological,
    render_markdown,
)
from anvil.services.vault.types_connectivity_metrics import ConnectivityMetrics
from anvil.services.vault.types_graph_health_report import GraphHealthReport
from anvil.services.vault.types_health_score import HealthScore
from anvil.services.vault.types_hygiene_metrics import HygieneMetrics
from anvil.services.vault.types_link_prediction_result import LinkPredictionResult
from anvil.services.vault.types_note_metadata import NoteMetadata
from anvil.services.vault.types_scored_pair import ScoredPair
from anvil.services.vault.types_structural_metrics import StructuralMetrics
from anvil.services.vault.types_temporal_metrics import TemporalMetrics
from anvil.services.vault.types_topological_metrics import TopologicalMetrics


def _note(stem: str, title: str | None = None) -> NoteMetadata:
    """Build a minimal NoteMetadata for testing."""
    return NoteMetadata(path=Path(f"{stem}.md"), stem=stem, title=title)


# ── _note_title ──────────────────────────────────────────────────────────────


class TestNoteTitle:
    """Tests for _note_title helper."""

    def test_returns_title_when_found(self) -> None:
        """Returns the note title when the stem exists."""
        notes = {"foo": _note("foo", "Foo Note")}
        assert _note_title("foo", notes) == "Foo Note"

    def test_returns_stem_when_not_found(self) -> None:
        """Returns backtick-wrapped stem when the note is missing."""
        notes: dict[str, NoteMetadata] = {}
        assert _note_title("missing", notes) == "`missing`"

    def test_returns_stem_when_title_is_none(self) -> None:
        """Returns backtick-wrapped stem when title is None."""
        notes = {"foo": _note("foo", None)}
        assert _note_title("foo", notes) == "`foo`"


# ── _render_health_score ─────────────────────────────────────────────────────


class TestRenderHealthScore:
    """Tests for _render_health_score."""

    def test_green_emoji_for_high_score(self) -> None:
        """Score >= 80 gets green emoji."""
        score = HealthScore(overall=85.0, breakdown={"orphan_rate": 20.0})
        result = _render_health_score(score)
        assert "🟢" in result
        assert "85.0/100" in result

    def test_yellow_emoji_for_medium_score(self) -> None:
        """Score 50-80 gets yellow emoji."""
        score = HealthScore(overall=65.0)
        result = _render_health_score(score)
        assert "🟡" in result

    def test_red_emoji_for_low_score(self) -> None:
        """Score < 50 gets red emoji."""
        score = HealthScore(overall=30.0)
        result = _render_health_score(score)
        assert "🔴" in result

    def test_renders_breakdown_table(self) -> None:
        """Breakdown items appear in a markdown table."""
        score = HealthScore(overall=80.0, breakdown={"orphan_rate": 20.0})
        result = _render_health_score(score)
        assert "|" in result
        assert "Orphan Rate" in result

    def test_empty_breakdown_shows_no_table(self) -> None:
        """Empty breakdown dict produces no table rows."""
        score = HealthScore(overall=80.0)
        result = _render_health_score(score)
        assert "| Component |" in result  # header still shown
        # just header and separator


# ── _render_connectivity ─────────────────────────────────────────────────────


class TestRenderConnectivity:
    """Tests for _render_connectivity."""

    def test_renders_metric_summary(self) -> None:
        """Basic connectivity metrics appear in the output."""
        metrics = ConnectivityMetrics(
            orphan_rate=10.0,
            orphan_count=3,
            dead_end_rate=5.0,
            dead_end_count=2,
            link_density_avg=4.5,
            link_density_class="healthy",
            largest_component_pct=95.0,
            largest_component_class="healthy",
            bidirectional_ratio=40.0,
            bidirectional_class="healthy",
        )
        result = _render_connectivity(metrics, {})
        assert "10.0%" in result
        assert "3 orphans" in result
        assert "5.0%" in result
        assert "4.5 avg" in result
        assert "95.0%" in result
        assert "40.0%" in result

    def test_renders_orphans_list(self) -> None:
        """Orphan stems appear in a sub-section."""
        metrics = ConnectivityMetrics(
            orphan_rate=50.0,
            orphan_count=2,
            orphans=["orphan_a", "orphan_b"],
        )
        notes = {"orphan_a": _note("orphan_a", "Orphan A")}
        result = _render_connectivity(metrics, notes)
        assert "Orphans" in result
        assert "Orphan A" in result

    def test_truncates_long_orphan_list(self) -> None:
        """More than 10 orphans shows 'and X more'."""
        metrics = ConnectivityMetrics(
            orphan_rate=100.0,
            orphan_count=15,
            orphans=[f"o{i}" for i in range(15)],
        )
        result = _render_connectivity(metrics, {})
        assert "...and 5 more" in result

    def test_shows_missing_reciprocals_count(self) -> None:
        """Missing reciprocal links are mentioned."""
        metrics = ConnectivityMetrics(
            missing_reciprocals=[("a", "b"), ("c", "d")],
        )
        result = _render_connectivity(metrics, {})
        assert "2 missing reciprocal" in result


# ── _render_topological ──────────────────────────────────────────────────────


class TestRenderTopological:
    """Tests for _render_topological."""

    def test_renders_summary(self) -> None:
        """Topological summary metrics appear."""
        metrics = TopologicalMetrics(
            information_sink_rate=5.0,
            information_sink_class="healthy",
            communities=[["a"], ["b"]],
            communities_needing_moc=[["c", "d", "e", "f", "g"]],
        )
        result = _render_topological(metrics, {})
        assert "5.0%" in result
        assert "2 detected" in result
        assert "1" in result  # just check communities_needing_moc is rendered

    def test_renders_pagerank_top(self) -> None:
        """Top PageRank notes appear."""
        metrics = TopologicalMetrics(
            pagerank_top=[("hub_a", 0.9), ("hub_b", 0.5)],
        )
        notes = {"hub_a": _note("hub_a", "Hub A")}
        result = _render_topological(metrics, notes)
        assert "Hub A" in result
        assert "0.9000" in result

    def test_renders_information_sinks(self) -> None:
        """Information sinks appear."""
        metrics = TopologicalMetrics(
            information_sinks=["sink_a", "sink_b"],
        )
        notes = {"sink_a": _note("sink_a", "Sink A")}
        result = _render_topological(metrics, notes)
        assert "Sink A" in result

    def test_truncates_long_sink_list(self) -> None:
        """More than 5 sinks shows 'and X more'."""
        metrics = TopologicalMetrics(
            information_sinks=[f"s{i}" for i in range(8)],
        )
        result = _render_topological(metrics, {})
        assert "...and 3 more" in result


# ── _render_temporal ─────────────────────────────────────────────────────────


class TestRenderTemporal:
    """Tests for _render_temporal."""

    def test_renders_summary(self) -> None:
        """Temporal summary metrics appear."""
        metrics = TemporalMetrics(
            stale_notes=["old_a"],
            dead_weight=["old_a"],
            high_coherence_pct=80.0,
            low_coherence_pct=5.0,
        )
        result = _render_temporal(metrics, {})
        assert "1" in result  # stale count
        assert "80.0%" in result
        assert "5.0%" in result

    def test_renders_stale_notes_list(self) -> None:
        """Stale notes appear."""
        metrics = TemporalMetrics(stale_notes=["old_a", "old_b"])
        notes = {"old_a": _note("old_a", "Old A")}
        result = _render_temporal(metrics, notes)
        assert "Old A" in result

    def test_truncates_long_stale_list(self) -> None:
        """More than 10 stale notes shows 'and X more'."""
        metrics = TemporalMetrics(stale_notes=[f"s{i}" for i in range(13)])
        result = _render_temporal(metrics, {})
        assert "...and 3 more" in result


# ── _render_hygiene ──────────────────────────────────────────────────────────


class TestRenderHygiene:
    """Tests for _render_hygiene."""

    def test_renders_summary(self) -> None:
        """Hygiene summary metrics appear."""
        metrics = HygieneMetrics(
            tag_conformity_pct=95.0,
            tag_conformity_class="healthy",
            frontmatter_completeness_pct=100.0,
            frontmatter_completeness_class="perfect",
            non_conformant_tags=[("a", "bad_tag")],
            near_duplicate_tags=[("x", "y")],
            phantom_links=[("a", "ghost")],
            over_linking=[("a", "sec", "target")],
        )
        result = _render_hygiene(metrics, {})
        assert "95.0%" in result
        assert "100.0%" in result
        assert "1" in result  # non-conformant count

    def test_renders_non_conformant_tags(self) -> None:
        """Non-conformant tags appear with note title."""
        metrics = HygieneMetrics(
            non_conformant_tags=[("note_a", "bad_tag")],
        )
        notes = {"note_a": _note("note_a", "Note A")}
        result = _render_hygiene(metrics, notes)
        assert "Note A" in result
        assert "bad_tag" in result

    def test_renders_phantom_links(self) -> None:
        """Phantom links appear."""
        metrics = HygieneMetrics(
            phantom_links=[("source_a", "ghost_target")],
        )
        notes = {"source_a": _note("source_a", "Source A")}
        result = _render_hygiene(metrics, notes)
        assert "Source A" in result
        assert "ghost_target" in result


# ── _render_structural ───────────────────────────────────────────────────────


class TestRenderStructural:
    """Tests for _render_structural."""

    def test_renders_summary(self) -> None:
        """Structural summary metrics appear."""
        metrics = StructuralMetrics(
            chain_gaps=[("a", "c", "b")],
            potential_silos=[(1, 2, 0.3)],
            broken_cycles=[["x", "y", "z"]],
        )
        result = _render_structural(metrics, {})
        assert "1" in result  # each count is 1

    def test_renders_broken_cycles(self) -> None:
        """Broken cycles appear as chains."""
        metrics = StructuralMetrics(broken_cycles=[["a", "b", "c"]])
        notes = {"a": _note("a", "Note A"), "b": _note("b", "Note B")}
        result = _render_structural(metrics, notes)
        assert "Note A" in result


# ── _render_link_prediction ──────────────────────────────────────────────────


class TestRenderLinkPrediction:
    """Tests for _render_link_prediction."""

    def test_no_candidates_message(self) -> None:
        """Shows message when no scored pairs."""
        result = LinkPredictionResult(scored_pairs=[])
        output = _render_link_prediction(result)
        assert "No candidates" in output

    def test_renders_candidates_table(self) -> None:
        """Scored pairs appear in a table."""
        pairs = [
            ScoredPair(source="a", target="b", ensemble_score=0.95),
            ScoredPair(source="c", target="d", ensemble_score=0.85),
        ]
        result = LinkPredictionResult(scored_pairs=pairs)
        output = _render_link_prediction(result)
        assert "| a | b | 0.950 |" in output
        assert "| c | d | 0.850 |" in output

    def test_respects_top_n_limit(self) -> None:
        """Only top_n pairs are rendered."""
        pairs = [ScoredPair(source=f"s{i}", target=f"t{i}") for i in range(5)]
        result = LinkPredictionResult(scored_pairs=pairs, top_n=2)
        output = _render_link_prediction(result)
        assert "s0" in output
        assert "s2" not in output  # beyond top_n

    def test_shows_action_taken(self) -> None:
        """Shows auto-fix message when action was taken."""
        pairs = [ScoredPair(source="a", target="b")]  # at least one pair
        result = LinkPredictionResult(scored_pairs=pairs, took_action=True)
        output = _render_link_prediction(result)
        assert "Auto-fixes were applied" in output


# ── _render_action_items ─────────────────────────────────────────────────────


class TestRenderActionItems:
    """Tests for _render_action_items."""

    def test_no_actions_when_healthy(self) -> None:
        """When all metrics are clean, shows healthy message."""
        report = GraphHealthReport()
        result = _render_action_items(report, {})
        assert "healthy" in result

    def test_orphan_action_item(self) -> None:
        """Orphans generate an action item."""
        report = GraphHealthReport(
            connectivity=ConnectivityMetrics(orphans=["o1", "o2"]),
        )
        result = _render_action_items(report, {})
        assert "orphan" in result
        assert "2" in result

    def test_non_conformant_tags_action_item(self) -> None:
        """Non-conformant tags generate an action item."""
        report = GraphHealthReport(
            hygiene=HygieneMetrics(non_conformant_tags=[("a", "bad")]),
        )
        result = _render_action_items(report, {})
        assert "non-conformant" in result

    def test_phantom_links_action_item(self) -> None:
        """Phantom links generate an action item."""
        report = GraphHealthReport(
            hygiene=HygieneMetrics(phantom_links=[("a", "ghost")]),
        )
        result = _render_action_items(report, {})
        assert "phantom" in result

    def test_stale_notes_action_item(self) -> None:
        """Stale notes generate an action item."""
        report = GraphHealthReport(
            temporal=TemporalMetrics(stale_notes=["old"]),
        )
        result = _render_action_items(report, {})
        assert "stale" in result

    def test_communities_needing_moc_action_item(self) -> None:
        """Communities needing MOC generate an action item."""
        report = GraphHealthReport(
            topological=TopologicalMetrics(
                communities_needing_moc=[["a", "b", "c", "d", "e"]],
            ),
        )
        result = _render_action_items(report, {})
        assert "MOC" in result

    def test_missing_fields_action_item(self) -> None:
        """Missing frontmatter fields generate an action item."""
        report = GraphHealthReport(
            hygiene=HygieneMetrics(missing_fields=[("a", "title")]),
        )
        result = _render_action_items(report, {})
        assert "frontmatter" in result

    def test_multiple_action_items(self) -> None:
        """Multiple issues produce multiple action items."""
        report = GraphHealthReport(
            connectivity=ConnectivityMetrics(orphans=["o1"]),
            hygiene=HygieneMetrics(phantom_links=[("a", "b")]),
        )
        result = _render_action_items(report, {})
        assert result.count("- ") >= 2


# ── render_markdown (integration) ────────────────────────────────────────────


class TestRenderMarkdown:
    """Tests for the top-level render_markdown function."""

    def test_generates_valid_markdown(self) -> None:
        """Produces a string with all expected sections."""
        report = GraphHealthReport(notes_scanned=10)
        result = render_markdown(report, {})
        assert result.startswith("# Vault Graph Health Report")
        assert "## Health Score" in result
        assert "## Connectivity" in result
        assert "## Action Items" in result

    def test_includes_timestamp(self) -> None:
        """Includes a generated timestamp."""
        report = GraphHealthReport()
        result = render_markdown(report, {})
        assert "Generated:" in result

    def test_includes_link_prediction_when_present(self) -> None:
        """Link prediction section included when scored pairs exist."""
        pairs = [ScoredPair(source="a", target="b")]
        report = GraphHealthReport(
            link_prediction=LinkPredictionResult(scored_pairs=pairs),
        )
        result = render_markdown(report, {})
        assert "## Link Prediction" in result

    def test_skips_link_prediction_when_empty(self) -> None:
        """Link prediction section skipped when no scored pairs."""
        report = GraphHealthReport()
        result = render_markdown(report, {})
        assert "## Link Prediction" not in result

    def test_renders_orphans_in_markdown(self) -> None:
        """Orphans appear in the rendered markdown."""
        report = GraphHealthReport(
            connectivity=ConnectivityMetrics(
                orphan_rate=50.0, orphan_count=1, orphans=["lonely"],
            ),
        )
        notes = {"lonely": _note("lonely", "Lonely Note")}
        result = render_markdown(report, notes)
        assert "Lonely Note" in result

    def test_no_crash_with_empty_report(self) -> None:
        """Empty report renders without error."""
        report = GraphHealthReport()
        result = render_markdown(report, {})
        assert isinstance(result, str)
        assert len(result) > 50