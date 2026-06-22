# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for vault structural analysis (anvil/services/vault/structural.py)."""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import pytest

from anvil.services.vault._types import NoteMetadata, TopologicalMetrics
from anvil.services.vault.structural import (
    _find_broken_cycles,
    _find_chain_gaps,
    _find_potential_silos,
    _is_hub,
    compute_structural,
)


def _meta(stem: str, tags: list[str] | None = None) -> NoteMetadata:
    return NoteMetadata(
        path=Path(f"/vault/{stem}.md"),
        stem=stem,
        tags=tags or [],
    )


class TestIsHub:
    """Tests for _is_hub."""

    def test_moc_is_hub(self) -> None:
        meta = _meta("moc-page", tags=["type/moc"])
        assert _is_hub(meta, out_degree=2, G=nx.DiGraph()) is True

    def test_reference_is_hub(self) -> None:
        meta = _meta("ref-page", tags=["type/reference"])
        assert _is_hub(meta, out_degree=2, G=nx.DiGraph()) is True

    def test_high_out_degree_is_hub(self) -> None:
        meta = _meta("busy-page", tags=[])
        assert _is_hub(meta, out_degree=9, G=nx.DiGraph()) is True

    def test_low_out_degree_not_hub(self) -> None:
        meta = _meta("normal-page", tags=[])
        assert _is_hub(meta, out_degree=3, G=nx.DiGraph()) is False

    def test_none_meta_is_not_hub(self) -> None:
        assert _is_hub(None, out_degree=2, G=nx.DiGraph()) is False


class TestFindChainGaps:
    """Tests for _find_chain_gaps."""

    def test_no_chain_gaps(self) -> None:
        G = nx.DiGraph()
        G.add_edges_from([("a", "b"), ("b", "c")])
        notes = {
            "a": _meta("a"),
            "b": _meta("b"),
            "c": _meta("c"),
        }
        gaps = _find_chain_gaps(G, notes)
        assert gaps == []

    def test_chain_gap_detected(self) -> None:
        G = nx.DiGraph()
        G.add_edges_from([("b", "a"), ("b", "c"), ("a", "c")])
        notes = {
            "a": _meta("a"),
            "b": _meta("b", tags=["type/principle"]),
            "c": _meta("c"),
        }
        gaps = _find_chain_gaps(G, notes)
        # pred(a)={b}, pred(c)={b,a}
        # common = pred(a) & pred(c) = {b}
        # But b is a predecessor of both a and c. The gap would be a->c via b
        # if a->b doesn't exist and b is not a hub.
        # a->b? No. So gap (a, c, b) should exist.
        assert ("a", "c", "b") in gaps

    def test_chain_gap_skips_hub(self) -> None:
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

    def test_empty_graph(self) -> None:
        G = nx.DiGraph()
        assert _find_chain_gaps(G, {}) == []


class TestFindPotentialSilos:
    """Tests for _find_potential_silos."""

    def test_no_communities(self) -> None:
        G = nx.DiGraph()
        assert _find_potential_silos(G, []) == []

    def test_silos_detected(self) -> None:
        G = nx.DiGraph()
        G.add_edges_from([("a1", "a2"), ("a2", "a3"), ("b1", "b2")])
        communities = [["a1", "a2", "a3"], ["b1", "b2"]]
        silos = _find_potential_silos(G, communities)
        assert len(silos) == 1
        assert silos[0][0] == 0
        assert silos[0][1] == 1
        assert silos[0][2] == 0.0

    def test_no_silos_with_bridging(self) -> None:
        G = nx.DiGraph()
        G.add_edges_from([("a1", "a2"), ("a2", "b1"), ("b1", "b2")])
        communities = [["a1", "a2"], ["b1", "b2"]]
        silos = _find_potential_silos(G, communities)
        assert silos == []


class TestFindBrokenCycles:
    """Tests for _find_broken_cycles."""

    def test_no_cycles(self) -> None:
        G = nx.DiGraph()
        G.add_edges_from([("a", "b"), ("b", "c")])
        assert _find_broken_cycles(G) == []

    def test_broken_cycle_detected(self) -> None:
        G = nx.DiGraph()
        G.add_edges_from([("a", "b"), ("b", "c"), ("c", "a")])
        cycles = _find_broken_cycles(G)
        assert len(cycles) == 1
        assert set(cycles[0]) == {"a", "b", "c"}

    def test_cycle_with_external_edges_not_broken(self) -> None:
        G = nx.DiGraph()
        G.add_edges_from([("a", "b"), ("b", "c"), ("c", "a"), ("a", "external")])
        cycles = _find_broken_cycles(G)
        assert cycles == []


class TestComputeStructural:
    """Tests for compute_structural."""

    def test_empty_graph(self) -> None:
        G = nx.DiGraph()
        topo = TopologicalMetrics()
        metrics = compute_structural(G, {}, topo)
        assert metrics.chain_gaps == []
        assert metrics.potential_silos == []
        assert metrics.broken_cycles == []

    def test_integration(self) -> None:
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
