"""Graph Health Module — vault wikilink graph analysis.

Extends vault_audit.py with connectivity metrics, topological health,
semantic hygiene, temporal decay, and structural gap analysis.
"""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import networkx as nx
    from . import hygiene
    from . import prediction as pred_mod
    from . import scanner
    from . import scoring
    from . import structural
    from . import temporal
    from . import topology


# ---------------------------------------------------------------------------
# Shared data types
# ---------------------------------------------------------------------------


@dataclass
class NoteMetadata:
    """Metadata about a vault note collected during scanning."""

    path: Path
    stem: str  # filename without extension
    frontmatter: dict  # raw parsed YAML frontmatter
    title: str | None = None
    note_type: str | None = None  # frontmatter type field (spec, moc, design, etc.)
    tags: list[str] = field(default_factory=list)
    created_date: date | None = None
    updated_date: date | None = None
    last_modified: datetime | None = None  # filesystem mtime
    outbound_stems: list[str] = field(default_factory=list)  # wikilink targets
    inbound_stems: list[str] = field(default_factory=list)  # populated after graph build


@dataclass
class ConnectivityMetrics:
    """Connectivity analysis results: orphans, dead ends, density, components, bidirectionals."""

    orphan_rate: float = 0.0  # percentage (0-100)
    orphan_count: int = 0
    orphans: list[str] = field(default_factory=list)
    dead_end_rate: float = 0.0
    dead_end_count: int = 0
    dead_ends: list[str] = field(default_factory=list)
    link_density_avg: float = 0.0  # avg links per file
    link_density_class: str = ""  # healthy / warning / critical
    largest_component_pct: float = 0.0
    largest_component_class: str = ""
    bidirectional_ratio: float = 0.0
    bidirectional_class: str = ""
    missing_reciprocals: list[tuple[str, str]] = field(default_factory=list)  # (source, target)


@dataclass
class TopologicalMetrics:
    """Topological analysis results: PageRank, betweenness, communities, sinks."""

    pagerank_top: list[tuple[str, float]] = field(default_factory=list)  # (note, score)
    betweenness_bridges: list[tuple[str, float]] = field(default_factory=list)
    communities: list[list[str]] = field(default_factory=list)  # note clusters
    communities_needing_moc: list[list[str]] = field(default_factory=list)  # >=5 no MOC
    information_sinks: list[str] = field(default_factory=list)
    information_sink_rate: float = 0.0
    information_sink_class: str = ""


@dataclass
class HygieneMetrics:
    """Hygiene analysis results: tags, frontmatter, phantom links, over-linking."""

    non_conformant_tags: list[tuple[str, str]] = field(default_factory=list)  # (note, tag)
    near_duplicate_tags: list[tuple[str, str]] = field(default_factory=list)  # (tag_a, tag_b)
    single_use_tags: list[str] = field(default_factory=list)
    unused_tags: list[str] = field(default_factory=list)
    missing_fields: list[tuple[str, str]] = field(default_factory=list)  # (note, field)
    type_mismatches: list[tuple[str, str, str]] = field(default_factory=list)  # (note, field, expected)
    inconsistent_dates: list[tuple[str, str]] = field(default_factory=list)  # (note, description)
    phantom_links: list[tuple[str, str]] = field(default_factory=list)  # (source, target)
    over_linking: list[tuple[str, str, str]] = field(default_factory=list)  # (note, section, target)
    tag_conformity_pct: float = 100.0
    tag_conformity_class: str = ""
    frontmatter_completeness_pct: float = 100.0
    frontmatter_completeness_class: str = ""


@dataclass
class TemporalMetrics:
    """Temporal decay analysis results: staleness, coherence."""

    stale_notes: list[str] = field(default_factory=list)  # note stems
    dead_weight: list[str] = field(default_factory=list)  # stale + orphaned
    temporally_distant_pairs: list[tuple[str, str, int]] = field(default_factory=list)  # (a, b, delta_days)
    temporal_deltas: list[int] = field(default_factory=list)  # all deltas for distribution
    high_coherence_pct: float = 0.0  # % of links within 90 days
    low_coherence_pct: float = 0.0  # % of links > 365 days


