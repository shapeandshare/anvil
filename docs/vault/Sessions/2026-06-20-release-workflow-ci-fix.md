---
title: Session — 2026-06-20 — Release Workflow CI Fix
type: session-log
tags:
  - type/session-log
  - domain/infrastructure
  - domain/tooling
created: '2026-06-20'
updated: '2026-06-20'
summary: >-
  Set BUMP_PAT secret and fixed the Release workflow: cz bump failed with 'empty
  ident name' (no git identity before bump) and the bump-PR step would have
  failed re-staging already-committed files. Fixed both in release.yml.
aliases:
  - 2026-06-20 Release Workflow CI Fix
source: agent
---
# Session — 2026-06-20 — Release Workflow CI Fix

**Date**: 2026-06-20
**Feature**: 007-automated-semver-release (post-implementation CI fix)

## Summary

Configured the `BUMP_PAT` repository secret for `shapeandshare/anvil` and diagnosed the first `Release` workflow run (`workflow_dispatch` run 27861722926), which failed at the `Bump version and update changelog` step. Root cause: git author identity was never configured before `commitizen bump` (which creates a commit), producing `fatal: empty ident name not allowed`. Found and fixed a coupled latent bug in the same workflow.

## Investigation

- `gh run view 27861722926 --log-failed` showed `cz bump` computed `0.1.0 → 0.1.1` correctly, then aborted at commit time with `empty ident name`.
- Identity was only set in the later `Create bump PR with auto-merge` step, not before `cz bump`.

## Bugs Fixed (`.github/workflows/release.yml`)

### Bug 1 — Missing git identity before `cz bump`

`commitizen bump` creates a commit, so it needs `user.name`/`user.email`. Added `git config` for the `github-actions[bot]` identity at the start of the `Bump version and update changelog` step. Also added `--no-tag` to prevent a local `vX.Y.Z` tag colliding with the explicit tag created later from merged `main`.

### Bug 2 — Bump-PR step re-stages already-committed files

Because `cz bump` already commits `pyproject.toml` + `CHANGELOG.md`, the original `git add` + `git commit` in `Create bump PR with auto-merge` would have failed with `nothing to commit`. Rewrote it to branch at the existing commit and `git commit --amend` to inject the `[skip ci]` message. This is the normal-bump-path analogue of the skip-bump empty-commit bug previously recorded for 007.

## Verification

- `release.yml` validated as syntactically correct YAML.
- Traced the full `workflow_dispatch` path step by step; confirmed the fix resolves the failure and the downstream tag/release/idempotency logic remains consistent.
- Noted (not fixed, environmental): "Allow auto-merge" must be enabled; squash-merge commit lacks `[skip ci]` so each release fires one harmless idempotent extra run; branch-protection review requirements would stall the auto-merge poll.

## Files Changed

- `.github/workflows/release.yml` — git identity + `--no-tag` in bump step; `git commit --amend` in bump-PR step; refreshed comments
- `docs/vault/Discoveries/release-workflow-git-identity-and-cz-commit.md` — discovery note (new)
- `docs/vault/Discoveries/Discoveries.md` — added new note + previously-orphaned version-stamping note to MOC

## Vault Enrichment

- [[Discoveries/release-workflow-git-identity-and-cz-commit]]

## Tags

- `type/session-log`
- `domain/infrastructure`
- `domain/tooling`
