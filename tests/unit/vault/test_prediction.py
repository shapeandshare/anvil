# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for vault link prediction ensemble.

Tests ``prediction.py``: Adamic-Adar, TF-IDF, community scoring,
ensemble combination, state persistence, filtering, and auto-fix.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import networkx as nx
import pytest

from anvil.services.vault.prediction import (
    FIX_THRESHOLD,
    _build_community_lookup,
    _is_working_tree_dirty,
    _parse_state_key,
    _state_path,
    apply_fix,
    clean_stale_entries,
    compute_adamic_adar,
    compute_link_prediction,
    compute_tfidf,
    filter_by_state,
    load_state,
    save_state,
)
from anvil.services.vault.types_note_metadata import NoteMetadata
from anvil.services.vault.types_scored_pair import ScoredPair

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def simple_graph() -> nx.DiGraph:
    """Return a small directed wikilink graph for testing."""
    g = nx.DiGraph()
    g.add_edges_from(
        [
            ("note_a", "note_b"),
            ("note_b", "note_c"),
            ("note_a", "note_c"),
            ("note_c", "note_d"),
            ("note_d", "note_a"),
        ]
    )
    return g


@pytest.fixture
def isolated_graph() -> nx.DiGraph:
    """Return a graph with two disconnected components."""
    g = nx.DiGraph()
    g.add_edges_from(
        [
            ("a1", "a2"),
            ("a2", "a1"),
            ("b1", "b2"),
        ]
    )
    return g


# ============================================================================
# compute_adamic_adar
# ============================================================================


class TestComputeAdamicAdar:
    """Tests for the Adamic-Adar structural similarity computation."""

    def test_basic_scores(self, simple_graph: nx.DiGraph) -> None:
        """Adamic-Adar returns a score for each candidate pair."""
        candidates = [("note_a", "note_d"), ("note_b", "note_a")]
        scores = compute_adamic_adar(simple_graph, candidates)
        assert len(scores) == 2
        for pair in candidates:
            assert pair in scores
            assert 0.0 <= scores[pair] <= 1.0

    def test_non_neighbor_pairs(self) -> None:
        """Pairs that share no neighbours get a very low (near-zero) score."""
        g = nx.DiGraph()
        g.add_nodes_from(["x", "y"])
        g.add_edge("x", "y")
        candidates = [("x", "y")]
        scores = compute_adamic_adar(g, candidates)
        # Single edge, no common neighbours → Adamic-Adar = 0
        assert scores[("x", "y")] == 0.0

    def test_empty_candidates(self, simple_graph: nx.DiGraph) -> None:
        """An empty candidate list produces an empty score dict."""
        assert compute_adamic_adar(simple_graph, []) == {}


# ============================================================================
# compute_tfidf
# ============================================================================


