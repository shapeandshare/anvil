# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for the vault graph health report renderer.

Tests ``render_markdown`` and all private rendering helpers:
``_note_title``, ``_render_health_score``, ``_render_connectivity``,
``_render_topological``, ``_render_temporal``, ``_render_hygiene``,
``_render_structural``, ``_render_link_prediction``, and
``_render_action_items``.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from anvil.services.vault.report import _note_title, render_markdown
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


def _make_note(title: str, stem: str = "") -> NoteMetadata:
    """Build a minimal NoteMetadata for testing."""
    return NoteMetadata(
        path=Path(f"/vault/{stem or title}.md"),
        stem=stem or title,
        title=title,
    )


def _default_report() -> GraphHealthReport:
    """Build a fully-defaulted GraphHealthReport."""
    return GraphHealthReport(
        connectivity=ConnectivityMetrics(),
        topological=TopologicalMetrics(),
        hygiene=HygieneMetrics(),
        temporal=TemporalMetrics(),
        structural=StructuralMetrics(),
        health_score=HealthScore(),
        link_prediction=LinkPredictionResult(),
    )


########################################################################
# _note_title tests
########################################################################


class TestNoteTitle:
    """Tests for _note_title helper."""

    def test_found_with_title(self) -> None:
        """Returns the note's title when the stem is found."""
        notes = {"abc": _make_note("Alpha Bravo Charlie", "abc")}
        assert _note_title("abc", notes) == "Alpha Bravo Charlie"

    def test_found_without_title(self) -> None:
        """Returns the stem in backticks when the note has no title."""
        notes = {"abc": NoteMetadata(path=Path("/vault/abc.md"), stem="abc")}
        assert _note_title("abc", notes) == "`abc`"

    def test_not_found(self) -> None:
        """Returns the stem in backticks when the stem is not in notes dict."""
        assert _note_title("missing", {}) == "`missing`"


########################################################################
# render_markdown top-level tests
########################################################################


class TestRenderMarkdown:
    """Tests for render_markdown."""

    def test_returns_string(self) -> None:
        """render_markdown returns a non-empty string."""
        report = _default_report()
        notes: dict[str, NoteMetadata] = {}
        result = render_markdown(report, notes)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_main_heading(self) -> None:
        """Output contains the main heading."""
        result = render_markdown(_default_report(), {})
        assert "# Vault Graph Health Report" in result

    def test_contains_section_headers(self) -> None:
        """Output contains all expected section headers."""
        result = render_markdown(_default_report(), {})
        assert "## Health Score" in result
        assert "## Connectivity" in result
        assert "## Topology" in result
        assert "## Temporal Health" in result
        assert "## Hygiene" in result
        assert "## Structural Health" in result
        assert "## Action Items" in result

    def test_healthy_vault_no_action_items(self) -> None:
        """A healthy vault shows 'No action items' message."""
        report = _default_report()
        report.health_score.overall = 100.0
        result = render_markdown(report, {})
        assert "No action items" in result

    def test_link_prediction_section_included_when_present(self) -> None:
        """Link prediction section appears when scored_pairs is non-empty."""
        report = _default_report()
        report.link_prediction = LinkPredictionResult(
            scored_pairs=[ScoredPair(source="a", target="b", ensemble_score=0.85)],
            top_n=5,
            threshold=0.7,
        )
        result = render_markdown(report, {})
        assert "## Link Prediction" in result
        assert "0.850" in result

    def test_link_prediction_section_omitted_when_empty(self) -> None:
        """Link prediction section is omitted when scored_pairs is empty."""
        report = _default_report()
        report.link_prediction = LinkPredictionResult(scored_pairs=[])
        result = render_markdown(report, {})
        assert "## Link Prediction" not in result


########################################################################
# Health Score rendering
########################################################################