@dataclass
class StructuralMetrics:
    """Structural gap analysis results: chain gaps, silos, broken cycles."""

    chain_gaps: list[tuple[str, str, str]] = field(default_factory=list)  # (a, c, b_intermediate)
    potential_silos: list[tuple[int, int, float]] = field(default_factory=list)  # (cluster_a, cluster_b, density)
    broken_cycles: list[list[str]] = field(default_factory=list)


@dataclass
class HealthScore:
    """Weighted health score for the vault graph."""

    overall: float = 0.0  # 0-100
    orphan_score: float = 0.0
    dead_end_score: float = 0.0
    link_density_score: float = 0.0
    largest_component_score: float = 0.0
    bidirectional_score: float = 0.0
    sink_score: float = 0.0
    tag_conformity_score: float = 0.0
    frontmatter_score: float = 0.0
    breakdown: dict[str, float] = field(default_factory=dict)


@dataclass
class ScoredPair:
    """A single scored missing-reciprocal candidate."""

    source: str = ""
    target: str = ""
    ensemble_score: float = 0.0
    adamic_adar: float = 0.0
    tfidf_cosine: float = 0.0
    community_match: float = 0.0


@dataclass
class LinkPredictionResult:
    """Output from the link prediction ensemble."""

    scored_pairs: list[ScoredPair] = field(default_factory=list)
    top_n: int = 20
    threshold: float = 0.7
    took_action: bool = False


@dataclass
class GraphHealthReport:
    """Aggregate output from all analysis passes."""

    connectivity: ConnectivityMetrics = field(default_factory=ConnectivityMetrics)
    topological: TopologicalMetrics = field(default_factory=TopologicalMetrics)
    hygiene: HygieneMetrics = field(default_factory=HygieneMetrics)
    temporal: TemporalMetrics = field(default_factory=TemporalMetrics)
    structural: StructuralMetrics = field(default_factory=StructuralMetrics)
    health_score: HealthScore = field(default_factory=HealthScore)
    link_prediction: LinkPredictionResult = field(default_factory=LinkPredictionResult)
    excluded_notes: list[str] = field(default_factory=list)
    notes_scanned: int = 0
    notes_excluded: int = 0

    def to_json(self) -> str:
        """Serialize to JSON, converting non-serializable types."""

        def _convert(obj: Any) -> Any:
            if isinstance(obj, (Path, date, datetime)):
                return str(obj)
            if isinstance(obj, set):
                return sorted(obj)
            return obj

        raw = asdict(self)
        return json.dumps(raw, indent=2, default=_convert)


# ---------------------------------------------------------------------------
# Excluded path checker
# ---------------------------------------------------------------------------

EXCLUDED_DIRS = {"_meta", ".obsidian", "addons"}


def should_exclude(path: Path, vault_root: Path) -> bool:
    """Check if a note path should be excluded from graph analysis.

    Args:
        path: Note file path to check.
        vault_root: Root directory of the vault.

    Returns:
        True if the path is in an excluded directory.
    """
    try:
        rel = path.relative_to(vault_root)
    except ValueError:
        return False
    return any(part in EXCLUDED_DIRS for part in rel.parts)


# ---------------------------------------------------------------------------
# GraphHealthRunner — orchestrator
# ---------------------------------------------------------------------------