class TestComputeTfidf:
    """Tests for TF-IDF content similarity computation."""

    def test_returns_empty_for_empty_candidates(self) -> None:
        """Empty candidate list produces an empty dict."""
        assert compute_tfidf({}, []) == {}

    def test_returns_zero_for_missing_notes(self) -> None:
        """When all candidate notes are missing, empty dict is returned."""
        candidates = [("missing_a", "missing_b")]
        scores = compute_tfidf({}, candidates)
        assert scores == {}

    def test_content_similarity(self, tmp_path: Path) -> None:
        """Notes with similar content get higher cosine similarity."""
        note_a_path = tmp_path / "note_a.md"
        note_b_path = tmp_path / "note_b.md"
        note_a_path.write_text("machine learning transformers attention")
        note_b_path.write_text("deep learning neural networks attention")

        notes = {
            "note_a": NoteMetadata(path=note_a_path, stem="note_a"),
            "note_b": NoteMetadata(path=note_b_path, stem="note_b"),
        }
        candidates = [("note_a", "note_b")]
        scores = compute_tfidf(notes, candidates)
        assert 0.0 < scores[("note_a", "note_b")] <= 1.0

    def test_dissimilar_content(self, tmp_path: Path) -> None:
        """Notes with completely different content get low cosine similarity."""
        note_a_path = tmp_path / "note_a.md"
        note_b_path = tmp_path / "note_b.md"
        note_a_path.write_text("quantum physics mechanics wave function particle")
        note_b_path.write_text("cooking recipes pasta italian cuisine tomato sauce")

        notes = {
            "note_a": NoteMetadata(path=note_a_path, stem="note_a"),
            "note_b": NoteMetadata(path=note_b_path, stem="note_b"),
        }
        candidates = [("note_a", "note_b")]
        scores = compute_tfidf(notes, candidates)
        assert 0.0 <= scores[("note_a", "note_b")] < 0.5

    def test_short_text_gets_zero(self, tmp_path: Path) -> None:
        """Notes with very short body text (<10 chars) get 0.0."""
        note_path = tmp_path / "short.md"
        note_path.write_text("hi")
        notes = {
            "short": NoteMetadata(path=note_path, stem="short"),
        }
        candidates = [("short", "short")]
        scores = compute_tfidf(notes, candidates)
        assert scores[("short", "short")] == 0.0

    def test_skips_frontmatter(self, tmp_path: Path) -> None:
        """Frontmatter (YAML between --- delimiters) is excluded from body."""
        note_path = tmp_path / "note.md"
        note_path.write_text("---\ntitle: Test\n---\nactual body text here for content")
        notes = {
            "note": NoteMetadata(path=note_path, stem="note"),
        }
        candidates = [("note", "note")]
        scores = compute_tfidf(notes, candidates)
        assert scores[("note", "note")] == pytest.approx(1.0)

    def test_read_error_returns_empty(self, tmp_path: Path) -> None:
        """A note whose file cannot be read returns empty dict."""
        note_path = tmp_path / "missing.md"
        notes = {
            "missing": NoteMetadata(path=note_path, stem="missing"),
        }
        candidates = [("missing", "missing")]
        scores = compute_tfidf(notes, candidates)
        assert scores == {}

    def test_all_zero_text_returns_empty(self, tmp_path: Path) -> None:
        """When all note bodies are empty, an empty dict is returned."""
        note_a_path = tmp_path / "a.md"
        note_b_path = tmp_path / "b.md"
        note_a_path.write_text("---\nkey: val\n---\n")
        note_b_path.write_text("---\nkey: val\n---\n")

        notes = {
            "a": NoteMetadata(path=note_a_path, stem="a"),
            "b": NoteMetadata(path=note_b_path, stem="b"),
        }
        candidates = [("a", "b")]
        # Bodies are empty after frontmatter strip
        scores = compute_tfidf(notes, candidates)
        assert scores == {}


# ============================================================================
# _build_community_lookup
# ============================================================================


class TestBuildCommunityLookup:
    """Tests for community lookup dictionary construction."""

    def test_basic_lookup(self) -> None:
        """Each node maps to its community index."""
        communities = [["a", "b"], ["c", "d"]]
        lookup = _build_community_lookup(communities)
        assert lookup == {"a": 0, "b": 0, "c": 1, "d": 1}

    def test_empty_communities(self) -> None:
        """Empty community list produces empty lookup."""
        assert _build_community_lookup([]) == {}

    def test_single_community(self) -> None:
        """All nodes in one community share index 0."""
        communities = [["x", "y", "z"]]
        lookup = _build_community_lookup(communities)
        assert lookup == {"x": 0, "y": 0, "z": 0}

    def test_singleton_clusters(self) -> None:
        """Each singleton cluster gets its own index."""
        communities = [["a"], ["b"], ["c"]]
        lookup = _build_community_lookup(communities)
        assert lookup == {"a": 0, "b": 1, "c": 2}


# ============================================================================
# compute_link_prediction (ensemble)
# ============================================================================


