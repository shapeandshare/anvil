# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for vault topology analysis (anvil/services/vault/topology.py)."""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import pytest

from anvil.services.vault.types_note_metadata import NoteMetadata
from anvil.services.vault.topology import _community_has_moc, compute_topological


def _meta(
    stem: str, tags: list[str] | None = None, note_type: str | None = None
) -> NoteMetadata:
    return NoteMetadata(
        path=Path(f"/vault/{stem}.md"),
        stem=stem,
        tags=tags or [],
        note_type=note_type,
    )


class TestCommunityHasMoc:
    """Tests for _community_has_moc."""

    def test_has_moc_by_tag(self) -> None:
        community = ["a", "b"]
        notes = {
            "a": _meta("a", tags=["type/moc"]),
            "b": _meta("b", tags=["type/principle"]),
        }
        assert _community_has_moc(community, notes) is True

    def test_has_moc_by_note_type(self) -> None:
        community = ["a", "b"]
        notes = {
            "a": _meta("a", note_type="moc"),
            "b": _meta("b", tags=["type/principle"]),
        }
        assert _community_has_moc(community, notes) is True

    def test_no_moc(self) -> None:
        community = ["a", "b"]
        notes = {
            "a": _meta("a", tags=["type/principle"]),
            "b": _meta("b", tags=["type/design"]),
        }
        assert _community_has_moc(community, notes) is False

    def test_empty_community(self) -> None:
        assert _community_has_moc([], {}) is False

    def test_missing_note_metadata(self) -> None:
        community = ["a", "b"]
        notes = {"a": _meta("a", tags=["type/principle"])}  # 'b' missing
        assert _community_has_moc(community, notes) is False


class TestComputeTopological:
    """Tests for compute_topological."""

    def test_empty_graph(self) -> None:
        G = nx.DiGraph()
        metrics = compute_topological(G, {})
        assert metrics.pagerank_top == []
        assert metrics.betweenness_bridges == []
        assert metrics.communities == []
        assert metrics.information_sinks == []
        assert metrics.information_sink_rate == 0.0

    def test_single_node(self) -> None:
        G = nx.DiGraph()
        G.add_node("a")
        notes = {"a": _meta("a", tags=["type/principle"])}
        metrics = compute_topological(G, notes)
        assert len(metrics.pagerank_top) == 1
        assert metrics.pagerank_top[0][0] == "a"
        assert len(metrics.communities) >= 1
        assert metrics.information_sinks == []

    def test_simple_graph(self) -> None:
        G = nx.DiGraph()
        G.add_edges_from([("a", "b"), ("b", "c"), ("c", "a")])
        notes = {
            "a": _meta("a", tags=["type/principle"]),
            "b": _meta("b", tags=["type/principle"]),
            "c": _meta("c", tags=["type/principle"]),
        }
        metrics = compute_topological(G, notes)
        assert len(metrics.pagerank_top) == 1
        assert len(metrics.betweenness_bridges) >= 0
        assert len(metrics.communities) >= 1

    def test_information_sinks_detected(self) -> None:
        G = nx.DiGraph()
        G.add_edges_from([("a", "b"), ("a", "c"), ("b", "c")])
        notes = {
            "a": _meta("a", tags=["type/principle"]),
            "b": _meta("b", tags=["type/principle"]),
            "c": _meta("c", tags=["type/principle"]),
        }
        metrics = compute_topological(G, notes)
        assert "c" in metrics.information_sinks
        assert metrics.information_sink_rate > 0

    def test_isolated_node_not_a_sink(self) -> None:
        """Nodes with both in_degree==0 and out_degree==0 should be skipped."""
        G = nx.DiGraph()
        G.add_node("isolated")
        notes = {"isolated": _meta("isolated", tags=["type/principle"])}
        metrics = compute_topological(G, notes)
        assert "isolated" not in metrics.information_sinks

    def test_communities_needing_moc(self) -> None:
        G = nx.DiGraph()
        nodes = [f"n{i}" for i in range(5)]
        for i in range(4):
            G.add_edge(nodes[i], nodes[i + 1])
        notes = {n: _meta(n, tags=["type/principle"]) for n in nodes}
        metrics = compute_topological(G, notes)
        for community in metrics.communities_needing_moc:
            assert len(community) >= 5

    def test_sink_classification(self) -> None:
        G = nx.DiGraph()
        for i in range(25):
            G.add_edge(f"n{i}", f"n{(i+1) % 25}")
        notes = {f"n{i}": _meta(f"n{i}", tags=["type/principle"]) for i in range(25)}
        metrics = compute_topological(G, notes)
        assert metrics.information_sink_rate == 0.0
        assert metrics.information_sink_class == "healthy"
        metrics = compute_topological(G, notes)
        assert metrics.information_sink_rate == 0.0
        assert metrics.information_sink_class == "healthy"
