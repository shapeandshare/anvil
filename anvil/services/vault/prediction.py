# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Link prediction ensemble for vault graph health report.

Ranks missing reciprocal links by a weighted ensemble of structural
(Adamic-Adar), content (TF-IDF cosine), and community (Louvain) signals.
Supports dry-run (ranked table) and ``--fix`` mode (auto-insert reciprocals).
"""

from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path
from typing import Any

from ._types import LinkPredictionResult, NoteMetadata, ScoredPair

try:
    import networkx as nx
except ImportError:
    nx = None

# Configuration
ENSEMBLE_WEIGHTS: dict[str, float] = {
    "adamic_adar": 0.4,
    "community_match": 0.3,
    "tfidf": 0.3,
}

FIX_THRESHOLD = 0.7
TOP_N = 20
STATE_FILE = "_meta/audit/link_prediction_state.json"


def compute_adamic_adar(
    graph: Any,
    candidates: list[tuple[str, str]],
) -> dict[tuple[str, str], float]:
    """Compute Adamic-Adar index for each candidate pair.

    Parameters
    ----------
    graph : nx.DiGraph
        Directed wikilink graph.
    candidates : list[tuple[str, str]]
        (source, target) pairs to score.

    Returns
    -------
    dict[tuple[str, str], float]
        Mapping from (source, target) -> score (0-1 normalized via tanh).
    """
    undirected = graph.to_undirected()

    scores: dict[tuple[str, str], float] = {}
    adar = nx.adamic_adar_index(undirected, ebunch=candidates)
    for u, v, s in adar:
        scores[(u, v)] = float(s)

    return {
        pair: 1.0 - 2.0 / (math.exp(2.0 * score) + 1.0)
        for pair, score in scores.items()
    }


def compute_tfidf(
    notes: dict[str, NoteMetadata],
    candidates: list[tuple[str, str]],
) -> dict[tuple[str, str], float]:
    """Compute TF-IDF cosine similarity between each candidate pair's body text.

    Parameters
    ----------
    notes : dict[str, NoteMetadata]
        Stem -> ``NoteMetadata`` mapping.
    candidates : list[tuple[str, str]]
        (source, target) pairs to score.

    Returns
    -------
    dict[tuple[str, str], float]
        (source, target) -> cosine similarity (0-1).
        Returns empty dict if scikit-learn is unavailable (signal reweights).
    """
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
    except ImportError:
        return {}

    unique_stems: set[str] = set()
    for u, v in candidates:
        unique_stems.add(u)
        unique_stems.add(v)

    stem_text: dict[str, str] = {}
    for stem in unique_stems:
        meta = notes.get(stem)
        if not meta:
            stem_text[stem] = ""
            continue
        try:
            content = meta.path.read_text(encoding="utf-8")
        except OSError:
            stem_text[stem] = ""
            continue
        body = content
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) == 3:
                body = parts[2].lstrip("\n")
        stem_text[stem] = body.strip()

    if not stem_text:
        return {}

    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        max_features=5000,
        stop_words="english",
    )
    stems = list(stem_text.keys())
    texts = [stem_text[s] for s in stems]
    try:
        tfidf_matrix = vectorizer.fit_transform(texts)
    except ValueError:
        return {}

    stem_index = {s: i for i, s in enumerate(stems)}
    scores: dict[tuple[str, str], float] = {}
    for u, v in candidates:
        i = stem_index.get(u)
        j = stem_index.get(v)
        if i is None or j is None:
            scores[(u, v)] = 0.0
        elif len(texts[i]) < 10 or len(texts[j]) < 10:
            scores[(u, v)] = 0.0
        else:
            sim = cosine_similarity(tfidf_matrix[i], tfidf_matrix[j])[0][0]
            scores[(u, v)] = float(sim)

    return scores


def _build_community_lookup(communities: list[list[str]]) -> dict[str, int]:
    """Convert communities into {node: community_id} lookup.

    Parameters
    ----------
    communities : list[list[str]]
        List of clusters, each cluster is list of note stems.

    Returns
    -------
    dict[str, int]
        Note stem -> community index.
    """
    lookup: dict[str, int] = {}
    for cid, cluster in enumerate(communities):
        for node in cluster:
            lookup[node] = cid
    return lookup


def compute_link_prediction(
    graph: Any,
    notes: dict[str, NoteMetadata],
    communities: list[list[str]],
    missing_reciprocals: list[tuple[str, str]],
    weights: dict[str, float] | None = None,
) -> LinkPredictionResult:
    """Score all missing reciprocal pairs and return a ranked result.

    Parameters
    ----------
    graph : nx.DiGraph
        Directed wikilink graph.
    notes : dict[str, NoteMetadata]
        Stem -> ``NoteMetadata`` mapping.
    communities : list[list[str]]
        Louvain clusters from topology phase.
    missing_reciprocals : list[tuple[str, str]]
        (source, target) pairs needing backlinks.
    weights : dict[str, float] or None
        Optional override for ensemble weights.

    Returns
    -------
    LinkPredictionResult
        Scored pairs sorted by ensemble score descending.
    """
    if not missing_reciprocals:
        return LinkPredictionResult()

    w = weights or ENSEMBLE_WEIGHTS
    comm_lookup = _build_community_lookup(communities)

    adar_scores = compute_adamic_adar(graph, missing_reciprocals)
    tfidf_scores = compute_tfidf(notes, missing_reciprocals)

    scored: list[ScoredPair] = []
    for u, v in missing_reciprocals:
        adar = adar_scores.get((u, v), 0.0)
        tfidf = tfidf_scores.get((u, v), 0.0)

        cu = comm_lookup.get(u)
        cv = comm_lookup.get(v)
        comm_match = 1.0 if (cu is not None and cv is not None and cu == cv) else 0.0

        available_weight = 0.0
        ensemble = 0.0

        ensemble += w["adamic_adar"] * adar
        available_weight += w["adamic_adar"]
        ensemble += w["tfidf"] * tfidf
        available_weight += w["tfidf"]
        ensemble += w["community_match"] * comm_match
        available_weight += w["community_match"]

        if available_weight > 0:
            ensemble /= available_weight
        ensemble = max(0.0, min(1.0, ensemble))

        scored.append(
            ScoredPair(
                source=u,
                target=v,
                ensemble_score=ensemble,
                adamic_adar=adar,
                tfidf_cosine=tfidf,
                community_match=comm_match,
            )
        )

    scored.sort(key=lambda p: p.ensemble_score, reverse=True)
    return LinkPredictionResult(scored_pairs=scored)


def _state_path(state_root: Path) -> Path:
    """Get the path to the link prediction state file.

    Parameters
    ----------
    state_root : Path
        Root directory for state storage (vault root in practice).

    Returns
    -------
    Path
        Path to the state JSON file.
    """
    return state_root / STATE_FILE


def load_state(state_root: Path) -> dict[str, Any]:
    """Load human-in-the-loop decisions from sidecar JSON.

    Parameters
    ----------
    state_root : Path
        Root directory for state storage.

    Returns
    -------
    dict
        State entries, or empty dict on failure.
    """
    path = _state_path(state_root)
    if not path.exists():
        return {}
    try:
        result: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return result
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state_root: Path, state: dict[str, Any]) -> None:
    """Persist human-in-the-loop decisions to sidecar JSON.

    Parameters
    ----------
    state_root : Path
        Root directory for state storage.
    state : dict
        State entries to persist.
    """
    path = _state_path(state_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def filter_by_state(
    scored: list[ScoredPair],
    state: dict[str, Any] | None = None,
    current_scores: dict[tuple[str, str], float] | None = None,
) -> list[ScoredPair]:
    """Filter scored pairs against persisted state.

    Parameters
    ----------
    scored : list[ScoredPair]
        List of scored pairs.
    state : dict or None
        State entries from ``load_state()``.
    current_scores : dict or None
        (source, target) -> current ensemble score.

    Returns
    -------
    list[ScoredPair]
        Filtered list, excluding stale confirmed/dismissed entries.
    """
    filtered: list[ScoredPair] = []
    if state is None:
        state = {}
    if current_scores is None:
        current_scores = {}
    for pair in scored:
        key = f"({pair.source}, {pair.target})"
        entry = state.get(key)
        if entry is None:
            filtered.append(pair)
        elif entry["state"] == "open":
            filtered.append(pair)
        elif entry["state"] in ("confirmed", "dismissed"):
            stored_score = entry.get("score", 0.0)
            current = current_scores.get((pair.source, pair.target), 0.0)
            if stored_score > 0 and abs(current - stored_score) / stored_score > 0.3:
                filtered.append(pair)
        else:
            filtered.append(pair)
    return filtered


def clean_stale_entries(
    state: dict[str, Any],
    current_missing: set[tuple[str, str]],
) -> dict[str, Any]:
    """Remove state entries for pairs that are no longer missing.

    Parameters
    ----------
    state : dict
        State entries.
    current_missing : set[tuple[str, str]]
        Current set of missing reciprocal pairs.

    Returns
    -------
    dict
        Cleaned state.
    """
    return {k: v for k, v in state.items() if _parse_state_key(k) in current_missing}


def _parse_state_key(key: str) -> tuple[str, str] | None:
    """Parse ``(source, target)`` string back to tuple.

    Parameters
    ----------
    key : str
        String key like ``"(source, target)"``.

    Returns
    -------
    tuple[str, str] or None
        (source, target) tuple, or ``None`` if unparseable.
    """
    try:
        inner = key.strip("()")
        parts = inner.split(", ", 1)
        if len(parts) == 2:
            return (parts[0].strip(" '\""), parts[1].strip(" '\""))
    except Exception:
        return None
    return None


def _is_working_tree_dirty() -> bool:
    """Check if git working tree has uncommitted changes.

    Returns
    -------
    bool
        True if there are uncommitted changes.
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
        )
        return bool(result.stdout.strip())
    except (FileNotFoundError, subprocess.SubprocessError):
        return False


