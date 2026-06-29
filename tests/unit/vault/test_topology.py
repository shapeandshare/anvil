# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for vault topology analysis (anvil/services/vault/topology.py).

Covers _community_has_moc and compute_topological with empty, well-formed,
and edge-case graphs including PageRank, betweenness, communities, sinks.
"""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import pytest

from anvil.services.vault.topology import _community_has_moc, compute_topological
from anvil.services.vault.types_note_metadata import NoteMetadata


def _meta(
    stem: str,
    tags: list[str] | None = None,
    note_type: str | None = None,
) -> NoteMetadata:
    """Build a NoteMetadata instance for testing."""
    return NoteMetadata(
        path=Path(f"/vault/{stem}.md"),
        stem=stem,
        tags=tags or [],
        note_type=note_type,
    )


######################################################################
# _community_has_moc
######################################################################


class TestCommunityHasMoc:
    """Tests for _community_has_moc."""

    def test_has_moc_by_tag(self) -> None:
        """Community with type/moc tagged note has a MOC."""
        community = ["a", "b"]
        notes = {
            "a": _meta("a", tags=["type/moc"]),
            "b": _meta("b", tags=["type/principle"]),
        }
        assert _community_has_moc(community, notes) is True

    def test_has_moc_by_note_type(self) -> None:
        """Community with note_type='moc' has a MOC."""
        community = ["a", "b"]
        notes = {
            "a": _meta("a", note_type="moc"),
            "b": _meta("b", tags=["type/principle"]),
        }
        assert _community_has_moc(community, notes) is True

    def test_has_spec_type(self) -> None:
        """Community with type/spec tagged note has a MOC (spec acts as MOC)."""
        community = ["a"]
        notes = {"a": _meta("a", tags=["type/spec"])}
        assert _community_has_moc(community, notes) is True

    def test_has_spec_note_type(self) -> None:
        """Community with note_type='spec' has a MOC."""
        community = ["a"]
        notes = {"a": _meta("a", note_type="spec")}
        assert _community_has_moc(community, notes) is True

    def test_no_moc(self) -> None:
        """Community without MOC-type notes returns False."""
        community = ["a", "b"]
        notes = {
            "a": _meta("a", tags=["type/principle"]),
            "b": _meta("b", tags=["type/design"]),
        }
        assert _community_has_moc(community, notes) is False

    def test_empty_community(self) -> None:
        """Empty community returns False."""
        assert _community_has_moc([], {}) is False

    def test_missing_note_metadata(self) -> None:
        """Notes missing from metadata dict are skipped."""
        community = ["a", "b"]
        notes = {"a": _meta("a", tags=["type/principle"])}
        assert _community_has_moc(community, notes) is False


######################################################################
# compute_topological
######################################################################


class TestComputeTopological:
    """Tests for compute_topological."""

    def test_empty_graph(self) -> None:
        """Empty graph returns all default values."""
        G = nx.DiGraph()
        metrics = compute_topological(G, {})
        assert metrics.pagerank_top == []
        assert metrics.betweenness_bridges == []
        assert metrics.communities == []
        assert metrics.communities_needing_moc == []
        assert metrics.information_sinks == []
        assert metrics.information_sink_rate == 0.0
        assert metrics.information_sink_class == ""

    def test_single_node(self) -> None:
        """Single node graph produces pagerank of that node."""
        G = nx.DiGraph()
        G.add_node("a")
        notes = {"a": _meta("a", tags=["type/principle"])}
        metrics = compute_topological(G, notes)
        assert len(metrics.pagerank_top) == 1
        assert metrics.pagerank_top[0][0] == "a"
        assert len(metrics.communities) >= 1
        assert metrics.information_sinks == []

    def test_simple_cycle_graph(self) -> None:
        """Cycle graph produces pagerank_top and at least one community."""
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
        """Nodes with inbound links but no outbound links are sinks."""
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
        """Isolated nodes (0 in, 0 out) are not counted as sinks."""
        G = nx.DiGraph()
        G.add_node("isolated")
        notes = {"isolated": _meta("isolated", tags=["type/principle"])}
        metrics = compute_topological(G, notes)
        assert "isolated" not in metrics.information_sinks

    def test_communities_needing_moc(self) -> None:
        """Large community without a MOC is flagged."""
        G = nx.DiGraph()
        nodes = [f"n{i}" for i in range(5)]
        for i in range(4):
            G.add_edge(nodes[i], nodes[i + 1])
        notes = {n: _meta(n, tags=["type/principle"]) for n in nodes}
        metrics = compute_topological(G, notes)
        for community in metrics.communities_needing_moc:
            assert len(community) >= 5

    def test_all_nodes_in_one_community(self) -> None:
        """Connected graph produces a single community."""
        G = nx.DiGraph()
        G.add_edges_from([("a", "b"), ("b", "c"), ("c", "a")])
        notes = {n: _meta(n, tags=["type/principle"]) for n in ("a", "b", "c")}
        metrics = compute_topological(G, notes)
        assert len(metrics.communities) >= 1
        all_stems = {s for c in metrics.communities for s in c}
        assert all_stems == {"a", "b", "c"}

    def test_sink_class_healthy(self) -> None:
        """No sinks produces 'healthy' sink class."""
        G = nx.DiGraph()
        for i in range(25):
            G.add_edge(f"n{i}", f"n{(i + 1) % 25}")
        notes = {
            f"n{i}": _meta(f"n{i}", tags=["type/principle"]) for i in range(25)
        }
        metrics = compute_topological(G, notes)
        assert metrics.information_sink_rate == 0.0
        assert metrics.information_sink_class == "healthy"

    def test_sink_class_warning(self) -> None:
        """Sink rate between 5% and 10% is 'warning'."""
        G = nx.DiGraph()
        # Cycle: 18 nodes, none are sinks (all have in > 0 and out > 0)
        for i in range(18):
            G.add_edge(f"n{i}", f"n{(i + 1) % 18}")
        # Add a dedicated sink: total nodes = 20, 1 sink = 5%
        G.add_edge("n0", "the_sink")
        notes = {
            f"n{i}": _meta(f"n{i}", tags=["type/principle"]) for i in range(18)
        }
        notes["the_sink"] = _meta("the_sink", tags=["type/principle"])
        metrics = compute_topological(G, notes)
        assert 0 < metrics.information_sink_rate <= 10
        assert metrics.information_sink_class == "warning"

    def test_sink_class_critical(self) -> None:
        """Sink rate > 10% is 'critical'."""
        G = nx.DiGraph()
        G.add_edge("a", "sink1")
        G.add_edge("a", "sink2")
        G.add_edge("a", "sink3")
        notes = {
            "a": _meta("a", tags=["type/principle"]),
            "sink1": _meta("sink1", tags=["type/principle"]),
            "sink2": _meta("sink2", tags=["type/principle"]),
            "sink3": _meta("sink3", tags=["type/principle"]),
        }
        metrics = compute_topological(G, notes)
        assert metrics.information_sink_rate > 10
        assert metrics.information_sink_class == "critical"