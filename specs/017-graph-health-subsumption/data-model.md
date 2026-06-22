# Data Model: Vault Health Services

**Date**: 2026-06-19 | **Feature**: [spec.md](spec.md)

This document defines the core data types for the `anvil/services/vault/` domain sub-package. All types use Pydantic `BaseModel` (per Constitutional requirement for touched/refactored code).

## Entity: `NoteMetadata`

Represents a single vault note with its frontmatter metadata and wikilink graph information.

| Field | Type | Description |
|-------|------|-------------|
| `path` | `Path` | Absolute filesystem path to the `.md` file |
| `stem` | `str` | Filename without extension (NFC-normalized) |
| `frontmatter` | `dict[str, Any]` | Raw parsed YAML frontmatter |
| `title` | `str \| None` | Frontmatter `title` field |
| `note_type` | `str \| None` | Frontmatter `type` field |
| `tags` | `list[str]` | Frontmatter `tags` list |
| `created_date` | `date \| None` | Frontmatter `created` field |
| `updated_date` | `date \| None` | Frontmatter `updated` field |
| `last_modified` | `datetime \| None` | Filesystem mtime |
| `outbound_stems` | `list[str]` | Wikilink targets extracted from body text |
| `inbound_stems` | `list[str]` | Populated after graph build (notes linking TO this note) |

**Validation**: `stem` MUST be NFC-normalized. `path` MUST be absolute.

## Entity: `ConnectivityMetrics`

Connectivity analysis results from the wikilink graph.

| Field | Type | Description |
|-------|------|-------------|
| `orphan_rate` | `float` | Percentage of notes with zero inbound links (0-100) |
| `orphan_count` | `int` | Count of orphan notes |
| `orphans` | `list[str]` | Stems of orphan notes |
| `dead_end_rate` | `float` | Percentage of notes with zero outbound links (0-100) |
| `dead_end_count` | `int` | Count of dead-end notes |
| `dead_ends` | `list[str]` | Stems of dead-end notes |
| `link_density_avg` | `float` | Average links per file |
| `link_density_class` | `Literal["healthy", "warning", "critical"]` | Classification based on threshold |
| `largest_component_pct` | `float` | Size of largest WCC as percentage of total nodes |
| `largest_component_class` | `Literal["healthy", "warning", "critical"]` | Classification based on threshold |
| `bidirectional_ratio` | `float` | Percentage of linked pairs with reciprocal links |
| `bidirectional_class` | `Literal["healthy", "warning", "critical"]` | Classification based on threshold |
| `missing_reciprocals` | `list[tuple[str, str]]` | (source, target) pairs lacking reverse links |

**Validation**: All rate values 0-100. Class strings must be one of the three literal values.

## Entity: `TopologicalMetrics`

Topological analysis results.

| Field | Type | Description |
|-------|------|-------------|
| `pagerank_top` | `list[tuple[str, float]]` | Top PageRank scores: (note_stem, score) |
| `betweenness_bridges` | `list[tuple[str, float]]` | High-betweenness notes: (note_stem, score) |
| `communities` | `list[list[str]]` | Louvain community clusters (list of stems per cluster) |
| `communities_needing_moc` | `list[list[str]]` | Communities >=5 notes without a MOC |
| `information_sinks` | `list[str]` | Notes with high in-degree, zero out-degree |
| `information_sink_rate` | `float` | Sink count as percentage of total nodes |
| `information_sink_class` | `Literal["healthy", "warning", "critical"]` | Classification |

## Entity: `HygieneMetrics`

Semantic hygiene analysis results.

| Field | Type | Description |
|-------|------|-------------|
| `non_conformant_tags` | `list[tuple[str, str]]` | (note_stem, tag) pairs outside controlled vocabulary |
| `near_duplicate_tags` | `list[tuple[str, str]]` | (tag_a, tag_b) near-duplicate tag pairs |
| `single_use_tags` | `list[str]` | Tags used exactly once |
| `unused_tags` | `list[str]` | Tags in controlled vocabulary with zero usage |
| `missing_fields` | `list[tuple[str, str]]` | (note_stem, field_name) missing required frontmatter |
| `type_mismatches` | `list[tuple[str, str, str]]` | (note_stem, field, expected_type) |
| `inconsistent_dates` | `list[tuple[str, str]]` | (note_stem, description) date inconsistencies |
| `phantom_links` | `list[tuple[str, str]]` | (source_stem, target_stem) — target file doesn't exist |
| `over_linking` | `list[tuple[str, str, str]]` | (note_stem, section, target) excessive links section |
| `tag_conformity_pct` | `float` | Percentage of tags conforming to vocabulary |
| `tag_conformity_class` | `Literal["healthy", "warning", "critical"]` | Classification |
| `frontmatter_completeness_pct` | `float` | Percentage of notes with complete frontmatter |
| `frontmatter_completeness_class` | `Literal["healthy", "warning", "critical"]` | Classification |

## Entity: `TemporalMetrics`

Temporal decay analysis results.

| Field | Type | Description |
|-------|------|-------------|
| `stale_notes` | `list[str]` | Stems of notes not updated in >180 days |
| `dead_weight` | `list[str]` | Stems that are both stale AND orphaned |
| `temporally_distant_pairs` | `list[tuple[str, str, int]]` | (note_a, note_b, delta_days) link pairs far apart in time |
| `temporal_deltas` | `list[int]` | All link-pair time deltas (for distribution analysis) |
| `high_coherence_pct` | `float` | % of links where notes were created within 90 days of each other |
| `low_coherence_pct` | `float` | % of links where notes are >365 days apart |

## Entity: `StructuralMetrics`

Structural gap analysis results.