class TestComputeLinkPrediction:
    """Tests for the ensemble link prediction entry point."""

    def test_empty_missing_returns_empty(self) -> None:
        """Empty missing_reciprocals returns an empty LinkPredictionResult."""
        result = compute_link_prediction(nx.DiGraph(), {}, [], [])
        assert result.scored_pairs == []

    def test_scores_all_pairs(self, simple_graph: nx.DiGraph) -> None:
        """All missing reciprocal pairs receive an ensemble score."""
        missing = [("note_b", "note_d")]
        notes = {}
        communities = [["note_a", "note_b", "note_c", "note_d"]]
        result = compute_link_prediction(simple_graph, notes, communities, missing)
        assert len(result.scored_pairs) == 1
        pair = result.scored_pairs[0]
        assert pair.source == "note_b"
        assert pair.target == "note_d"
        assert 0.0 <= pair.ensemble_score <= 1.0

    def test_community_match_flag(self) -> None:
        """Pairs in the same community get community_match=1.0."""
        g = nx.DiGraph()
        g.add_edge("a", "b")
        communities = [["a", "b"]]
        missing = [("b", "a")]
        result = compute_link_prediction(g, {}, communities, missing)
        assert result.scored_pairs[0].community_match == 1.0

    def test_different_community_no_match(self) -> None:
        """Pairs in different communities get community_match=0.0."""
        g = nx.DiGraph()
        g.add_edge("a", "b")
        communities = [["a"], ["b"]]
        missing = [("b", "a")]
        result = compute_link_prediction(g, {}, communities, missing)
        assert result.scored_pairs[0].community_match == 0.0

    def test_custom_weights(self) -> None:
        """Custom ensemble weights override defaults."""
        g = nx.DiGraph()
        g.add_edge("a", "b")
        communities = [["a", "b"]]
        missing = [("b", "a")]
        weights = {"adamic_adar": 1.0, "tfidf": 0.0, "community_match": 0.0}
        result = compute_link_prediction(g, {}, communities, missing, weights=weights)
        pair = result.scored_pairs[0]
        # With these weights, ensemble == adamic_adar (since others are 0).
        # Adamic-Adar for a single-edge graph is 0, so ensemble = 0.
        assert pair.ensemble_score == 0.0

    def test_sort_descending(self) -> None:
        """Scored pairs are sorted by ensemble score descending."""
        g = nx.DiGraph()
        # Create a more connected subgraph so scores differ
        g.add_edges_from(
            [
                ("a1", "b1"),
                ("a1", "c1"),
                ("b1", "c1"),
                ("b1", "a1"),
                ("c1", "a1"),
                ("x1", "y1"),
            ]
        )
        communities = [["a1", "b1", "c1"], ["x1", "y1"]]
        missing = [("c1", "b1"), ("y1", "x1")]
        result = compute_link_prediction(g, {}, communities, missing)
        assert len(result.scored_pairs) == 2
        assert (
            result.scored_pairs[0].ensemble_score
            >= result.scored_pairs[1].ensemble_score
        )


# ============================================================================
# _state_path
# ============================================================================


class TestStatePath:
    """Tests for state file path resolution."""

    def test_returns_expected_path(self, tmp_path: Path) -> None:
        """State path joins root with the STATE_FILE constant."""
        state_path = _state_path(tmp_path)
        assert state_path == tmp_path / "_meta/audit/link_prediction_state.json"

    def test_type_is_path(self, tmp_path: Path) -> None:
        """Return type is Path."""
        assert isinstance(_state_path(tmp_path), Path)


# ============================================================================
# load_state / save_state
# ============================================================================


class TestLoadSaveState:
    """Tests for state persistence (load and save)."""

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        """Saved state can be loaded back identically."""
        state = {"(a, b)": {"state": "confirmed", "score": 0.85}}
        save_state(tmp_path, state)
        loaded = load_state(tmp_path)
        assert loaded == state

    def test_load_nonexistent_returns_empty(self, tmp_path: Path) -> None:
        """Loading state when no file exists returns empty dict."""
        assert load_state(tmp_path) == {}

    def test_load_corrupted_returns_empty(self, tmp_path: Path) -> None:
        """Loading corrupted JSON returns empty dict."""
        state_file = tmp_path / "_meta/audit/link_prediction_state.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text("not valid json")
        assert load_state(tmp_path) == {}

    def test_save_creates_parent_dirs(self, tmp_path: Path) -> None:
        """Save creates intermediate directories automatically."""
        deep_path = tmp_path / "a" / "b" / "c"
        save_state(deep_path, {"key": "val"})
        assert load_state(deep_path) == {"key": "val"}


