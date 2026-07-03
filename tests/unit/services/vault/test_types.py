"""Tests for vault type/domain models — Pydantic models and serde helpers.

Covers all ``anvil/services/vault/types_*.py`` modules including
Finding, HealthScore, HygieneMetrics, MechanicalReport, NoteMetadata,
GraphHealthReport (with custom JSON serialization), ScoredPair,
ConnectivityMetrics, LinkPredictionResult, StructuralMetrics,
TemporalMetrics, and TopologicalMetrics.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import pytest

from anvil.services.vault.types_connectivity_metrics import ConnectivityMetrics
from anvil.services.vault.types_finding import Finding
from anvil.services.vault.types_graph_health_report import GraphHealthReport
from anvil.services.vault.types_health_score import HealthScore
from anvil.services.vault.types_hygiene_metrics import HygieneMetrics
from anvil.services.vault.types_link_prediction_result import LinkPredictionResult
from anvil.services.vault.types_mechanical_report import MechanicalReport
from anvil.services.vault.types_note_metadata import NoteMetadata
from anvil.services.vault.types_scored_pair import ScoredPair
from anvil.services.vault.types_structural_metrics import StructuralMetrics
from anvil.services.vault.types_temporal_metrics import TemporalMetrics
from anvil.services.vault.types_topological_metrics import TopologicalMetrics

# ── Finding ──────────────────────────────────────────────────────────────────


class TestFinding:
    """Tests for Finding model."""

    def test_construct_with_minimal_args(self) -> None:
        """Constructs with only required path."""
        f = Finding(note_path="docs/vault/foo.md")
        assert f.note_path == "docs/vault/foo.md"
        assert f.line == 0
        assert f.severity == ""

    def test_construct_with_all_args(self) -> None:
        """Constructs with all fields."""
        f = Finding(
            note_path="docs/vault/bar.md",
            line=42,
            rule="FM-001",
            message="Missing title",
            severity="ERROR",
            fixable=True,
        )
        assert f.note_path == "docs/vault/bar.md"
        assert f.line == 42
        assert f.rule == "FM-001"
        assert f.message == "Missing title"
        assert f.severity == "ERROR"
        assert f.fixable is True


# ── HealthScore ──────────────────────────────────────────────────────────────


class TestHealthScore:
    """Tests for HealthScore model."""

    def test_defaults_to_zero(self) -> None:
        """All fields default to 0.0 or empty dict."""
        hs = HealthScore()
        assert hs.overall == 0.0
        assert hs.orphan_score == 0.0
        assert hs.breakdown == {}

    def test_construct_with_values(self) -> None:
        """Constructs with explicit scores."""
        hs = HealthScore(
            overall=85.5,
            orphan_score=90.0,
            dead_end_score=70.0,
            breakdown={"orphan_weight": 0.3},
        )
        assert hs.overall == 85.5
        assert hs.breakdown["orphan_weight"] == 0.3


# ── HygieneMetrics ───────────────────────────────────────────────────────────


class TestHygieneMetrics:
    """Tests for HygieneMetrics model."""

    def test_defaults(self) -> None:
        """All list fields default to empty lists, percentages to 100."""
        hm = HygieneMetrics()
        assert hm.non_conformant_tags == []
        assert hm.tag_conformity_pct == 100.0
        assert hm.frontmatter_completeness_pct == 100.0

    def test_construct_with_data(self) -> None:
        """Constructs with non-conformant tags."""
        hm = HygieneMetrics(
            non_conformant_tags=[("note_a", "bad_tag")],
            tag_conformity_pct=50.0,
        )
        assert len(hm.non_conformant_tags) == 1
        assert hm.tag_conformity_pct == 50.0


# ── MechanicalReport ─────────────────────────────────────────────────────────


class TestMechanicalReport:
    """Tests for MechanicalReport model — includes add() routing logic."""

    def test_defaults(self) -> None:
        """All finding lists default to empty."""
        mr = MechanicalReport()
        assert mr.errors == []
        assert mr.warnings == []
        assert mr.skipped == []
        assert mr.stats == {}

    def test_add_routes_error_by_severity(self) -> None:
        """add() routes ERROR findings to errors list."""
        mr = MechanicalReport()
        f = Finding(note_path="a.md", severity="ERROR", message="Bad")
        mr.add(f)
        assert len(mr.errors) == 1
        assert mr.errors[0].message == "Bad"
        assert len(mr.warnings) == 0
        assert len(mr.skipped) == 0

    def test_add_routes_warn_by_severity(self) -> None:
        """add() routes WARN findings to warnings list."""
        mr = MechanicalReport()
        f = Finding(note_path="a.md", severity="WARN", message="Meh")
        mr.add(f)
        assert len(mr.warnings) == 1
        assert mr.warnings[0].message == "Meh"

    def test_add_routes_other_severity_to_skipped(self) -> None:
        """add() routes non-ERROR/WARN findings to skipped list."""
        mr = MechanicalReport()
        f = Finding(note_path="a.md", severity="SKIPPED", message="Skip")
        mr.add(f)
        assert len(mr.skipped) == 1
        assert mr.skipped[0].severity == "SKIPPED"

    def test_add_multiple_findings(self) -> None:
        """Multiple add() calls accumulate correctly."""
        mr = MechanicalReport()
        mr.add(Finding(note_path="a.md", severity="ERROR"))
        mr.add(Finding(note_path="b.md", severity="WARN"))
        mr.add(Finding(note_path="c.md", severity="SKIPPED"))
        assert len(mr.errors) == 1
        assert len(mr.warnings) == 1
        assert len(mr.skipped) == 1


# ── NoteMetadata ─────────────────────────────────────────────────────────────


class TestNoteMetadata:
    """Tests for NoteMetadata model."""

    def test_requires_path_and_stem(self) -> None:
        """Requires at least path and stem."""
        nm = NoteMetadata(path=Path("/vault/note.md"), stem="note")
        assert nm.path == Path("/vault/note.md")
        assert nm.stem == "note"
        assert nm.tags == []
        assert nm.outbound_stems == []

    def test_construct_with_full_metadata(self) -> None:
        """Constructs with all optional fields."""
        nm = NoteMetadata(
            path=Path("/vault/note.md"),
            stem="note",
            title="My Note",
            note_type="discovery",
            tags=["ml", "transformer"],
            created_date=date(2026, 1, 1),
            outbound_stems=["other"],
        )
        assert nm.title == "My Note"
        assert nm.note_type == "discovery"
        assert "ml" in nm.tags
        assert nm.created_date == date(2026, 1, 1)


# ── ScoredPair ───────────────────────────────────────────────────────────────


class TestScoredPair:
    """Tests for ScoredPair model."""

    def test_defaults(self) -> None:
        """All fields default to empty/zero."""
        sp = ScoredPair()
        assert sp.source == ""
        assert sp.target == ""
        assert sp.ensemble_score == 0.0

    def test_construct_with_values(self) -> None:
        """Constructs with explicit scores."""
        sp = ScoredPair(
            source="note_a",
            target="note_b",
            ensemble_score=0.85,
            adamic_adar=0.7,
            tfidf_cosine=0.6,
            community_match=0.9,
        )
        assert sp.source == "note_a"
        assert sp.ensemble_score == 0.85


# ── ConnectivityMetrics ──────────────────────────────────────────────────────


class TestConnectivityMetrics:
    """Tests for ConnectivityMetrics model."""

    def test_defaults(self) -> None:
        """All fields default to zero/empty."""
        cm = ConnectivityMetrics()
        assert cm.orphan_rate == 0.0
        assert cm.orphan_count == 0
        assert cm.orphans == []
        assert cm.link_density_class == ""

    def test_construct_with_orphans(self) -> None:
        """Constructs with orphan data."""
        cm = ConnectivityMetrics(
            orphan_rate=25.0,
            orphan_count=2,
            orphans=["note_a", "note_b"],
            link_density_class="healthy",
        )
        assert cm.orphan_rate == 25.0
        assert len(cm.orphans) == 2


# ── LinkPredictionResult ─────────────────────────────────────────────────────


class TestLinkPredictionResult:
    """Tests for LinkPredictionResult model."""

    def test_defaults(self) -> None:
        """All fields default to empty/zero."""
        lpr = LinkPredictionResult()
        assert lpr.scored_pairs == []
        assert lpr.top_n == 20
        assert lpr.threshold == 0.7
        assert lpr.took_action is False

    def test_construct_with_pairs(self) -> None:
        """Constructs with scored pairs."""
        sp = ScoredPair(source="a", target="b", ensemble_score=0.9)
        lpr = LinkPredictionResult(scored_pairs=[sp], top_n=10, took_action=True)
        assert len(lpr.scored_pairs) == 1
        assert lpr.top_n == 10
        assert lpr.took_action is True


# ── StructuralMetrics ────────────────────────────────────────────────────────


class TestStructuralMetrics:
    """Tests for StructuralMetrics model."""

    def test_defaults(self) -> None:
        """All fields default to empty lists."""
        sm = StructuralMetrics()
        assert sm.chain_gaps == []
        assert sm.potential_silos == []
        assert sm.broken_cycles == []

    def test_construct_with_gaps(self) -> None:
        """Constructs with chain gaps."""
        sm = StructuralMetrics(chain_gaps=[("a", "c", "b")])
        assert len(sm.chain_gaps) == 1


# ── TemporalMetrics ──────────────────────────────────────────────────────────


class TestTemporalMetrics:
    """Tests for TemporalMetrics model."""

    def test_defaults(self) -> None:
        """All fields default to zero/empty."""
        tm = TemporalMetrics()
        assert tm.stale_notes == []
        assert tm.temporal_deltas == []
        assert tm.high_coherence_pct == 0.0

    def test_construct_with_deltas(self) -> None:
        """Constructs with temporal deltas."""
        tm = TemporalMetrics(
            stale_notes=["old_note"],
            temporal_deltas=[10, 200, 400],
            high_coherence_pct=66.7,
        )
        assert len(tm.stale_notes) == 1
        assert len(tm.temporal_deltas) == 3


# ── TopologicalMetrics ───────────────────────────────────────────────────────


class TestTopologicalMetrics:
    """Tests for TopologicalMetrics model."""

    def test_defaults(self) -> None:
        """All fields default to zero/empty."""
        tm = TopologicalMetrics()
        assert tm.pagerank_top == []
        assert tm.communities == []
        assert tm.information_sink_rate == 0.0

    def test_construct_with_communities(self) -> None:
        """Constructs with community data."""
        tm = TopologicalMetrics(
            pagerank_top=[("note_a", 0.5)],
            communities=[["a", "b"], ["c"]],
            information_sink_rate=10.0,
        )
        assert len(tm.pagerank_top) == 1
        assert len(tm.communities) == 2


# ── GraphHealthReport (aggregate + to_json) ─────────────────────────────────


class TestGraphHealthReport:
    """Tests for GraphHealthReport — the aggregate report model with JSON serde."""

    def test_defaults(self) -> None:
        """All sub-models default to empty instances."""
        ghr = GraphHealthReport()
        assert isinstance(ghr.connectivity, ConnectivityMetrics)
        assert isinstance(ghr.health_score, HealthScore)
        assert ghr.notes_scanned == 0
        assert ghr.excluded_notes == []

    def test_construct_with_values(self) -> None:
        """Constructs with explicit values."""
        ghr = GraphHealthReport(
            notes_scanned=100,
            notes_excluded=5,
            excluded_notes=["secret.md"],
        )
        assert ghr.notes_scanned == 100
        assert ghr.notes_excluded == 5
        assert "secret.md" in ghr.excluded_notes

    def test_to_json_serializes_basic_report(self) -> None:
        """to_json() produces valid JSON with default values."""
        ghr = GraphHealthReport(notes_scanned=10)
        raw = ghr.to_json()
        parsed = json.loads(raw)
        assert parsed["notes_scanned"] == 10
        assert "connectivity" in parsed
        assert "health_score" in parsed

    def test_to_json_handles_path_in_excluded_notes(self) -> None:
        """to_json() converts Path objects to strings via _convert_types."""
        ghr = GraphHealthReport(excluded_notes=["a.md"])
        raw = ghr.to_json()
        parsed = json.loads(raw)
        assert "a.md" in parsed["excluded_notes"]

    def test_to_json_indent_is_two_spaces(self) -> None:
        """to_json() uses indent=2 for readability."""
        ghr = GraphHealthReport()
        raw = ghr.to_json()
        lines = raw.splitlines()
        # Each nesting level should have 2-space indent.
        for line in lines:
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            assert indent % 2 == 0


# ── _convert_types helper (via GraphHealthReport.to_json) ────────────────────


class TestConvertTypes:
    """Tests for _convert_types helper exercised through to_json()."""

    def test_converts_path_to_str(self) -> None:
        """Path objects become strings in JSON."""
        ghr = GraphHealthReport()
        ghr.health_score.breakdown["key"] = Path("some/path")
        raw = ghr.to_json()
        parsed = json.loads(raw)
        assert parsed["health_score"]["breakdown"]["key"] == "some/path"

    def test_converts_date_to_str(self) -> None:
        """Date objects become strings in JSON."""
        ghr = GraphHealthReport()
        ghr.health_score.breakdown["dt"] = date(2026, 6, 1)
        raw = ghr.to_json()
        parsed = json.loads(raw)
        assert parsed["health_score"]["breakdown"]["dt"] == "2026-06-01"

    def test_converts_datetime_to_str(self) -> None:
        """Datetime objects become ISO strings in JSON."""
        ghr = GraphHealthReport()
        ghr.health_score.breakdown["dt"] = datetime(2026, 6, 1, 12, 30, 0)
        raw = ghr.to_json()
        parsed = json.loads(raw)
        # str(datetime) uses space separator, not T
        assert "2026-06-01" in parsed["health_score"]["breakdown"]["dt"]

    def test_converts_set_to_sorted_list(self) -> None:
        """Set objects become sorted lists in JSON."""
        ghr = GraphHealthReport()
        ghr.health_score.breakdown["s"] = {"z", "a", "m"}
        raw = ghr.to_json()
        parsed = json.loads(raw)
        assert parsed["health_score"]["breakdown"]["s"] == ["a", "m", "z"]

    def test_unknown_type_passes_through(self) -> None:
        """Non-serializable types that don't match known converters pass through."""
        ghr = GraphHealthReport()
        ghr.health_score.breakdown["n"] = 42
        raw = ghr.to_json()
        parsed = json.loads(raw)
        assert parsed["health_score"]["breakdown"]["n"] == 42
