# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for vault temporal analysis (anvil/services/vault/temporal.py).

Covers _get_staleness_date fallback chain and compute_temporal with empty,
well-formed, and edge-case graphs including stale notes, dead weight,
and temporal coherence metrics.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import networkx as nx
import pytest

from anvil.services.vault.temporal import _get_staleness_date, compute_temporal
from anvil.services.vault.types_note_metadata import NoteMetadata


def _meta(
    stem: str,
    created_date: date | None = None,
    updated_date: date | None = None,
    last_modified: datetime | None = None,
    tags: list[str] | None = None,
) -> NoteMetadata:
    """Build a NoteMetadata instance for testing."""
    return NoteMetadata(
        path=Path(f"/vault/{stem}.md"),
        stem=stem,
        tags=tags or [],
        created_date=created_date,
        updated_date=updated_date,
        last_modified=last_modified,
    )


######################################################################
# _get_staleness_date
######################################################################


class TestGetStalenessDate:
    """Tests for _get_staleness_date."""

    def test_uses_updated_date(self) -> None:
        """updated_date is preferred first."""
        d = date(2026, 1, 15)
        meta = _meta("note", updated_date=d, created_date=date(2025, 1, 1))
        assert _get_staleness_date(meta) == d

    def test_falls_back_to_created_date(self) -> None:
        """Falls back to created_date when updated_date is None."""
        d = date(2025, 6, 1)
        meta = _meta("note", created_date=d)
        assert _get_staleness_date(meta) == d

    def test_falls_back_to_last_modified(self) -> None:
        """Falls back to last_modified.date() when both frontmatter dates are None."""
        dt = datetime(2025, 1, 1, 12, 0, 0)
        meta = _meta("note", last_modified=dt)
        assert _get_staleness_date(meta) == dt.date()

    def test_returns_none_when_no_dates(self) -> None:
        """Returns None when no date info is available."""
        meta = _meta("note")
        assert _get_staleness_date(meta) is None


######################################################################
# compute_temporal
######################################################################


