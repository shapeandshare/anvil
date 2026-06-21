# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Data types for vault health analysis — Pydantic BaseModels.

Migrated from legacy ``@dataclass`` types in ``scripts/ci/graph_health/__init__.py``
and converted to :class:`pydantic.BaseModel` per project convention.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class NoteMetadata(BaseModel):
    """Metadata about a vault note collected during scanning.

    Attributes
    ----------
    path : Path
        Absolute filesystem path to the ``.md`` file.
    stem : str
        Filename without extension (NFC-normalized).
    frontmatter : dict
        Raw parsed YAML frontmatter.
    title : str | None
        Frontmatter ``title`` field.
    note_type : str | None
        Frontmatter ``type`` field.
    tags : list[str]
        Frontmatter ``tags`` list.
    created_date : date | None
        Frontmatter ``created`` field.
    updated_date : date | None
        Frontmatter ``updated`` field.
    last_modified : datetime | None
        Filesystem mtime.
    outbound_stems : list[str]
        Wikilink targets extracted from body text.
    inbound_stems : list[str]
        Populated after graph build (notes linking to this note).
    """

    path: Path
    stem: str
    frontmatter: dict[str, Any] = Field(default_factory=dict)
    title: str | None = None
    note_type: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_date: date | None = None
    updated_date: date | None = None
    last_modified: datetime | None = None
    outbound_stems: list[str] = Field(default_factory=list)
    inbound_stems: list[str] = Field(default_factory=list)


class ConnectivityMetrics(BaseModel):
    """Connectivity analysis results: orphans, dead ends, density, components, bidirectionals.

    Attributes
    ----------
    orphan_rate : float
        Percentage of notes with zero inbound links (0-100).
    orphan_count : int
        Count of orphan notes.
    orphans : list[str]
        Stems of orphan notes.
    dead_end_rate : float
        Percentage of notes with zero outbound links (0-100).
    dead_end_count : int
        Count of dead-end notes.
    dead_ends : list[str]
        Stems of dead-end notes.
    link_density_avg : float
        Average links per file.
    link_density_class : str
        Classification: ``healthy``, ``warning``, or ``critical``.
    largest_component_pct : float
        Size of largest WCC as percentage of total nodes.
    largest_component_class : str
        Classification.
    bidirectional_ratio : float
        Percentage of linked pairs with reciprocal links.
    bidirectional_class : str
        Classification.
    missing_reciprocals : list[tuple[str, str]]
        (source, target) pairs lacking reverse links.
    """

    orphan_rate: float = 0.0
    orphan_count: int = 0
    orphans: list[str] = Field(default_factory=list)
    dead_end_rate: float = 0.0
    dead_end_count: int = 0
    dead_ends: list[str] = Field(default_factory=list)
    link_density_avg: float = 0.0
    link_density_class: str = ""
    largest_component_pct: float = 0.0
    largest_component_class: str = ""
    bidirectional_ratio: float = 0.0
    bidirectional_class: str = ""
    missing_reciprocals: list[tuple[str, str]] = Field(default_factory=list)


class TopologicalMetrics(BaseModel):
    """Topological analysis: PageRank, betweenness, communities, information sinks.

    Attributes
    ----------
    pagerank_top : list[tuple[str, float]]
        Top PageRank scores (note, score).
    betweenness_bridges : list[tuple[str, float]]
        High-betweenness notes (note, score).
    communities : list[list[str]]
        Louvain community clusters (stems per cluster).
    communities_needing_moc : list[list[str]]
        Communities of >=5 notes without a MOC.
    information_sinks : list[str]
        High in-degree, zero out-degree notes.
    information_sink_rate : float
        Sink count as percentage of total nodes.
    information_sink_class : str
        Classification.
    """

    pagerank_top: list[tuple[str, float]] = Field(default_factory=list)
    betweenness_bridges: list[tuple[str, float]] = Field(default_factory=list)
    communities: list[list[str]] = Field(default_factory=list)
    communities_needing_moc: list[list[str]] = Field(default_factory=list)
    information_sinks: list[str] = Field(default_factory=list)
    information_sink_rate: float = 0.0
    information_sink_class: str = ""