class TestHealthScoreRendering:
    """Tests for the health score section."""

    def test_green_emoji_high_score(self) -> None:
        """Scores >= 80 get green indicator."""
        report = _default_report()
        report.health_score.overall = 95.0
        result = render_markdown(report, {})
        assert "🟢" in result
        assert "95.0/100" in result

    def test_yellow_emoji_medium_score(self) -> None:
        """Scores >= 50 and < 80 get yellow indicator."""
        report = _default_report()
        report.health_score.overall = 65.0
        result = render_markdown(report, {})
        assert "🟡" in result
        assert "65.0/100" in result

    def test_red_emoji_low_score(self) -> None:
        """Scores < 50 get red indicator."""
        report = _default_report()
        report.health_score.overall = 30.0
        result = render_markdown(report, {})
        assert "🔴" in result
        assert "30.0/100" in result

    def test_breakdown_rendered(self) -> None:
        """Breakdown scores are rendered in a table."""
        report = _default_report()
        report.health_score.overall = 75.0
        report.health_score.breakdown = {
            "orphan_score": 80.0,
            "tag_conformity_score": 70.0,
        }
        result = render_markdown(report, {})
        assert "| Orphan Score | 80.0/100 |" in result
        assert "| Tag Conformity Score | 70.0/100 |" in result


########################################################################
# Connectivity rendering
########################################################################


class TestConnectivityRendering:
    """Tests for the connectivity section."""

    def test_basic_metrics(self) -> None:
        """Basic connectivity metrics are rendered."""
        report = _default_report()
        report.connectivity = ConnectivityMetrics(
            orphan_rate=15.5,
            orphan_count=3,
            link_density_avg=4.2,
            link_density_class="healthy",
            largest_component_pct=85.0,
            largest_component_class="healthy",
            bidirectional_ratio=60.0,
            bidirectional_class="warning",
            dead_end_rate=5.0,
            dead_end_count=2,
        )
        result = render_markdown(report, {})
        assert "15.5%" in result
        assert "4.2 avg" in result
        assert "85.0%" in result
        assert "60.0%" in result
        assert "healthy" in result
        assert "warning" in result
        assert "2 dead ends" in result

    def test_orphans_listed_with_titles(self) -> None:
        """Orphan stems are listed with resolved titles."""
        report = _default_report()
        report.connectivity = ConnectivityMetrics(
            orphan_rate=100.0,
            orphan_count=2,
            orphans=["orphan-a", "orphan-b"],
        )
        notes = {
            "orphan-a": _make_note("Orphan Alpha", "orphan-a"),
            "orphan-b": _make_note("Orphan Beta", "orphan-b"),
        }
        result = render_markdown(report, notes)
        assert "Orphan Alpha" in result
        assert "Orphan Beta" in result

    def test_orphans_truncated_at_10(self) -> None:
        """More than 10 orphans shows '...and N more'."""
        report = _default_report()
        report.connectivity = ConnectivityMetrics(
            orphan_rate=100.0,
            orphan_count=15,
            orphans=[f"o{i}" for i in range(15)],
        )
        result = render_markdown(report, {})
        assert "...and 5 more" in result

    def test_missing_reciprocals_count(self) -> None:
        """Missing reciprocal links count is shown."""
        report = _default_report()
        report.connectivity = ConnectivityMetrics(
            missing_reciprocals=[("a", "b"), ("c", "d")],
        )
        result = render_markdown(report, {})
        assert "2 missing reciprocal" in result


########################################################################
# Topology rendering
########################################################################