class TestComputeTemporal:
    """Tests for compute_temporal."""

    def test_empty_graph_and_notes(self) -> None:
        """Empty graph with no notes returns default values."""
        G = nx.DiGraph()
        metrics = compute_temporal(G, {})
        assert metrics.stale_notes == []
        assert metrics.dead_weight == []
        assert metrics.temporal_deltas == []
        assert metrics.temporally_distant_pairs == []
        assert metrics.high_coherence_pct == 0.0
        assert metrics.low_coherence_pct == 0.0

    def test_no_stale_notes(self) -> None:
        """Notes updated recently are not stale."""
        today = date.today()
        recent = today - timedelta(days=30)
        G = nx.DiGraph()
        G.add_node("note_a")
        notes = {"note_a": _meta("note_a", updated_date=recent)}
        metrics = compute_temporal(G, notes)
        assert metrics.stale_notes == []
        assert metrics.dead_weight == []

    def test_stale_notes_detected(self) -> None:
        """Notes not updated in >180 days are stale."""
        today = date.today()
        old = today - timedelta(days=200)
        G = nx.DiGraph()
        G.add_node("old_note")
        notes = {"old_note": _meta("old_note", updated_date=old)}
        metrics = compute_temporal(G, notes)
        assert "old_note" in metrics.stale_notes

    def test_stale_notes_skip_when_no_date(self) -> None:
        """Notes without any date info are not flagged as stale."""
        G = nx.DiGraph()
        G.add_node("no_date_note")
        notes = {"no_date_note": _meta("no_date_note")}
        metrics = compute_temporal(G, notes)
        assert metrics.stale_notes == []

    def test_dead_weight_stale_and_orphaned(self) -> None:
        """Stale notes with zero inbound links are dead weight."""
        today = date.today()
        old = today - timedelta(days=200)
        G = nx.DiGraph()
        G.add_node("stale_orphan")
        notes = {"stale_orphan": _meta("stale_orphan", updated_date=old)}
        metrics = compute_temporal(G, notes)
        assert "stale_orphan" in metrics.stale_notes
        assert "stale_orphan" in metrics.dead_weight

    def test_stale_not_dead_when_linked(self) -> None:
        """Stale notes with inbound links are not dead weight."""
        today = date.today()
        old = today - timedelta(days=200)
        G = nx.DiGraph()
        G.add_edge("active", "stale_but_linked")
        notes = {
            "active": _meta("active", updated_date=today),
            "stale_but_linked": _meta("stale_but_linked", updated_date=old),
        }
        metrics = compute_temporal(G, notes)
        assert "stale_but_linked" in metrics.stale_notes
        assert "stale_but_linked" not in metrics.dead_weight

    def test_temporal_coherence_high(self) -> None:
        """Edges between notes created within 90 days are highly coherent."""
        base = date(2026, 1, 1)
        close = date(2026, 2, 15)  # 45 days later
        G = nx.DiGraph()
        G.add_edge("a", "b")
        notes = {
            "a": _meta("a", created_date=base),
            "b": _meta("b", created_date=close),
        }
        metrics = compute_temporal(G, notes)
        assert metrics.high_coherence_pct == 100.0
        assert metrics.low_coherence_pct == 0.0
        assert len(metrics.temporal_deltas) == 1
        assert metrics.temporal_deltas[0] == 45

    def test_temporal_coherence_low(self) -> None:
        """Edges between notes created >365 days apart are low coherence."""
        base = date(2020, 1, 1)
        far = date(2026, 6, 1)
        G = nx.DiGraph()
        G.add_edge("a", "b")
        notes = {
            "a": _meta("a", created_date=base),
            "b": _meta("b", created_date=far),
        }
        metrics = compute_temporal(G, notes)
        assert metrics.high_coherence_pct == 0.0
        assert metrics.low_coherence_pct == 100.0
        assert ("a", "b", (far - base).days) in metrics.temporally_distant_pairs

    def test_temporally_distant_pairs_filtered(self) -> None:
        """Only pairs >365 days apart appear in temporally_distant_pairs."""
        base = date(2026, 1, 1)
        G = nx.DiGraph()
        G.add_edge("a", "b")
        G.add_edge("a", "c")
        notes = {
            "a": _meta("a", created_date=base),
            "b": _meta("b", created_date=date(2026, 3, 1)),  # 59 days
            "c": _meta("c", created_date=date(2020, 1, 1)),  # ~2192 days
        }
        metrics = compute_temporal(G, notes)
        assert len(metrics.temporally_distant_pairs) == 1
        assert metrics.temporally_distant_pairs[0][0] == "a"
        assert metrics.temporally_distant_pairs[0][1] == "c"

    def test_missing_notes_skipped(self) -> None:
        """Edges referencing notes not in metadata dict are skipped."""
        G = nx.DiGraph()
        G.add_edge("exists", "missing")
        notes = {"exists": _meta("exists", created_date=date(2026, 1, 1))}
        metrics = compute_temporal(G, notes)
        assert metrics.temporal_deltas == []

    def test_missing_created_dates_skipped(self) -> None:
        """Edges where either note lacks created_date are skipped."""
        G = nx.DiGraph()
        G.add_edge("a", "b")
        notes = {
            "a": _meta("a", created_date=date(2026, 1, 1)),
            "b": _meta("b"),  # no created_date
        }
        metrics = compute_temporal(G, notes)
        assert metrics.temporal_deltas == []

    def test_staleness_via_created_date_fallback(self) -> None:
        """Notes only having created_date are checked for staleness via that date."""
        today = date.today()
        very_old = today - timedelta(days=400)
        G = nx.DiGraph()
        G.add_node("old_created")
        notes = {"old_created": _meta("old_created", created_date=very_old)}
        metrics = compute_temporal(G, notes)
        assert "old_created" in metrics.stale_notes

    def test_staleness_via_last_modified_fallback(self) -> None:
        """Notes only having last_modified are checked for staleness via mtime."""
        today = date.today()
        very_old_dt = datetime(today.year - 2, 1, 1, 0, 0, 0)
        G = nx.DiGraph()
        G.add_node("old_mtime")
        notes = {"old_mtime": _meta("old_mtime", last_modified=very_old_dt)}
        metrics = compute_temporal(G, notes)
        assert "old_mtime" in metrics.stale_notes

    def test_mixed_stale_and_fresh(self) -> None:
        """Mix of stale and fresh notes yields correct counts."""
        today = date.today()
        fresh = today - timedelta(days=30)
        old = today - timedelta(days=200)
        G = nx.DiGraph()
        G.add_nodes_from(["fresh", "old1", "old2"])
        notes = {
            "fresh": _meta("fresh", updated_date=fresh),
            "old1": _meta("old1", updated_date=old),
            "old2": _meta("old2", updated_date=old),
        }
        metrics = compute_temporal(G, notes)
        assert len(metrics.stale_notes) == 2
        assert "fresh" not in metrics.stale_notes