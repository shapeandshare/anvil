---
title: Session — 2026-06-19 — Version Stamping Bugfix
type: session-log
tags:
  - type/session-log
  - domain/infrastructure
  - domain/tooling
created: '2026-06-19'
updated: '2026-06-19'
summary: >-
  Audited version stamping incremental logic, found and fixed three bugs: stale
  test imports, empty commit in release workflow, hardcoded version string.
aliases:
  - 2026-06-19 Version Stamping Bugfix
source: agent
---
# Session — 2026-06-19 — Version Stamping Bugfix

**Date**: 2026-06-19
**Feature**: Version stamping incremental logic audit and bugfix

## Summary

Audited the version stamping incremental logic (commitizen + release workflow + auto-bump + bump scope guard) and found three bugs. Also updated the e2e test to read version dynamically.

### Bug 1 — Stale test imports after DDD restructure

- `tests/unit/ci/test_check_bump_scope.py` imported from `scripts.ci.check_bump_scope` (thin wrapper)
- Real logic in `anvil/services/vault/check_bump_scope.py`
- Root cause: 012-ddd-services-restructure moved logic but tests weren't updated
- Fix: re-import from `anvil.services.vault.check_bump_scope`

### Bug 2 — Skip-bump path creates empty commit

- When version manually bumped (increment=SKIP), the "Create bump PR" step runs unconditionally
- `git commit` fails with "nothing to commit" since files already at new version
- Fix: added `&& steps.preflight.outputs.skip-bump != 'true'` guard at `release.yml:313`

### Bug 3 — Hardcoded version in e2e test

- `tests/e2e/test_setup.py` asserted `anvil.__version__ == "0.1.0"`
- Would break on first release
- Fix: read version dynamically via `tomllib`

### Health Check

- Bump scope classification logic (`_is_version_only`) is correct
- Auto-bump safety-net (`auto-bump.yml`) uses correct shell arithmetic
- Loop prevention via `[skip ci]` + version-no-change detection works
- Runtime version resolution (`pyproject.toml` → `anvil.__version__` → `/health` endpoint) works

## Files Changed

- `.github/workflows/release.yml` — added skip-bump guard to Create bump PR step
- `tests/unit/ci/test_check_bump_scope.py` — corrected import path
- `tests/e2e/test_setup.py` — dynamic version from pyproject.toml
- `docs/vault/Discoveries/version-stamping-bugs-after-ddd-restructure.md` — discovery note

## Vault Enrichment

- [[Discoveries/version-stamping-bugs-after-ddd-restructure]]

## Tags

- `type/session-log`
- `domain/infrastructure`
- `domain/tooling`
