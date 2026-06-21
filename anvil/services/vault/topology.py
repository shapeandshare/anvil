# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Topological analysis for vault wikilink graph.

PageRank authority, betweenness centrality bridges,
Louvain community detection, information sink detection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import networkx as nx

from ._types import NoteMetadata, TopologicalMetrics


def compute_topological(
    G: nx.DiGraph,
    notes: dict[str, NoteMetadata],
) -> TopologicalMetrics:
    """Compute topological metrics: PageRank, betweenness, communities, sinks.

    Parameters
    ----------
    G : nx.DiGraph
        Directed wikilink graph.
    notes : dict[str, NoteMetadata]
        Mapping from stem to ``NoteMetadata``.

    Returns
    -------
    TopologicalMetrics
        All topology calculations.
    """
    import networkx as nx

    metrics = TopologicalMetrics()

    # --- PageRank authority ---
    if G.number_of_nodes() > 0:
        pagerank_scores = nx.pagerank(G, alpha=0.85)
        sorted_pr = sorted(pagerank_scores.items(), key=lambda x: x[1], reverse=True)
        top_n = max(1, int(len(sorted_pr) * 0.05))
        metrics.pagerank_top = sorted_pr[:top_n]

    # --- Betweenness centrality bridges ---
    if G.number_of_nodes() > 0:
        betweenness_scores = nx.betweenness_centrality(G)
        sorted_bc = sorted(betweenness_scores.items(), key=lambda x: x[1], reverse=True)
        top_n = max(1, int(len(sorted_bc) * 0.10))
        high_betweenness: list[tuple[str, float]] = []
        for stem, score in sorted_bc:
            if score > 0.1 or len(high_betweenness) < top_n:
                high_betweenness.append((stem, score))
        metrics.betweenness_bridges = high_betweenness

    # --- Louvain community detection ---
    if G.number_of_nodes() > 0:
        G_undirected = G.to_undirected()
        try:
            raw_communities = list(
                nx.community.louvain_communities(G_undirected, seed=42)
            )
        except AttributeError:
            raw_communities = list(
                nx.community.greedy_modularity_communities(G_undirected)
            )

        community_lists = [list(c) for c in raw_communities]
        metrics.communities = community_lists

        for community in community_lists:
            if len(community) >= 5:
                has_moc = _community_has_moc(community, notes)
                if not has_moc:
                    metrics.communities_needing_moc.append(community)

    # --- Information sinks ---
    if G.number_of_nodes() > 0:
        sinks: list[str] = []
        total_nodes = 0

        for stem in G.nodes():
            in_deg = G.in_degree(stem)
            out_deg = G.out_degree(stem)
            if in_deg == 0 and out_deg == 0:
                continue
            total_nodes += 1
            if in_deg > 0 and out_deg == 0:
                sinks.append(stem)

        metrics.information_sinks = sinks
        if total_nodes > 0:
            sink_rate = len(sinks) / total_nodes * 100
            metrics.information_sink_rate = sink_rate
            if sink_rate < 5:
                metrics.information_sink_class = "healthy"
            elif sink_rate <= 10:
                metrics.information_sink_class = "warning"
            else:
                metrics.information_sink_class = "critical"

    return metrics


def _community_has_moc(
    community: list[str],
    notes: dict[str, NoteMetadata],
) -> bool:
    """Check if a community has a Map of Content node.

    A community needs a MOC if it has >=5 members.

    Parameters
    ----------
    community : list of str
        List of note stems in the community.
    notes : dict[str, NoteMetadata]
        Mapping from stem to ``NoteMetadata``.

    Returns
    -------
    bool
        True if the community has a MOC.
    """
    for stem in community:
        meta = notes.get(stem)
        if meta is None:
            continue
        if (
            meta.note_type in ("moc", "spec")
            or "type/moc" in meta.tags
            or "type/spec" in meta.tags
        ):
            return True
    return False