class HygieneMetrics(BaseModel):
    """Hygiene analysis: tag conformity, frontmatter completeness, phantom links, over-linking.

    Attributes
    ----------
    non_conformant_tags : list[tuple[str, str]]
        (note, tag) pairs outside controlled vocabulary.
    near_duplicate_tags : list[tuple[str, str]]
        (tag_a, tag_b) near-duplicate pairs.
    single_use_tags : list[str]
        Tags used exactly once.
    unused_tags : list[str]
        Tags in vocabulary with zero usage.
    missing_fields : list[tuple[str, str]]
        (note, field) missing required frontmatter.
    type_mismatches : list[tuple[str, str, str]]
        (note, field, expected_type).
    inconsistent_dates : list[tuple[str, str]]
        (note, description) date inconsistencies.
    phantom_links : list[tuple[str, str]]
        (source, target) — target file doesn't exist.
    over_linking : list[tuple[str, str, str]]
        (note, section, target) excessive links.
    tag_conformity_pct : float
        Percentage conforming to vocabulary.
    tag_conformity_class : str
        Classification.
    frontmatter_completeness_pct : float
        Percentage with complete frontmatter.
    frontmatter_completeness_class : str
        Classification.
    """

    non_conformant_tags: list[tuple[str, str]] = Field(default_factory=list)
    near_duplicate_tags: list[tuple[str, str]] = Field(default_factory=list)
    single_use_tags: list[str] = Field(default_factory=list)
    unused_tags: list[str] = Field(default_factory=list)
    missing_fields: list[tuple[str, str]] = Field(default_factory=list)
    type_mismatches: list[tuple[str, str, str]] = Field(default_factory=list)
    inconsistent_dates: list[tuple[str, str]] = Field(default_factory=list)
    phantom_links: list[tuple[str, str]] = Field(default_factory=list)
    over_linking: list[tuple[str, str, str]] = Field(default_factory=list)
    tag_conformity_pct: float = 100.0
    tag_conformity_class: str = ""
    frontmatter_completeness_pct: float = 100.0
    frontmatter_completeness_class: str = ""


class TemporalMetrics(BaseModel):
    """Temporal decay analysis: staleness, coherence.

    Attributes
    ----------
    stale_notes : list[str]
        Note stems not updated in >180 days.
    dead_weight : list[str]
        Stale + orphaned notes.
    temporally_distant_pairs : list[tuple[str, str, int]]
        (a, b, delta_days) link pairs far apart in time.
    temporal_deltas : list[int]
        All link-pair time deltas.
    high_coherence_pct : float
        % of links within 90 days.
    low_coherence_pct : float
        % of links >365 days apart.
    """

    stale_notes: list[str] = Field(default_factory=list)
    dead_weight: list[str] = Field(default_factory=list)
    temporally_distant_pairs: list[tuple[str, str, int]] = Field(default_factory=list)
    temporal_deltas: list[int] = Field(default_factory=list)
    high_coherence_pct: float = 0.0
    low_coherence_pct: float = 0.0


class StructuralMetrics(BaseModel):
    """Structural gap analysis: chain gaps, silos, broken cycles.

    Attributes
    ----------
    chain_gaps : list[tuple[str, str, str]]
        (a, c, b_intermediate) — missing intermediate concepts.
    potential_silos : list[tuple[int, int, float]]
        (cluster_a, cluster_b, density) isolated clusters.
    broken_cycles : list[list[str]]
        Cycles with no external connections.
    """

    chain_gaps: list[tuple[str, str, str]] = Field(default_factory=list)
    potential_silos: list[tuple[int, int, float]] = Field(default_factory=list)
    broken_cycles: list[list[str]] = Field(default_factory=list)


class HealthScore(BaseModel):
    """Weighted health score for the vault graph (0-100).

    Attributes
    ----------
    overall : float
        Composite health score 0-100.
    orphan_score : float
        Component score 0-100.
    dead_end_score : float
        Component score 0-100.
    link_density_score : float
        Component score 0-100.
    largest_component_score : float
        Component score 0-100.
    bidirectional_score : float
        Component score 0-100.
    sink_score : float
        Component score 0-100.
    tag_conformity_score : float
        Component score 0-100.
    frontmatter_score : float
        Component score 0-100.
    breakdown : dict[str, float]
        Named breakdown for extensibility.
    """

    overall: float = 0.0
    orphan_score: float = 0.0
    dead_end_score: float = 0.0
    link_density_score: float = 0.0
    largest_component_score: float = 0.0
    bidirectional_score: float = 0.0
    sink_score: float = 0.0
    tag_conformity_score: float = 0.0
    frontmatter_score: float = 0.0
    breakdown: dict[str, float] = Field(default_factory=dict)


