---
title: Version Stamping Bugs After DDD Restructure
type: discovery
status: draft
source: agent
session: 2026-06-19-version-bugfix
created: '2026-06-19'
updated: '2026-06-19'
summary: >-
  Three bugs found in version stamping incremental logic after DDD restructure:
  stale test imports, empty commit in release workflow, hardcoded version
  string.
tags:
  - type/discovery
  - domain/infrastructure
  - domain/tooling
  - status/draft
aliases:
  - Version Stamping Bugfix
code-refs:
  - .github/workflows/release.yml
  - tests/unit/ci/test_check_bump_scope.py
  - tests/e2e/test_setup.py
---
# Version Stamping Bugs After DDD Restructure

## Bug 1 — Bump Scope Tests Import From Stale Wrapper

**File**: `tests/unit/ci/test_check_bump_scope.py`

The test imported `_changed_files`, `_is_version_only`, and `_validate_bump_scope` from `scripts.ci.check_bump_scope`. During the 012-ddd-services-restructure, the real logic was moved to `anvil/services/vault/check_bump_scope.py`, and `scripts/ci/check_bump_scope.py` became a thin CLI wrapper delegating to `anvil-vault check-bump-scope`. The tests were never updated.

**Impact**: `make test` failed to collect with `ImportError: cannot import name '_changed_files'`

**Fix**: Re-import from `anvil.services.vault.check_bump_scope`

## Bug 2 — Release Workflow Skip-Bump Path Creates Empty Commit

**File**: `.github/workflows/release.yml` (line 313)

When a user manually bumps the version (increment=SKIP), the `cz bump` step is correctly skipped, but the "Create bump PR with auto-merge" step runs unconditionally. It attempts `git add pyproject.toml CHANGELOG.md && git commit`, but those files already reflect the new version, so `git commit` fails with "nothing to commit, working tree clean".

**Impact**: Release workflow fails for manually-bumped versions

**Fix**: Added `&& steps.preflight.outputs.skip-bump != 'true'` guard to the step

## Bug 3 — Hardcoded Version in E2E Test

**File**: `tests/e2e/test_setup.py`

The test asserted `anvil.__version__ == "0.1.0"` as a hardcoded string. This would break after the first version bump.

**Impact**: Brittle test requiring manual updates on every release

**Fix**: Read version dynamically from `pyproject.toml` via `tomllib`
