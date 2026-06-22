# Implementation Plan: Graph Health Subsumption into Anvil

**Branch**: `017-graph-health-subsumption` | **Date**: 2026-06-19 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/017-graph-health-subsumption/spec.md`

## Summary

Move 5 CI scripts (~4,500 lines) from `scripts/ci/` into a new `anvil/services/vault/` domain sub-package, refactoring to project conventions (NumPy docstrings, mypy strict, Pydantic BaseModel, one class per file, enums) and exposing them via `anvil-vault` CLI entry points. The existing `shared/vault.mk` Makefile targets delegate to the new CLI instead of direct script invocation. `networkx` remains optional via `anvil[vault-health]` extra.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: PyYAML (existing), networkx (optional via `anvil[vault-health]` extra)  
**Storage**: Filesystem — vault health reports written to `_meta/audit/` under vault dir (legacy behavior preserved)  
**Testing**: pytest (existing project convention)  
**Target Platform**: Linux/macOS CLI  
**Project Type**: CLI tool within an existing Python package (anvil)  
**Performance Goals**: N/A — on-demand CLI tool, legacy runtime is sub-second for typical vaults  
**Constraints**: Zero behavioral delta from legacy scripts; must pass `mypy --strict`; follow all constitutional articles  
**Scale/Scope**: ~4,500 lines across 5 legacy scripts → ~3,500 lines after refactoring to one-class-per-file + BaseModel

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Assessment |
|---------|-----------|
| **Art I** — Zero-Dependency Core | ✅ PASS. Vault health lives in `services/`, not `core/`. |
| **Art II** — Educational Clarity | ✅ PASS. Not applicable (vault tooling, not core engine). |
| **Art III** — Seeded Reproducibility | ✅ PASS. Not applicable. |
| **Art IV** — TDD Mandatory | ⚠️ **GATE.** Tests required for all new/refactored service classes. Legacy scripts lack comprehensive test coverage — new `_test.py` files must be created alongside each service module. |
| **Art V** — Async-First | ⚠️ **GATE.** Legacy vault health code is synchronous (sync file I/O). Per Art V, the service layer MUST be async. Design decision: vault health service methods accept async call patterns by wrapping sync file I/O in `asyncio.to_thread()` or `loop.run_in_executor()`. CLI entry points use `asyncio.run()` to call async services. |
| **Art VI** — `__init__.py` Ownership | ✅ PASS. New `vault/` sub-package gets a bare docstring-only `__init__.py`. |
| **Art VII** — Layered Architecture | ⚠️ **GATE.** Vault health does NOT use DB — no Repository layer needed. Service classes instantiated independently (not through AnvilWorkbench, as per spec Assumptions). This is an intentional exception: vault health is CLI-first, not web-first. |
| **Art VIII** — iOS-Grade Polish | ✅ PASS. Not applicable (CLI tooling). |
| **Art IX** — Pit of Success | ✅ PASS. `networkx` gracefully downgraded when absent — same as legacy behavior. |
| **Art X** — Domain-Driven Decomposition | ✅ PASS. New `vault/` sub-package follows `§10.4` (plural noun naming). |
| **Add'l: Pydantic BaseModel** | ⚠️ **GATE.** Legacy `graph_health/__init__.py` uses `@dataclass` for 10+ types. Per constitution: existing `@dataclass` is grandfathered until touched, but all NEW code MUST use `BaseModel`. Since we are moving/refactoring these types, they count as "touched" — MUST be converted to `BaseModel`. |
| **Add'l: One class per file** | ⚠️ **GATE.** `graph_health/__init__.py` contains ~10 dataclass types + `GraphHealthRunner` class in one file. Must be split into individual files per constitutional rule. |
| **Add'l: No type suppression** | ✅ PASS. `mypy --strict` must pass on all new code. |

### Gate Summary

- **3 MUST-PASS gates**: Art IV (tests), Art V (async), Add'l (BaseModel + one-class-per-file)
- **2 intentional exceptions**: Art VII (no Repository — no DB), Art VII (no AnvilWorkbench — CLI-first)
- **All other articles**: PASS

### Post-Design Re-Check

| Article | Post-Design Status |
|---------|--------------------|
| **Art IV** (TDD) | ⚠️ **Mitigated**. Tests planned for VaultHealthService, GraphHealthService, and each analysis module. Will be created as `tests/services/vault/` files. |
| **Art V** (Async) | ⚠️ **Mitigated**. Async interface with sync I/O wrapped in `asyncio.to_thread()`. Decision documented in research.md. |
| **Art VI** (`__init__.py`) | ✅ PASS. Bare docstring-only `__init__.py` for `vault/` sub-package. |
| **Art VII** (Layered) | ⚠️ **Mitigated**. No DB = no Repository. Intentional exception documented in Complexity Tracking. |
| **Art X** (DDD) | ✅ PASS. `vault/` follows plural noun convention (§10.4). Types in `_types.py` (§10.2). |
| **Add'l: BaseModel** | ⚠️ **Mitigated**. All legacy `@dataclass` types converted to `BaseModel` in `_types.py`. |
| **Add'l: One class/file** | ⚠️ **Mitigated**. Legacy monolithic `__init__.py` split into per-class modules. Exception for tiny value objects in `_types.py` (tight coupling per §10.2). |

**Result**: All gates have mitigation plans. Plan is viable.

## Project Structure

### Documentation (this feature)

```text
specs/017-graph-health-subsumption/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── checklists/          # Spec quality checklist
│   └── requirements.md
└── contracts/           # Phase 1 output (CLI contract schemas)
```

### Source Code (repository root)

```text
# Service layer — new domain sub-package
anvil/services/vault/
├── __init__.py              # docstring-only package marker
├── _types.py                # Pydantic BaseModels: NoteMetadata, ConnectivityMetrics,
│                            #   TopologicalMetrics, HygieneMetrics, TemporalMetrics,
│                            #   StructuralMetrics, HealthScore, GraphHealthReport,
│                            #   ScoredPair, LinkPredictionResult, MechanicalReport, Finding
├── scanner.py               # GraphHealthRunner (scan_all_notes, build_graph, run_all, write_reports)
├── connectivity.py          # compute_connectivity (orphans, dead ends, density, bidirectionals)
├── topology.py              # compute_topological (PageRank, betweenness, communities, sinks)
├── hygiene.py               # compute_hygiene (tag conformity, frontmatter, phantom links)
├── temporal.py              # compute_temporal (staleness, coherence)
├── structural.py            # compute_structural (chain gaps, silos, broken cycles)
├── scoring.py               # compute_health_score
├── prediction.py            # compute_link_prediction ensemble (Adamic-Adar, TF-IDF, community)
├── report.py                # render_markdown for graph health reports
├── vault_audit.py           # VaultAuditService — mechanical audit (frontmatter, wikilinks, links)
├── vault_health_service.py  # VaultHealthService — orchestrator wrapping audit + graph health
├── check_adr_unique.py      # ADR uniqueness checker
├── check_guarded_imports.py # Guarded import violation checker
├── check_bump_scope.py      # Bump scope classifier
└── cli.py                   # CLI argument parsers for vault subcommands

# CLI entry points (in pyproject.toml [project.scripts])
# anvil-vault = "anvil.services.vault.cli:main"

# Updated Makefile reference
shared/vault.mk              # Delegates to `anvil-vault` instead of `scripts/ci/*.py`
```

**Structure Decision**: The new `anvil/services/vault/` domain sub-package mirrors the existing DDD decomposition pattern. Service classes (VaultAuditService, GraphHealthService, VaultHealthService) wrap the pure-function analysis modules. CLI entry points live in `cli.py` within the vault package, following the same pattern as `anvil/cli.py` for other commands. The flat per-script CLI commands (`check_adr_unique`, `check_guarded_imports`, `check_bump_scope`) are migrated as-is to preserve their behavioral contract.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Service layer sync I/O (Art V exception) | Vault file I/O is inherently synchronous — converting to `aiofiles` adds complexity with zero throughput benefit for on-demand CLI tools | Wrapping in `asyncio.to_thread()` preserves async service interface while using efficient sync I/O internally |
| No Repository/AnvilWorkbench (Art VII exception) | Vault health has zero DB dependencies — no Repository pattern needed | Forcing DB abstraction would require creating schema tables with no business justification |
