"""Temporal decay analysis for vault wikilink graph.

Stale notes (updated_date -> created_date -> last_modified fallback).
Temporal coherence of directed edges (created_date deltas).
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import networkx as nx

from ._types import NoteMetadata, TemporalMetrics


def compute_temporal(
    G: nx.DiGraph,
    notes: dict[str, NoteMetadata],
) -> TemporalMetrics:
    """Compute temporal decay metrics for the vault graph.

    Parameters
    ----------
    G : nx.DiGraph
        Directed wikilink graph (stem -> stem edges).
    notes : dict[str, NoteMetadata]
        Mapping from stem to ``NoteMetadata``.

    Returns
    -------
    TemporalMetrics
        Stale notes, dead weight, temporal deltas, and coherence stats.
    """
    metrics = TemporalMetrics()
    today = date.today()

    # --- Stale notes detection (>180 days) ---
    stale_notes: list[str] = []
    for stem, meta in notes.items():
        staleness_date = _get_staleness_date(meta)
        if staleness_date is None:
            continue
        delta_days = (today - staleness_date).days
        if delta_days > 180:
            stale_notes.append(stem)

    metrics.stale_notes = stale_notes

    # --- Dead weight (stale + orphaned) ---
    dead_weight: list[str] = []
    for stem in stale_notes:
        if G.in_degree(stem) == 0:
            dead_weight.append(stem)

    metrics.dead_weight = dead_weight

    # --- Temporal coherence ---
    temporal_deltas: list[int] = []
    temporally_distant_pairs: list[tuple[str, str, int]] = []

    for source, target in G.edges():
        source_meta = notes.get(source)
        target_meta = notes.get(target)

        if source_meta is None or target_meta is None:
            continue

        source_date = source_meta.created_date
        target_date = target_meta.created_date

        if source_date is None or target_date is None:
            continue

        delta_days = abs((source_date - target_date).days)
        temporal_deltas.append(delta_days)

        if delta_days > 365:
            temporally_distant_pairs.append((source, target, delta_days))

    metrics.temporal_deltas = temporal_deltas
    metrics.temporally_distant_pairs = temporally_distant_pairs

    if temporal_deltas:
        total_links = len(temporal_deltas)
        high_coherence = sum(1 for delta in temporal_deltas if delta <= 90)
        metrics.high_coherence_pct = (
            (high_coherence / total_links) * 100 if total_links > 0 else 0.0
        )
        low_coherence = sum(1 for delta in temporal_deltas if delta > 365)
        metrics.low_coherence_pct = (
            (low_coherence / total_links) * 100 if total_links > 0 else 0.0
        )

    return metrics


def _get_staleness_date(meta: NoteMetadata) -> date | None:
    """Get the date to use for staleness determination using fallback chain.

    Fallback chain:
    1. ``updated_date`` from frontmatter
    2. ``created_date`` from frontmatter
    3. ``last_modified`` (filesystem mtime)

    Parameters
    ----------
    meta : NoteMetadata
        Note metadata to check.

    Returns
    -------
    date or None
        The staleness reference date, or ``None`` if unavailable.
    """
    if meta.updated_date is not None:
        return meta.updated_date
    if meta.created_date is not None:
        return meta.created_date
    if meta.last_modified is not None:
        return meta.last_modified.date()
    return None
