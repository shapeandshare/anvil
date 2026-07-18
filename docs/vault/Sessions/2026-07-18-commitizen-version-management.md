---
title: 'Session: Replace Custom Version Bump Code with Commitizen'
type: session-log
tags:
  - type/session-log
  - domain/tooling
  - domain/infrastructure
created: '2026-07-18'
updated: '2026-07-18'
aliases:
  - commitizen-version-management
source: agent
---
# Session Log: Replace Custom Version Bump Code with Commitizen

**Date**: 2026-07-18  
**Session focus**: Removing custom `anvil-vault bump` / `bump_version.py` / `build_notes.py` / `detect_increment.py` code in favor of direct commitizen usage

## Summary

The release workflow had drifted from its original ADR-008 design. Custom Python modules (`bump_version.py`, `build_notes.py`, `detect_increment.py`, `version_utils.py`, `check_version.py`) duplicated commitizen's functionality — they manually parsed `pyproject.toml`, classified merge commits with a custom function, and generated boilerplate changelog entries. This session replaced all of that with direct `cz bump` calls.

## Changes

### Removed files
- `anvil/services/vault/bump_version.py` — replaced by `cz bump --changelog --yes`
- `anvil/services/vault/build_notes.py` — replaced by commitizen changelog + `awk` extraction
- `anvil/services/_shared/version_utils.py` — only used by removed modules
- `anvil/services/vault/check_version.py` — unused in the workflow
- `scripts/ci/detect_increment.py` — thin wrapper
- `scripts/ci/check_version.py` — thin wrapper
- `scripts/release/build_notes.py` — thin wrapper
- `tests/unit/services/test_version_utils.py`
- `tests/unit/vault/test_bump_version.py`
- `tests/unit/vault/test_build_notes.py`
- `tests/services/vault/test_build_notes.py`

### Updated files
- `anvil/services/vault/detect_increment.py` — inlined `_read_version`/`_parent_version` helpers, removed `classify_increment()` function. Now outputs `AUTO`/`PATCH`/`SKIP`/`NONE` instead of `MAJOR`/`MINOR`/`PATCH`/`NONE`. The actual increment type is determined by commitizen scanning commit history.
- `anvil/services/vault/cli.py` — removed `bump`, `bump-patch`, `check-version`, `build-notes` subcommands and their handler functions
- `pyproject.toml` — `commitizen` bumped from `>=3.0,<4` to `>=4,<5`
- `.github/workflows/release.yml` — bump step uses `cz bump --changelog --yes` (auto-detect) or `cz bump --changelog --yes --increment PATCH` (workflow_dispatch). Tag-delete dance added: `cz bump` creates a local tag, which is deleted before the bump PR is pushed (the tag is re-created on `main` after the PR merges). Release notes extracted from `CHANGELOG.md` via `awk`.
- `tests/unit/vault/test_detect_increment.py` — updated mock paths (`_read_version`/`_parent_version`), expected output is now `AUTO` instead of `MAJOR`/`MINOR`/`PATCH`
- `tests/unit/vault/test_cli.py` — removed subcommand tests for removed commands
- `tests/services/vault/test_detect_increment.py` — updated mock paths and expected values
- `docs/vault/Decisions/ADR-008-automated-semver-release.md` — updated to reflect current implementation

## Key Design Decisions

- **Keep the bump PR pattern**: Tag is created on the bump branch, then deleted and re-created on `main` after the PR merges. This ensures the tag points at the canonical `main` commit.
- **Keep the `detect-increment` shim**: Still needed for `SKIP` (manually bumped version) and `NONE` (no relevant commit) detection. But it outputs `AUTO` instead of specific increment types — commitizen handles the actual classification.
- **Direct `cz bump` without `--increment`**: For the common case (`AUTO`), `cz bump` scans commits since the last tag and determines the correct increment type. This removes the need for the custom `classify_increment()` function.

## ADR Updated

ADR-008 was updated to reflect the current implementation (the original described the custom code approach, which was already outdated).

## Tags

- `type/session-log`
- `domain/tooling`
- `domain/infrastructure`
