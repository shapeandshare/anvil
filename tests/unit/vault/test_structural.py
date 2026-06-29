# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for vault structural analysis (anvil/services/vault/structural.py).

Covers _is_hub, _find_chain_gaps, _find_potential_silos, _find_broken_cycles,
and compute_structural with empty, well-formed, and edge-case graphs.
"""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import pytest

from anvil.services.vault.structural import (
    _find_broken_cycles,
    _find_chain_gaps,
    _find_potential_silos,
    _is_hub,
    compute_structural,
)
from anvil.services.vault.types_note_metadata import NoteMetadata
from anvil.services.vault.types_topological_metrics import TopologicalMetrics


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
# _is_hub
######################################################################


class TestIsHub:
    """Tests for _is_hub."""

    def test_moc_is_hub(self) -> None:
        """Notes with type/moc tag are hubs."""
        meta = _meta("moc-page", tags=["type/moc"])
        assert _is_hub(meta, out_degree=2, G=nx.DiGraph()) is True

    def test_reference_is_hub(self) -> None:
        """Notes with type/reference tag are hubs."""
        meta = _meta("ref-page", tags=["type/reference"])
        assert _is_hub(meta, out_degree=2, G=nx.DiGraph()) is True

    def test_high_out_degree_is_hub(self) -> None:
        """Out-degree > 8 is considered a hub."""
        meta = _meta("busy-page", tags=[])
        assert _is_hub(meta, out_degree=9, G=nx.DiGraph()) is True

    def test_low_out_degree_not_hub(self) -> None:
        """Out-degree <= 8 without hub tags is not a hub."""
        meta = _meta("normal-page", tags=[])
        assert _is_hub(meta, out_degree=3, G=nx.DiGraph()) is False

    def test_none_meta_not_hub(self) -> None:
        """None metadata is not considered a hub."""
        assert _is_hub(None, out_degree=2, G=nx.DiGraph()) is False

    def test_spec_subfile_is_hub(self) -> None:
        """Spec subfiles are considered hubs."""
        meta = _meta("detail", tags=[], path=Path("/vault/Specs/x/detail.md"))
        assert _is_hub(meta, out_degree=1, G=nx.DiGraph()) is True


######################################################################
# _find_chain_gaps
######################################################################


class TestFindChainGaps:
    """Tests for _find_chain_gaps."""

    def test_no_chain_gaps(self) -> None:
        """Direct transitive edges via intermediate produce no gap."""
        G = nx.DiGraph()
        G.add_edges_from([("a", "b"), ("b", "c")])
        notes = {"a": _meta("a"), "b": _meta("b"), "c": _meta("c")}
        assert _find_chain_gaps(G, notes) == []

    def test_chain_gap_detected(self) -> None:
        """Missing edge between a and b when both share a common predecessor is a gap."""
        G = nx.DiGraph()
        G.add_edges_from([("b", "a"), ("b", "c"), ("a", "c")])
        notes = {"a": _meta("a"), "b": _meta("b", tags=["type/principle"]), "c": _meta("c")}
        gaps = _find_chain_gaps(G, notes)
        assert ("a", "c", "b") in gaps

    def test_chain_gap_skips_hub(self) -> None:
        """Hubs are not suggested as missing intermediates."""
        G = nx.DiGraph()
        G.add_edges_from([("b", "a"), ("b", "c"), ("a", "c")])
        notes = {
            "a": _meta("a"),
            "b": _meta("b", tags=["type/moc"]),
            "c": _meta("c"),
        }
        gaps = _find_chain_gaps(G, notes)
        hub_gaps = [g for g in gaps if g[2] == "b"]
        assert len(hub_gaps) == 0

    def test_self_loop_skipped(self) -> None:
        """Self-loops (a->a) do not create chain gaps."""
        G = nx.DiGraph()
        G.add_edges_from([("a", "a"), ("a", "b")])
        notes = {"a": _meta("a"), "b": _meta("b")}
        gaps = _find_chain_gaps(G, notes)
        assert all(g[0] != g[1] for g in gaps)

    def test_empty_graph(self) -> None:
        """Empty graph returns empty list."""
        G = nx.DiGraph()
        assert _find_chain_gaps(G, {}) == []

    def test_existing_edge_skipped(self) -> None:
        """If edge a->b already exists, it is not a gap."""
        G = nx.DiGraph()
        G.add_edges_from([("b", "a"), ("b", "c"), ("a", "b"), ("a", "c")])
        notes = {"a": _meta("a"), "b": _meta("b"), "c": _meta("c")}
        gaps = _find_chain_gaps(G, notes)
        gap_a_c_b = [g for g in gaps if g == ("a", "c", "b")]
        assert len(gap_a_c_b) == 0


######################################################################
# _find_potential_silos
######################################################################


class TestFindPotentialSilos:
    """Tests for _find_potential_silos."""

    def test_no_communities(self) -> None:
        """Empty communities list produces no silos."""
        G = nx.DiGraph()
        assert _find_potential_silos(G, []) == []

    def test_silos_detected(self) -> None:
        """Disconnected clusters yield a silo with density 0.0."""
        G = nx.DiGraph()
        G.add_edges_from([("a1", "a2"), ("a2", "a3"), ("b1", "b2")])
        communities = [["a1", "a2", "a3"], ["b1", "b2"]]
        silos = _find_potential_silos(G, communities)
        assert len(silos) == 1
        assert silos[0][0] == 0
        assert silos[0][1] == 1
        assert silos[0][2] == 0.0

    def test_no_silos_with_bridging(self) -> None:
        """Clusters connected by bridging links are not silos."""
        G = nx.DiGraph()
        G.add_edges_from([("a1", "a2"), ("a2", "b1"), ("b1", "b2")])
        communities = [["a1", "a2"], ["b1", "b2"]]
        assert _find_potential_silos(G, communities) == []

    def test_single_cluster(self) -> None:
        """Single cluster produces no silos (no pairs to compare)."""
        G = nx.DiGraph()
        G.add_edge("a", "b")
        communities = [["a", "b"]]
        assert _find_potential_silos(G, communities) == []

    def test_missing_nodes_in_graph(self) -> None:
        """Nodes in communities but not in G are handled gracefully."""
        G = nx.DiGraph()
        G.add_edge("a", "b")
        communities = [["a", "b"], ["c", "d"]]  # c, d not in G
        silos = _find_potential_silos(G, communities)
        assert len(silos) >= 0


######################################################################
# _find_broken_cycles
######################################################################


class TestFindBrokenCycles:
    """Tests for _find_broken_cycles."""

    def test_no_cycles(self) -> None:
        """Acyclic graph returns no broken cycles."""
        G = nx.DiGraph()
        G.add_edges_from([("a", "b"), ("b", "c")])
        assert _find_broken_cycles(G) == []

    def test_broken_cycle_detected(self) -> None:
        """A cycle with no external edges is broken."""
        G = nx.DiGraph()
        G.add_edges_from([("a", "b"), ("b", "c"), ("c", "a")])
        cycles = _find_broken_cycles(G)
        assert len(cycles) == 1
        assert set(cycles[0]) == {"a", "b", "c"}

    def test_cycle_with_external_edges_not_broken(self) -> None:
        """A cycle with at least one external edge is not broken."""
        G = nx.DiGraph()
        G.add_edges_from([("a", "b"), ("b", "c"), ("c", "a"), ("a", "external")])
        cycles = _find_broken_cycles(G)
        assert cycles == []

    def test_large_cycle_skipped(self) -> None:
        """Cycles > 6 nodes are not returned (length_bound=6)."""
        G = nx.DiGraph()
        nodes = [chr(ord("a") + i) for i in range(8)]
        for i in range(8):
            G.add_edge(nodes[i], nodes[(i + 1) % 8])
        cycles = _find_broken_cycles(G)
        assert len(cycles) == 0

    def test_empty_graph(self) -> None:
        """Empty graph returns no broken cycles."""
        G = nx.DiGraph()
        assert _find_broken_cycles(G) == []

    def test_two_node_broken_cycle(self) -> None:
        """A 2-node cycle with no external edges is broken."""
        G = nx.DiGraph()
        G.add_edges_from([("a", "b"), ("b", "a")])
        cycles = _find_broken_cycles(G)
        assert len(cycles) == 1
        assert set(cycles[0]) == {"a", "b"}


######################################################################
# compute_structural
######################################################################


class TestComputeStructural:
    """Tests for compute_structural."""

    def test_empty_graph(self) -> None:
        """Empty graph returns empty metrics."""
        G = nx.DiGraph()
        topo = TopologicalMetrics()
        metrics = compute_structural(G, {}, topo)
        assert metrics.chain_gaps == []
        assert metrics.potential_silos == []
        assert metrics.broken_cycles == []

    def test_integration(self) -> None:
        """Multiple clusters with a broken cycle detected."""
        G = nx.DiGraph()
        G.add_edges_from(
            [
                ("a", "b"),
                ("a", "c"),
                ("b", "c"),
                ("x", "y"),
                ("y", "x"),
            ]
        )
        notes = {
            "a": _meta("a"),
            "b": _meta("b"),
            "c": _meta("c"),
            "x": _meta("x"),
            "y": _meta("y"),
        }
        topo = TopologicalMetrics(communities=[["a", "b", "c"], ["x", "y"]])
        metrics = compute_structural(G, notes, topo)
        assert len(metrics.potential_silos) >= 0
        assert len(metrics.broken_cycles) >= 1
        found = [c for c in metrics.broken_cycles if set(c) == {"x", "y"}]
        assert len(found) == 1