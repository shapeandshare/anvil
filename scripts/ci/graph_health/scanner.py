"""Connectivity metrics and wikilink graph builder.

FR-001-FR-008: inbound/outbound counts, orphan/dead-end detection,
link density, bidirectional completeness, largest component.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import networkx as nx
    from . import ConnectivityMetrics, NoteMetadata


def compute_connectivity(
    G: "nx.DiGraph",
    notes: dict[str, NoteMetadata],
) -> ConnectivityMetrics:
    """Compute connectivity metrics: orphans, dead ends, density, component, bidirectionals.

    Args:
        G: Directed wikilink graph (node stems with edges for links).
        notes: Mapping from stem to NoteMetadata.

    Returns:
        ConnectivityMetrics dataclass with all connectivity calculations.
    """
    import networkx as nx
    from . import ConnectivityMetrics

    metrics = ConnectivityMetrics()

    # --- Orphan detection ---
    EXEMPT_ORPHAN_TYPES = {"type/moc", "type/session-log"}
    EXEMPT_ORPHAN_NAMES = {"index", "README"}

    for stem in G.nodes():
        meta = notes.get(stem)
        if meta is None:
            continue
        if _is_exempt(meta, EXEMPT_ORPHAN_TYPES, EXEMPT_ORPHAN_NAMES):
            continue
        if G.in_degree(stem) == 0:
            metrics.orphans.append(stem)

    total_eligible = len(G.nodes()) - _count_exempt(
        notes, EXEMPT_ORPHAN_TYPES, EXEMPT_ORPHAN_NAMES
    )
    metrics.orphan_count = len(metrics.orphans)
    metrics.orphan_rate = (
        (metrics.orphan_count / total_eligible * 100) if total_eligible > 0 else 0.0
    )

    # --- Dead end detection ---
    EXEMPT_DEADEND_TYPES = {"type/moc", "type/session-log"}
    EXEMPT_DEADEND_NAMES = {"index", "README"}

    for stem in G.nodes():
        meta = notes.get(stem)
        if meta is None:
            continue
        if _is_exempt(meta, EXEMPT_DEADEND_TYPES, EXEMPT_DEADEND_NAMES):
            continue
        if G.out_degree(stem) == 0:
            metrics.dead_ends.append(stem)

    metrics.dead_end_count = len(metrics.dead_ends)
    eligible_de = len(G.nodes()) - _count_exempt(
        notes, EXEMPT_DEADEND_TYPES, EXEMPT_DEADEND_NAMES
    )
    metrics.dead_end_rate = (
        (metrics.dead_end_count / eligible_de * 100) if eligible_de > 0 else 0.0
    )

    # --- Link density ---
    total_out = sum(1 for _ in G.edges())
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
            continue  # Skip self-loops

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
    """Check if a note is a spec subfile.

    Spec directories are organized as subdirectories within a vault with
    a root note and subfiles (plans, tasks, etc.). Subfiles are intentional
    leaves: they document a spec but are not navigation targets. Exempting
    them from orphan/dead-end detection prevents noise.

    Args:
        meta: NoteMetadata for the note to check.

    Returns:
        True if the note is a spec subfile (not the root spec note).
    """
    try:
        parts = meta.path.parts
        specs_idx = parts.index("Specs")
    except ValueError:
        return False
    # Need at least Specs/NNN Title/filename
    if specs_idx + 2 >= len(parts):
        return False
    spec_dir = parts[specs_idx + 1]
    main_note = f"{spec_dir}.md"
    return parts[-1] != main_note


def _is_exempt(
    meta: NoteMetadata, exempt_types: set[str], exempt_names: set[str]
) -> bool:
    """Check if a note is exempt from a metric based on type, name, or path.

    Args:
        meta: NoteMetadata for the note.
        exempt_types: Set of type strings to exempt (e.g. {"type/moc"}).
        exempt_names: Set of stem names to exempt (e.g. {"index"}).

    Returns:
        True if the note should be exempted.
    """
    if meta.stem in exempt_names:
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
    notes: dict[str, NoteMetadata], exempt_types: set[str], exempt_names: set[str]
) -> int:
    """Count how many notes are exempt from a metric.

    Args:
        notes: All scanned notes.
        exempt_types: Set of type strings to exempt.
        exempt_names: Set of stem names to exempt.

    Returns:
        Count of exempt notes.
    """
    count = 0
    for stem, meta in notes.items():
        if stem in exempt_names:
            count += 1
        elif _is_exempt(meta, exempt_types, exempt_names):
            count += 1
    return count


def _is_reciprocal_exempt(
    source: str, target: str, notes: dict[str, NoteMetadata]
) -> bool:
    """Check if a (source, target) edge should be excluded from reciprocal expectation.

    Three categories are exempt:
    1. Target is Constitution -- foundational governance doc cited by many;
       expecting reciprocity would produce meaningless backlinks.
    2. Target is a thread/essay note -- outward-facing essays link to concepts;
       concepts should not reciprocate many thread backlinks.
    3. Source is a spec sub-artifact (plan/task/etc.) -- template-generated
       files that link to their parent spec by design.

    Args:
        source: Source stem of the edge.
        target: Target stem of the edge.
        notes: All scanned notes.

    Returns:
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
