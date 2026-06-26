---
title: 2026-06-24-release-workflow-consolidation
type: session
tags:
  - type/session-log
  - domain/tooling
created: '2026-06-24'
updated: '2026-06-24'
aliases:
  - Release Workflow Consolidation
source: sisyphus
---
# Session: Release Workflow Consolidation

**Date**: 2026-06-24
**Feature**: CI/CD — consolidate auto-bump + release into single workflow

## What was done

- **Consolidated** `.github/workflows/auto-bump.yml` and `.github/workflows/release.yml` into a single `release.yml`
- **Deleted** `auto-bump.yml` (safety-net no longer needed as separate workflow)
- **Generalized** `anvil-vault bump` to support MAJOR, MINOR, and PATCH increments (was patch-only)
- **Removed commitizen dependency** from the release pipeline — all version logic now lives in `anvil-vault`
- **Updated** the workflow trigger contract in the vault to reflect the single-workflow design

## What was fixed

The old dual-workflow design had two structural problems:

1. **Race condition**: Both workflows fired on the same `push main` event. Auto Bump always did a patch bump (0.1.4→0.1.5). Release tried a MINOR bump (0.1.4→0.2.0 for "feat" commits). They conflicted, and Auto Bump always won because it was simpler.

2. **Commitizen exit 16**: The Release workflow used `cz bump --changelog` which requires prior git tags for incremental changelog generation. No tags existed → exit code 16 → the workflow always failed. This meant no GitHub Release or tag was ever created.

The net effect: every merge got a patch bump regardless of conventional commit type, and no release artifacts were produced.

## Key decisions

1. **Single workflow, single tool**: One workflow to rule them all. `anvil-vault` is the single version management tool — no commitizen needed.
2. **Path filter on `anvil/**`**: The consolidated workflow only fires on source code changes, not on version-only bump PRs (which only touch `pyproject.toml` and `CHANGELOG.md`).
3. **`[skip ci]` still used**: Bump PR commits include `[skip ci]` to prevent re-triggering the workflow.
4. **Correct semver**: `feat` → MINOR bump (not patch), `fix` → PATCH, `BREAKING CHANGE` → MAJOR.

## Files changed

- `.github/workflows/release.yml` (rewritten — 339 lines, replaced 427 + 147 lines)
- `.github/workflows/auto-bump.yml` (deleted)
- `anvil/services/vault/bump_version.py` (generalized to MAJOR/MINOR/PATCH)
- `anvil/services/vault/cli.py` (added `bump --increment` subcommand)
- `anvil/services/vault/check_version.py` (updated docstring)
- `tests/unit/vault/test_bump_version.py` (added 7 tests for _bump + changelog labels)
- `docs/vault/Specs/010 Automated Semver Release/contracts/workflow-trigger-contract.md` (updated)
- `scripts/README.md` (updated reference)

## Related

- [[Specs/010 Automated Semver Release/010 Automated Semver Release|010 Automated Semver Release]] — release automation feature specification
- [[Decisions/ADR-008-automated-semver-release|ADR-008: Automated Semver Release]] — architecture decision record
- [[Decisions/ADR-028-ci-merge-gate-enforcement|ADR-028: CI Merge Gate Enforcement]] — related CI decision
- [[Discoveries/release-workflow-git-identity-and-cz-commit|Release Workflow Git Identity and cz bump Commit Ownership]] — related discovery
