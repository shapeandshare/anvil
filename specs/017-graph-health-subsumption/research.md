# Research: Graph Health Subsumption Design Decisions

**Date**: 2026-06-19 | **Feature**: [spec.md](spec.md)

## Architecture Decisions

### Decision 1: Package namespace — `anvil/services/vault/`

- **Decision**: Place vault health code in a new `anvil/services/vault/` domain sub-package.
- **Rationale**: Follows the existing DDD pattern established by `governance/`, `datasets/`, `training/`, etc. The user's suggestion of "data science" namespace would conflate vault wikilink analysis (a governance/quality function) with ML/data science operations. Vault health is a vault-observability tool, not a data science tool.
- **Alternatives considered**:
  - `anvil/services/datascience/` — Too broad, mixes concerns; vault analysis is not data science.
  - `anvil/services/governance/` — Governance already has provenance/audit services. Graph health is more about vault quality analysis than data governance.
  - Keep as standalone `scripts/ci/` — Rejected per spec (subsumption required).
  - Top-level `anvil/vault/` — Would violate DDD layer discipline (services must be under `anvil/services/`).

### Decision 2: Async boundary — sync file I/O wrapped in `asyncio.to_thread()`

- **Decision**: Vault health service methods present an async interface but delegate synchronous file I/O to `asyncio.to_thread()`.
- **Rationale**: Constitution Art V requires async service layer. However, vault file I/O (scanning hundreds of `.md` files) is CPU-bound string processing, not I/O-bound network operations. Adding `aiofiles` or replacing `Path.read_text()` with async equivalents adds complexity with zero measurable benefit for an on-demand CLI tool. `asyncio.to_thread()` satisfies the async interface contract while keeping the efficient sync implementation.
- **Alternatives considered**:
  - Pure sync service layer — Violates Art V explicitly.
  - Full async with `aiofiles` — Over-engineering for a CLI tool. Adds `aiofiles` dependency.
  - Keep CLI-only, no service class — Misses the programmatic API opportunity (User Story 3).

### Decision 3: Pydantic BaseModel for all types

- **Decision**: Migrate all `@dataclass` types in legacy `graph_health/__init__.py` to Pydantic `BaseModel`.
- **Rationale**: Constitution mandates BaseModel for all new code and "touched" existing code. Since we are refactoring these types during subsumption (splitting into individual files), they are "touched" and must be converted.
- **Alternatives considered**:
  - Keep `@dataclass` with grandfather exception — The move/refactor constitutes "touched for other reasons" per the constitutional clause.
  - `dataclasses.dataclass` + Pydantic `BaseModel` mix — Inconsistent. Choose one.

### Decision 4: One class per file decomposition

- **Decision**: Split the legacy `graph_health/__init__.py` monolithic file (10+ types + `GraphHealthRunner`) into separate files per type/class.
- **Rationale**: Constitutional one-class-per-file rule. The existing 528-line file violates this.
- **File mapping**:
  - `_types.py` — All data types (NoteMetadata, ConnectivityMetrics, etc.) — exception: types share a file since they are tightly coupled value objects per Art X §10.2
  - `scanner.py` — `GraphHealthRunner` class and `should_exclude`
  - `connectivity.py` — `compute_connectivity` (+ private helpers)
  - `topology.py` — `compute_topological`
  - `hygiene.py` — `compute_hygiene`
  - `temporal.py` — `compute_temporal`
  - `structural.py` — `compute_structural`
  - `scoring.py` — `compute_health_score`
  - `prediction.py` — `compute_link_prediction` ensemble
  - `report.py` — `render_markdown`
  - `vault_audit.py` — `VaultAuditService` class
  - `vault_health_service.py` — `VaultHealthService` orchestrator

### Decision 5: CLI entry point — `anvil-vault` with subcommands

- **Decision**: Single `anvil-vault` console script with argparse subcommands: `audit`, `check-adrs`, `check-guarded-imports`, `check-bump-scope`.
- **Rationale**: Follows the existing `anvil` CLI pattern where each domain has its own entry point (`anvil-corpus`, `anvil-db`, `anvil-train`). Subcommands keep the namespace clean: `anvil-vault audit --apply`, `anvil-vault check-adrs`, etc.
- **Alternatives considered**:
  - `anvil vault audit` (subcommand of `anvil` main CLI) — Would require restructuring the existing monolithic `anvil` CLI with subparsers. Higher risk of breaking existing commands.
  - Separate entry points `anvil-vault-audit`, `anvil-vault-check-adrs` etc. — Too many console scripts, pollutes `$PATH`.
  - Keep `scripts/ci/` as thin wrappers — Interim solution, not final.

### Decision 6: `networkx` as optional dependency

- **Decision**: `networkx` listed only under `[project.optional-dependencies] vault-health = ["networkx>=3,<4"]`.
- **Rationale**: Legacy code already handles missing `networkx` gracefully (skips graph health, mechanical audit still runs). This preserves Pit of Success (Art IX).
- **Alternatives considered**: Make `networkx` a hard dependency — would force all users to install graph analysis libs even for basic vault checks.

### Decision 7: `scripts/ci/vault_audit.py` retained as thin wrapper

- **Decision**: Legacy `scripts/ci/vault_audit.py` becomes a thin wrapper that imports and delegates to `anvil.services.vault.cli:main`. Other CI scripts may be removed entirely.
- **Rationale**: `vault_audit.py` is referenced in `shared/vault.mk` and possibly in CI workflow files. Keeping a thin wrapper during transition ensures zero CI disruption. The wrapper can be removed in a follow-up.
- **Alternatives considered**: Remove all scripts immediately — risk of breaking CI if workflow files reference them.

## Dependency Analysis

| Dependency | Status | Usage | Risk |
|---|---|---|---|
| `networkx` | Optional extra | Graph algorithms (PageRank, community detection, centrality) | Low — gracefully skipped when absent |
| `PyYAML` | Existing dep | Frontmatter parsing | Low — well-established |
| `scikit-learn` | Not needed | TF-IDF in prediction.py uses manual implementation | None — no new dep |
| `matplotlib` | Not needed | All reports are text/Markdown | None |

## Legacy Code Audit

| File | Lines | Complexity | Risk |
|---|---|---|---|
| `scripts/ci/vault_audit.py` | 980 | High — monolithic CLI with mechanical audit + graph health orchestration | Medium — needs careful decomposition |
| `scripts/ci/graph_health/__init__.py` | 528 | High — types + orchestrator + utilities | High — must split into one-class-per-file |
| `scripts/ci/graph_health/scanner.py` | 233 | Medium | Low |
| `scripts/ci/graph_health/topology.py` | 123 | Medium — PageRank, betweenness | Low |
| `scripts/ci/graph_health/hygiene.py` | 349 | Medium-High — multiple tag checks | Low |
| `scripts/ci/graph_health/temporal.py` | 113 | Low | Low |
| `scripts/ci/graph_health/structural.py` | 236 | Medium | Low |
| `scripts/ci/graph_health/scoring.py` | 133 | Low | Low |
| `scripts/ci/graph_health/prediction.py` | 475 | High — ensemble with state management | Medium — state handling needs care |
| `scripts/ci/graph_health/report.py` | 768 | High — Markdown rendering | Low — straightforward text output |
| `scripts/ci/check_adr_unique.py` | 162 | Low | Low |
| `scripts/ci/check_guarded_imports.py` | 269 | Medium | Low |
| `scripts/ci/check_bump_scope.py` | 103 | Low | Low |