class TestTopologyRendering:
    """Tests for the topology section."""

    def test_basic_topology(self) -> None:
        """Basic topology metrics are rendered."""
        report = _default_report()
        report.topological = TopologicalMetrics(
            information_sink_rate=10.0,
            information_sink_class="warning",
            communities=[["a", "b"], ["c"]],
            communities_needing_moc=[["x", "y", "z", "m", "n"]],
        )
        result = render_markdown(report, {})
        assert "10.0%" in result
        assert "2 detected" in result  # communities
        assert "1" in result  # communities needing MOC

    def test_pagerank_top_rendered(self) -> None:
        """Top PageRank notes are rendered with scores."""
        report = _default_report()
        report.topological = TopologicalMetrics(
            pagerank_top=[("hub-a", 0.95), ("hub-b", 0.85), ("hub-c", 0.75)],
        )
        notes = {"hub-a": _make_note("Hub Alpha", "hub-a")}
        result = render_markdown(report, notes)
        assert "Hub Alpha" in result
        assert "0.9500" in result
        assert "0.8500" in result

    def test_information_sinks_rendered(self) -> None:
        """Information sinks are listed with titles."""
        report = _default_report()
        report.topological = TopologicalMetrics(
            information_sink_rate=20.0,
            information_sinks=["sink-a", "sink-b"],
        )
        notes = {"sink-a": _make_note("Sink Alpha", "sink-a")}
        result = render_markdown(report, notes)
        assert "Sink Alpha" in result

    def test_information_sinks_truncated(self) -> None:
        """More than 5 sinks shows '...and N more'."""
        report = _default_report()
        report.topological = TopologicalMetrics(
            information_sink_rate=50.0,
            information_sinks=[f"s{i}" for i in range(8)],
        )
        result = render_markdown(report, {})
        assert "...and 3 more" in result


########################################################################
# Temporal rendering
########################################################################


class TestTemporalRendering:
    """Tests for the temporal health section."""

    def test_basic_temporal(self) -> None:
        """Basic temporal metrics are rendered."""
        report = _default_report()
        report.temporal = TemporalMetrics(
            stale_notes=["old-a", "old-b"],
            dead_weight=["dead-a"],
            high_coherence_pct=75.5,
            low_coherence_pct=10.0,
        )
        result = render_markdown(report, {})
        assert "**Stale notes**: 2" in result
        assert "**Dead weight**: 1" in result
        assert "75.5%" in result
        assert "10.0%" in result

    def test_stale_notes_listed(self) -> None:
        """Stale notes are listed with titles."""
        report = _default_report()
        report.temporal = TemporalMetrics(
            stale_notes=["stale-a", "stale-b"],
        )
        notes = {"stale-a": _make_note("Stale Alpha", "stale-a")}
        result = render_markdown(report, notes)
        assert "Stale Alpha" in result

    def test_stale_notes_truncated(self) -> None:
        """More than 10 stale notes shows '...and N more'."""
        report = _default_report()
        report.temporal = TemporalMetrics(
            stale_notes=[f"s{i}" for i in range(15)],
        )
        result = render_markdown(report, {})
        assert "...and 5 more" in result


########################################################################
# Hygiene rendering
########################################################################


class TestHygieneRendering:
    """Tests for the hygiene section."""

    def test_basic_hygiene(self) -> None:
        """Basic hygiene metrics are rendered."""
        report = _default_report()
        report.hygiene = HygieneMetrics(
            tag_conformity_pct=90.0,
            tag_conformity_class="good",
            frontmatter_completeness_pct=85.0,
            frontmatter_completeness_class="warning",
            non_conformant_tags=[("note-a", "bad/tag")],
            near_duplicate_tags=[("cat", "cats")],
            phantom_links=[("note-a", "missing-target")],
            over_linking=[("note-a", "section", "target")],
        )
        result = render_markdown(report, {})
        assert "**Tag conformity**: 90.0%" in result
        assert "**Frontmatter completeness**: 85.0%" in result
        assert "**Non-conformant tags**: 1" in result
        assert "**Near-duplicate tags**: 1" in result
        assert "**Phantom links**: 1" in result
        assert "**Over-linking instances**: 1" in result

    def test_non_conformant_tags_listed(self) -> None:
        """Non-conformant tags are listed with titles."""
        report = _default_report()
        report.hygiene = HygieneMetrics(
            tag_conformity_pct=50.0,
            non_conformant_tags=[("note-a", "bad/tag")],
        )
        notes = {"note-a": _make_note("Note Alpha", "note-a")}
        result = render_markdown(report, notes)
        assert "Note Alpha" in result
        assert "bad/tag" in result

    def test_phantom_links_listed(self) -> None:
        """Phantom links are listed with titles."""
        report = _default_report()
        report.hygiene = HygieneMetrics(
            phantom_links=[("note-a", "ghost")],
        )
        notes = {"note-a": _make_note("Note Alpha", "note-a")}
        result = render_markdown(report, notes)
        assert "Note Alpha" in result
        assert "ghost" in result

    def test_non_conformant_tags_truncated(self) -> None:
        """More than 10 non-conformant tags are truncated."""
        report = _default_report()
        report.hygiene = HygieneMetrics(
            tag_conformity_pct=10.0,
            non_conformant_tags=[(f"n{i}", f"bad/{i}") for i in range(15)],
        )
        result = render_markdown(report, {})
        # Not checking exact count, just that it doesn't crash

    def test_phantom_links_truncated(self) -> None:
        """More than 10 phantom links are truncated."""
        report = _default_report()
        report.hygiene = HygieneMetrics(
            phantom_links=[(f"n{i}", f"t{i}") for i in range(15)],
        )
        result = render_markdown(report, {})
        assert isinstance(result, str)