# ============================================================================
# filter_by_state
# ============================================================================


class TestFilterByState:
    """Tests for state-based filtering of scored pairs."""

    @pytest.fixture
    def scored_pairs(self) -> list[ScoredPair]:
        """Sample scored pairs for filtering tests."""
        return [
            ScoredPair(source="a", target="b", ensemble_score=0.9),
            ScoredPair(source="c", target="d", ensemble_score=0.5),
            ScoredPair(source="e", target="f", ensemble_score=0.3),
        ]

    def test_no_state_keeps_all(self, scored_pairs: list[ScoredPair]) -> None:
        """When state is None/empty, all pairs pass through."""
        assert filter_by_state(scored_pairs) == scored_pairs
        assert filter_by_state(scored_pairs, state={}) == scored_pairs

    def test_open_entries_pass_through(self, scored_pairs: list[ScoredPair]) -> None:
        """Pairs with state='open' are included."""
        state = {"(a, b)": {"state": "open"}}
        filtered = filter_by_state(scored_pairs, state=state)
        assert len(filtered) == 3

    def test_confirmed_removed_when_score_stable(
        self, scored_pairs: list[ScoredPair]
    ) -> None:
        """Confirmed pairs are removed unless the score changed >30%."""
        state = {"(a, b)": {"state": "confirmed", "score": 0.9}}
        current_scores = {("a", "b"): 0.9}
        filtered = filter_by_state(
            scored_pairs, state=state, current_scores=current_scores
        )
        assert len(filtered) == 2
        assert all(p.source != "a" for p in filtered)

    def test_dismissed_removed_when_score_stable(
        self, scored_pairs: list[ScoredPair]
    ) -> None:
        """Dismissed pairs are removed unless the score changed >30%."""
        state = {"(a, b)": {"state": "dismissed", "score": 0.9}}
        current_scores = {("a", "b"): 0.9}
        filtered = filter_by_state(
            scored_pairs, state=state, current_scores=current_scores
        )
        assert len(filtered) == 2

    def test_confirmed_reappears_when_score_changed(
        self, scored_pairs: list[ScoredPair]
    ) -> None:
        """Confirmed pairs reappear when the score changes >30%."""
        state = {"(a, b)": {"state": "confirmed", "score": 0.3}}
        current_scores = {("a", "b"): 0.9}
        filtered = filter_by_state(
            scored_pairs, state=state, current_scores=current_scores
        )
        assert len(filtered) == 3

    def test_dismissed_reappears_when_score_changed(
        self, scored_pairs: list[ScoredPair]
    ) -> None:
        """Dismissed pairs reappear when the score changes >30%."""
        state = {"(a, b)": {"state": "dismissed", "score": 0.3}}
        current_scores = {("a", "b"): 0.9}
        filtered = filter_by_state(
            scored_pairs, state=state, current_scores=current_scores
        )
        assert len(filtered) == 3

    def test_zero_stored_score_removes_pair(
        self, scored_pairs: list[ScoredPair]
    ) -> None:
        """When stored score is 0, the pair is filtered out (no re-inclusion)."""
        state = {"(a, b)": {"state": "confirmed", "score": 0.0}}
        filtered = filter_by_state(scored_pairs, state=state)
        assert len(filtered) == 2
        assert all(p.source != "a" for p in filtered)

    def test_unknown_state_passes_through(self, scored_pairs: list[ScoredPair]) -> None:
        """An unrecognised state value passes the pair through."""
        state = {"(a, b)": {"state": "unknown_value"}}
        filtered = filter_by_state(scored_pairs, state=state)
        assert len(filtered) == 3

    def test_empty_pairs(self) -> None:
        """Empty scored pair list returns empty list."""
        assert filter_by_state([]) == []


# ============================================================================
# _parse_state_key
# ============================================================================


