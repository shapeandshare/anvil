# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Connectivity metrics for vault wikilink graph analysis.

FR-001-FR-008: inbound/outbound counts, orphan/dead-end detection,
link density, bidirectional completeness, largest component.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import networkx as nx

try:
    import networkx as nx
except ImportError:
    nx = None

from .types_connectivity_metrics import ConnectivityMetrics
from .types_note_metadata import NoteMetadata

# Exempt note types and names for orphan/dead-end detection
EXEMPT_ORPHAN_TYPES: set[str] = {"type/moc", "type/session-log"}
EXEMPT_ORPHAN_NAMES: set[str] = {"index", "README"}
EXEMPT_DEADEND_TYPES: set[str] = {"type/moc", "type/session-log"}
EXEMPT_DEADEND_NAMES: set[str] = {"index", "README"}


def compute_connectivity(
    G: nx.DiGraph,
    notes: dict[str, NoteMetadata],
    excluded_stems: set[str] | None = None,
) -> ConnectivityMetrics:
    """Compute connectivity metrics: orphans, dead ends, density, component, bidirectionals.

    Parameters
    ----------
    G : nx.DiGraph
        Directed wikilink graph (node stems with edges for links).
    notes : dict[str, NoteMetadata]
        Mapping from stem to ``NoteMetadata``.
    excluded_stems : set of str, optional
        Stems to exclude from orphan/dead-end/sink counts (e.g. spec
        subfiles, scaffold files). These notes remain in the graph for
        link resolution but are not counted in connectivity analysis.

    Returns
    -------
    ConnectivityMetrics
        All connectivity calculations.
    """
    metrics = ConnectivityMetrics()

    # --- Orphan detection ---
    for stem in G.nodes():
        meta = notes.get(stem)
        if meta is None:
            continue
        if _is_exempt(meta, EXEMPT_ORPHAN_TYPES, EXEMPT_ORPHAN_NAMES, excluded_stems):
            continue
        if G.in_degree(stem) == 0:
            metrics.orphans.append(stem)

    total_eligible = len(G.nodes()) - _count_exempt(
        notes, EXEMPT_ORPHAN_TYPES, EXEMPT_ORPHAN_NAMES, excluded_stems
    )
    metrics.orphan_count = len(metrics.orphans)
    metrics.orphan_rate = (
        (metrics.orphan_count / total_eligible * 100) if total_eligible > 0 else 0.0
    )

    # --- Dead end detection ---
    for stem in G.nodes():
        meta = notes.get(stem)
        if meta is None:
            continue
        if _is_exempt(meta, EXEMPT_DEADEND_TYPES, EXEMPT_DEADEND_NAMES, excluded_stems):
            continue
        if G.out_degree(stem) == 0:
            metrics.dead_ends.append(stem)

    metrics.dead_end_count = len(metrics.dead_ends)
    eligible_de = len(G.nodes()) - _count_exempt(
        notes, EXEMPT_DEADEND_TYPES, EXEMPT_DEADEND_NAMES, excluded_stems
    )
    metrics.dead_end_rate = (
        (metrics.dead_end_count / eligible_de * 100) if eligible_de > 0 else 0.0
    )

    # --- Link density ---
    total_out = G.number_of_edges()
    if len(G.nodes()) > 0:
        metrics.link_density_avg = total_out / len(G.nodes())
    if metrics.link_density_avg >= 3:
        metrics.link_density_class = "healthy"
    elif metrics.link_density_avg >= 1:
        metrics.link_density_class = "warning"
    else:
        metrics.link_density_class = "critical"

    # --- Largest connected component ---
    if G.number_of_nodes() > 0:
        wcc = list(nx.weakly_connected_components(G))
        largest = max(len(c) for c in wcc)
        metrics.largest_component_pct = largest / G.number_of_nodes() * 100
        if metrics.largest_component_pct >= 90:
            metrics.largest_component_class = "healthy"
        elif metrics.largest_component_pct >= 70:
            metrics.largest_component_class = "warning"
        else:
            metrics.largest_component_class = "critical"

    # --- Bidirectional completeness ---
    seen_pairs: set[tuple[str, str]] = set()
    reciprocal_pairs = 0
    missing_reciprocals: list[tuple[str, str]] = []

    for u, v in G.edges():
        if u == v:
            continue
        if _is_reciprocal_exempt(u, v, notes):
            continue

        pair = (u, v) if u <= v else (v, u)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        if G.has_edge(v, u):
            reciprocal_pairs += 1
        else:
            if G.has_edge(u, v):
                missing_reciprocals.append((u, v))
            else:
                missing_reciprocals.append((v, u))

    metrics.missing_reciprocals = missing_reciprocals
    total_pairs = len(seen_pairs)
    if total_pairs > 0:
        metrics.bidirectional_ratio = reciprocal_pairs / total_pairs * 100
        if metrics.bidirectional_ratio >= 30:
            metrics.bidirectional_class = "healthy"
        elif metrics.bidirectional_ratio >= 15:
            metrics.bidirectional_class = "warning"
        else:
            metrics.bidirectional_class = "critical"

    return metrics