| Field | Type | Description |
|-------|------|-------------|
| `chain_gaps` | `list[tuple[str, str, str]]` | (a, c, b_intermediate) — a→c exists, a→b→c would improve coherence |
| `potential_silos` | `list[tuple[int, int, float]]` | (cluster_a_idx, cluster_b_idx, cross_density) isolated clusters |
| `broken_cycles` | `list[list[str]]` | Cycles with no external connections (stems) |

## Entity: `HealthScore`

Weighted composite health score.

| Field | Type | Description |
|-------|------|-------------|
| `overall` | `float` | Composite score 0-100 |
| `orphan_score` | `float` | Component score 0-100 |
| `dead_end_score` | `float` | Component score 0-100 |
| `link_density_score` | `float` | Component score 0-100 |
| `largest_component_score` | `float` | Component score 0-100 |
| `bidirectional_score` | `float` | Component score 0-100 |
| `sink_score` | `float` | Component score 0-100 |
| `tag_conformity_score` | `float` | Component score 0-100 |
| `frontmatter_score` | `float` | Component score 0-100 |
| `breakdown` | `dict[str, float]` | Named breakdown for extensibility |

**Score calculation**: Each component: `healthy → 1.0`, `warning → 0.5`, `critical → 0.0`. Weighted by component weight from FR-023 table. `overall = sum(weighted_scores) / sum(weights) * 100`.

## Entity: `ScoredPair`

A single scored missing-reciprocal candidate for link prediction.

| Field | Type | Description |
|-------|------|-------------|
| `source` | `str` | Source note stem |
| `target` | `str` | Target note stem |
| `ensemble_score` | `float` | Weighted ensemble score 0.0-1.0 |
| `adamic_adar` | `float` | Adamic-Adar structural similarity |
| `tfidf_cosine` | `float` | TF-IDF content cosine similarity |
| `community_match` | `float` | Community overlap score 0.0-1.0 |

## Entity: `LinkPredictionResult`

Link prediction ensemble output.

| Field | Type | Description |
|-------|------|-------------|
| `scored_pairs` | `list[ScoredPair]` | All scored candidates |
| `top_n` | `int` | Number of top candidates to report (default 20) |
| `threshold` | `float` | Ensemble score threshold for auto-fix (default 0.7) |
| `took_action` | `bool` | Whether --fix mode inserted any links |

## Entity: `MechanicalReport`

Output from vault mechanical audit (frontmatter, wikilinks, links).

| Field | Type | Description |
|-------|------|-------------|
| `errors` | `list[Finding]` | ERROR severity findings |
| `warnings` | `list[Finding]` | WARN severity findings |
| `skipped` | `list[Finding]` | SKIPPED severity findings |
| `stats` | `dict[str, int]` | Summary statistics (notes scanned, files checked, etc.) |

## Entity: `Finding`

A single issue detected during vault auditing.

| Field | Type | Description |
|-------|------|-------------|
| `note_path` | `str` | File path relative to vault root |
| `line` | `int` | Line number (0 if file-level) |
| `rule` | `str` | Rule identifier (e.g., "FM-001", "WL-003") |
| `message` | `str` | Human-readable description |
| `severity` | `Literal["ERROR", "WARN", "SKIPPED"]` | Severity level |
| `fixable` | `bool` | Whether auto-fix is available via --apply |

## Entity: `GraphHealthReport`

Aggregate output from all analysis passes.

| Field | Type | Description |
|-------|------|-------------|
| `connectivity` | `ConnectivityMetrics` | Connectivity analysis |
| `topological` | `TopologicalMetrics` | Topological analysis |
| `hygiene` | `HygieneMetrics` | Hygiene analysis |
| `temporal` | `TemporalMetrics` | Temporal decay analysis |
| `structural` | `StructuralMetrics` | Structural gap analysis |
| `health_score` | `HealthScore` | Composite health score |
| `link_prediction` | `LinkPredictionResult` | Link prediction results |
| `excluded_notes` | `list[str]` | Notes excluded from analysis |
| `notes_scanned` | `int` | Total notes scanned |
| `notes_excluded` | `int` | Notes excluded count |

## Relationships

```
VaultHealthService
├── VaultAuditService ──────────► MechanicalReport
│                                   └── Finding[]
│
└── GraphHealthService ─────────► GraphHealthReport
    ├── GraphHealthRunner
    │   ├── scan_all_notes() ────► dict[str, NoteMetadata]
    │   ├── build_graph() ───────► nx.DiGraph
    │   └── run_all() ───────────► GraphHealthReport
    ├── compute_connectivity() ──► ConnectivityMetrics
    ├── compute_topological() ───► TopologicalMetrics
    ├── compute_hygiene() ───────► HygieneMetrics
    ├── compute_temporal() ──────► TemporalMetrics
    ├── compute_structural() ────► StructuralMetrics
    ├── compute_health_score() ──► HealthScore
    └── compute_link_prediction() ► LinkPredictionResult
                                     └── ScoredPair[]
```

## State Transitions

Vault health analysis is stateless — each invocation produces a fresh result. The only persistent state is:
- **Link prediction state** (`_meta/audit/link_prediction_state.json`): Tracks which suggestions have been applied/dismissed to avoid re-suggesting.
- **Report files** (`_meta/audit/graph-health_{timestamp}.json` + `.md`): Written on each run.

## Validation Rules

1. All stem fields MUST be NFC-normalized Unicode.
2. All classification class strings MUST be one of `"healthy"`, `"warning"`, `"critical"`.
3. Percentage fields MUST be in range 0.0-100.0.
4. Score fields MUST be in range 0.0-100.0.
5. Ensemble scores (ScoredPair) MUST be in range 0.0-1.0.