class TestParseStateKey:
    """Tests for state key string parsing."""

    def test_simple_pair(self) -> None:
        """A standard (source, target) key is parsed correctly."""
        assert _parse_state_key("(note_a, note_b)") == ("note_a", "note_b")

    def test_with_spaces(self) -> None:
        """Stems with internal spaces are parsed correctly."""
        assert _parse_state_key("(my note, your note)") == (
            "my note",
            "your note",
        )

    def test_with_quotes(self) -> None:
        """Keys wrapped in quotes have quotes stripped."""
        assert _parse_state_key("('a', 'b')") == ("a", "b")
        assert _parse_state_key('("a", "b")') == ("a", "b")

    def test_invalid_returns_none(self) -> None:
        """Unparseable keys return None."""
        assert _parse_state_key("not_a_pair") is None
        assert _parse_state_key("") is None

    def test_single_element(self) -> None:
        """A key with one element returns None."""
        assert _parse_state_key("(only_one)") is None


# ============================================================================
# clean_stale_entries
# ============================================================================


class TestCleanStaleEntries:
    """Tests for stale state entry cleanup."""

    def test_keeps_current_missing(self) -> None:
        """Entries for still-missing pairs are kept."""
        state = {
            "(a, b)": {"state": "confirmed", "score": 0.9},
            "(c, d)": {"state": "dismissed", "score": 0.5},
        }
        current = {("a", "b")}
        cleaned = clean_stale_entries(state, current)
        assert len(cleaned) == 1
        assert "(a, b)" in cleaned

    def test_removes_stale(self) -> None:
        """Entries for no-longer-missing pairs are removed."""
        state = {
            "(a, b)": {"state": "confirmed", "score": 0.9},
        }
        current: set[tuple[str, str]] = set()
        cleaned = clean_stale_entries(state, current)
        assert cleaned == {}

    def test_empty_state(self) -> None:
        """Empty state returns empty dict."""
        assert clean_stale_entries({}, {("a", "b")}) == {}

    def test_unparseable_key_removed(self) -> None:
        """Entries with unparseable keys are treated as stale."""
        state = {"bad_key": {"state": "confirmed"}}
        current: set[tuple[str, str]] = set()
        cleaned = clean_stale_entries(state, current)
        assert cleaned == {}


# ============================================================================
# _is_working_tree_dirty
# ============================================================================