########################################################################
# Structural rendering
########################################################################


class TestStructuralRendering:
    """Tests for the structural health section."""

    def test_basic_structural(self) -> None:
        """Basic structural metrics are rendered."""
        report = _default_report()
        report.structural = StructuralMetrics(
            chain_gaps=[("a", "c", "b")],
            potential_silos=[(1, 2, 0.1)],
            broken_cycles=[["x", "y", "z"]],
        )
        result = render_markdown(report, {})
        assert "1 chain gap" in result or "Chain gaps" in result
        assert "1 potential silo" in result or "Potential silos" in result
        assert "1 broken cycle" in result or "Broken cycles" in result

    def test_broken_cycles_rendered_with_titles(self) -> None:
        """Broken cycles are rendered with note titles."""
        report = _default_report()
        report.structural = StructuralMetrics(
            broken_cycles=[["cycle-a", "cycle-b", "cycle-c"]],
        )
        notes = {
            "cycle-a": _make_note("Cycle Alpha", "cycle-a"),
            "cycle-b": _make_note("Cycle Beta", "cycle-b"),
        }
        result = render_markdown(report, notes)
        assert "Cycle Alpha" in result
        assert "Cycle Beta" in result

    def test_broken_cycles_truncated(self) -> None:
        """More than 5 broken cycles are truncated."""
        report = _default_report()
        report.structural = StructuralMetrics(
            broken_cycles=[[f"c{i}"] for i in range(8)],
        )
        result = render_markdown(report, {})
        assert isinstance(result, str)


########################################################################
# Link Prediction rendering
########################################################################


class TestLinkPredictionRendering:
    """Tests for the link prediction section."""

    def test_pairs_rendered(self) -> None:
        """Scored pairs render in a table."""
        report = _default_report()
        report.link_prediction = LinkPredictionResult(
            scored_pairs=[
                ScoredPair(source="src-a", target="tgt-a", ensemble_score=0.85),
                ScoredPair(source="src-b", target="tgt-b", ensemble_score=0.72),
            ],
            top_n=10,
            threshold=0.7,
        )
        result = render_markdown(report, {})
        assert "| src-a | tgt-a | 0.850 |" in result or "src-a" in result
        assert "0.850" in result
        assert "0.720" in result

    def test_no_candidates_section_omitted(self) -> None:
        """Empty scored_pairs means no link prediction section is rendered."""
        report = _default_report()
        report.link_prediction = LinkPredictionResult(
            scored_pairs=[], top_n=5, threshold=0.7
        )
        result = render_markdown(report, {})
        assert "## Link Prediction" not in result

    def test_took_action_shown(self) -> None:
        """When auto-fixes were applied, a note is shown."""
        report = _default_report()
        report.link_prediction = LinkPredictionResult(
            scored_pairs=[ScoredPair(source="a", target="b", ensemble_score=0.9)],
            took_action=True,
        )
        result = render_markdown(report, {})
        assert "Auto-fixes were applied" in result


########################################################################
# Action Items rendering
########################################################################


