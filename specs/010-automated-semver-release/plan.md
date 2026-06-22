# Implementation Plan: Automated Semantic Versioning & Release

**Branch**: `010-automated-semver-release` | **Date**: 2026-06-14 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/010-automated-semver-release/spec.md`

## Summary

Add Commitizen-based semantic versioning to the anvil project with automated changelog generation, version bumping, and GitHub Releases triggered on merge to main. PR titles (conventional commits) determine bump level. Includes a safety-net auto-bump workflow for un-versioned changes.

## Technical Context

**Language/Version**: Python 3.11+ (pyproject.toml config), YAML (GitHub Actions workflows), Shell (CI scripts)  
**Primary Dependencies**: `commitizen` (new dev dependency), GitHub Actions (`actions/checkout@v4`, `actions/cache@v4`), `gh` CLI (GitHub CLI, pre-installed on GitHub runners)  
**Storage**: `pyproject.toml` (version source), `CHANGELOG.md` (changelog), git tags (release markers), GitHub Releases API (release artifacts)  
**Testing**: pytest (existing, for any helper scripts), manual workflow validation via `act` or GitHub workflow_dispatch on a test branch  
**Target Platform**: GitHub (CI/CD — GitHub Actions + GitHub Releases)  
**Project Type**: CI/CD pipeline configuration + Python project tooling config  
**Performance Goals**: N/A (CI-only, no user-facing latency requirements)  
**Constraints**: Must not break existing CI pipeline; all operations must be idempotent; must respect branch protection rules; version bump commit must not re-trigger the release workflow (`[skip ci]`); auto-merge PR pattern required to satisfy branch protection  
**Scale/Scope**: Single repository (anvil) — no monorepo multi-package concerns

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Result: PASS** — No violations found.

| Article | Assessment | Rationale |
|---------|-----------|-----------|
| I — Zero-Dependency Core | ✅ Not affected | This feature adds CI/CD config and a dev dependency only. No changes to `anvil/core/`. |
| II — Educational Clarity | ✅ Applicable | Workflow YAML comments and commitizen config comments explain WHY patterns are used. Implementation guidance in spec already provides rationale. |
| III — Seeded Reproducibility | ✅ Not affected | No training-related changes. |
| IV — TDD Mandatory | ✅ Partial | GitHub Actions workflows are YAML configuration, not Python code. No new Python modules under test. CI workflow behavior validated via `act` or manual workflow_dispatch. Existing pytest suite unchanged. |
| V — Async-First | ✅ Not affected | No new Python service code. |
| VI — Implicit Namespace | ✅ Not affected | Only addition is `commitizen` in dev deps — no new `__init__.py` files. |
| VII — Layered Architecture | ✅ Not affected | No new Python modules. |
| VIII — Whimsy Without Compromise | ✅ Not affected | No UI changes. |
| IX — Pit of Success | ✅ Compliant | `commitizen` added as dev optional dependency (`pip install anvil[dev]`). `cz` command auto-detected in CI via `pip install`. If `cz` is unavailable at runtime, the workflow fails early with a clear diagnostic message (AR-003). Release workflow only runs on push to main — no impact on local development. |

**Article IV note**: While YAML workflows are not testable via pytest, the workflow behavior is validated through:
1. YAML syntax validation (GitHub natively validates on push)
2. `act` local runner for pre-merge validation
3. The `workflow_dispatch` escape hatch for manual verification
4. The agentic checklist in the spec provides explicit verification commands

## Project Structure

### Documentation (this feature)

```text
specs/010-automated-semver-release/
├── plan.md              # This file
├── spec.md              # Feature specification (with clarifications)
├── research.md          # Phase 0 — reference pattern analysis
├── data-model.md        # Phase 1 — entities and relationships
├── quickstart.md        # Phase 1 — developer onboarding
├── contracts/           # Phase 1 — interface contracts
│   ├── commitizen-config.md
│   ├── conventional-commit-format.md
│   ├── changelog-format.md
│   └── workflow-trigger-contract.md
├── checklists/
│   └── requirements.md  # Quality checklist
└── tasks.md             # Phase 2 — task breakdown (created by /speckit.tasks)
```

### Source Code (repository root)

```text
.github/
└── workflows/
    ├── release.yml         # NEW — Release on merge to main
    └── auto-bump.yml       # NEW — Safety-net patch bump

pyproject.toml              # MODIFY — Add [tool.commitizen] + commitizen dep

CHANGELOG.md                # NEW — Conventional Commits changelog

specs/
└── 007-automated-semver-release/
    └── ...                 # Planning artifacts (above)
```

**Structure Decision**: CI/CD configuration in `.github/workflows/` (GitHub standard). Project tooling config in `pyproject.toml` (PEP 621 standard). Changelog at repo root (standard convention). No new Python modules — purely configuration and CI.

## Complexity Tracking

> No violations to justify. All additions are standard CI/CD tooling patterns.