def _is_spec_subfile(meta: NoteMetadata) -> bool:
    """Check if a note is a spec subfile (intentional leaf, not a navigation target).

    Parameters
    ----------
    meta : NoteMetadata
        Note metadata to check.

    Returns
    -------
    bool
        True if the note is a spec subfile.
    """
    try:
        parts = meta.path.parts
        specs_idx = parts.index("Specs")
    except ValueError:
        return False
    if specs_idx + 2 >= len(parts):
        return False
    spec_dir = parts[specs_idx + 1]
    main_note = f"{spec_dir}.md"
    return parts[-1] != main_note


def _is_exempt(
    meta: NoteMetadata,
    exempt_types: set[str],
    exempt_names: set[str],
    excluded_stems: set[str] | None = None,
) -> bool:
    """Check if a note is exempt from a metric based on type, name, or path.

    Parameters
    ----------
    meta : NoteMetadata
        Note metadata.
    exempt_types : set of str
        Type strings to exempt.
    exempt_names : set of str
        Stem names to exempt.
    excluded_stems : set of str, optional
        Additional stems to exclude (e.g. scaffold files from scanner).

    Returns
    -------
    bool
        True if the note should be exempted.
    """
    if meta.stem in exempt_names:
        return True
    if excluded_stems and meta.stem in excluded_stems:
        return True
    if meta.note_type and f"type/{meta.note_type}" in exempt_types:
        return True
    tags = set(meta.tags)
    if tags & exempt_types:
        return True
    if _is_spec_subfile(meta):
        return True
    return False


def _count_exempt(
    notes: dict[str, NoteMetadata],
    exempt_types: set[str],
    exempt_names: set[str],
    excluded_stems: set[str] | None = None,
) -> int:
    """Count how many notes are exempt from a metric.

    Parameters
    ----------
    notes : dict[str, NoteMetadata]
        All scanned notes.
    exempt_types : set of str
        Type strings to exempt.
    exempt_names : set of str
        Stem names to exempt.
    excluded_stems : set of str, optional
        Additional stems to exclude.

    Returns
    -------
    int
        Count of exempt notes.
    """
    count = 0
    for stem, meta in notes.items():
        if stem in exempt_names:
            count += 1
        elif _is_exempt(meta, exempt_types, exempt_names, excluded_stems):
            count += 1
    return count


def _is_reciprocal_exempt(
    source: str,
    target: str,
    notes: dict[str, NoteMetadata],
) -> bool:
    """Check if an edge should be excluded from reciprocal expectation.

    Parameters
    ----------
    source : str
        Source stem of the edge.
    target : str
        Target stem of the edge.
    notes : dict[str, NoteMetadata]
        All scanned notes.

    Returns
    -------
    bool
        True if this edge should be exempt from reciprocal expectation.
    """
    if target == "Constitution":
        return True
    meta_src = notes.get(source)
    if meta_src and _is_spec_subfile(meta_src):
        return True
    meta_tgt = notes.get(target)
    if meta_tgt and "Thread" in meta_tgt.stem:
        return True
    return False