def apply_fix(
    scored_pairs: list[ScoredPair],
    notes: dict[str, NoteMetadata],
    threshold: float = FIX_THRESHOLD,
) -> bool:
    """Insert reciprocal wikilinks for high-confidence candidates.

    For each candidate with ``ensemble_score >= threshold``, adds ``[[source]]``
    to the target note's ``related:`` frontmatter field.

    Parameters
    ----------
    scored_pairs : list[ScoredPair]
        Scored pairs.
    notes : dict[str, NoteMetadata]
        Stem -> ``NoteMetadata`` mapping.
    threshold : float
        Minimum ensemble score to auto-fix (default 0.7).

    Returns
    -------
    bool
        True if any fix was applied.
    """
    if _is_working_tree_dirty():
        print(
            "[LinkPrediction] WARNING: Working tree is dirty. "
            "Commit or stash changes before --fix mode."
        )
        return False

    candidates = [p for p in scored_pairs if p.ensemble_score >= threshold]
    if not candidates:
        return False

    applied = False
    for pair in candidates:
        meta = notes.get(pair.target)
        if not meta:
            continue
        path = meta.path
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue

        if f"[[{pair.source}]]" in content:
            continue

        parts = content.split("---", 2)
        if len(parts) < 3:
            continue

        frontmatter = parts[1]
        new_link = f"  - '[[{pair.source}]]'"
        lines = frontmatter.split("\n")

        if "related:" in frontmatter:
            new_lines: list[str] = []
            inserted = False
            i = 0
            indent = "  "
            while i < len(lines):
                new_lines.append(lines[i])
                if lines[i].strip().startswith("related:") and not inserted:
                    i += 1
                    while i < len(lines) and (
                        lines[i].strip() == "" or lines[i].startswith(("  ", "- "))
                    ):
                        if lines[i].strip():
                            if not inserted:
                                leading = len(lines[i]) - len(lines[i].lstrip())
                                indent = " " * leading if leading > 0 else ""
                                inserted = True
                            new_lines.append(lines[i])
                        i += 1
                    new_link = f"{indent}- '[[{pair.source}]]'"
                    new_lines.append(new_link)
                    inserted = True
                    continue
                i += 1
            new_fm = "\n".join(new_lines)
        else:
            new_lines = []
            inserted = False
            in_tags = False
            for line in lines:
                if line.strip().startswith("tags:"):
                    in_tags = True
                    new_lines.append(line)
                    continue
                if in_tags:
                    if line.startswith(("  ", "- ")):
                        new_lines.append(line)
                        continue
                    in_tags = False
                if not inserted and line.strip().startswith(
                    ("created:", "epic:", "spec_number:", "phase:", "status:")
                ):
                    new_lines.append("related:")
                    new_lines.append(new_link)
                    inserted = True
                new_lines.append(line)
            if not inserted:
                new_lines.append("related:")
                new_lines.append(new_link)
            new_fm = "\n".join(new_lines)

        new_content = f"---{new_fm}---{parts[2]}"
        path.write_text(new_content, encoding="utf-8")
        print(f"  [fix] Added [[{pair.source}]] to {pair.target}")
        applied = True

    if applied:
        print(
            f"  [fix] Applied {len(candidates)} reciprocal links "
            f"(threshold >= {threshold})."
        )

    return applied