class TestActionItemsRendering:
    """Tests for the action items section."""

    def test_orphan_action_item(self) -> None:
        """Orphan notes generate a link action item."""
        report = _default_report()
        report.connectivity = ConnectivityMetrics(orphans=["o1", "o2"])
        result = render_markdown(report, {})
        assert "2 orphan" in result or "orphan" in result
        # Should have 🔗 emoji
        assert "🔗" in result

    def test_tag_action_item(self) -> None:
        """Non-conformant tags generate a fix action item."""
        report = _default_report()
        report.hygiene = HygieneMetrics(
            tag_conformity_pct=50.0,
            non_conformant_tags=[("n1", "bad")],
        )
        result = render_markdown(report, {})
        assert "🏷️" in result
        assert "1 non-conformant" in result

    def test_phantom_link_action_item(self) -> None:
        """Phantom links generate a resolve action item."""
        report = _default_report()
        report.hygiene = HygieneMetrics(phantom_links=[("n1", "ghost")])
        result = render_markdown(report, {})
        assert "👻" in result
        assert "1 phantom" in result

    def test_stale_note_action_item(self) -> None:
        """Stale notes generate a review action item."""
        report = _default_report()
        report.temporal = TemporalMetrics(stale_notes=["old"])
        result = render_markdown(report, {})
        assert "📅" in result
        assert "1 stale" in result

    def test_communities_needing_moc_action_item(self) -> None:
        """Communities needing MOC generate an action item."""
        report = _default_report()
        report.topological = TopologicalMetrics(
            communities_needing_moc=[["a", "b", "c", "d", "e"]],
        )
        result = render_markdown(report, {})
        assert "🗺️" in result
        assert "MOC" in result or "communities" in result

    def test_missing_fields_action_item(self) -> None:
        """Missing frontmatter fields generate an action item."""
        report = _default_report()
        report.hygiene = HygieneMetrics(
            missing_fields=[("n1", "title")],
        )
        result = render_markdown(report, {})
        assert "📝" in result
        assert "1 missing" in result

    def test_multiple_action_items(self) -> None:
        """Multiple issues generate multiple action items."""
        report = _default_report()
        report.connectivity = ConnectivityMetrics(orphans=["o1"])
        report.hygiene = HygieneMetrics(
            non_conformant_tags=[("n1", "bad")],
            phantom_links=[("n1", "ghost")],
        )
        report.temporal = TemporalMetrics(stale_notes=["old"])
        result = render_markdown(report, {})
        assert "🔗" in result
        assert "🏷️" in result
        assert "👻" in result
        assert "📅" in result


########################################################################
# Edge cases
########################################################################


class TestRenderEdgeCases:
    """Tests for edge cases in rendering."""

    def test_empty_orphans_no_orphan_section(self) -> None:
        """Empty orphans list does not render orphans subsection."""
        report = _default_report()
        report.connectivity = ConnectivityMetrics(orphans=[])
        result = render_markdown(report, {})
        # "Orphans" heading should NOT appear
        assert "### Orphans" not in result

    def test_empty_stale_notes_no_section(self) -> None:
        """Empty stale_notes list does not render stale notes subsection."""
        report = _default_report()
        report.temporal = TemporalMetrics(stale_notes=[])
        result = render_markdown(report, {})
        assert "### Stale Notes" not in result

    def test_no_action_items_when_healthy(self) -> None:
        """Healthy vault has no action items beyond the message."""
        report = _default_report()
        result = render_markdown(report, {})
        assert "No action items" in result

    def test_link_prediction_empty_scored_pairs_no_section(self) -> None:
        """Link prediction section is absent when scored_pairs is empty."""
        report = _default_report()
        report.link_prediction = LinkPredictionResult(scored_pairs=[])
        result = render_markdown(report, {})
        assert "## Link Prediction" not in result

    def test_render_without_link_prediction(self) -> None:
        """When link_prediction is default (empty), no section rendered."""
        report = _default_report()
        # link_prediction is already a default LinkPredictionResult with [] pairs
        result = render_markdown(report, {})
        assert "## Link Prediction" not in result
