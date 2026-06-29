# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for :mod:`anvil.services.vault.prediction` — link prediction
ensemble.
"""

from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
import pytest

from anvil.services.vault.prediction import (
    _build_community_lookup,
    _parse_state_key,
    clean_stale_entries,
    compute_adamic_adar,
    compute_link_prediction,
    filter_by_state,
    load_state,
    save_state,
)
from anvil.services.vault.types_note_metadata import NoteMetadata


class TestBuildCommunityLookup:
    """Tests for ``_build_community_lookup``."""

    def test_single_community(self) -> None:
        communities = [["note_a", "note_b", "note_c"]]
        lookup = _build_community_lookup(communities)
        assert lookup == {"note_a": 0, "note_b": 0, "note_c": 0}

    def test_multiple_communities(self) -> None:
        communities = [["note_a", "note_b"], ["note_c"]]
        lookup = _build_community_lookup(communities)
        assert lookup["note_a"] == 0
        assert lookup["note_b"] == 0
        assert lookup["note_c"] == 1

    def test_empty_communities(self) -> None:
        assert _build_community_lookup([]) == {}

    def test_empty_cluster(self) -> None:
        communities: list[list[str]] = [["a"], [], ["b"]]
        lookup = _build_community_lookup(communities)
        assert lookup["a"] == 0
        assert lookup["b"] == 2


class TestComputeAdamicAdar:
    """Tests for ``compute_adamic_adar``."""

    def test_simple_graph(self) -> None:
        g = nx.DiGraph()
        g.add_edges_from([("A", "B"), ("B", "C"), ("A", "C")])
        candidates = [("C", "A")]
        scores = compute_adamic_adar(g, candidates)
        assert len(scores) == 1
        key = ("C", "A")
        assert key in scores
        # Score should be normalized to 0-1 via tanh
        assert 0.0 <= scores[key] <= 1.0

    def test_empty_candidates(self) -> None:
        g = nx.DiGraph()
        g.add_edge("A", "B")
        scores = compute_adamic_adar(g, [])
        assert scores == {}

    def test_isolated_nodes(self) -> None:
        g = nx.DiGraph()
        g.add_node("A")
        g.add_node("B")
        candidates = [("A", "B")]
        scores = compute_adamic_adar(g, candidates)
        # No common neighbors → Adar is 0 → normalized score is 0.0
        assert scores[("A", "B")] == pytest.approx(0.0, abs=0.01)


class TestComputeLinkPrediction:
    """Tests for ``compute_link_prediction``."""

    def test_empty_missing_reciprocals(self) -> None:
        g = nx.DiGraph()
        result = compute_link_prediction(g, {}, [], [])
        assert result.scored_pairs == []

    def test_single_candidate(self) -> None:
        g = nx.DiGraph()
        g.add_edges_from([("A", "B"), ("B", "C")])
        result = compute_link_prediction(
            g,
            {},
            [["A", "B", "C"]],
            [("C", "A")],
        )
        assert len(result.scored_pairs) == 1
        pair = result.scored_pairs[0]
        assert pair.source == "C"
        assert pair.target == "A"
        # Ensemble should be 0-1
        assert 0.0 <= pair.ensemble_score <= 1.0

    def test_multiple_candidates_sorted(self) -> None:
        g = nx.DiGraph()
        g.add_edges_from([("A", "B"), ("B", "A"), ("A", "C"), ("B", "C")])
        result = compute_link_prediction(
            g,
            {},
            [["A", "B"], ["C"]],
            [("C", "A"), ("C", "B")],
        )
        assert len(result.scored_pairs) == 2
        # Should be sorted descending by ensemble_score
        assert (
            result.scored_pairs[0].ensemble_score
            >= result.scored_pairs[1].ensemble_score
        )

    def test_same_community_boosts_score(self) -> None:
        g = nx.DiGraph()
        g.add_edges_from([("A", "B"), ("B", "A")])
        result = compute_link_prediction(
            g,
            {},
            [["A", "B"]],
            [("A", "B")],
        )
        assert len(result.scored_pairs) == 1
        # Same community → community_match = 1.0
        assert result.scored_pairs[0].community_match == 1.0

    def test_different_community_no_boost(self) -> None:
        g = nx.DiGraph()
        g.add_edges_from([("A", "B")])
        result = compute_link_prediction(
            g,
            {},
            [["A"], ["B"]],
            [("B", "A")],
        )
        assert len(result.scored_pairs) == 1
        # Different community → community_match = 0.0
        assert result.scored_pairs[0].community_match == 0.0

    def test_custom_weights(self) -> None:
        g = nx.DiGraph()
        # A-B-C chain: B is a common neighbor between A and C
        g.add_edges_from([("A", "B"), ("B", "C")])
        weights = {"adamic_adar": 1.0, "community_match": 0.0, "tfidf": 0.0}
        notes: dict[str, NoteMetadata] = {}
        result = compute_link_prediction(
            g, notes, [["A", "B", "C"]], [("C", "A")], weights=weights
        )
        assert len(result.scored_pairs) == 1
        # Only adamic_adar contributes; C and A share neighbor B
        assert result.scored_pairs[0].ensemble_score > 0.0


class TestParseStateKey:
    """Tests for ``_parse_state_key``."""

    def test_simple_pair(self) -> None:
        assert _parse_state_key("(A, B)") == ("A", "B")

    def test_pair_with_spaces(self) -> None:
        assert _parse_state_key("(note one, note two)") == ("note one", "note two")

    def test_invalid_format(self) -> None:
        assert _parse_state_key("not a pair") is None

    def test_empty_string(self) -> None:
        assert _parse_state_key("()") is None


class TestLoadSaveState:
    """Tests for ``load_state`` and ``save_state``."""

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        state = {"(A, B)": {"state": "confirmed", "score": 0.85}}
        save_state(tmp_path, state)
        loaded = load_state(tmp_path)
        assert loaded == state

    def test_load_nonexistent_file(self, tmp_path: Path) -> None:
        loaded = load_state(tmp_path / "nonexistent")
        assert loaded == {}

    def test_load_corrupted_json(self, tmp_path: Path) -> None:
        p = tmp_path / "_meta" / "audit" / "link_prediction_state.json"
        p.parent.mkdir(parents=True)
        p.write_text("not json")
        loaded = load_state(tmp_path)
        assert loaded == {}


class TestFilterByState:
    """Tests for ``filter_by_state``."""

    @pytest.fixture
    def scored_pairs(self) -> list:
        from anvil.services.vault.types_scored_pair import ScoredPair

        return [
            ScoredPair(source="A", target="B", ensemble_score=0.9),
            ScoredPair(source="C", target="D", ensemble_score=0.5),
            ScoredPair(source="E", target="F", ensemble_score=0.3),
        ]

    def test_no_state_returns_all(self, scored_pairs: list) -> None:
        result = filter_by_state(scored_pairs)
        assert len(result) == 3

    def test_confirmed_pair_filtered(self, scored_pairs: list) -> None:
        state = {"(A, B)": {"state": "confirmed", "score": 0.9}}
        current_scores = {("A", "B"): 0.9}
        result = filter_by_state(
            scored_pairs, state=state, current_scores=current_scores
        )
        assert len(result) == 2
        assert all(p.source != "A" for p in result)

    def test_dismissed_pair_filtered(self, scored_pairs: list) -> None:
        state = {"(C, D)": {"state": "dismissed", "score": 0.5}}
        current_scores = {("C", "D"): 0.5}
        result = filter_by_state(
            scored_pairs, state=state, current_scores=current_scores
        )
        assert len(result) == 2
        assert all(p.source != "C" for p in result)

    def test_open_pair_returns(self, scored_pairs: list) -> None:
        state = {"(A, B)": {"state": "open", "score": 0.9}}
        result = filter_by_state(scored_pairs, state=state)
        assert len(result) == 3

    def test_score_drift_triggers_refilter(self, scored_pairs: list) -> None:
        state = {"(A, B)": {"state": "confirmed", "score": 0.9}}
        current_scores = {("A", "B"): 0.5}
        result = filter_by_state(
            scored_pairs, state=state, current_scores=current_scores
        )
        # Score dropped: |0.5 - 0.9| / 0.9 ≈ 0.44 > 0.3 → re-include
        assert len(result) == 3

    def test_empty_state(self, scored_pairs: list) -> None:
        result = filter_by_state(scored_pairs, state={})
        assert len(result) == 3


class TestCleanStaleEntries:
    """Tests for ``clean_stale_entries``."""

    def test_removes_stale_entries(self) -> None:
        state = {
            "(A, B)": {"state": "confirmed"},
            "(C, D)": {"state": "dismissed"},
        }
        current = {("A", "B")}
        cleaned = clean_stale_entries(state, current)
        assert "(A, B)" in cleaned
        assert "(C, D)" not in cleaned

    def test_all_entries_current(self) -> None:
        state = {"(A, B)": {"state": "confirmed"}}
        current = {("A", "B")}
        cleaned = clean_stale_entries(state, current)
        assert cleaned == state

    def test_empty_state(self) -> None:
        cleaned = clean_stale_entries({}, {("A", "B")})
        assert cleaned == {}
