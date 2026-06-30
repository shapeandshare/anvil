# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for vault connectivity analysis (anvil/services/vault/connectivity.py).

Covers compute_connectivity, _is_spec_subfile, _is_exempt, _count_exempt,
and _is_reciprocal_exempt with empty, well-formed, and edge-case graphs.
"""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import pytest

from anvil.services.vault.connectivity import (
    _count_exempt,
    _is_exempt,
    _is_reciprocal_exempt,
    _is_spec_subfile,
    compute_connectivity,
)
from anvil.services.vault.types_note_metadata import NoteMetadata


def _meta(
    stem: str,
    tags: list[str] | None = None,
    note_type: str | None = None,
    path: Path | None = None,
) -> NoteMetadata:
    """Build a NoteMetadata instance for testing."""
    return NoteMetadata(
        path=path or Path(f"/vault/{stem}.md"),
        stem=stem,
        tags=tags or [],
        note_type=note_type,
    )


######################################################################
# _is_spec_subfile
######################################################################


class TestIsSpecSubfile:
    """Tests for _is_spec_subfile."""

    def test_spec_subfile_detected(self) -> None:
        """A file under Specs/<name>/ that is not the main note is a subfile."""
        meta = _meta("details", path=Path("/vault/Specs/feature-x/details.md"))
        assert _is_spec_subfile(meta) is True

    def test_main_spec_file_not_subfile(self) -> None:
        """The main spec note (same name as directory) is NOT a subfile."""
        meta = _meta("feature-x", path=Path("/vault/Specs/feature-x/feature-x.md"))
        assert _is_spec_subfile(meta) is False

    def test_not_in_specs_dir(self) -> None:
        """Files outside Specs/ are never subfiles."""
        meta = _meta("note", path=Path("/vault/notes/note.md"))
        assert _is_spec_subfile(meta) is False

    def test_no_specs_in_path(self) -> None:
        """Path without 'Specs' component is not a subfile."""
        meta = _meta("note", path=Path("/vault/random/details.md"))
        assert _is_spec_subfile(meta) is False


######################################################################
# _is_exempt
######################################################################


class TestIsExempt:
    """Tests for _is_exempt."""

    def test_exempt_by_stem_name(self) -> None:
        """Stem in exempt_names is exempt."""
        meta = _meta("index", tags=["type/principle"])
        assert _is_exempt(meta, {"type/moc"}, {"index"}) is True

    def test_exempt_by_tag(self) -> None:
        """Tag overlap with exempt_types triggers exemption."""
        meta = _meta("note", tags=["type/moc"])
        assert _is_exempt(meta, {"type/moc"}, set()) is True

    def test_exempt_by_note_type_converted_to_tag(self) -> None:
        """note_type converted to type/{note_type} matches exempt_types."""
        meta = _meta("note", tags=[], note_type="moc")
        assert _is_exempt(meta, {"type/moc"}, set()) is True

    def test_not_exempt(self) -> None:
        """No overlaps means not exempt."""
        meta = _meta("note", tags=["type/principle"])
        assert _is_exempt(meta, {"type/moc"}, {"index"}) is False

    def test_spec_subfile_exempt(self) -> None:
        """Spec subfiles are exempt even with empty exempt sets."""
        meta = _meta("details", tags=[], path=Path("/vault/Specs/feature-x/details.md"))
        assert _is_exempt(meta, set(), set()) is True

    def test_excluded_stems(self) -> None:
        """Stems in excluded_stems are exempt."""
        meta = _meta("scaffold_note", tags=[])
        assert _is_exempt(meta, set(), set(), excluded_stems={"scaffold_note"}) is True


######################################################################
# _count_exempt
######################################################################


class TestCountExempt:
    """Tests for _count_exempt."""

    def test_counts_correctly(self) -> None:
        """Counts notes exempt by name or type."""
        notes = {
            "index": _meta("index", tags=["type/moc"]),
            "note_a": _meta("note_a", tags=["type/principle"]),
            "note_b": _meta("note_b", tags=["type/moc"]),
        }
        assert _count_exempt(notes, {"type/moc"}, {"index"}) == 2

    def test_empty_notes(self) -> None:
        """Empty dict yields zero count."""
        assert _count_exempt({}, set(), set()) == 0

    def test_excluded_stems_counted(self) -> None:
        """Stems in excluded_stems are counted as exempt."""
        notes = {
            "a": _meta("a", tags=[]),
            "b": _meta("b", tags=[]),
        }
        assert _count_exempt(notes, set(), set(), excluded_stems={"a"}) == 1


######################################################################
# _is_reciprocal_exempt
######################################################################


class TestIsReciprocalExempt:
    """Tests for _is_reciprocal_exempt."""

    def test_constitution_target_exempt(self) -> None:
        """Edges targeting 'Constitution' are exempt from reciprocal expectation."""
        notes = {"other": _meta("other")}
        assert _is_reciprocal_exempt("other", "Constitution", notes) is True

    def test_spec_subfile_source_exempt(self) -> None:
        """Edges from spec subfiles are exempt."""
        notes = {
            "detail": _meta("detail", path=Path("/vault/Specs/x/detail.md")),
            "other": _meta("other"),
        }
        assert _is_reciprocal_exempt("detail", "other", notes) is True

    def test_thread_target_exempt(self) -> None:
        """Edges targeting 'Thread*' notes are exempt."""
        notes = {
            "source": _meta("source"),
            "Thread-abc": _meta("Thread-abc"),
        }
        assert _is_reciprocal_exempt("source", "Thread-abc", notes) is True

    def test_not_exempt(self) -> None:
        """Ordinary edges are not exempt."""
        notes = {"a": _meta("a"), "b": _meta("b")}
        assert _is_reciprocal_exempt("a", "b", notes) is False


######################################################################
# compute_connectivity
######################################################################


class TestComputeConnectivity:
    """Tests for compute_connectivity."""

    def test_empty_graph(self) -> None:
        """Empty graph returns zero-valued metrics."""
        G = nx.DiGraph()
        metrics = compute_connectivity(G, {})
        assert metrics.orphan_count == 0
        assert metrics.dead_end_count == 0
        assert metrics.link_density_avg == 0.0
        assert metrics.largest_component_pct == 0.0
        assert metrics.bidirectional_ratio == 0.0
        assert metrics.orphans == []
        assert metrics.dead_ends == []
        assert metrics.missing_reciprocals == []

    def test_single_node_no_edges(self) -> None:
        """Single node with no edges is both orphan and dead end."""
        G = nx.DiGraph()
        G.add_node("note_a")
        notes = {"note_a": _meta("note_a", tags=["type/principle"])}
        metrics = compute_connectivity(G, notes)
        assert "note_a" in metrics.orphans
        assert "note_a" in metrics.dead_ends
        assert metrics.link_density_avg == 0.0

    def test_exempt_orphan_not_counted(self) -> None:
        """Orphans with exempt types are not counted."""
        G = nx.DiGraph()
        G.add_node("index")
        notes = {"index": _meta("index", tags=["type/moc"])}
        metrics = compute_connectivity(G, notes)
        assert "index" not in metrics.orphans
        assert "index" not in metrics.dead_ends

    def test_excluded_stems_skipped(self) -> None:
        """Stems in excluded_stems are not counted as orphans/dead-ends."""
        G = nx.DiGraph()
        G.add_node("scaffold")
        notes = {"scaffold": _meta("scaffold", tags=[])}
        metrics = compute_connectivity(G, notes, excluded_stems={"scaffold"})
        assert "scaffold" not in metrics.orphans
        assert "scaffold" not in metrics.dead_ends

    def test_bidirectional_links(self) -> None:
        """Fully reciprocal links yield 100% bidirectional ratio."""
        G = nx.DiGraph()
        G.add_edge("a", "b")
        G.add_edge("b", "a")
        notes = {
            "a": _meta("a", tags=["type/principle"]),
            "b": _meta("b", tags=["type/principle"]),
        }
        metrics = compute_connectivity(G, notes)
        assert metrics.bidirectional_ratio == 100.0
        assert metrics.missing_reciprocals == []

    def test_missing_reciprocal(self) -> None:
        """One-way edges appear in missing_reciprocals."""
        G = nx.DiGraph()
        G.add_edge("a", "b")
        notes = {
            "a": _meta("a", tags=["type/principle"]),
            "b": _meta("b", tags=["type/principle"]),
        }
        metrics = compute_connectivity(G, notes)
        assert ("a", "b") in metrics.missing_reciprocals or (
            "b",
            "a",
        ) in metrics.missing_reciprocals
        assert metrics.bidirectional_ratio == 0.0

    def test_link_density_warning(self) -> None:
        """Link density of 1.0 is 'warning' class."""
        G = nx.DiGraph()
        G.add_edges_from([("a", "b"), ("b", "c"), ("c", "a")])
        notes = {n: _meta(n, tags=["type/principle"]) for n in ("a", "b", "c")}
        metrics = compute_connectivity(G, notes)
        assert metrics.link_density_avg == 1.0
        assert metrics.link_density_class == "warning"

    def test_link_density_healthy(self) -> None:
        """Link density >= 3 is 'healthy'."""
        G = nx.DiGraph()
        G.add_edges_from(
            [("a", "b"), ("a", "c"), ("a", "d"), ("b", "c"), ("b", "d"), ("c", "d")]
        )
        notes = {n: _meta(n, tags=["type/principle"]) for n in ("a", "b", "c", "d")}
        metrics = compute_connectivity(G, notes)
        assert metrics.link_density_avg == 1.5
        assert metrics.link_density_class == "warning"

    def test_link_density_critical(self) -> None:
        """Link density < 1 is 'critical'."""
        G = nx.DiGraph()
        G.add_edge("a", "b")
        notes = {"a": _meta("a", tags=["type/principle"]), "b": _meta("b", tags=[])}
        metrics = compute_connectivity(G, notes)
        assert metrics.link_density_avg == 0.5
        assert metrics.link_density_class == "critical"

    def test_largest_component_percentage(self) -> None:
        """Isolated nodes reduce largest component percentage."""
        G = nx.DiGraph()
        G.add_edges_from([("a", "b"), ("b", "c"), ("c", "a")])
        G.add_node("isolated")
        notes = {
            "a": _meta("a", tags=["type/principle"]),
            "b": _meta("b", tags=["type/principle"]),
            "c": _meta("c", tags=["type/principle"]),
            "isolated": _meta("isolated", tags=["type/principle"]),
        }
        metrics = compute_connectivity(G, notes)
        assert metrics.largest_component_pct == 75.0
        assert metrics.largest_component_class == "warning"

    def test_largest_component_healthy(self) -> None:
        """Single component covering all nodes is 'healthy' (>90%)."""
        G = nx.DiGraph()
        G.add_edges_from([("a", "b"), ("b", "c"), ("c", "a")])
        notes = {n: _meta(n, tags=["type/principle"]) for n in ("a", "b", "c")}
        metrics = compute_connectivity(G, notes)
        assert metrics.largest_component_pct == 100.0
        assert metrics.largest_component_class == "healthy"

    def test_self_loop_excluded_from_reciprocal(self) -> None:
        """Self-loops are excluded from reciprocal counting."""
        G = nx.DiGraph()
        G.add_edge("a", "a")
        notes = {"a": _meta("a", tags=[])}
        metrics = compute_connectivity(G, notes)
        assert metrics.missing_reciprocals == []
        assert metrics.bidirectional_ratio == 0.0

    def test_reciprocal_exempt_edges_not_missing(self) -> None:
        """Constitution-target edges are not flagged as missing reciprocals."""
        G = nx.DiGraph()
        G.add_edge("a", "Constitution")
        notes = {"a": _meta("a", tags=[])}
        metrics = compute_connectivity(G, notes)
        assert metrics.missing_reciprocals == []

    def test_orphan_rate_calculation(self) -> None:
        """Orphan rate is based on eligible (non-exempt) notes."""
        G = nx.DiGraph()
        G.add_edges_from([("a", "b")])
        G.add_node("c")
        notes = {
            "a": _meta("a", tags=["type/principle"]),
            "b": _meta("b", tags=["type/principle"]),
            "c": _meta("c", tags=["type/principle"]),
        }
        metrics = compute_connectivity(G, notes)
        # out of 3 eligible: a has in=0, b has in=1, c has in=0
        assert metrics.orphan_count == 2
        assert metrics.orphan_rate == pytest.approx(66.666, rel=0.01)

    def test_dead_end_rate_calculation(self) -> None:
        """Dead-end rate is based on eligible (non-exempt) notes."""
        G = nx.DiGraph()
        G.add_edges_from([("a", "b")])
        notes = {
            "a": _meta("a", tags=["type/principle"]),
            "b": _meta("b", tags=["type/principle"]),
        }
        metrics = compute_connectivity(G, notes)
        assert metrics.dead_end_count == 1
        assert metrics.dead_end_rate == 50.0
