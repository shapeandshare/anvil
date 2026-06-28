# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for vault connectivity analysis (anvil/services/vault/connectivity.py)."""

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
    return NoteMetadata(
        path=path or Path(f"/vault/{stem}.md"),
        stem=stem,
        tags=tags or [],
        note_type=note_type,
    )


class TestIsSpecSubfile:
    """Tests for _is_spec_subfile."""

    def test_spec_subfile_detected(self) -> None:
        meta = _meta(
            "details",
            path=Path("/vault/Specs/feature-x/details.md"),
        )
        assert _is_spec_subfile(meta) is True

    def test_main_spec_file_not_subfile(self) -> None:
        meta = _meta(
            "feature-x",
            path=Path("/vault/Specs/feature-x/feature-x.md"),
        )
        assert _is_spec_subfile(meta) is False

    def test_not_in_specs_dir(self) -> None:
        meta = _meta("note", path=Path("/vault/notes/note.md"))
        assert _is_spec_subfile(meta) is False

    def test_no_specs_in_path(self) -> None:
        meta = _meta("note", path=Path("/vault/random/details.md"))
        assert _is_spec_subfile(meta) is False


class TestIsExempt:
    """Tests for _is_exempt."""

    def test_exempt_by_stem_name(self) -> None:
        meta = _meta("index", tags=["type/principle"])
        assert _is_exempt(meta, {"type/moc"}, {"index"}) is True

    def test_exempt_by_tag(self) -> None:
        meta = _meta("note", tags=["type/moc"])
        assert _is_exempt(meta, {"type/moc"}, set()) is True

    def test_exempt_by_note_type(self) -> None:
        meta = _meta("note", tags=[], note_type="moc")
        assert _is_exempt(meta, {"type/moc"}, set()) is True

    def test_not_exempt(self) -> None:
        meta = _meta("note", tags=["type/principle"])
        assert _is_exempt(meta, {"type/moc"}, {"index"}) is False

    def test_spec_subfile_exempt(self) -> None:
        meta = _meta(
            "details",
            tags=[],
            path=Path("/vault/Specs/feature-x/details.md"),
        )
        assert _is_exempt(meta, set(), set()) is True


class TestCountExempt:
    """Tests for _count_exempt."""

    def test_counts_exempt_notes(self) -> None:
        notes = {
            "index": _meta("index", tags=["type/moc"]),
            "note_a": _meta("note_a", tags=["type/principle"]),
            "note_b": _meta("note_b", tags=["type/moc"]),
        }
        count = _count_exempt(notes, {"type/moc"}, {"index"})
        assert count == 2

    def test_empty_notes(self) -> None:
        assert _count_exempt({}, set(), set()) == 0


class TestIsReciprocalExempt:
    """Tests for _is_reciprocal_exempt."""

    def test_constitution_target_exempt(self) -> None:
        notes = {"other": _meta("other")}
        assert _is_reciprocal_exempt("other", "Constitution", notes) is True

    def test_spec_subfile_source_exempt(self) -> None:
        notes = {
            "detail": _meta("detail", path=Path("/vault/Specs/x/detail.md")),
            "other": _meta("other"),
        }
        assert _is_reciprocal_exempt("detail", "other", notes) is True

    def test_thread_target_exempt(self) -> None:
        notes = {
            "source": _meta("source"),
            "Thread-abc": _meta("Thread-abc"),
        }
        assert _is_reciprocal_exempt("source", "Thread-abc", notes) is True

    def test_not_exempt(self) -> None:
        notes = {
            "a": _meta("a"),
            "b": _meta("b"),
        }
        assert _is_reciprocal_exempt("a", "b", notes) is False


class TestComputeConnectivity:
    """Tests for compute_connectivity."""

    def test_empty_graph(self) -> None:
        G = nx.DiGraph()
        metrics = compute_connectivity(G, {})
        assert metrics.orphan_count == 0
        assert metrics.dead_end_count == 0
        assert metrics.link_density_avg == 0.0
        assert metrics.largest_component_pct == 0.0
        assert metrics.bidirectional_ratio == 0.0

    def test_single_node_no_edges(self) -> None:
        G = nx.DiGraph()
        G.add_node("note_a")
        notes = {"note_a": _meta("note_a", tags=["type/principle"])}
        metrics = compute_connectivity(G, notes)
        assert "note_a" in metrics.orphans
        assert "note_a" in metrics.dead_ends
        assert metrics.link_density_avg == 0.0

    def test_exempt_orphan_not_counted(self) -> None:
        G = nx.DiGraph()
        G.add_node("index")
        notes = {"index": _meta("index", tags=["type/moc"])}
        metrics = compute_connectivity(G, notes)
        assert "index" not in metrics.orphans
        assert "index" not in metrics.dead_ends

    def test_bidirectional_links(self) -> None:
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

    def test_link_density_classification(self) -> None:
        """Test link density classes."""
        G = nx.DiGraph()
        G.add_edges_from([("a", "b"), ("b", "c"), ("c", "a")])
        notes = {n: _meta(n, tags=["type/principle"]) for n in ("a", "b", "c")}
        metrics = compute_connectivity(G, notes)
        assert metrics.link_density_avg == 1.0
        assert metrics.link_density_class == "warning"

    def test_largest_component(self) -> None:
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