class GraphHealthRunner:
    """Entry point for graph health analysis.

    Usage:
        runner = GraphHealthRunner(vault_root, repo_root)
        runner.scan_all_notes()               # read vault files
        runner.build_graph()                  # build nx.DiGraph
        report = runner.run_all()             # all analyses
        runner.write_reports(report, output_dir)
    """

    def __init__(self, vault_root: Path, repo_root: Path):
        """Initialize the runner.

        Args:
            vault_root: Path to the vault directory (e.g., docs/vault/).
            repo_root: Path to the repository root (e.g., for --fix mode).
        """
        self.vault_root = vault_root
        self.repo_root = repo_root
        self.notes: dict[str, NoteMetadata] = {}  # stem -> metadata
        self.graph = None  # nx.DiGraph (lazy, built by build_graph)
        self._filename_index: dict[str, list[Path]] | None = None

    def set_filename_index(self, index: dict[str, list[Path]]) -> None:
        """Pre-populate filename index from vault_audit.py scan.

        Args:
            index: Mapping from wikilink target to list of matching file paths.
        """
        self._filename_index = index

    def scan_all_notes(self) -> None:
        """Read all vault .md files and extract metadata + wikilinks.

        Single-pass: reads each file once, parses frontmatter with yaml,
        extracts wikilinks. Avoids double I/O.
        """
        import re
        import yaml

        all_md = sorted(self.vault_root.rglob("*.md"))
        self.notes = {}

        for note_path in all_md:
            if should_exclude(note_path, self.vault_root):
                continue

            stem = note_path.stem
            stem = unicodedata.normalize("NFC", stem)

            try:
                content = note_path.read_text(encoding="utf-8")
            except OSError:
                continue

            # Normalize content
            content = unicodedata.normalize("NFC", content)

            # Split frontmatter from body
            parts = content.split("---\n", 2)
            if len(parts) < 3:
                parts = content.split("---\r\n", 2)
            if len(parts) < 3:
                body = content
                fm = {}
            else:
                fm_text = parts[1]
                body = parts[2]
                try:
                    fm = yaml.safe_load(fm_text) or {}
                except Exception:
                    fm = {}

            # Extract wikilinks from body using regex
            wikilink_pattern = re.compile(r"\[\[([^\]]+)\]\]")
            all_links: list[str] = [
                unicodedata.normalize("NFC", m.group(1))
                for m in wikilink_pattern.finditer(body)
            ]

            # Extract from related field if present
            related = fm.get("related", [])
            if isinstance(related, list):
                for item in related:
                    if isinstance(item, str):
                        all_links.extend(
                            unicodedata.normalize("NFC", m.group(1))
                            for m in wikilink_pattern.finditer(item)
                        )
            elif isinstance(related, str):
                all_links.extend(
                    unicodedata.normalize("NFC", m.group(1))
                    for m in wikilink_pattern.finditer(related)
                )

            # Deduplicate preserving order
            seen: set[str] = set()
            unique_links = [
                link for link in all_links if not (link in seen or seen.add(link))
            ]

            created = self._parse_date(fm.get("created"))
            updated = self._parse_date(fm.get("updated"))
            try:
                last_mod = datetime.fromtimestamp(note_path.stat().st_mtime)
            except OSError:
                last_mod = None

            self.notes[stem] = NoteMetadata(
                path=note_path,
                stem=stem,
                frontmatter=fm,
                title=fm.get("title"),
                note_type=fm.get("type"),
                tags=fm.get("tags", []),
                created_date=created,
                updated_date=updated,
                last_modified=last_mod,
                outbound_stems=unique_links,
            )

    @staticmethod
    def _parse_frontmatter(path: Path) -> dict:
        """Minimal frontmatter parser.

        Args:
            path: Path to a markdown file.

        Returns:
            Parsed frontmatter dictionary or empty dict on failure.
        """
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            return {}
        import yaml

        parts = content.split("---\n", 2)
        if len(parts) < 3:
            parts = content.split("---\r\n", 2)
        if len(parts) < 3:
            return {}
        try:
            data = yaml.safe_load(parts[1]) or {}
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _parse_date(val: Any) -> date | None:
        """Parse a date from frontmatter (ISO string or date object).

        Args:
            val: Value to parse (str, date, datetime, or None).

        Returns:
            Parsed date or None.
        """
        if val is None:
            return None
        if isinstance(val, date) and not isinstance(val, datetime):
            return val
        if isinstance(val, datetime):
            return val.date()
        if isinstance(val, str):
            val = val.strip().strip("'\"")
            for fmt in (
                "%Y-%m-%d",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%fZ",
            ):
                try:
                    return datetime.strptime(val, fmt).date()
                except ValueError:
                    continue
        return None

    @staticmethod
    def _resolve_wikilink(target: str) -> str:
        """Strip directory prefix from a wikilink target to get the note stem.

        Vault wikilinks sometimes use path-prefixed format (e.g. [[Systems/X]],
        [[Discoveries/X]], [[Art/X]]) while notes are keyed by stem only (X).
        Strip everything up to and including the last / to resolve correctly.

        Args:
            target: Raw wikilink target (possibly with directory prefix).

        Returns:
            Resolved stem (last path component).
        """
        if "/" in target:
            return target.rsplit("/", 1)[-1]
        return target

    def build_graph(self) -> Any:
        """Build a directed wikilink graph from scanned notes.

        Returns:
            nx.DiGraph. Stores on self.graph.
        """
        import networkx as nx

        G = nx.DiGraph()

        for stem, meta in self.notes.items():
            G.add_node(stem, file_path=str(meta.path))
            for target in meta.outbound_stems:
                resolved = self._resolve_wikilink(target)
                # Only add edge if target exists in our notes (valid wikilink)
                if resolved in self.notes:
                    G.add_edge(stem, resolved)

        # Populate inbound stems
        for source, target in G.edges():
            if target in self.notes:
                self.notes[target].inbound_stems.append(source)

        self.graph = G
        return G

    def run_all(
        self, apply: bool = False, repo_root: Path | None = None
    ) -> GraphHealthReport:
        """Run all health checks and return a report.

        Args:
            apply: If True, run --fix mode on link prediction candidates.
            repo_root: Repository root path (needed for --fix to find notes).

        Returns:
            Fully-populated GraphHealthReport.
        """
        from . import (
            hygiene,
            prediction as pred_mod,
            scanner,
            scoring,
            structural,
            temporal,
            topology,
        )

        report = GraphHealthReport()
        report.notes_scanned = len(self.notes)

        if self.graph is None or len(self.graph.nodes) == 0:
            return report

        # Run each module
        report.connectivity = scanner.compute_connectivity(self.graph, self.notes)
        report.topological = topology.compute_topological(self.graph, self.notes)
        report.hygiene = hygiene.compute_hygiene(
            self.notes, self.vault_root, self._filename_index
        )
        report.temporal = temporal.compute_temporal(self.graph, self.notes)
        report.structural = structural.compute_structural(
            self.graph, self.notes, report.topological
        )

        # Link prediction ensemble
        communities = report.topological.communities
        missing = report.connectivity.missing_reciprocals
        if missing:
            result = pred_mod.compute_link_prediction(
                self.graph,
                self.notes,
                communities,
                missing,
            )
            # Apply state filtering. The link-prediction state sidecar lives under
            # the vault's _meta/audit/ (alongside the reports), not the repo root.
            state_root = self.vault_root
            if repo_root:
                state = pred_mod.load_state(state_root)
                current_scores = {
                    (p.source, p.target): p.ensemble_score
                    for p in result.scored_pairs
                }
                result.scored_pairs = pred_mod.filter_by_state(
                    result.scored_pairs, state, current_scores,
                )
            report.link_prediction = result

            # --fix mode
            if apply and repo_root:
                acted = pred_mod.apply_fix(result.scored_pairs, self.notes)
                if acted:
                    result.took_action = True
                    # Clean stale state entries
                    state = pred_mod.load_state(state_root)
                    state = pred_mod.clean_stale_entries(state, set(missing))
                    pred_mod.save_state(state_root, state)

        report.health_score = scoring.compute_health_score(report)

        return report

    def write_reports(
        self, report: GraphHealthReport, output_dir: Path
    ) -> tuple[Path, Path]:
        """Write JSON + Markdown reports.

        Args:
            report: The GraphHealthReport to write.
            output_dir: Directory to write reports into.

        Returns:
            Tuple of (json_path, md_path).
        """
        from . import report as report_mod

        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        json_path = output_dir / f"graph-health_{timestamp}.json"
        json_path.write_text(report.to_json(), encoding="utf-8")

        md_path = output_dir / f"graph-health_{timestamp}.md"
        md_path.write_text(
            report_mod.render_markdown(report, self.notes), encoding="utf-8"
        )

        return json_path, md_path
