---
title: Release Workflow Git Identity and cz bump Commit Ownership
type: discovery
status: draft
source: agent
session: 2026-06-20-release-workflow-ci-fix
related:
  - '[[Discoveries/version-stamping-bugs-after-ddd-restructure]]'
  - '[[Sessions/2026-06-20-release-workflow-ci-fix]]'
code-refs:
  - .github/workflows/release.yml
created: '2026-06-20'
updated: '2026-06-20'
summary: >-
  The Release workflow failed at the cz bump step with 'empty ident name not
  allowed' because git user identity was only configured in a later step. cz
  bump itself creates a commit, which also means the subsequent bump-PR step
  must amend that commit rather than git add + git commit (which would stage
  nothing).
tags:
  - type/discovery
  - domain/infrastructure
  - domain/tooling
  - status/draft
aliases:
  - Release Workflow Git Identity and cz bump Commit Ownership
---
The `Release` workflow (`workflow_dispatch` run 27861722926) failed at the `Bump version and update changelog` step with `fatal: empty ident name (for <runner@...>) not allowed`. The root cause and a coupled latent bug are both about who owns the commit that `cz bump` creates.

## Root Cause — Missing Git Identity Before `cz bump`

`commitizen bump` does not just edit files — it creates a git commit (and, by default, a tag). Creating a commit requires a configured `user.name` / `user.email`. The workflow only configured the identity inside the later `Create bump PR with auto-merge` step, so the earlier bump step ran with no identity and aborted. The version edit (`0.1.0 → 0.1.1`) was computed correctly before the failure, confirming the abort was purely at commit time.

## Coupled Latent Bug — `git add` + `git commit` Stages Nothing

Because `cz bump` already commits `pyproject.toml` and `CHANGELOG.md`, the original `Create bump PR` step (`git add pyproject.toml CHANGELOG.md` then `git commit`) would have failed even after the identity fix: the tree is already clean, so `git add` stages nothing and `git commit` errors with `nothing to commit`. This is a distinct failure mode from the skip-bump empty-commit issue recorded in [[Discoveries/version-stamping-bugs-after-ddd-restructure]] (Bug 2) — that one is the manual-bump SKIP path; this one is the normal automatic-bump path and was never reached before because the workflow aborted earlier at the identity error.

## Fix

Two edits to `.github/workflows/release.yml`:

1. In the `Bump version and update changelog` step, configure `git config user.name` / `user.email` before invoking `cz bump`, and pass `--no-tag` so commitizen does not create a local `vX.Y.Z` tag that would later collide with the explicit tag created from merged `main`.
2. In the `Create bump PR with auto-merge` step, branch at the commit `cz bump` already created and `git commit --amend` to inject the `[skip ci]` message, instead of re-staging files that are already committed.

## Secondary Behaviors Noted During Verification (not fixed — environmental)

- `gh pr merge --auto --squash` requires repository setting "Allow auto-merge" to be enabled, otherwise the merge step errors.
- The squash-merge commit message defaults to the bump PR title (`chore: bump version to vX.Y.Z`), which does not carry `[skip ci]`. The bump landing on `main` therefore fires a fresh `Release` run. That run detects the version already changed (the SKIP path), reaches the tag step, finds the tag already exists, and no-ops via the idempotency guard. Net effect: one harmless extra workflow run per release, no infinite loop.
- If branch protection requires reviews/checks on the bump PR, auto-merge will block; the tag step's 120s poll then times out and tags `origin/main` at the pre-bump state. This is a branch-protection configuration concern, not a workflow-code defect.

## References

- `.github/workflows/release.yml` — `Bump version and update changelog` and `Create bump PR with auto-merge` steps
- [[Discoveries/version-stamping-bugs-after-ddd-restructure]] — related skip-bump empty-commit finding
