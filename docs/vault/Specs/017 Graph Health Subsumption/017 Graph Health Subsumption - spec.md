---
title: 017 Graph Health Subsumption - spec
type: spec
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/017 Graph Health Subsumption/
related:
  - '[[017 Graph Health Subsumption]]'
created: ~
updated: ~
---
# Feature Specification: Graph Health Subsumption into Anvil

**Feature Branch**: `017-graph-health-subsumption`
**Created**: 2026-06-19
**Status**: Draft
**Input**: User description: "scripts/ci contains code for graph health, lets move this into our anvil code base under a common namespace perhaps around data science, etc. move cli uages to anvil, enfoce our coding, archteciture, standard exrta and refactor during the subsumption"

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Developer runs vault health checks via `anvil` CLI (Priority: P1)

An anvil developer needs to run vault integrity checks (frontmatter validation, wikilink resolution, graph health analysis) without knowing about `scripts/ci/`. They invoke a single `anvil` CLI command and get the same output they previously got from `make vault-audit`.

**Why this priority**: This is the primary value — the whole point of subsumption is making these tools accessible through the standard `anvil` interface. Without this, nothing is improved.

**Independent Test**: Can be fully tested by invoking `anvil-vault audit` on the project's own `docs/vault/` and verifying the same exit codes and report structure as the legacy `scripts/ci/vault_audit.py`.

**Acceptance Scenarios**:

1. **Given** the anvil package is installed with the vault-health extra, **When** a developer runs `anvil-vault audit`, **Then** the command produces a mechanical audit report (frontmatter/wikilink validation) with exit code 0 for clean, 1 for errors found.
2. **Given** the `networkx` dependency is available, **When** a developer runs `anvil-vault audit`, **Then** the output includes graph health analysis (connectivity, topology, hygiene, temporal decay, health score).
3. **Given** a vault with known frontmatter violations, **When** a developer runs `anvil-vault audit --apply`, **Then** safe auto-fixes are applied in-place, and a summary of changes is reported.
4. **Given** a vault with known frontmatter violations, **When** a developer runs `anvil-vault audit --diff`, **Then** proposed fixes are shown but no files are modified.

---

### User Story 2 — Developer runs CI-specific validators via `anvil` CLI (Priority: P1)

Developers and CI pipelines need to validate ADR uniqueness and guarded import discipline through the standard `anvil` interface, replacing `make adr-check` and `make guarded-imports-check`.

**Why this priority**: These CI gates are part of the merge pipeline. They must remain functional after subsumption. Moving them into `anvil` ensures consistent invocation regardless of whether the developer uses `make` or directly imports the package.

**Independent Test**: Can be fully tested by running `anvil-vault check-adrs` and `anvil-vault check-guarded-imports` on the project and verifying they exit 0 on a clean state.

**Acceptance Scenarios**:

1. **Given** the anvil package is installed, **When** a developer runs `anvil-vault check-adrs`, **Then** it validates all ADR-0NN files in `docs/vault/Decisions/` for uniqueness and naming conventions, exiting 0 if valid.
2. **Given** duplicate ADR identifiers exist, **When** a developer runs `anvil-vault check-adrs`, **Then** it lists each duplicate and exits with code 1.
3. **Given** the anvil package is installed, **When** a developer runs `anvil-vault check-guarded-imports`, **Then** it scans all `.py` files for TYPE_CHECKING-guarded symbols used outside annotations, exiting 0 if no violations.

---

### User Story 3 — Developer uses vault health services programmatically (Priority: P2)

A developer writing automation scripts or building new features that interact with vault metadata imports `anvil.services.vault` classes directly for programmatic access to vault analysis, bypassing the CLI entirely.

**Why this priority**: This unlocks the full value of the subsumption — the graph health code becomes a proper library within `anvil`, importable and composable just like any other service. However, it depends on the CLI being functional first (P1 stories completed).

**Independent Test**: Can be tested by importing vault health service classes and instantiating them with a vault path, running analysis, and inspecting the returned report objects.

**Acceptance Scenarios**:

1. **Given** an importable `VaultAuditService` class, **When** instantiated with a vault directory path, **Then** it provides methods for scanning, validating, and reporting on vault health.
2. **Given** an importable `GraphHealthService` class, **When** instantiated, **Then** it provides methods for connectivity, topological, hygiene, temporal, and structural analysis of vault wikilink graphs.
3. **Given** a vault audit service instance, **When** the developer inspects the returned `MechanicalReport`, **Then** the object exposes typed fields for errors, warnings, and stats.

---

### User Story 4 — Makefile targets transparently delegate to `anvil` CLI (Priority: P2)

Existing `make vault-audit`, `make adr-check`, and `make guarded-imports-check` targets continue to work unchanged, now delegating to `anvil-vault` subcommands instead of `scripts/ci/*.py` directly.

**Why this priority**: Backward compatibility — developers habituated to Makefile targets should experience zero friction. This is a transparent implementation detail.

**Independent Test**: After updating `shared/vault.mk`, running `make vault-audit` produces identical output to running `anvil-vault audit` on the same vault.

**Acceptance Scenarios**:

1. **Given** the updated Makefile, **When** a developer runs `make vault-audit`, **Then** the output and exit codes match the pre-subsumption behavior.
2. **Given** the updated Makefile, **When** a developer runs `make vault-audit-apply`, **Then** safe auto-fixes are applied in-place just as before.
3. **Given** the updated Makefile, **When** a developer runs `make guarded-imports-check`, **Then** the output matches pre-subsumption behavior.

---

### Edge Cases

