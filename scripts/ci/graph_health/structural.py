"""Structural gap analysis for vault wikilink graph.

Chain gaps — missing intermediate notes in transitive relationships.
Inter-cluster bridge density — potential silos between communities.
Broken cycles — isolated cycles with no external connections.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import networkx as nx
    from . import StructuralMetrics, TopologicalMetrics, NoteMetadata

# Maximum out-degree for a note to be considered a specific-enough
# intermediate concept (rather than a broad hub like a MOC or thread).
# Notes with more outbound links than this are excluded from being
# suggested as "missing intermediate" concepts in chain gap detection.
_CHAIN_GAP_MAX_OUT_DEGREE = 8


def compute_structural(
    G: "nx.DiGraph",
    notes: dict[str, NoteMetadata],
    topological: TopologicalMetrics,
) -> StructuralMetrics:
    """Compute structural gap metrics: chain gaps, potential silos, broken cycles.

    Args:
        G: Directed wikilink graph (nodes = note stems).
        notes: Stem -> NoteMetadata mapping.
        topological: Precomputed topological metrics (contains communities).

    Returns:
        StructuralMetrics with chain_gaps, potential_silos, broken_cycles.
    """
    import networkx as nx
    from . import StructuralMetrics

    metrics = StructuralMetrics()

    # Chain gaps
    metrics.chain_gaps = _find_chain_gaps(G, notes)

    # Inter-cluster bridge density
    metrics.potential_silos = _find_potential_silos(G, topological.communities)

    # Broken cycles
    metrics.broken_cycles = _find_broken_cycles(G)

    return metrics


def _is_hub(meta: NoteMetadata | None, out_degree: int, G: "nx.DiGraph") -> bool:
    """Check if a note is a hub too broad to be a meaningful intermediate.

    Args:
        meta: NoteMetadata for the note.
        out_degree: Out-degree of the note in the graph.
        G: Directed wikilink graph.

    Returns:
        True if the note is a hub (MOC, reference, high out-degree, or spec subfile).
    """
    if meta is None:
        return False
    tags = set(meta.tags)
    if "type/moc" in tags or "type/reference" in tags:
        return True
    if out_degree > _CHAIN_GAP_MAX_OUT_DEGREE:
        return True
    from .scanner import _is_spec_subfile

    return _is_spec_subfile(meta)


def _find_chain_gaps(
    G: "nx.DiGraph", notes: dict[str, NoteMetadata]
) -> list[tuple[str, str, str]]:
    """Find missing intermediate notes in transitive relationships.

    Args:
        G: Directed wikilink graph.
        notes: Stem -> NoteMetadata mapping.

    Returns:
        List of (source, target, intermediate) tuples where a chain gap exists.
    """
    import networkx as nx

    pred_cache = {node: set(G.predecessors(node)) for node in G.nodes()}

    chain_gaps: list[tuple[str, str, str]] = []
    for a in G.nodes():
        successors = list(G.successors(a))
        pred_a = pred_cache[a]
        for c in successors:
            if a == c:
                continue
            pred_c = pred_cache[c]
            common = pred_a.intersection(pred_c)
            for b in common:
                if b == a:
                    continue
                if G.has_edge(a, b):
                    continue
                meta_b = notes.get(b)
                out_deg_b = G.out_degree(b)
                if _is_hub(meta_b, out_deg_b, G):
                    continue
                chain_gaps.append((a, c, b))

    return chain_gaps


def _find_potential_silos(
    G: "nx.DiGraph", communities: list[list[str]]
) -> list[tuple[int, int, float]]:
    """Find potential silos between clusters based on bridge density.

    For each pair of clusters (ci, cj), count bridging notes that have
    links to members of BOTH clusters. Compute bridge density as:
    bridging_notes / min(len(ci), len(cj)). If density < 0.02 (< 2%),
    flag as potential silo.

    Args:
        G: Directed wikilink graph.
        communities: List of clusters, each cluster is list of note stems.

    Returns:
        List of (cluster_i, cluster_j, density) tuples where density < 0.02.
    """
    potential_silos: list[tuple[int, int, float]] = []

    if not communities:
        return potential_silos

    node_to_cluster: dict[str, int] = {}
    for i, cluster in enumerate(communities):
        for node in cluster:
            node_to_cluster[node] = i

    for i in range(len(communities)):
        for j in range(i + 1, len(communities)):
            cluster_i = communities[i]
            cluster_j = communities[j]

            bridging_notes: set[str] = set()

            for node in cluster_i:
                if node not in G:
                    continue
                for neighbor in G.successors(node):
                    if (
                        neighbor in node_to_cluster
                        and node_to_cluster[neighbor] == j
                    ):
                        bridging_notes.add(node)
                        break
                else:
                    for predecessor in G.predecessors(node):
                        if (
                            predecessor in node_to_cluster
                            and node_to_cluster[predecessor] == j
                        ):
                            bridging_notes.add(node)
                            break

            for node in cluster_j:
                if node not in G:
                    continue
                for neighbor in G.successors(node):
                    if (
                        neighbor in node_to_cluster
                        and node_to_cluster[neighbor] == i
                    ):
                        bridging_notes.add(node)
                        break
                else:
                    for predecessor in G.predecessors(node):
                        if (
                            predecessor in node_to_cluster
                            and node_to_cluster[predecessor] == i
                        ):
                            bridging_notes.add(node)
                            break

            min_size = min(len(cluster_i), len(cluster_j))
            if min_size > 0:
                density = len(bridging_notes) / min_size
                if density < 0.02:
                    potential_silos.append((i, j, density))

    return potential_silos


def _find_broken_cycles(G: "nx.DiGraph") -> list[list[str]]:
    """Find isolated cycles (<=6 nodes) with no external edges.

    Args:
        G: Directed wikilink graph.

    Returns:
        List of cycles, where each cycle is a list of note stems.
    """
    import networkx as nx

    broken_cycles: list[list[str]] = []

    try:
        cycles = list(nx.simple_cycles(G, length_bound=6))
    except TypeError:
        try:
            cycles = []
            for i, cycle in enumerate(nx.simple_cycles(G)):
                if i >= 200:
                    break
                if len(cycle) <= 6:
                    cycles.append(cycle)
        except Exception:
            return broken_cycles
    except nx.NetworkXNoCycle:
        return broken_cycles

    for cycle in cycles:
        cycle_set = set(cycle)
        has_external_edges = False

        for node in cycle:
            for neighbor in G.successors(node):
                if neighbor not in cycle_set:
                    has_external_edges = True
                    break
            if has_external_edges:
                break
            for predecessor in G.predecessors(node):
                if predecessor not in cycle_set:
                    has_external_edges = True
                    break
            if has_external_edges:
                break

        if not has_external_edges:
            broken_cycles.append(list(cycle))

    return broken_cycles