class ScoredPair(BaseModel):
    """A single scored missing-reciprocal candidate.

    Attributes
    ----------
    source : str
        Source note stem.
    target : str
        Target note stem.
    ensemble_score : float
        Weighted ensemble score 0.0-1.0.
    adamic_adar : float
        Adamic-Adar structural similarity.
    tfidf_cosine : float
        TF-IDF content cosine similarity.
    community_match : float
        Community overlap score 0.0-1.0.
    """

    source: str = ""
    target: str = ""
    ensemble_score: float = 0.0
    adamic_adar: float = 0.0
    tfidf_cosine: float = 0.0
    community_match: float = 0.0


class LinkPredictionResult(BaseModel):
    """Output from the link prediction ensemble.

    Attributes
    ----------
    scored_pairs : list[ScoredPair]
        All scored candidates.
    top_n : int
        Number of top candidates to report (default 20).
    threshold : float
        Ensemble score threshold for auto-fix (default 0.7).
    took_action : bool
        Whether ``--fix`` mode inserted any links.
    """

    scored_pairs: list[ScoredPair] = Field(default_factory=list)
    top_n: int = 20
    threshold: float = 0.7
    took_action: bool = False


class Finding(BaseModel):
    """A single issue detected during vault auditing.

    Attributes
    ----------
    note_path : str
        File path relative to vault root.
    line : int
        Line number (0 if file-level).
    rule : str
        Rule identifier (e.g. ``FM-001``, ``WL-003``).
    message : str
        Human-readable description.
    severity : str
        ``ERROR``, ``WARN``, or ``SKIPPED``.
    fixable : bool
        Whether auto-fix is available via ``--apply``.
    """

    note_path: str
    line: int = 0
    rule: str = ""
    message: str = ""
    severity: str = ""
    fixable: bool = False


class MechanicalReport(BaseModel):
    """Output from vault mechanical audit (frontmatter, wikilinks, links).

    Attributes
    ----------
    errors : list[Finding]
        ERROR severity findings.
    warnings : list[Finding]
        WARN severity findings.
    skipped : list[Finding]
        SKIPPED severity findings.
    stats : dict[str, int]
        Summary statistics.
    """

    errors: list[Finding] = Field(default_factory=list)
    warnings: list[Finding] = Field(default_factory=list)
    skipped: list[Finding] = Field(default_factory=list)
    stats: dict[str, int] = Field(default_factory=dict)

    def add(self, finding: Finding) -> None:
        """Add a finding, routing by severity.

        Parameters
        ----------
        finding : Finding
            The finding to add.
        """
        if finding.severity == "ERROR":
            self.errors.append(finding)
        elif finding.severity == "WARN":
            self.warnings.append(finding)
        else:
            self.skipped.append(finding)


class GraphHealthReport(BaseModel):
    """Aggregate output from all analysis passes.

    Attributes
    ----------
    connectivity : ConnectivityMetrics
        Connectivity analysis.
    topological : TopologicalMetrics
        Topological analysis.
    hygiene : HygieneMetrics
        Hygiene analysis.
    temporal : TemporalMetrics
        Temporal decay analysis.
    structural : StructuralMetrics
        Structural gap analysis.
    health_score : HealthScore
        Composite health score.
    link_prediction : LinkPredictionResult
        Link prediction results.
    excluded_notes : list[str]
        Notes excluded from analysis.
    notes_scanned : int
        Total notes scanned.
    notes_excluded : int
        Notes excluded count.
    """

    connectivity: ConnectivityMetrics = Field(default_factory=ConnectivityMetrics)
    topological: TopologicalMetrics = Field(default_factory=TopologicalMetrics)
    hygiene: HygieneMetrics = Field(default_factory=HygieneMetrics)
    temporal: TemporalMetrics = Field(default_factory=TemporalMetrics)
    structural: StructuralMetrics = Field(default_factory=StructuralMetrics)
    health_score: HealthScore = Field(default_factory=HealthScore)
    link_prediction: LinkPredictionResult = Field(default_factory=LinkPredictionResult)
    excluded_notes: list[str] = Field(default_factory=list)
    notes_scanned: int = 0
    notes_excluded: int = 0

    def to_json(self) -> str:
        """Serialize to JSON, converting non-serializable types.

        Returns
        -------
        str
            JSON string.
        """
        import json

        def _convert(obj: object) -> object:
            if isinstance(obj, (Path, date, datetime)):
                return str(obj)
            if isinstance(obj, set):
                return sorted(obj)
            return obj

        raw = self.model_dump()
        return json.dumps(raw, indent=2, default=_convert)