- What happens when `networkx` is not installed? Graph health analysis is skipped with a clear message; mechanical audit still runs.
- What happens when the vault directory does not exist at the expected path? The CLI should accept an explicit `--vault-dir` / path argument.
- What happens when `yaml` (PyYAML) is not available? The tool should error with a clear installation hint (as `vault_audit.py` currently does).
- How does the system handle vaults with no `.md` files or an empty vault directory? Graceful empty report with zero notes scanned.
- What happens with symlinks or broken symlinks within the vault directory? They should be skipped with a warning, not crash.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide an `anvil-vault audit` CLI command that replicates the full functionality of `scripts/ci/vault_audit.py`, including `--apply`, `--diff`, and `--skip-graph-health` flags.
- **FR-002**: The system MUST provide an `anvil-vault check-adrs` CLI command that replicates `scripts/ci/check_adr_unique.py`.
- **FR-003**: The system MUST provide an `anvil-vault check-guarded-imports` CLI command that replicates `scripts/ci/check_guarded_imports.py`.
- **FR-004**: The bump-scope gate (`scripts/ci/check_bump_scope.py`) MUST be moved into the `anvil` package as an importable module with an `anvil-vault check-bump-scope` CLI entry point.
- **FR-005**: The graph health analysis code (currently `scripts/ci/graph_health/`) MUST be refactored into an `anvil/services/vault/` domain sub-package with proper service classes, following the project's layered architecture (service → god class → CLI).
- **FR-006**: All vault health code MUST be refactored to follow project conventions during subsumption: NumPy-style docstrings, mypy strict typing, enums over magic strings, relative imports within the package, one class per file.
- **FR-007**: The vault health domain sub-package MUST expose a `VaultHealthService` service class that wraps vault auditing operations, and a `GraphHealthService` class that wraps graph analysis operations.
- **FR-008**: The existing `shared/vault.mk` Makefile targets MUST be updated to delegate to the `anvil` CLI commands instead of `scripts/ci/` scripts.
- **FR-009**: The original `scripts/ci/` files MAY be retained post-subsumption as thin wrappers that call the `anvil` CLI, OR may be removed if no other consumers exist.
- **FR-010**: The vault audit types currently defined in `graph_health/__init__.py` (NoteMetadata, ConnectivityMetrics, TopologicalMetrics, HygieneMetrics, TemporalMetrics, StructuralMetrics, HealthScore, GraphHealthReport, etc.) MUST be migrated to a dedicated `anvil/services/vault/_types.py` module (or co-located `_types/` sub-package if the type count warrants it).
- **FR-011**: CLI entry points MUST be exposed via the existing `anvil.cli` mechanism (e.g., a `vault` subcommand group), consistent with the project's CLI architecture.
- **FR-012**: The `vault` domain sub-package MUST be registered as an optional extra (`vault-health`) in `pyproject.toml` with `networkx` as its only additional dependency, since graph analysis is optional.

### Key Entities *(include if feature involves data)*

- **Vault Audit Report** — A container for mechanical audit findings (frontmatter schema violations, broken wikilinks, broken markdown links), organized by severity (error, warning, skipped).
- **Graph Health Report** — A multi-section analysis report covering connectivity (orphans, dead ends, density), topology (PageRank, communities, sinks), hygiene (tag conformity, phantom links), temporal decay (staleness, coherence), and structural gaps (chain gaps, silos).
- **Health Score** — A weighted composite score (0-100) with per-component breakdown, derived from connectivity, topology, and hygiene metrics.
- **VaultHealthService** — Wraps vault scanning, frontmatter validation, wikilink resolution, report generation.
- **GraphHealthService** — Wraps graph construction, all analysis passes (connectivity, topology, hygiene, temporal, structural), link prediction ensemble, and report rendering.
- **Audit Finding** — A single issue detected during vault auditing: path, line number, rule name, severity, fixable flag.
- **Bump Scope Classification** — Output from the bump-scope gate: whether a change set is version-only (pyproject.toml + CHANGELOG.md) or full (touches source code).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All existing `make vault-audit` / `make vault-audit-apply` / `make vault-audit-diff` / `make vault-audit-fast` targets produce identical output and exit codes before and after subsumption.
- **SC-002**: All legacy CI scripts (`scripts/ci/vault_audit.py`, `check_adr_unique.py`, `check_guarded_imports.py`) are either removed or reduced to thin wrappers post-subsumption, with zero behavioral change.
- **SC-003**: The new `anvil/services/vault/` package passes `mypy --strict` with zero errors.
- **SC-004**: Every module in `anvil/services/vault/` has full NumPy-style docstrings on all public classes, methods, and functions.
- **SC-005**: The graph health code has zero hardcoded path references — all paths are parameterized via service constructor or CLI arguments.
- **SC-006**: The vault health extra (`pip install anvil[vault-health]`) installs `networkx` as its only additional dependency.
- **SC-007**: CLI help output (`anvil-vault --help`) clearly documents all subcommands and flags, matching the functionality of the legacy scripts.

## Assumptions

- The graph health code depends on `networkx` for graph algorithms — this remains a pre-existing dependency constraint that is already handled gracefully in the legacy code (skipped if not installed).
- The vault audit code depends on `PyYAML` for frontmatter parsing — already a project dependency.
- The new domain sub-package name is `anvil/services/vault/` — this follows the domain-driven decomposition pattern established by `governance/`, `datasets/`, `training/`, etc.
- The existing `AnvilWorkbench` god class pattern is NOT extended to vault health services — vault health is invoked primarily via CLI rather than the web API, so a dedicated service class instantiated independently is appropriate.
- CLI subcommand grouping under `anvil-vault` follows the pattern established by any existing CLI subcommands in the project.
- The bump-scope gate (`check_bump_scope.py`) is a classifier (always exits 0) — this behavioral contract is preserved.
- No data persistence layer (database tables) is needed — vault health runs are ephemeral, writing report files to disk as the legacy code does.