class TestIsWorkingTreeDirty:
    """Tests for git working-tree-dirty check."""

    def test_clean_repo(self) -> None:
        """A clean repo returns False."""
        # In the test environment the repo may be clean or dirty
        # This is a smoke test — just check the function runs without error
        result = _is_working_tree_dirty()
        assert isinstance(result, bool)

    def test_subprocess_error_returns_false(self) -> None:
        """When git command fails, the function returns False."""
        with patch(
            "anvil.services.vault.prediction.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            assert _is_working_tree_dirty() is False


# ============================================================================
# apply_fix
# ============================================================================


class TestApplyFix:
    """Tests for the auto-fix (reciprocal link insertion)."""

    @patch("anvil.services.vault.prediction._is_working_tree_dirty")
    def test_dirty_tree_returns_false(self, mock_dirty, tmp_path: Path) -> None:
        """When the working tree is dirty, no fix is applied."""
        mock_dirty.return_value = True
        scored = [
            ScoredPair(
                source="src",
                target="tgt",
                ensemble_score=FIX_THRESHOLD,
            )
        ]
        tgt_path = tmp_path / "tgt.md"
        tgt_path.write_text("---\ntitle: TGT\n---\nbody")
        notes = {
            "tgt": NoteMetadata(path=tgt_path, stem="tgt"),
        }
        assert apply_fix(scored, notes) is False

    @patch("anvil.services.vault.prediction._is_working_tree_dirty")
    def test_below_threshold_no_fix(self, mock_dirty, tmp_path: Path) -> None:
        """Candidates below threshold are not applied."""
        mock_dirty.return_value = False
        scored = [
            ScoredPair(
                source="src",
                target="tgt",
                ensemble_score=0.1,
            )
        ]
        tgt_path = tmp_path / "tgt.md"
        tgt_path.write_text("---\ntitle: TGT\n---\nbody")
        notes = {
            "tgt": NoteMetadata(path=tgt_path, stem="tgt"),
        }
        assert apply_fix(scored, notes) is False

    @patch("anvil.services.vault.prediction._is_working_tree_dirty")
    def test_inserts_related_link(self, mock_dirty, tmp_path: Path) -> None:
        """A high-confidence candidate gets a related: link inserted."""
        mock_dirty.return_value = False
        scored = [
            ScoredPair(
                source="src_note",
                target="tgt_note",
                ensemble_score=0.9,
            )
        ]
        tgt_path = tmp_path / "tgt_note.md"
        tgt_path.write_text("---\ntitle: Target\ncreated: 2025-01-01\n---\nbody text")
        notes = {
            "tgt_note": NoteMetadata(path=tgt_path, stem="tgt_note"),
        }
        assert apply_fix(scored, notes) is True
        content = tgt_path.read_text()
        assert "[[src_note]]" in content
        assert "related:" in content

    @patch("anvil.services.vault.prediction._is_working_tree_dirty")
    def test_skips_if_already_present(self, mock_dirty, tmp_path: Path) -> None:
        """If the source is already linked in the target, no change."""
        mock_dirty.return_value = False
        scored = [
            ScoredPair(
                source="src_note",
                target="tgt_note",
                ensemble_score=0.9,
            )
        ]
        tgt_path = tmp_path / "tgt_note.md"
        tgt_path.write_text("---\ntitle: Target\n---\nSome text [[src_note]] more text")
        notes = {
            "tgt_note": NoteMetadata(path=tgt_path, stem="tgt_note"),
        }
        assert apply_fix(scored, notes) is False

    @patch("anvil.services.vault.prediction._is_working_tree_dirty")
    def test_appends_to_existing_related(self, mock_dirty, tmp_path: Path) -> None:
        """When related: already exists, the new link is appended."""
        mock_dirty.return_value = False
        scored = [
            ScoredPair(
                source="new_note",
                target="existing",
                ensemble_score=0.9,
            )
        ]
        tgt_path = tmp_path / "existing.md"
        tgt_path.write_text(
            "---\ntitle: Existing\nrelated:\n" "  - '[[old_note]]'\n---\nbody"
        )
        notes = {
            "existing": NoteMetadata(path=tgt_path, stem="existing"),
        }
        assert apply_fix(scored, notes) is True
        content = tgt_path.read_text()
        assert "[[new_note]]" in content
        assert "[[old_note]]" in content

    @patch("anvil.services.vault.prediction._is_working_tree_dirty")
    def test_skip_missing_target_note(self, mock_dirty, tmp_path: Path) -> None:
        """When the target note has no metadata entry, skip."""
        mock_dirty.return_value = False
        scored = [
            ScoredPair(
                source="src",
                target="nonexistent",
                ensemble_score=0.9,
            )
        ]
        assert apply_fix(scored, {}) is False

    @patch("anvil.services.vault.prediction._is_working_tree_dirty")
    def test_skip_missing_file_on_disk(self, mock_dirty, tmp_path: Path) -> None:
        """When the target file does not exist on disk, skip."""
        mock_dirty.return_value = False
        scored = [
            ScoredPair(
                source="src",
                target="missing",
                ensemble_score=0.9,
            )
        ]
        notes = {
            "missing": NoteMetadata(path=tmp_path / "nonexistent.md", stem="missing"),
        }
        assert apply_fix(scored, notes) is False

    @patch("anvil.services.vault.prediction._is_working_tree_dirty")
    def test_no_frontmatter_skips(self, mock_dirty, tmp_path: Path) -> None:
        """A note without frontmatter (no --- delimiter) is skipped."""
        mock_dirty.return_value = False
        scored = [
            ScoredPair(
                source="src",
                target="no_fm",
                ensemble_score=0.9,
            )
        ]
        tgt_path = tmp_path / "no_fm.md"
        tgt_path.write_text("Just a body with no frontmatter")
        notes = {
            "no_fm": NoteMetadata(path=tgt_path, stem="no_fm"),
        }
        assert apply_fix(scored, notes) is False
